"""Common asynchronous connector contract and shared result models."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

@dataclass
class QueryResult:
    rows: list[dict[str, Any]]
    columns: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0
    source: str = "unknown"
    def __post_init__(self):
        if not self.columns and self.rows:
            self.columns = list(self.rows[0])

class BaseConnector(ABC):
    """Pluggable query source. Implementations must enforce their own read-only policy."""
    kind = "base"
    @abstractmethod
    async def query(self, statement: str, **options: Any) -> QueryResult: ...
    async def health(self) -> dict[str, Any]:
        return {"status": "ready", "kind": self.kind}
    async def close(self) -> None:
        return None


def ensure_read_only(statement: str) -> str:
    """Reject multi-statement and mutating SQL before handing it to a SQL connector."""
    import re
    sql = statement.strip()
    if not sql or len(sql) > 100_000:
        raise ValueError("Query is empty or exceeds the 100KB limit")
    clean = re.sub(r"/\*.*?\*/|--[^\n]*", " ", sql, flags=re.S).strip()
    if ";" in clean.rstrip(";"):
        raise ValueError("Multiple SQL statements are not allowed")
    if not re.match(r"^(SELECT|WITH|EXPLAIN|DESCRIBE|SHOW)\b", clean, re.I):
        raise ValueError("Only read-only SELECT/CTE queries are allowed")
    forbidden = r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|COPY|PRAGMA|CALL|EXEC|TRUNCATE|GRANT|REVOKE|VACUUM|INSTALL|LOAD)\b"
    if re.search(forbidden, clean, re.I):
        raise ValueError("Mutating or administrative SQL is not allowed")
    external = r"\b(read_csv|read_csv_auto|read_json|read_json_auto|read_parquet|glob|http_get|read_text|read_blob|sqlite_scan|postgres_scan|pg_read_file|pg_read_binary_file|pg_ls_dir|dblink|lo_import|lo_export|pg_sleep|nextval|setval|pg_notify)\s*\("
    if re.search(external, clean, re.I):
        raise ValueError("Direct external file and network access is not allowed in queries")
    return clean.rstrip(";")
