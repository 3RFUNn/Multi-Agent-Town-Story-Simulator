"""Transport adapters that subscribe to the simulation event bus.

These adapters consume :class:`~matss.domain.events.Event` objects published by
the engine and forward them to a UI/console. They never import the engine, and
the engine never imports them — the only link is the :class:`~matss.ports.EventBus`.
That decoupling is the structural fix for the prototype's ``manager -> app``
import cycle.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..domain.enums import EventType
from ..domain.events import Event
from ..observability import get_logger

_log = get_logger("gateway")


class ConsoleSink:
    """A headless sink that logs notable events (day rollovers, stories).

    Subscribe with ``bus.subscribe(ConsoleSink().handle)``.
    """

    NOTABLE = frozenset({
        EventType.SIM_STARTED, EventType.DAY_ROLLOVER,
        EventType.STORY_COMPILED, EventType.NUDGE_APPLIED,
    })

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose

    def handle(self, event: Event) -> None:
        if self.verbose or event.type in self.NOTABLE:
            _log.info("event", type=event.type, tick=event.tick,
                      day=event.day_of_week, agent=event.agent_id)


class SnapshotBroadcaster:
    """Maintains the latest client-facing view from the event stream.

    Merges static agent definition fields (name/icon/color/personality, from
    content) with the per-tick dynamic snapshot carried by ``TICK_COMPLETED``
    events, and collects daily stories from ``STORY_COMPILED`` events.
    """

    def __init__(self, content) -> None:
        self._defs = {d.id: d for d in content.agent_defs}
        self._latest_state: Optional[Dict[str, Any]] = None
        self._daily_stories: List[Dict[str, Any]] = []
        self._listeners: List[Any] = []

    def on_state(self, callback) -> None:
        """Register a callback invoked with each new client state payload."""
        self._listeners.append(("state", callback))

    def on_story(self, callback) -> None:
        self._listeners.append(("story", callback))

    def handle(self, event: Event) -> None:
        if event.type == EventType.TICK_COMPLETED:
            self._latest_state = self._build_state(event.payload.get("snapshot", {}))
            self._emit("state", self._latest_state)
        elif event.type == EventType.STORY_COMPILED:
            story = {
                "day": f"Day {event.payload.get('day_number')} ({event.payload.get('day')})",
                "text": event.payload.get("text", ""),
            }
            self._daily_stories.append(story)
            self._emit("story", story)

    def latest_state(self) -> Optional[Dict[str, Any]]:
        return self._latest_state

    def daily_stories(self) -> List[Dict[str, Any]]:
        return list(self._daily_stories)

    # --- internals ------------------------------------------------------------

    def _build_state(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        agents_canon = snapshot.get("agents", {})
        agents = []
        for aid, a in agents_canon.items():
            d = self._defs.get(aid)
            view = dict(a)
            if d is not None:
                view.update({"name": d.name, "icon": d.icon, "color": d.color,
                             "personality": list(d.personality)})
            agents.append(view)
        return {
            "agents": agents,
            "time": snapshot.get("time"),
            "day_of_week": snapshot.get("day_of_week"),
            "tick": snapshot.get("tick"),
        }

    def _emit(self, kind: str, payload: Any) -> None:
        for k, cb in self._listeners:
            if k == kind:
                try:
                    cb(payload)
                except Exception:  # pragma: no cover - listener isolation
                    _log.warning("listener_error", kind=kind)


class WebGateway:
    """Optional Flask + SocketIO web gateway (lazy-imported).

    Serves the existing ``static/`` frontend and pushes ``simulation_state_update``
    / ``new_daily_story`` messages — the same protocol the legacy client speaks —
    but now as a pure bus subscriber rather than an imported dependency of the sim.
    """

    def __init__(self, content, static_folder: str = "static", host: str = "0.0.0.0",
                 port: int = 5000) -> None:
        self.content = content
        self.static_folder = static_folder
        self.host = host
        self.port = port
        self.broadcaster = SnapshotBroadcaster(content)
        self._app = None
        self._socketio = None

    def _build(self):  # pragma: no cover - requires flask extra
        from flask import Flask, send_from_directory
        from flask_socketio import SocketIO

        app = Flask(__name__, static_folder=None)
        socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

        @app.route("/")
        def index():
            return send_from_directory(self.static_folder, "index.html")

        @app.route("/<path:filename>")
        def static_files(filename):
            return send_from_directory(self.static_folder, filename)

        self.broadcaster.on_state(lambda s: socketio.emit("simulation_state_update", s))
        self.broadcaster.on_story(lambda s: socketio.emit("new_daily_story", s))

        self._app, self._socketio = app, socketio
        return app, socketio

    def subscribe_to(self, bus) -> None:
        """Wire this gateway as a subscriber of the simulation event bus."""
        bus.subscribe(self.broadcaster.handle)

    def run(self):  # pragma: no cover - requires flask extra + a server
        app, socketio = self._build()
        socketio.run(app, host=self.host, port=self.port, allow_unsafe_werkzeug=True)
