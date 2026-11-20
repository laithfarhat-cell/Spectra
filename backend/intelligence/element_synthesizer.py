"""Deterministic mapping from semantic schemas to editable panel specifications."""
from __future__ import annotations

def recommend(schema: dict) -> list[dict]:
    cols=schema.get("columns",[]); by={c.get("semantic"):c for c in cols}; out=[]
    def add(kind,title,fields,score,description,config=None):
        out.append({"id":f"{kind}-{len(out)+1}","type":kind,"title":title,"fields":fields,"score":score,"description":description,"config":config or {}})
    timestamp=by.get("timestamp"); metrics=[c for c in cols if c.get("semantic") in {"metric","counter","latency","numeric_dimension"}]
    if timestamp and metrics: add("timeseries","Telemetry over time",{"time":timestamp["name"],"values":[m["name"] for m in metrics]},.98,"Time-aligned multi-series chart with anomaly context",{"anomaly":"zscore","aggregation":"avg"})
    edge=next((r for r in schema.get("relationships",[]) if r.get("type")=="directed_edge"),{})
    src=by.get("graph_source") or next((c for c in cols if c.get("name")==edge.get("source")),None)
    target=by.get("graph_target") or next((c for c in cols if c.get("name")==edge.get("target")),None)
    if src and target:
        weight=next((c for c in metrics if "weight" in c["name"].lower() or "count" in c["name"].lower()),None)
        fields={"source":src["name"],"target":target["name"],"weight":weight["name"] if weight else None}
        add("topology","Service & entity topology",fields,.97,"Explore source-to-target relationships")
        add("sankey","Traffic flow",fields,.86,"Compare weighted flows between entities")
    if "geo_latitude" in by and "geo_longitude" in by: add("geo","Geospatial events",{"latitude":by["geo_latitude"]["name"],"longitude":by["geo_longitude"]["name"]},.96,"Map event coordinates")
    elif any(c.get("semantic") in {"ipv4","ipv6"} for c in cols): add("geo","IP activity",{"ip":next(c["name"] for c in cols if c.get("semantic") in {"ipv4","ipv6"})},.72,"IP addresses detected; geolocation provider required")
    latency=next((c for c in cols if c.get("semantic")=="latency"),None)
    if latency: add("heatmap","Latency distribution",{"value":latency["name"]},.91,"Percentile distribution and histogram",{"percentiles":[50,95,99]})
    if timestamp and any(c.get("semantic") in {"severity","text"} for c in cols): add("logs","Live log explorer",{"time":timestamp["name"],"severity":by.get("severity",{}).get("name"),"message":by.get("text",{}).get("name")},.94,"Faceted searchable event stream")
    if metrics and len(metrics)==1: add("stat","Key metric",{"value":metrics[0]["name"]},.7,"Metric summary with sparkline and thresholds")
    add("table","Raw data",{"columns":[c["name"] for c in cols]},.45,"Sortable, filterable records")
    return sorted(out,key=lambda x:x["score"],reverse=True)

class ElementSynthesizer:
    recommend=staticmethod(recommend)
