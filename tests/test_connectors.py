import pytest
from backend.connectors.base import ensure_read_only
from backend.connectors.duckdb_connector import DuckDBConnector


def test_read_only_sql_guard():
    assert ensure_read_only("SELECT 1;") == "SELECT 1"
    for sql in ("DROP TABLE telemetry", "SELECT 1; SELECT 2", "SELECT * FROM read_csv('/etc/passwd')", "SELECT pg_read_file('/etc/passwd')"):
        with pytest.raises(ValueError):
            ensure_read_only(sql)


@pytest.mark.asyncio
async def test_duckdb_query_and_ingest():
    db=DuckDBConnector()
    db.ingest_events([{"timestamp":1.0,"service":"api","latency":120.0,"kind":"metric"}])
    result=await db.query("SELECT service, latency FROM telemetry")
    assert result.rows==[{"service":"api","latency":120.0}]
    await db.close()
