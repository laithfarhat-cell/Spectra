"""Fast deterministic semantic profiling for tabular telemetry.

The profiler accepts Polars frames, Arrow-ish records, or ordinary Python rows. It bounds
samples and string scans so large streams remain responsive; detailed inference is a hint,
not a substitute for validating untrusted input.
"""
from __future__ import annotations
import ipaddress, math, re, statistics
from collections import Counter
from datetime import datetime
from typing import Any
import polars as pl

PATTERNS={
 "uuid":re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",re.I),
 "mac_address":re.compile(r"^(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}$",re.I), "url":re.compile(r"^https?://",re.I),
 "cve":re.compile(r"^CVE-\d{4}-\d{4,}$",re.I), "http_status":re.compile(r"^[1-5]\d\d$"),
 "severity":re.compile(r"^(trace|debug|info|notice|warning|warn|error|critical|fatal)$",re.I),
 "ipv4":re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$"), "ipv6":re.compile(r"^[0-9a-f:]{3,}$",re.I),
}
DIMENSION_WORDS={"host","hostname","service","env","environment","region","zone","cluster","namespace","method","status","severity","level","country","protocol"}
METRIC_WORDS=("duration","latency","cpu","memory","bytes","size","count","rate","requests","errors","usage","percent","throughput","value","load")

def _rows(data: Any) -> list[dict[str,Any]]:
    if hasattr(data,"to_dicts"): return data.to_dicts()
    if hasattr(data,"to_dict"): return data.to_dict(orient="records")
    if isinstance(data,dict):
        if data and all(isinstance(v,(list,tuple)) for v in data.values()):
            return [dict(zip(data, vals)) for vals in zip(*data.values())]
        return [data]
    return [dict(r) for r in (data or []) if isinstance(r,dict)]

def _type(values):
    v=next((x for x in values if x is not None),None)
    if v is None:return "null"
    if isinstance(v,bool):return "boolean"
    if isinstance(v,(int,float)):return "numeric"
    if isinstance(v,datetime):return "datetime"
    return "string"

def _timestamp(name, vals, typ):
    n=name.lower()
    if any(x in n for x in ("timestamp","datetime","time","date","_at")): return True
    if typ=="numeric" and any(x in n for x in ("ts","epoch")):
        nums=[abs(float(x)) for x in vals if isinstance(x,(int,float)) and not isinstance(x,bool)]
        return bool(nums and 1e8 < statistics.median(nums) < 1e14)
    if typ=="string":
        sample=[str(x) for x in vals if x is not None][:12]
        if sample and sum(bool(re.match(r"^\d{4}-\d\d-\d\d[T ]",x)) for x in sample)/len(sample)>.7: return True
    return False

def _semantic(name, vals, typ, cardinality, count):
    n=name.lower(); nonnull=[x for x in vals if x is not None]
    if _timestamp(name,vals,typ): return "timestamp"
    if typ=="boolean" or n.startswith("is_") or n.startswith("has_"): return "boolean"
    if "trace" in n and ("id" in n or "_id" in n): return "trace_id"
    if "span" in n and "id" in n: return "span_id"
    if typ=="string" and nonnull:
        sample=[str(x).strip() for x in nonnull[:50]]
        for semantic in ("ipv4","ipv6"):
            pat=PATTERNS[semantic]
            if sum(bool(pat.match(x)) for x in sample)/len(sample)>=.8:
                try:
                    if all(ipaddress.ip_address(x) for x in sample): return semantic
                except ValueError: pass
    if n in {"source","src","from"} or (n.startswith("source_") and not n.endswith(("_ip","_ipv4","_ipv6"))): return "graph_source"
    if n in {"target","dst","destination","to"} or (n.startswith("target_") and not n.endswith(("_ip","_ipv4","_ipv6"))): return "graph_target"
    if n in {"lat","latitude"}: return "geo_latitude"
    if n in {"lon","lng","longitude"}: return "geo_longitude"
    if nonnull and typ=="string":
        ss=[str(x).strip() for x in nonnull[:50]]
        for semantic,pat in PATTERNS.items():
            if sum(bool(pat.match(x)) for x in ss)/len(ss) >= .8:
                if semantic in {"ipv4","ipv6"}:
                    try:
                        if not all(ipaddress.ip_address(x) for x in ss): continue
                    except ValueError: continue
                return semantic
    if typ=="numeric":
        ints=[int(x) for x in nonnull if isinstance(x,(int,float)) and float(x).is_integer()]
        if any(k in n for k in ("status_code","http_status")) and ints and all(100<=x<=599 for x in ints): return "http_status"
        if n in {"lat","latitude"}: return "geo_latitude"
        if n in {"lon","lng","longitude"}: return "geo_longitude"
        if "duration" in n or "latency" in n: return "latency"
        if any(k in n for k in ("total","_count","_counter")) or n.endswith("_total"): return "counter"
        return "metric" if (any(w in n for w in METRIC_WORDS) or cardinality/count>.25) else "numeric_dimension"
    if typ=="string" and cardinality/max(count,1)>.8 and ("id" in n or "uuid" in n or "key" in n):return "identifier"
    if typ=="string" and cardinality/max(count,1)>.8:return "high_cardinality"
    if typ=="string" and any(w in n for w in ("message","log","text","body")):return "text"
    if typ=="string" and any(w in n for w in DIMENSION_WORDS):return "dimension"
    if typ=="string":return "category" if cardinality<=min(100,max(10,count*.5)) else "high_cardinality"
    return typ

def _periodicity(nums: list[float]) -> dict[str,Any]:
    """Approximate dominant autocorrelation over short lags; intended as a visual hint."""
    n=len(nums)
    if n<8:return {"period_lag":None,"periodicity_score":0.0}
    mean=statistics.fmean(nums); centered=[x-mean for x in nums]; best=(0,0.0)
    for lag in range(1,min(25,n//3)):
        left=centered[:-lag]; right=centered[lag:]
        denom=math.sqrt(sum(x*x for x in left)*sum(y*y for y in right))
        corr=sum(x*y for x,y in zip(left,right))/denom if denom else 0.0
        if corr>best[1]:best=(lag,corr)
    return {"period_lag":best[0] if best[1]>=.35 else None,"periodicity_score":round(max(0.0,best[1]),4)}


def profile(data: Any, sample_size: int=1000) -> dict[str,Any]:
    source_count=None
    if hasattr(data,"to_dicts") and hasattr(data,"height"):
        source_count=int(data.height); rows=data.head(sample_size).to_dicts()
    elif isinstance(data,dict) and data and all(isinstance(v,(list,tuple)) for v in data.values()):
        source_count=len(next(iter(data.values()))); rows=[dict(zip(data,vals)) for vals in zip(*(v[:sample_size] for v in data.values()))]
    elif isinstance(data,(list,tuple)):
        source_count=len(data); rows=[dict(r) for r in data[:sample_size] if isinstance(r,dict)]
    else:
        rows=_rows(data)
    sample=rows[:sample_size]; count=source_count if source_count is not None else len(rows)
    if not sample:return {"row_count":count,"columns":[],"relationships":[],"fingerprint":{"sampled":0,"complete":count==0}}
    names=list(dict.fromkeys(k for row in sample for k in row.keys())); columns=[]
    for name in names:
        vals=[r.get(name) for r in sample]; nonnull=[v for v in vals if v is not None]; distinct=len(set(map(str,nonnull)))
        typ=_type(vals); semantic=_semantic(name,vals,typ,distinct,len(vals)); nums=[]
        for v in nonnull:
            if isinstance(v,(int,float)) and not isinstance(v,bool):
                f=float(v)
                if math.isfinite(f):nums.append(f)
        numeric=pl.Series("values",nums,dtype=pl.Float64) if nums else None
        n=len(nums)
        mean=numeric.mean() if numeric is not None else None
        std=numeric.std(ddof=0) if n>1 else 0
        skew=numeric.skew(bias=True) if std and numeric is not None else 0
        def pct(p): return numeric.quantile(p,interpolation="lower") if numeric is not None else None
        col={"name":name,"type":typ,"semantic":semantic,"nullable":len(vals)-len(nonnull),"null_ratio":round((len(vals)-len(nonnull))/max(1,len(vals)),4),"cardinality":distinct,"cardinality_ratio":round(distinct/max(1,len(nonnull)),4)}
        if n: col["statistics"]={"min":numeric.min(),"max":numeric.max(),"mean":round(mean,5),"skewness":round(skew or 0,4),"p50":pct(.5),"p95":pct(.95),"p99":pct(.99),**_periodicity(nums)}
        if semantic=="category": col["top_values"]=[{"value":k,"count":v} for k,v in Counter(map(str,nonnull)).most_common(8)]
        columns.append(col)
    semantics=[c["semantic"] for c in columns]
    rel=[]
    if "geo_latitude" in semantics and "geo_longitude" in semantics: rel.append({"type":"geospatial_pair","columns":[columns[semantics.index("geo_latitude")]["name"],columns[semantics.index("geo_longitude")]["name"]]})
    source_col=next((c for c in columns if c["semantic"]=="graph_source" or c["name"].lower() in {"source","src","from"}),None)
    target_col=next((c for c in columns if c["semantic"]=="graph_target" or c["name"].lower() in {"target","dst","destination","to"}),None)
    if source_col and target_col: rel.append({"type":"directed_edge","source":source_col["name"],"target":target_col["name"]})
    if "timestamp" in semantics and any(x in semantics for x in ("metric","counter","latency")): rel.append({"type":"time_series"})
    return {"row_count":count,"sampled_rows":len(sample),"columns":columns,"relationships":rel,"fingerprint":{"sampled":len(sample),"complete":count<=sample_size}}

class SchemaProfiler:
    def profile(self,data: Any, sample_size: int=1000): return profile(data,sample_size)
