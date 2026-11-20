from __future__ import annotations
import asyncio
from collections import deque
from typing import Any
from .base import BaseConnector, QueryResult

class StreamConnector(BaseConnector):
    """In-memory bounded event buffer shared by ingest and websocket subscribers."""
    kind="stream"
    def __init__(self, max_events: int=50_000):
        self.events=deque(maxlen=max_events); self.subscribers:set[asyncio.Queue]=set(); self.lock=asyncio.Lock()
    async def publish(self, event: dict[str, Any]) -> dict[str, Any]:
        async with self.lock:
            self.events.append(event)
            for q in list(self.subscribers):
                try: q.put_nowait(event)
                except asyncio.QueueFull:
                    try: q.get_nowait(); q.put_nowait(event)
                    except asyncio.QueueEmpty: pass
        return event
    async def query(self, statement: str="", **options):
        limit=min(int(options.get("limit",1000)), 10_000)
        events=list(self.events)
        if options.get("kind"): events=[e for e in events if e.get("kind")==options["kind"]]
        return QueryResult(events[-limit:], list(events[-1]) if events else [], source=self.kind)
    async def subscribe(self):
        q=asyncio.Queue(maxsize=500); self.subscribers.add(q)
        try:
            while True: yield await q.get()
        finally: self.subscribers.discard(q)
    async def health(self): return {"status":"ready", "kind":self.kind, "events":len(self.events)}
