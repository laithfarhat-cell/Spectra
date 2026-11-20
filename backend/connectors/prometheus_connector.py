from __future__ import annotations
import os
import httpx
from .base import BaseConnector, QueryResult

class PrometheusConnector(BaseConnector):
    kind = "prometheus"
    def __init__(self, url: str | None = None, timeout: float = 10):
        self.url = (url or os.getenv("PROMETHEUS_URL", "http://localhost:9090")).rstrip("/")
        self.client = httpx.AsyncClient(timeout=timeout)
    async def query(self, statement: str, **options) -> QueryResult:
        endpoint = "/api/v1/query_range" if options.get("start") and options.get("end") else "/api/v1/query"
        params = {"query": statement}
        for key in ("start", "end", "step", "time"):
            if options.get(key) is not None: params[key] = options[key]
        response = await self.client.get(self.url + endpoint, params=params); response.raise_for_status()
        body = response.json()
        if body.get("status") != "success": raise ValueError(body.get("error", "Prometheus query failed"))
        rows=[]
        for series in body.get("data", {}).get("result", []):
            metric = series.get("metric", {})
            values = series.get("values", [[*series.get("value", [None, None])]])
            for ts, value in values:
                rows.append({**metric, "timestamp": float(ts), "value": float(value)})
        return QueryResult(rows, list(rows[0]) if rows else [], source=self.kind)
    async def health(self):
        try:
            r=await self.client.get(self.url+"/-/healthy"); return {"status":"ready" if r.is_success else "degraded", "kind":self.kind}
        except Exception as e: return {"status":"unavailable", "kind":self.kind, "detail":str(e)}
    async def close(self): await self.client.aclose()
