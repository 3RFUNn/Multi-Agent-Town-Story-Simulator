"""Append-only run journal (F24, F42).

Each run gets its own directory under runs/ (never overwrites a previous
run). The journal is JSONL: one header line, then one line per event. The
determinism hash covers behavioral events only, so two runs with the same
seed and a deterministic provider produce identical hashes (golden replay).
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from townsim.kernel.events import BEHAVIORAL, Event


class Journal:
    def __init__(self, run_dir: Path, seed: int, config_summary: dict | None = None) -> None:
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.path = run_dir / "journal.jsonl"
        self._hash = hashlib.sha256()
        self._file = open(self.path, "a", encoding="utf-8", newline="\n")
        header = {
            "header": True, "version": 2, "seed": seed,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "config": config_summary or {},
        }
        self._file.write(json.dumps(header, ensure_ascii=False) + "\n")
        self._file.flush()

    def append(self, event: Event) -> None:
        line = json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True)
        self._file.write(line + "\n")
        if event.type in BEHAVIORAL:
            self._hash.update(line.encode("utf-8"))

    def extend(self, events: list[Event]) -> None:
        for event in events:
            self.append(event)
        self._file.flush()

    def determinism_hash(self) -> str:
        return self._hash.hexdigest()

    def close(self) -> None:
        if not self._file.closed:
            self._file.flush()
            self._file.close()


def new_run_dir(runs_root: Path, seed: int) -> Path:
    """Timestamped, collision-safe run directory (F24)."""
    runs_root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = runs_root / f"run_{stamp}_seed{seed}"
    candidate, n = base, 1
    while candidate.exists():
        candidate = Path(f"{base}_{n}")
        n += 1
    candidate.mkdir(parents=True)
    return candidate


def read_journal(path: Path) -> tuple[dict, list[dict]]:
    """Load a journal file -> (header, events)."""
    header: dict = {}
    events: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if i == 0 and record.get("header"):
                header = record
            else:
                events.append(record)
    return header, events
