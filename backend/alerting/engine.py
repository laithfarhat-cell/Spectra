"""Scheduled threshold/drift alert state machine with deduplication and webhooks."""
from __future__ import annotations
import asyncio, json, os, statistics, time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import httpx

class AlertState(str,Enum): OK="OK"; PENDING="PENDING"; FIRING="FIRING"; RESOLVED="RESOLVED"
@dataclass
class AlertRule:
    name:str; field:str; threshold:float; operator:str=">"; for_seconds:int=0; cooldown_seconds:int=300; webhook:str|None=None
    state:AlertState=AlertState.OK; pending_since:float|None=None; last_sent:float=0; last_value:float|None=None

class AlertEngine:
    def __init__(self): self.rules:dict[str,AlertRule]={}; self.history=[]; self._task=None
    def add_rule(self, rule:AlertRule): self.rules[rule.name]=rule
    async def evaluate(self, name:str, rows:list[dict[str,Any]]):
        rule=self.rules[name]; vals=[float(r[rule.field]) for r in rows if r.get(rule.field) is not None]
        value=vals[-1] if vals else None; rule.last_value=value; now=time.time()
        triggered=value is not None and ((value>rule.threshold) if rule.operator==">" else (value<rule.threshold))
        old=rule.state
        if triggered:
            if rule.state in (AlertState.OK,AlertState.RESOLVED): rule.state=AlertState.PENDING; rule.pending_since=now
            if now-(rule.pending_since or now)>=rule.for_seconds: rule.state=AlertState.FIRING
        elif rule.state!=AlertState.OK: rule.state=AlertState.RESOLVED; rule.pending_since=None
        event={"name":name,"previous":old.value,"state":rule.state.value,"value":value,"at":now}
        if rule.state!=old:
            self.history.append(event)
            if rule.state in (AlertState.FIRING,AlertState.RESOLVED) and rule.webhook and now-rule.last_sent>=rule.cooldown_seconds:
                try:
                    async with httpx.AsyncClient(timeout=5) as client: await client.post(rule.webhook,json=event)
                    rule.last_sent=now
                except Exception: pass
        return event
    async def start(self, source, interval=10):
        async def loop():
            while True:
                rows=(await source.query(limit=1000)).rows
                for name in list(self.rules): await self.evaluate(name,rows)
                await asyncio.sleep(interval)
        if self._task is None: self._task=asyncio.create_task(loop())
    async def stop(self):
        if self._task: self._task.cancel(); self._task=None
