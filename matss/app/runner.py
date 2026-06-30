"""Headless deterministic run entrypoint (``matss-run``).

Runs the simulation fully offline (mock LLM, in-memory log) and prints a
reproducibility summary. Optionally persists the event log to JSONL and/or serves
the legacy web frontend via the Flask gateway.

Examples::

    python -m matss.app.runner --seed 42 --days 2
    python -m matss.app.runner --seed 42 --ticks 600 --jsonl run.jsonl
    python -m matss.app.runner --seed 42 --days 3 --web      # requires .[web]
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from ..domain.enums import EventType
from ..eventlog import InMemoryEventLog, InProcessEventBus, JsonlEventLog
from ..observability import configure_logging
from ..sim import build_engine
from .gateway import ConsoleSink, WebGateway


def _count(log, event_type: str) -> int:
    return sum(1 for ev in log.read() if ev.type == event_type)


def run(seed: int = 42, ticks: Optional[int] = None, days: Optional[int] = None,
        jsonl: Optional[str] = None, hierarchical: bool = False,
        web: bool = False, verbose: bool = False) -> int:
    configure_logging()
    bus = InProcessEventBus()
    log = JsonlEventLog(jsonl) if jsonl else InMemoryEventLog()

    engine = build_engine(seed=seed, event_log=log, event_bus=bus,
                          hierarchical_narrative=hierarchical)

    bus.subscribe(ConsoleSink(verbose=verbose).handle)

    gateway: Optional[WebGateway] = None
    if web:  # pragma: no cover - requires flask + a running server
        gateway = WebGateway(engine.content)
        gateway.subscribe_to(bus)

    engine.start()

    if web:  # pragma: no cover
        import threading
        target_days = days if days is not None else 10_000
        threading.Thread(target=engine.run_until_day, args=(target_days,), daemon=True).start()
        print(f"Serving web gateway on http://localhost:5000 (seed={seed}) ...")
        gateway.run()
        return 0

    if days is not None:
        engine.run_until_day(days)
    else:
        engine.run(ticks if ticks is not None else 600)

    hashes: List[str] = engine.state_hashes
    print("=" * 64)
    print("MATSS v2 — headless run complete")
    print("=" * 64)
    print(f"seed:               {seed}")
    print(f"ticks:              {engine.world.tick}")
    print(f"sim time:           day {engine.world.day_index} ({engine.world.day_of_week}) "
          f"{engine.world.time[0]:02d}:{engine.world.time[1]:02d}")
    print(f"events logged:      {len(log)}")
    print(f"  agent_moved:      {_count(log, EventType.AGENT_MOVED)}")
    print(f"  activities:       {_count(log, EventType.ACTIVITY_STARTED)}")
    print(f"  interactions:     {_count(log, EventType.INTERACTION_STARTED)}")
    print(f"  diaries:          {_count(log, EventType.DIARY_WRITTEN)}")
    print(f"  town stories:     {_count(log, EventType.STORY_COMPILED)}")
    print(f"state-hash chain:   {len(hashes)} hashes")
    print(f"final state_hash:   {hashes[-1] if hashes else '(none)'}")
    if jsonl:
        print(f"event log written:  {jsonl}")
    print("=" * 64)
    print("Reproducibility: re-run with the same --seed to reproduce this exact")
    print("final state_hash. Verify a persisted log with: python -m matss.app.replay")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Run the MATSS v2 simulation (headless/offline).")
    p.add_argument("--seed", type=int, default=42)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--ticks", type=int, help="number of ticks to run")
    g.add_argument("--days", type=int, help="run until this simulated day index")
    p.add_argument("--jsonl", type=str, help="persist the event log to this JSONL path")
    p.add_argument("--hierarchical", action="store_true", help="agent->group->town narration")
    p.add_argument("--web", action="store_true", help="serve the web gateway (needs .[web])")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)
    if args.ticks is None and args.days is None:
        args.days = 2
    return run(seed=args.seed, ticks=args.ticks, days=args.days, jsonl=args.jsonl,
               hierarchical=args.hierarchical, web=args.web, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
