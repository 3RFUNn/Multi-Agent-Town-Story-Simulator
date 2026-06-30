"""Replay + reproducibility verification entrypoint (``matss-replay``).

Reads a persisted JSONL event log and:

* validates the internal ``state_hash`` chain;
* reconstructs the final world snapshot from the log (CQRS projection);
* optionally re-runs the engine from a given seed and asserts the freshly
  produced chain is byte-identical to the logged one — the reproducibility
  certificate that pure-LLM agent simulations cannot offer.

Examples::

    python -m matss.app.replay --jsonl run.jsonl
    python -m matss.app.replay --jsonl run.jsonl --verify-seed 42
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from ..eventlog import JsonlEventLog, reconstruct_world_canonical, replay_state_hashes
from ..sim import build_engine


def replay(jsonl_path: str, verify_seed: Optional[int] = None) -> int:
    log = JsonlEventLog(jsonl_path)
    events = list(log.read())
    hashes = replay_state_hashes(events)
    final = reconstruct_world_canonical(events)

    print("=" * 64)
    print("MATSS v2 — event-log replay")
    print("=" * 64)
    print(f"log:                {jsonl_path}")
    print(f"events:             {len(events)}")
    print(f"state-hash chain:   {len(hashes)} ticks")
    print(f"final state_hash:   {hashes[-1] if hashes else '(none)'}")
    if final is not None:
        print(f"final sim time:     {final.get('day_of_week')} {tuple(final.get('time', []))}")
        print(f"agents:             {len(final.get('agents', {}))}")

    if verify_seed is not None:
        ticks = len(hashes) - 1  # minus the initial baseline frame
        engine = build_engine(seed=verify_seed)
        fresh = engine.run(max(0, ticks))
        match = fresh == hashes
        print("-" * 64)
        print(f"re-run seed={verify_seed} ticks={ticks}: "
              f"chain {'MATCHES' if match else 'DIFFERS'} the logged run")
        print("=" * 64)
        return 0 if match else 1

    print("=" * 64)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Replay and verify a MATSS event log.")
    p.add_argument("--jsonl", type=str, required=True, help="path to a JSONL event log")
    p.add_argument("--verify-seed", type=int, default=None,
                   help="re-run this seed and assert an identical state-hash chain")
    args = p.parse_args(argv)
    return replay(args.jsonl, verify_seed=args.verify_seed)


if __name__ == "__main__":
    sys.exit(main())
