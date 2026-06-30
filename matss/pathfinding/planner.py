"""High-level path planning: A* for dynamic paths, flow-fields for shared goals.

:class:`PathPlanner` is the single entry point the simulation uses for movement.
It picks the right strategy:

* :meth:`PathPlanner.plan` — one-off A* search honouring per-tick ``blocked``
  cells, for ad-hoc navigation toward an arbitrary, possibly-contested tile.
* :meth:`PathPlanner.flow_to` — cached flow-field routing toward shared,
  well-known destinations (cafe, office, home), amortising the search across
  every agent and tick that targets the same place.
"""

from __future__ import annotations

from typing import FrozenSet, Iterable, List, Optional, Set, Tuple

from ..domain.world import NavGrid
from .astar import astar, manhattan
from .flowfield import FlowFieldCache

Coord = Tuple[int, int]


class PathPlanner:
    """Routes agents over a static grid using A* or cached flow-fields."""

    __slots__ = ("nav", "_flow_cache")

    def __init__(self, nav: NavGrid) -> None:
        """Bind the planner to a static navigation grid.

        Args:
            nav: The static grid all planning is performed against.
        """
        self.nav = nav
        self._flow_cache = FlowFieldCache(nav)

    def plan(
        self,
        start: Coord,
        goal: Coord,
        blocked: FrozenSet[Coord] = frozenset(),
    ) -> Optional[List[Coord]]:
        """Plan a one-off path with A*, avoiding transiently ``blocked`` cells.

        Args:
            start: The origin cell ``(x, y)``.
            goal: The destination cell ``(x, y)``.
            blocked: Cells to route around (the goal itself stays reachable).

        Returns:
            The path ``[start, ..., goal]`` or ``None`` if unreachable.
        """
        return astar(self.nav, start, goal, blocked)

    def flow_to(
        self,
        start: Coord,
        goal_coords: Iterable[Coord],
        max_len: int = 10_000,
    ) -> Optional[List[Coord]]:
        """Route toward shared destination(s) using the cached flow field.

        The flow field ignores dynamic blockers (it is built over the static
        grid), so this is the cheap path for uncontested, well-known goals.

        Args:
            start: The origin cell ``(x, y)``.
            goal_coords: One or more destination cells (order-independent).
            max_len: Safety bound passed to :meth:`FlowField.full_path`.

        Returns:
            The path ``[start, ..., goal]`` or ``None`` if no goal is reachable.
        """
        field = self._flow_cache.get(goal_coords)
        return field.full_path(start, max_len=max_len)

    def nearest_free(
        self,
        target: Coord,
        occupied: Set[Coord],
    ) -> Optional[Coord]:
        """Find the closest traversable, unoccupied cell to ``target``.

        Useful for placing an agent *near* a contested destination tile. The
        search expands outward by Manhattan rings; ties are broken by the fixed
        :meth:`NavGrid.neighbors4` ordering, so the result is deterministic.

        Args:
            target: The ideal cell ``(x, y)``.
            occupied: Cells that are taken and must be avoided.

        Returns:
            ``target`` itself if it is free, else the nearest free traversable
            cell, or ``None`` if no traversable cell is reachable.
        """
        if self.nav.is_traversable(*target) and target not in occupied:
            return target

        seen: Set[Coord] = {target}
        frontier: List[Coord] = [target]
        # Bound the search to the whole grid; it terminates when frontier empties.
        while frontier:
            # Sort the frontier for deterministic, distance-then-coordinate order.
            frontier.sort(key=lambda c: (manhattan(c, target), c))
            cur = frontier.pop(0)
            for nbr in self.nav.neighbors4(*cur):
                if nbr in seen:
                    continue
                seen.add(nbr)
                if nbr not in occupied:
                    return nbr
                frontier.append(nbr)
        return None
