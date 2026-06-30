"""Precomputed flow-fields for shared destinations on the static nav grid.

Many agents converge on a handful of well-known destinations (the cafe, the
office, home). Running A* per-agent per-tick toward those shared goals is
wasteful. Instead we compute, once per goal-set, a Dijkstra/BFS *flow field* over
the static grid: a distance-to-goal value for every reachable cell plus a
``next_step`` pointer that always moves one tile closer to the nearest goal.
Following the pointers from any start yields a shortest path "for free", and the
field is reused across every agent and tick that shares the destination.

Because the grid is static, the field ignores dynamic (per-tick) blockers; a
caller that needs to route *around* transient obstacles should fall back to
:func:`matss.pathfinding.astar.astar` instead.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, Iterable, List, Optional, Tuple

from ..domain.world import NavGrid

Coord = Tuple[int, int]


class FlowField:
    """A distance field + next-step map flowing toward one or more goal cells.

    The BFS expands outward from every goal simultaneously (multi-source), so each
    cell's ``next_step`` heads toward whichever goal is nearest. Neighbour
    iteration order is fixed by :meth:`NavGrid.neighbors4`, making the resulting
    field deterministic.
    """

    __slots__ = ("nav", "goals", "_dist", "_next")

    def __init__(self, nav: NavGrid, goals: Iterable[Coord]) -> None:
        """Build the field by BFS outward from the (traversable) goal cells.

        Args:
            nav: The static navigation grid.
            goals: The destination cells. Untraversable goals are skipped.
        """
        self.nav = nav
        self.goals: Tuple[Coord, ...] = tuple(goals)
        self._dist: Dict[Coord, int] = {}
        self._next: Dict[Coord, Optional[Coord]] = {}
        self._build()

    def _build(self) -> None:
        queue: deque[Coord] = deque()
        for g in self.goals:
            if self.nav.is_traversable(*g) and g not in self._dist:
                self._dist[g] = 0
                self._next[g] = None  # a goal cell is its own terminus
                queue.append(g)

        while queue:
            cur = queue.popleft()
            cur_d = self._dist[cur]
            for nbr in self.nav.neighbors4(*cur):
                if nbr not in self._dist:
                    self._dist[nbr] = cur_d + 1
                    # Step from ``nbr`` back toward the goal we just came from.
                    self._next[nbr] = cur
                    queue.append(nbr)

    def distance(self, pos: Coord) -> Optional[int]:
        """Return the shortest distance from ``pos`` to the nearest goal.

        Args:
            pos: The query cell ``(x, y)``.

        Returns:
            The number of steps to the nearest goal, ``0`` if ``pos`` is a goal,
            or ``None`` if ``pos`` cannot reach any goal.
        """
        return self._dist.get(pos)

    def reaches(self, pos: Coord) -> bool:
        """Return whether ``pos`` can reach any goal via the static grid."""
        return pos in self._dist

    def next_step(self, pos: Coord) -> Optional[Coord]:
        """Return the next cell on a shortest path from ``pos`` toward a goal.

        Args:
            pos: The current cell ``(x, y)``.

        Returns:
            The adjacent cell one step closer to the nearest goal, or ``None`` if
            ``pos`` is already a goal or cannot reach any goal.
        """
        return self._next.get(pos)

    def full_path(self, start: Coord, max_len: int = 10_000) -> Optional[List[Coord]]:
        """Follow ``next_step`` pointers to build the full path to the goal.

        Args:
            start: The origin cell ``(x, y)``.
            max_len: A safety bound on the number of cells in the returned path
                (the static field is acyclic, so this only guards pathological
                misuse).

        Returns:
            The path ``[start, ..., goal]`` as a list of cells, or ``None`` if
            ``start`` cannot reach any goal.
        """
        if start not in self._dist:
            return None
        path: List[Coord] = [start]
        cur = start
        while self._next.get(cur) is not None and len(path) < max_len:
            cur = self._next[cur]  # type: ignore[assignment]
            path.append(cur)
        return path


class FlowFieldCache:
    """Memoises one :class:`FlowField` per goal-set so lookups are O(1) on reuse.

    The cache key is the sorted tuple of goal coordinates, so callers that pass
    the same destinations in a different order share a single field. Repeated
    :meth:`get` calls for the same goals return the *identical* object.
    """

    __slots__ = ("nav", "_cache")

    def __init__(self, nav: NavGrid) -> None:
        """Create an empty cache bound to a static grid.

        Args:
            nav: The static navigation grid all cached fields are built over.
        """
        self.nav = nav
        self._cache: Dict[Tuple[Coord, ...], FlowField] = {}

    @staticmethod
    def _key(goals: Iterable[Coord]) -> Tuple[Coord, ...]:
        """Normalise a goal-set into an order-independent cache key."""
        return tuple(sorted(set(goals)))

    def get(self, goals: Iterable[Coord]) -> FlowField:
        """Return the (memoised) flow field for ``goals``, building it if absent.

        Args:
            goals: The destination cell(s). Order and duplicates do not matter.

        Returns:
            The cached :class:`FlowField`; the same instance on repeat calls.
        """
        key = self._key(goals)
        field = self._cache.get(key)
        if field is None:
            field = FlowField(self.nav, key)
            self._cache[key] = field
        return field

    def clear(self) -> None:
        """Drop all cached fields (e.g. if the grid is swapped)."""
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)
