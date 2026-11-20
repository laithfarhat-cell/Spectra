"""NL-to-panel helper with optional OpenAI-compatible endpoint and safe rule fallback."""
from __future__ import annotations
import os
import re
import httpx
from .element_synthesizer import recommend

async def generate(prompt: str, schema: dict, datasource: str="demo") -> dict:
    endpoint=os.getenv("LLM_BASE_URL"); api_key=os.getenv("LLM_API_KEY"); model=os.getenv("LLM_MODEL","local-model")
    if endpoint:
        system="Return JSON only: {title, query, panels}. Use read-only SQL. Infer panel fields only from provided schema."
        payload={"model":model,"messages":[{"role":"system","content":system},{"role":"user","content":f"Prompt: {prompt}\nSchema: {schema}"}],"temperature":0.1}
        async with httpx.AsyncClient(timeout=20) as client:
            response=await client.post(endpoint.rstrip("/")+"/chat/completions",json=payload,headers={"Authorization":f"Bearer {api_key}"} if api_key else {})
            response.raise_for_status(); text=response.json()["choices"][0]["message"]["content"]
        import json
        match=re.search(r"\{.*\}",text,re.S)
        if match:
            result=json.loads(match.group()); result["mode"]="llm"; return result
    recs=recommend(schema); prompt_l=prompt.lower()
    if "latency" in prompt_l or "p95" in prompt_l: selected=[x for x in recs if x["type"] in {"heatmap","timeseries"}]
    elif any(x in prompt_l for x in ("log","error","severity")): selected=[x for x in recs if x["type"] in {"logs","timeseries"}]
    elif any(x in prompt_l for x in ("network","topology","flow")): selected=[x for x in recs if x["type"] in {"topology","sankey"}]
    else: selected=recs[:3]
    query="SELECT * FROM telemetry LIMIT 1000"
    metric=next((c for c in schema.get("columns",[]) if c.get("semantic") in {"latency","metric"}),None)
    if metric and "p95" in prompt_l: query=f"SELECT service, quantile_cont({metric['name']}, 0.95) AS p95 FROM telemetry GROUP BY service"
    return {"title":prompt.strip().capitalize()[:80] or "Suggested dashboard","datasource":datasource,"query":query,"panels":selected,"mode":"rules","note":"Rule-based suggestion; validate query and fields against your datasource."}
