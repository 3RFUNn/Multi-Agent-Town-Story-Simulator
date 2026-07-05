"""Seeded RNG registry (F23).

Each subsystem draws from its own named stream so that adding randomness in
one system never perturbs another system's sequence — keeping replays stable
across unrelated code changes.
"""
from __future__ import annotations

import random
import zlib


class RngRegistry:
    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._streams: dict[str, random.Random] = {}

    def stream(self, name: str) -> random.Random:
        if name not in self._streams:
            derived = zlib.crc32(name.encode()) ^ (self.seed & 0xFFFFFFFF)
            self._streams[name] = random.Random(derived)
        return self._streams[name]
