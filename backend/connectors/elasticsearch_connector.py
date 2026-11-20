"""Read-only Elasticsearch/OpenSearch search connector."""
from __future__ import annotations
import json, os
from typing import Any
import httpx
from .base import BaseConnector, QueryResult

class ElasticsearchConnector(BaseConnector):
    kind="elasticsearch"
    def __init__(self,url:str|None=None,index:str|None=None,username:str|None=None,password:str|None=None):
        self.url=(url or os.getenv("ELASTICSEARCH_URL","http://localhost:9200")).rstrip("/")
        self.index=index or os.getenv("ELASTICSEARCH_INDEX","logs-*")
        self.auth=(username or os.getenv("ELASTICSEARCH_USER",""),password or os.getenv("ELASTICSEARCH_PASSWORD",""))
    async def query(self,statement:str="{}",**options:Any)->QueryResult:
        try: body=json.loads(statement or "{}")
        except json.JSONDecodeError as exc: raise ValueError("Elasticsearch query must be a JSON Query DSL object") from exc
        if not isinstance(body,dict) or any(k in body for k in ("script","script_fields","runtime_mappings")):
            raise ValueError("Only object queries without scripts are permitted")
        body.setdefault("size",min(int(options.get("limit",1000)),5000))
        async with httpx.AsyncClient(timeout=15) as client:
            response=await client.post(f"{self.url}/{self.index}/_search",json=body,auth=self.auth if self.auth[0] else None)
            response.raise_for_status()
        hits=response.json().get("hits",{}).get("hits",[])
        rows=[{"_id":h.get("_id"),"_index":h.get("_index"),**h.get("_source",{})} for h in hits]
        return QueryResult(rows,list(rows[0]) if rows else [],source=self.kind)
    async def health(self):
        try:
            async with httpx.AsyncClient(timeout=3) as client: r=await client.get(self.url,auth=self.auth if self.auth[0] else None)
            return {"status":"ready" if r.is_success else "degraded","kind":self.kind}
        except Exception as exc: return {"status":"unavailable","kind":self.kind,"detail":str(exc)}
