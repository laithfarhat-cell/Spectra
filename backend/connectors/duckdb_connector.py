from __future__ import annotations
import time
from pathlib import Path
from typing import Any
import duckdb
from .base import BaseConnector, QueryResult, ensure_read_only

class DuckDBConnector(BaseConnector):
    kind = "duckdb"
    def __init__(self, database: str = ":memory:", data_dir: str | None = None):
        self.database = database
        self.data_dir = Path(data_dir).resolve() if data_dir else None
        self.connection = duckdb.connect(database=database, read_only=False)
        self.connection.execute("SET threads = 4")
        self.connection.execute("CREATE TABLE IF NOT EXISTS telemetry (timestamp DOUBLE, kind VARCHAR, service VARCHAR, host VARCHAR, environment VARCHAR, severity VARCHAR, message VARCHAR, value DOUBLE, requests DOUBLE, cpu DOUBLE, memory DOUBLE, latency DOUBLE, status_code INTEGER, trace_id VARCHAR, source VARCHAR, target VARCHAR, client_ip VARCHAR, cve VARCHAR, latitude DOUBLE, longitude DOUBLE, tenant_id VARCHAR)")
        self.connection.execute("ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS tenant_id VARCHAR")
        self.cache: dict[str, tuple[float, QueryResult]] = {}

    def ingest_events(self, events: list[dict[str, Any]]) -> None:
        cols=["timestamp","kind","service","host","environment","severity","message","value","requests","cpu","memory","latency","status_code","trace_id","source","target","client_ip","cve","latitude","longitude","tenant_id"]
        placeholders=", ".join(["?"]*len(cols))
        rows=[]
        for event in events:
            values=[]
            for col in cols:
                value=event.get(col)
                if col=="timestamp" and value is not None:
                    try: value=float(value)
                    except (TypeError,ValueError):
                        from datetime import datetime
                        try: value=datetime.fromisoformat(str(value).replace("Z","+00:00")).timestamp()
                        except ValueError: value=None
                values.append(value)
            rows.append(values)
        if rows: self.connection.executemany(f"INSERT INTO telemetry VALUES ({placeholders})", rows)
        self.cache.clear()

    def _register_files(self) -> None:
        if not self.data_dir or not self.data_dir.exists(): return
        # Only files within configured data_dir are exposed. Names are sanitized identifiers.
        for p in self.data_dir.glob("*"):
            if p.suffix.lower() not in {".csv", ".json", ".jsonl", ".parquet"} or not p.is_file(): continue
            name = "\"" + p.stem.replace('"', '') + "\""
            path = str(p).replace("'", "''")
            reader = {".csv": f"read_csv_auto('{path}')", ".parquet": f"read_parquet('{path}')", ".json": f"read_json_auto('{path}')", ".jsonl": f"read_json_auto('{path}', format='newline_delimited')"}[p.suffix.lower()]
            try: self.connection.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM {reader}")
            except Exception: continue

    async def query(self, statement: str, **options: Any) -> QueryResult:
        sql = ensure_read_only(statement); ttl = max(0, int(options.get("cache_ttl", 3)))
        cached = self.cache.get(sql)
        if cached and time.monotonic() - cached[0] < ttl: return cached[1]
        started = time.perf_counter(); self._register_files()
        try:
            rel = self.connection.execute(sql)
            rows = rel.fetchmany(min(int(options.get("limit", 10_000)), 50_000))
            cols = [d[0] for d in rel.description or []]
            result = QueryResult([dict(zip(cols, row)) for row in rows], cols, (time.perf_counter()-started)*1000, self.kind)
            self.cache[sql] = (time.monotonic(), result)
            return result
        except Exception as exc: raise ValueError(f"DuckDB query failed: {exc}") from exc

    async def health(self): return {"status":"ready", "kind":self.kind, "database":self.database}
    async def close(self): self.connection.close()
