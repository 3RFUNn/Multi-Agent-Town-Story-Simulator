"""Uniform-grid spatial hash for O(1) proximity queries.

Replaces V1's per-agent linear scans (O(n^2) per tick across agents) so the
sim scales to hundreds of agents.
"""
from __future__ import annotations

from collections import defaultdict

Coord = tuple[int, int]


class SpatialHash:
    def __init__(self, cell_size: int = 4) -> None:
        self.cell_size = cell_size
        self._buckets: dict[Coord, set[str]] = defaultdict(set)
        self._positions: dict[str, Coord] = {}

    def _bucket(self, pos: Coord) -> Coord:
        return (pos[0] // self.cell_size, pos[1] // self.cell_size)

    def upsert(self, entity_id: str, pos: Coord) -> None:
        old = self._positions.get(entity_id)
        if old == pos:
            return
        if old is not None:
            self._buckets[self._bucket(old)].discard(entity_id)
        self._buckets[self._bucket(pos)].add(entity_id)
        self._positions[entity_id] = pos

    def remove(self, entity_id: str) -> None:
        old = self._positions.pop(entity_id, None)
        if old is not None:
            self._buckets[self._bucket(old)].discard(entity_id)

    def position_of(self, entity_id: str) -> Coord | None:
        return self._positions.get(entity_id)

    def neighbors_within(self, pos: Coord, radius: int, *, exclude: str | None = None) -> list[str]:
        """Entities with Chebyshev distance <= radius from pos."""
        bx, by = self._bucket(pos)
        reach = radius // self.cell_size + 1
        found: list[str] = []
        for gx in range(bx - reach, bx + reach + 1):
            for gy in range(by - reach, by + reach + 1):
                for entity_id in self._buckets.get((gx, gy), ()):
                    if entity_id == exclude:
                        continue
                    ex, ey = self._positions[entity_id]
                    if max(abs(ex - pos[0]), abs(ey - pos[1])) <= radius:
                        found.append(entity_id)
        found.sort()  # deterministic order regardless of set iteration
        return found

    def occupied(self) -> set[Coord]:
        return set(self._positions.values())
