"""WebSocket hub: broadcasts tick deltas and narrative events to browsers.

The browser is a pure view (V1's F25/F33/F46/F47 class of bugs): it can
connect, disconnect, and reconnect at any time; the server owns pause state
and re-sends a full init snapshot on every connect.
"""
from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import WebSocket

from townsim.kernel.events import Event
from townsim.kernel.kernel import Kernel

log = structlog.get_logger(__name__)


class WsHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, kernel: Kernel) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        await self._send(ws, self.init_payload(kernel))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    def init_payload(self, kernel: Kernel) -> dict:
        now = kernel.now()
        return {
            "type": "init",
            "map": kernel.world.town.to_dict(),
            "snapshot": kernel.world.snapshot(now.to_dict()),
            "stories": list(kernel.world.stories),
            "paused": kernel.paused,
            "seed": kernel.cfg.kernel.seed,
            "run_dir": str(kernel.run_dir),
        }

    async def on_tick(self, kernel: Kernel, events: list[Event]) -> None:
        if not self._clients:
            return
        now = kernel.now()
        messages: list[dict] = [{
            "type": "tick",
            "time": now.to_dict(),
            "agents": [a.to_public_dict() for a in kernel.world.agents_sorted()],
        }]
        logs = [
            {"agent": e.agent_id,
             "name": kernel.world.agents[e.agent_id].spec.name
             if e.agent_id in kernel.world.agents else e.agent_id,
             "text": e.data.get("text", ""), "t": now.label()}
            for e in events if e.type == "log"
        ]
        if logs:
            messages.append({"type": "logs", "items": logs})
        for event in events:
            if event.type == "story_written":
                messages.append({"type": "story",
                                 "day": f"Day {event.data['day_number']} ({event.data['weekday']})",
                                 "text": event.data["text"]})
            elif event.type == "diary_written":
                messages.append({"type": "diary", "agent": event.agent_id,
                                 "day": event.data["day_number"],
                                 "text": event.data["text"]})
        await self.broadcast(messages)

    async def broadcast_paused(self, value: bool) -> None:
        await self.broadcast([{"type": "paused", "value": value}])

    async def broadcast(self, messages: list[dict]) -> None:
        if not self._clients:
            return
        payloads = [json.dumps(m, ensure_ascii=False) for m in messages]
        dead: list[WebSocket] = []
        async with self._lock:
            clients = list(self._clients)
        for ws in clients:
            try:
                for payload in payloads:
                    await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    async def _send(self, ws: WebSocket, message: dict) -> None:
        await ws.send_text(json.dumps(message, ensure_ascii=False))
