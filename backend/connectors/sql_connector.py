from __future__ import annotations
import os
import time
from typing import Any
import asyncpg
from .base import BaseConnector, QueryResult, ensure_read_only

class SQLConnector(BaseConnector):
    """PostgreSQL async pool; credentials are read from DATABASE_URL."""
    kind = "postgres"
    def __init__(self, dsn: str | None = None, min_size: int = 1, max_size: int = 8):
        self.dsn = dsn or os.getenv("DATABASE_URL", "postgresql://spectra:spectra@localhost:5432/spectra")
        self.min_size=min_size; self.max_size=max_size; self.pool=None
    async def _pool(self):
        if self.pool is None: self.pool = await asyncpg.create_pool(self.dsn, min_size=self.min_size, max_size=self.max_size, command_timeout=20)
        return self.pool
    async def query(self, statement: str, **options: Any) -> QueryResult:
        sql=ensure_read_only(statement); started=time.perf_counter()
        async with (await self._pool()).acquire() as conn:
            async with conn.transaction(readonly=True):
                records=await conn.fetch(sql)
        rows=[dict(r) for r in records]
        return QueryResult(rows, list(rows[0]) if rows else [], (time.perf_counter()-started)*1000, self.kind)
    async def health(self):
        try: await self._pool(); return {"status":"ready", "kind":self.kind}
        except Exception as e: return {"status":"unavailable", "kind":self.kind, "detail":str(e)}
    async def close(self):
        if self.pool: await self.pool.close()

class ClickHouseConnector(BaseConnector):
    kind="clickhouse"
    def __init__(self, url: str | None=None, username: str | None=None, password: str | None=None):
        self.url=url or os.getenv("CLICKHOUSE_URL", "http://localhost:8123"); self.username=username or os.getenv("CLICKHOUSE_USER", "default"); self.password=password or os.getenv("CLICKHOUSE_PASSWORD", "")
    async def query(self, statement: str, **options):
        import httpx, json
        sql=ensure_read_only(statement) + " FORMAT JSONEachRow"
        async with httpx.AsyncClient(timeout=20) as client:
            r=await client.post(self.url, content=sql, auth=(self.username,self.password)); r.raise_for_status()
        rows=[json.loads(line) for line in r.text.splitlines() if line.strip()]
        return QueryResult(rows, list(rows[0]) if rows else [], source=self.kind)
