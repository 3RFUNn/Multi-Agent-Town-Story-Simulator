"""World domain: the navigation grid, places, and the composite world state.

``WorldState`` is the projection target: it is rebuilt deterministically by
replaying events, and its :meth:`WorldState.to_canonical` feeds the per-tick
``state_hash``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .agent import Agent

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# Tile that is never traversable (grass / out-of-bounds border in the prototype).
WALL_TILE = "G"


@dataclass(frozen=True)
class Place:
    """A named location: a class/kind plus the tile coordinates it occupies."""

    name: str
    kind: str
    coords: Tuple[Tuple[int, int], ...]

    def contains(self, x: int, y: int) -> bool:
        return (x, y) in self.coords

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "coords": [list(c) for c in self.coords]}


class NavGrid:
    """Immutable tile grid with O(1) traversability checks.

    The grid is static for the lifetime of a run, which is what makes
    precomputed flow-field pathfinding (see :mod:`matss.pathfinding`) sound.
    """

    __slots__ = ("_layout", "rows", "cols", "_wall")

    def __init__(self, layout: Iterable[Iterable[str]], wall_tile: str = WALL_TILE) -> None:
        self._layout: Tuple[Tuple[str, ...], ...] = tuple(tuple(row) for row in layout)
        self.rows = len(self._layout)
        self.cols = len(self._layout[0]) if self.rows else 0
        self._wall = wall_tile

    def tile(self, x: int, y: int) -> Optional[str]:
        if 0 <= y < self.rows and 0 <= x < self.cols:
            return self._layout[y][x]
        return None

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.cols and 0 <= y < self.rows

    def is_traversable(self, x: int, y: int) -> bool:
        t = self.tile(x, y)
        return t is not None and t != self._wall

    def neighbors4(self, x: int, y: int) -> List[Tuple[int, int]]:
        out = []
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nx, ny = x + dx, y + dy
            if self.is_traversable(nx, ny):
                out.append((nx, ny))
        return out

    def to_canonical(self) -> Dict[str, Any]:
        # The grid is static; hashing its dimensions + a digest-friendly form is
        # enough to bind a run to its map without bloating every tick hash.
        return {"rows": self.rows, "cols": self.cols, "wall": self._wall,
                "layout": ["".join(r) for r in self._layout]}


@dataclass
class WorldState:
    """The full mutable world: clock, calendar, agents, places, activities, grid."""

    nav: NavGrid
    places: Dict[str, Place]
    activity_data: Dict[str, Dict[str, Any]]
    agents: Dict[str, Agent] = field(default_factory=dict)
    time: Tuple[int, int] = (8, 0)  # (hour, minute)
    day_index: int = 0
    tick: int = 0
    sim_minute: int = 0

    @property
    def hour(self) -> int:
        return self.time[0]

    @property
    def minute(self) -> int:
        return self.time[1]

    @property
    def day_of_week(self) -> str:
        return DAYS[self.day_index % 7]

    def agent_list(self) -> List[Agent]:
        """Agents in a STABLE, id-sorted order (never rely on dict insertion)."""
        return [self.agents[k] for k in sorted(self.agents)]

    def occupied_positions(self, exclude: Optional[str] = None) -> set:
        return {a.pos for a in self.agents.values() if a.id != exclude}

    def to_canonical(self) -> Dict[str, Any]:
        return {
            "time": list(self.time),
            "day_index": self.day_index,
            "day_of_week": self.day_of_week,
            "tick": self.tick,
            "sim_minute": self.sim_minute,
            # id-sorted for order independence.
            "agents": {aid: self.agents[aid].to_canonical() for aid in sorted(self.agents)},
        }
