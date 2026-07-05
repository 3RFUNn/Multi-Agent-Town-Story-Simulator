"""WebSocket hub: broadcasts tick deltas and narrative events to browsers.

The browser is a pure view: it can connect, disconnect, and reconnect at any
time; the server owns pause state and re-sends a full init snapshot on every
connect.

Backpressure isolation (R02): each client gets a bounded queue drained by its
own sender task. broadcast() only enqueues (never awaits a network write), so
a slow or stalled browser can never block the simulation tick loop — when a
client's queue overflows, its oldest frames are dropped (the next tick frame
supersedes them anyway); a client that stays stalled is eventually
disconnected by uvicorn's keepalive, which cancels its sender task here.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

import structlog
from fastapi import WebSocket

from townsim.kernel.events import Event
from townsim.kernel.kernel import Kernel

log = structlog.get_logger(__name__)

QUEUE_SIZE = 64


@dataclass
class _Client:
    ws: WebSocket
    queue: asyncio.Queue
    task: asyncio.Task


class WsHub:
    def __init__(self) -> None:
        self._clients: dict[WebSocket, _Client] = {}

    # ---- lifecycle --------------------------------------------------------
    async def connect(self, ws: WebSocket, kernel: Kernel) -> None:
        await ws.accept()
        queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        client = _Client(ws=ws, queue=queue, task=asyncio.create_task(self._sender(ws, queue)))
        self._clients[ws] = client
        self._enqueue(client, json.dumps(self.init_payload(kernel), ensure_ascii=False))

    async def disconnect(self, ws: WebSocket) -> None:
        client = self._clients.pop(ws, None)
        if client is not None:
            client.task.cancel()

    async def _sender(self, ws: WebSocket, queue: asyncio.Queue) -> None:
        try:
            while True:
                payload = await queue.get()
                await ws.send_text(payload)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Socket died mid-send: unregister; the endpoint's finally block
            # also calls disconnect, which is idempotent.
            self._clients.pop(ws, None)

    def _enqueue(self, client: _Client, payload: str) -> None:
        while True:
            try:
                client.queue.put_nowait(payload)
                return
            except asyncio.QueueFull:
                try:
                    client.queue.get_nowait()   # drop oldest frame
                except asyncio.QueueEmpty:
                    pass

    # ---- payloads ---------------------------------------------------------
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
        """Enqueue only — never blocks on any client's socket (R02)."""
        if not self._clients:
            return
        payloads = [json.dumps(m, ensure_ascii=False) for m in messages]
        for client in list(self._clients.values()):
            for payload in payloads:
                self._enqueue(client, payload)
