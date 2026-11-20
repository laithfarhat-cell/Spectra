from __future__ import annotations
import asyncio, hashlib, json, os, secrets, time, uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .connectors.duckdb_connector import DuckDBConnector
from .connectors.prometheus_connector import PrometheusConnector
from .connectors.stream_connector import StreamConnector
from .connectors.sql_connector import SQLConnector, ClickHouseConnector
from .connectors.elasticsearch_connector import ElasticsearchConnector
from .intelligence.schema_profiler import profile
from .intelligence.element_synthesizer import recommend
from .intelligence.nl_copilot import generate
from .alerting.engine import AlertEngine, AlertRule
from .auth.rbac import Role, current_user, require_role, create_token

stream=StreamConnector(); duck=DuckDBConnector(database=os.getenv("DUCKDB_PATH",":memory:"),data_dir=os.getenv("DATA_DIR","./data")); alerts=AlertEngine()
connectors={"duckdb":duck,"stream":stream,"prometheus":PrometheusConnector(),"postgres":SQLConnector(),"clickhouse":ClickHouseConnector(),"elasticsearch":ElasticsearchConnector()}
api_keys:dict[str,dict[str,Any]]={}

@asynccontextmanager
async def lifespan(app):
    await stream.publish({"kind":"system","timestamp":time.time(),"service":"spectra-api","severity":"info","message":"Spectra telemetry stream online","value":1})
    await alerts.start(stream)
    yield
    await alerts.stop()
    for c in connectors.values():
        try: await c.close()
        except Exception: pass
app=FastAPI(title="Spectra Observability API",version="0.1.0",description="Open telemetry analytics and intelligent dashboards",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=os.getenv("CORS_ORIGINS","*").split(","),allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

class QueryRequest(BaseModel): datasource:str="duckdb"; query:str="SELECT * FROM telemetry LIMIT 100"; options:dict[str,Any]=Field(default_factory=dict)
class IngestRequest(BaseModel): events:list[dict[str,Any]]|dict[str,Any]
class CopilotRequest(BaseModel): prompt:str; schema_data:dict[str,Any]=Field(default_factory=dict,alias="schema"); datasource:str="duckdb"
class RuleRequest(BaseModel): name:str; field:str; threshold:float; operator:str=">"; for_seconds:int=0; webhook:str|None=None

async def verify_ingest(x_api_key:str|None=Header(default=None)):
    expected=os.getenv("SPECTRA_INGEST_API_KEY")
    if expected and x_api_key==expected: return {"tenant":"default","scopes":["ingest:write"]}
    if x_api_key:
        digest=hashlib.sha256(x_api_key.encode()).hexdigest()
        for record in api_keys.values():
            if secrets.compare_digest(record["hash"],digest) and "ingest:write" in record["scopes"]:
                return {"tenant":record["tenant"],"scopes":record["scopes"]}
    if expected or api_keys: raise HTTPException(401,"Invalid or unscoped ingestion API key")
    return {"tenant":"default","scopes":["ingest:write"]}

@app.get("/api/v1/health")
async def health(): return {"status":"ok","service":"spectra","connectors":{k:await v.health() for k,v in connectors.items() if k in {"duckdb","stream"}}}
@app.post("/api/v1/ingest")
async def ingest(payload:IngestRequest,tenant_info:dict=Depends(verify_ingest)):
    events=payload.events if isinstance(payload.events,list) else [payload.events]
    if len(events)>10_000: raise HTTPException(413,"Maximum 10,000 events per request")
    received=[]
    for raw in events:
        event={**raw}; event.setdefault("timestamp",time.time()); event.setdefault("kind","event"); event.setdefault("event_id",str(uuid.uuid4())); event.setdefault("tenant_id",tenant_info["tenant"])
        received.append(await stream.publish(event))
    duck.ingest_events(received)
    return {"accepted":len(received),"schema":profile(received)}
@app.get("/api/v1/stream")
async def recent_stream(limit:int=100,kind:str|None=None):
    result=await stream.query(limit=limit,kind=kind); return {"rows":result.rows,"schema":profile(result.rows)}
@app.post("/api/v1/query")
async def query(body:QueryRequest,user=Depends(current_user)):
    if body.datasource not in connectors: raise HTTPException(404,"Unknown datasource")
    try:
        result=await connectors[body.datasource].query(body.query,**body.options)
        return {"rows":result.rows,"columns":result.columns,"elapsed_ms":round(result.elapsed_ms,2),"source":result.source,"schema":profile(result.rows),"recommendations":recommend(profile(result.rows))}
    except ValueError as e: raise HTTPException(400,str(e))
    except Exception as e: raise HTTPException(502,f"Datasource query failed: {e}")
@app.post("/api/v1/profile")
async def profile_data(body:dict[str,Any]):
    rows=body.get("rows",body)
    result=profile(rows)
    return {"schema":result,"recommendations":recommend(result)}
@app.post("/api/v1/copilot/generate")
async def copilot(body:CopilotRequest,user=Depends(current_user)):
    return await generate(body.prompt,body.schema_data,body.datasource)
@app.get("/api/v1/dashboards")
async def dashboards():
    items=[]
    for path in (Path("provisioning/dashboards"),Path(os.getenv("DASHBOARD_DIR","./data/dashboards"))):
        if path.exists():
            for f in list(path.glob("*.json"))+list(path.glob("*.yaml"))+list(path.glob("*.yml")):
                try:
                    if f.suffix.lower() in {".yaml",".yml"}:
                        import yaml
                        items.append(yaml.safe_load(f.read_text()))
                    else: items.append(json.loads(f.read_text()))
                except Exception: continue
    return items or [demo_dashboard()]
@app.put("/api/v1/dashboards/{dashboard_id}")
async def save_dashboard(dashboard_id:str,body:dict[str,Any],user=Depends(require_role(Role.ADMIN,Role.EDITOR))):
    # Provisioning is filesystem-backed; sanitize IDs and enforce dashboard directory boundary.
    if not dashboard_id.replace("-","").replace("_","").isalnum(): raise HTTPException(400,"Invalid dashboard id")
    path=Path(os.getenv("DASHBOARD_DIR","./data/dashboards")); path.mkdir(parents=True,exist_ok=True); (path/f"{dashboard_id}.json").write_text(json.dumps(body,indent=2))
    return {"saved":True,"id":dashboard_id}
@app.post("/api/v1/alerts/rules")
async def add_alert(body:RuleRequest,user=Depends(require_role(Role.ADMIN,Role.EDITOR))):
    rule=AlertRule(**body.model_dump()); alerts.add_rule(rule); return {"name":rule.name,"state":rule.state.value}
@app.get("/api/v1/alerts")
async def list_alerts(): return {"rules":[{"name":r.name,"field":r.field,"threshold":r.threshold,"state":r.state.value,"last_value":r.last_value} for r in alerts.rules.values()],"history":alerts.history[-100:]}
@app.post("/api/v1/auth/token")
async def token(body:dict[str,str]):
    # For a real deployment, replace this bootstrap endpoint with an external identity provider.
    if os.getenv("SPECTRA_BOOTSTRAP_PASSWORD") and body.get("password")!=os.getenv("SPECTRA_BOOTSTRAP_PASSWORD"): raise HTTPException(401,"Invalid credentials")
    role=Role(body.get("role","Viewer"))
    if role!=Role.VIEWER and not os.getenv("SPECTRA_BOOTSTRAP_PASSWORD"): raise HTTPException(403,"Privileged roles require configured bootstrap password")
    return {"access_token":create_token(body.get("username","viewer"),role),"token_type":"bearer"}
@app.post("/api/v1/auth/api-keys")
async def create_api_key(body:dict[str,str],user=Depends(require_role(Role.ADMIN))):
    key_id=str(uuid.uuid4()); secret="spk_"+secrets.token_urlsafe(32)
    api_keys[key_id]={"hash":hashlib.sha256(secret.encode()).hexdigest(),"label":body.get("label","ingest key")[:80],"scopes":["ingest:write"],"tenant":body.get("tenant",user.get("tenant","default"))}
    return {"id":key_id,"key":secret,"scopes":["ingest:write"],"warning":"Store this key securely; it is shown only once."}
@app.get("/api/v1/auth/api-keys")
async def list_api_keys(user=Depends(require_role(Role.ADMIN))):
    return [{"id":key_id,"label":record["label"],"scopes":record["scopes"],"tenant":record["tenant"]} for key_id,record in api_keys.items()]
@app.delete("/api/v1/auth/api-keys/{key_id}")
async def revoke_api_key(key_id:str,user=Depends(require_role(Role.ADMIN))):
    if api_keys.pop(key_id,None) is None: raise HTTPException(404,"API key not found")
    return {"revoked":True,"id":key_id}
@app.websocket("/api/v1/ws/stream")
async def websocket_stream(ws:WebSocket):
    await ws.accept(); sub=stream.subscribe(); task=asyncio.create_task(_send_stream(ws,sub))
    try:
        while True:
            message=await ws.receive_text()
            if message=="ping": await ws.send_json({"type":"pong"})
    except WebSocketDisconnect: pass
    finally: task.cancel()
async def _send_stream(ws,sub):
    async for event in sub: await ws.send_json(event)

def demo_dashboard():
    return {"id":"demo-overview","title":"System Overview","schemaVersion":1,"timeRange":"1h","variables":[{"name":"environment","value":"production"},{"name":"service","value":"all"},{"name":"severity","value":"all"}],"panels":[{"id":"p1","type":"timeseries","title":"Request & resource telemetry","x":0,"y":0,"w":8,"h":5},{"id":"p2","type":"stat","title":"Events ingested","x":8,"y":0,"w":4,"h":3,"config":{"mode":"row_count","label":"Events in view"}},{"id":"p3","type":"logs","title":"Live security & application events","x":0,"y":5,"w":8,"h":5},{"id":"p4","type":"topology","title":"Service topology","x":8,"y":3,"w":4,"h":5}],"refreshSeconds":5}

# In the production image, serve the compiled SPA from the same origin as the API.
_frontend = Path(os.getenv("FRONTEND_DIST", "/app/frontend-dist"))
if _frontend.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
