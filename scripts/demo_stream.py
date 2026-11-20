#!/usr/bin/env python3
"""Generate realistic local telemetry for a Spectra demo stack."""
import json, math, os, random, time, urllib.error, urllib.request, uuid

URL=os.getenv("SPECTRA_INGEST_URL","http://api:8000/api/v1/ingest")
API_KEY=os.getenv("SPECTRA_INGEST_API_KEY","")
SERVICES=["edge-gateway","checkout","inventory","payments","search"]
HOSTS=[f"node-{i:02d}" for i in range(1,9)]
IPS=["198.51.100.24","203.0.113.12","10.42.1.18","192.0.2.87"]

def send(events):
    body=json.dumps({"events":events}).encode(); headers={"Content-Type":"application/json"}
    if API_KEY: headers["X-API-Key"]=API_KEY
    req=urllib.request.Request(URL,data=body,headers=headers,method="POST")
    try:
        with urllib.request.urlopen(req,timeout=5) as response: return response.status
    except Exception as exc:
        print(f"ingest retry: {exc}",flush=True); return None

def main():
    print(f"Sending demo telemetry to {URL}",flush=True)
    while True:
        now=time.time(); events=[]
        for i in range(25):
            service=random.choice(SERVICES); latency=max(5,random.lognormvariate(4.0,.45)); fail=random.random()<.035
            events.append({"kind":"metric","timestamp":now-random.random()*4,"service":service,"host":random.choice(HOSTS),"environment":"production","requests":round(random.uniform(85,180),2),"cpu":round(random.uniform(18,84),2),"memory":round(random.uniform(42,88),2),"latency":round(latency,2),"status_code":random.choice([200,200,200,201,204,429,500]) if fail else 200,"trace_id":str(uuid.uuid4()),"source":service,"target":random.choice(["postgres-primary","redis-cache","inventory","payments"]),"value":random.randint(1,12)})
            if i%3==0:
                severity="error" if fail else random.choice(["info","info","warning"])
                msg=("HTTP 5xx upstream timeout from suspicious address" if fail else "Request completed within service objective")
                events.append({"kind":"log","timestamp":now,"service":service,"host":random.choice(HOSTS),"environment":"production","severity":severity,"message":msg,"status_code":500 if fail else 200,"client_ip":random.choice(IPS),"trace_id":str(uuid.uuid4()),"latency":round(latency,2)})
        if random.random()<.3:
            events.append({"kind":"security","timestamp":now,"service":"edge-gateway","severity":"warning","message":"Repeated authentication failures detected","source":random.choice(IPS),"target":"edge-gateway","cve":"CVE-2024-3094","attempts":random.randint(5,30),"country":random.choice(["LY","DE","US","NL"])})
        if send(events): print(f"ingested {len(events)} events",flush=True)
        time.sleep(2)
if __name__=="__main__": main()
