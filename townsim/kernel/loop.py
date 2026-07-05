"""Fixed-timestep async run loop (F41): wall-clock pacing never affects sim
time, and ticks_per_second=0 runs headless flat-out for experiments."""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable

import structlog

from townsim.kernel.kernel import Kernel

log = structlog.get_logger(__name__)

TickCallback = Callable[[Kernel, list], Awaitable[None]]


async def run_kernel(kernel: Kernel, *, max_days: int | None = None,
                     on_tick: TickCallback | None = None,
                     stop_event: asyncio.Event | None = None) -> None:
    tps = kernel.cfg.kernel.ticks_per_second
    budget = (1.0 / tps) if tps > 0 else 0.0
    ticks_done = 0
    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            if kernel.paused:
                await asyncio.sleep(0.1)
                continue
            started = time.perf_counter()
            events = kernel.step()
            ticks_done += 1
            # Strict determinism: settle all narrative work at the rollover
            # tick so cognition results land at a reproducible sim time.
            if (kernel.cfg.kernel.strict_narrative_sync and kernel.narrative is not None
                    and any(e.type == "day_started" for e in events)):
                await kernel.narrative.drain()
                events = events + kernel.flush_intents()
            if on_tick is not None:
                await on_tick(kernel, events)
            # Stop only after stepping the first tick OF the boundary day, so
            # the rollover (which enqueues the final day's diaries/story)
            # always executes before we stop.
            if max_days is not None and kernel.clock.at(kernel.tick - 1).day_index >= max_days:
                log.info("run complete", days=max_days, ticks=kernel.tick)
                break
            if budget:
                elapsed = time.perf_counter() - started
                await asyncio.sleep(max(0.0, budget - elapsed))
            elif ticks_done % 500 == 0:
                await asyncio.sleep(0)  # yield so cognition workers can run
    finally:
        if kernel.narrative is not None:
            await kernel.narrative.drain()
            events = kernel.flush_intents()  # last day's diaries/story land in the journal
            if on_tick is not None and events:
                await on_tick(kernel, events)
        kernel.close()
