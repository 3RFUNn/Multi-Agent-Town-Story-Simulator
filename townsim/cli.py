"""Command-line entry points.

  python -m townsim serve                 # dashboard + live simulation
  python -m townsim run --days 3 --fast   # headless run (great with provider=fake)
  python -m townsim replay <journal.jsonl>  # summarize a recorded run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import Counter
from pathlib import Path

import structlog

from townsim.config.models import SimConfig, load_config


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stdout)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level),
        processors=[
            structlog.processors.TimeStamper(fmt="%H:%M:%S"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(colors=False),
        ],
    )


def _apply_overrides(cfg: SimConfig, args) -> SimConfig:
    if getattr(args, "seed", None) is not None:
        cfg.kernel.seed = args.seed
    if getattr(args, "fast", False):
        cfg.kernel.ticks_per_second = 0
    if getattr(args, "provider", None):
        cfg.llm.provider = args.provider
    if getattr(args, "strict", None) is not None:
        cfg.kernel.strict_narrative_sync = args.strict
    return cfg


def cmd_serve(args) -> int:
    import uvicorn

    from townsim.server.app import create_app

    cfg = _apply_overrides(load_config(args.config), args)
    app = create_app(cfg)
    uvicorn.run(app, host=cfg.server.host, port=cfg.server.port, log_level="warning")
    return 0


def cmd_run(args) -> int:
    from townsim.cognition.narrative import NarrativeCoordinator
    from townsim.kernel.kernel import Kernel
    from townsim.kernel.loop import run_kernel
    from townsim.llm.gateway import LLMGateway, SemanticCache
    from townsim.llm.providers import build_provider
    from townsim.llm.templates import PromptLibrary

    cfg = _apply_overrides(load_config(args.config), args)
    log = structlog.get_logger("run")

    async def main() -> Kernel:
        provider = build_provider(cfg.llm)
        gateway = LLMGateway(provider, max_concurrency=cfg.llm.max_concurrency,
                             max_attempts=cfg.llm.max_attempts,
                             retry_max_wait_s=cfg.llm.retry_max_wait_s,
                             requests_per_minute=cfg.llm.requests_per_minute,
                             cache=SemanticCache(cfg.llm.semantic_cache_threshold))
        narrative = NarrativeCoordinator(gateway, PromptLibrary(cfg.paths.prompts_dir), cfg)
        kernel = Kernel(cfg, narrative=narrative)
        log.info("headless run", days=args.days, seed=cfg.kernel.seed,
                 provider=provider.name, run_dir=str(kernel.run_dir))
        narrative.start()
        try:
            await run_kernel(kernel, max_days=args.days)
        finally:
            await narrative.stop()
        log.info("done", ticks=kernel.tick, stories=len(kernel.world.stories),
                 determinism_hash=kernel.journal.determinism_hash(),
                 gateway=gateway.stats)
        return kernel

    kernel = asyncio.run(main())
    print(f"\nRun directory: {kernel.run_dir}")
    print(f"Stories written: {len(kernel.world.stories)}")
    print(f"Determinism hash: {kernel.journal.determinism_hash()}")
    return 0


def cmd_replay(args) -> int:
    from townsim.kernel.journal import read_journal

    header, events = read_journal(Path(args.journal))
    counts = Counter(e["type"] for e in events)
    print(f"Journal: {args.journal}")
    print(f"Seed: {header.get('seed')}  created: {header.get('created_at')}")
    print(f"Events: {len(events)}")
    for event_type, count in counts.most_common():
        print(f"  {event_type:>26}: {count}")
    days = {e["day"] for e in events}
    print(f"Days covered: {min(days)}..{max(days)}" if days else "empty journal")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="townsim", description=__doc__)
    parser.add_argument("--config", default=None, help="path to a YAML config file")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="run the simulation with the web dashboard")
    p_serve.add_argument("--seed", type=int, default=None)
    p_serve.add_argument("--provider", choices=["auto", "openai", "openrouter", "fake"], default=None)
    p_serve.set_defaults(func=cmd_serve)

    p_run = sub.add_parser("run", help="headless simulation run")
    p_run.add_argument("--days", type=int, default=1)
    p_run.add_argument("--seed", type=int, default=None)
    p_run.add_argument("--fast", action="store_true", help="no wall-clock pacing")
    p_run.add_argument("--provider", choices=["auto", "openai", "openrouter", "fake"], default=None)
    p_run.add_argument("--strict", dest="strict", action="store_true", default=True,
                       help="settle narrative at day rollovers for bit-exact replays (default)")
    p_run.add_argument("--no-strict", dest="strict", action="store_false")
    p_run.set_defaults(func=cmd_run)

    p_replay = sub.add_parser("replay", help="summarize a recorded journal")
    p_replay.add_argument("journal")
    p_replay.set_defaults(func=cmd_replay)

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
