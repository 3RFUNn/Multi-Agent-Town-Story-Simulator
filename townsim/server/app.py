"""FastAPI application: single process hosting the simulation kernel, the
cognition workers, the WebSocket hub, and the dashboard (V2 architecture —
no more two-process split, which caused V1's lost-story bug F04)."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from townsim.cognition.narrative import NarrativeCoordinator
from townsim.config.models import SimConfig
from townsim.kernel.kernel import Kernel
from townsim.kernel.loop import run_kernel
from townsim.llm.gateway import LLMGateway, SemanticCache
from townsim.llm.providers import build_provider
from townsim.llm.templates import PromptLibrary
from townsim.server.hub import WsHub

log = structlog.get_logger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


def create_app(cfg: SimConfig | None = None) -> FastAPI:
    cfg = cfg or SimConfig()

    provider = build_provider(cfg.llm)
    gateway = LLMGateway(provider, max_concurrency=cfg.llm.max_concurrency,
                         max_attempts=cfg.llm.max_attempts,
                         retry_max_wait_s=cfg.llm.retry_max_wait_s,
                         requests_per_minute=cfg.llm.requests_per_minute,
                         cache=SemanticCache(threshold=cfg.llm.semantic_cache_threshold))
    prompts = PromptLibrary(cfg.paths.prompts_dir)
    narrative = NarrativeCoordinator(gateway, prompts, cfg)
    kernel = Kernel(cfg, narrative=narrative)
    hub = WsHub()
    stop_event = asyncio.Event()

    def _observe_sim_task(task: asyncio.Task) -> None:
        """R14: a crashed simulation must be loud, not a frozen dashboard."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            log.error("SIMULATION CRASHED — dashboard is now frozen",
                      error=repr(exc), exc_info=exc)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        narrative.start()
        sim_task = asyncio.create_task(
            run_kernel(kernel, on_tick=hub.on_tick, stop_event=stop_event))
        sim_task.add_done_callback(_observe_sim_task)
        log.info("simulation started", provider=provider.name,
                 seed=cfg.kernel.seed, run_dir=str(kernel.run_dir))
        yield
        stop_event.set()
        try:
            await asyncio.wait_for(sim_task, timeout=120)
        except asyncio.TimeoutError:
            sim_task.cancel()
        except Exception:
            pass   # sim crash — already logged loudly by _observe_sim_task
        finally:
            # Teardown must run even on the crashed-sim path: the kernel's
            # creator owns the close, and a crash must still close the journal.
            await narrative.stop()
            kernel.flush_intents()   # R13: results completed during stop() still land
            kernel.close()

    app = FastAPI(title="Town Simulator V2", lifespan=lifespan)
    app.state.kernel = kernel
    app.state.hub = hub

    # ---- dashboard --------------------------------------------------------
    @app.get("/")
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # ---- REST inspection API ----------------------------------------------
    @app.get("/api/state")
    async def api_state():
        now = kernel.now()
        return {"time": now.to_dict(),
                "paused": kernel.paused,
                "seed": cfg.kernel.seed,
                "provider": provider.name,
                "gateway_stats": gateway.stats,
                "agents": [a.to_public_dict() for a in kernel.world.agents_sorted()],
                "stories": kernel.world.stories}

    @app.get("/api/agents/{agent_id}")
    async def api_agent(agent_id: str):
        agent = kernel.world.agents.get(agent_id)
        if agent is None:
            raise HTTPException(404, f"no such agent: {agent_id}")
        return {
            "agent": agent.to_public_dict(),
            "log": list(agent.recent_log),
            "relationships": {k: r.to_dict() for k, r in sorted(agent.relationships.items())},
            "diary": agent.last_diary,
            "utility_weights": agent.utility_weights,
            "memory_size": len(agent.memory.entries),
        }

    @app.get("/api/stories")
    async def api_stories():
        return {"stories": kernel.world.stories}

    # ---- WebSocket ---------------------------------------------------------
    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await hub.connect(ws, kernel)
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if message.get("type") == "pause":
                    kernel.paused = True
                    await hub.broadcast_paused(True)
                elif message.get("type") == "resume":
                    kernel.paused = False
                    await hub.broadcast_paused(False)
        except WebSocketDisconnect:
            pass
        finally:
            await hub.disconnect(ws)   # R23: no leaks on ANY exit path

    return app
