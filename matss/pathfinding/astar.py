"""A* shortest-path search over the static :class:`~matss.domain.world.NavGrid`.

This replaces the prototype's per-move breadth-first search (``find_path_bfs`` in
``simulation/manager.py``) for one-off, dynamic paths where a subset of cells is
transiently blocked (e.g. by other agents). The search is deterministic: ties in
the priority queue are broken by a monotonically increasing insertion counter, so
the same ``(start, goal, blocked)`` always yields byte-identical paths regardless
of platform or hash-randomisation.
"""

from __future__ import annotations

import heapq
from typing import Dict, FrozenSet, List, Optional, Tuple

from ..domain.world import NavGrid

Coord = Tuple[int, int]


def manhattan(a: Coord, b: Coord) -> int:
    """Return the 4-connected Manhattan distance between two cells.

    This is an admissible (never-overestimating) heuristic for a unit-cost,
    4-connected grid, which guarantees A* returns an optimal-length path.

    Args:
        a: The first cell as an ``(x, y)`` tuple.
        b: The second cell as an ``(x, y)`` tuple.

    Returns:
        The sum of the absolute coordinate differences.
    """
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar(
    nav: NavGrid,
    start: Coord,
    goal: Coord,
    blocked: FrozenSet[Coord] = frozenset(),
) -> Optional[List[Coord]]:
    """Find a shortest path from ``start`` to ``goal`` on the static grid.

    Movement is 4-connected via :meth:`NavGrid.neighbors4`; a neighbour is only
    expanded if it is traversable on the static grid AND not present in
    ``blocked`` — with the single exception of ``goal`` itself, which is always
    reachable even when listed as blocked (this lets a caller route an agent onto
    a target tile that is, momentarily, occupied).

    Args:
        nav: The static navigation grid to search.
        start: The origin cell ``(x, y)``.
        goal: The destination cell ``(x, y)``.
        blocked: Cells that may not be traversed (the goal is exempt).

    Returns:
        The full path ``[start, ..., goal]`` (inclusive of both endpoints) as a
        list of cells, or ``None`` if no path exists or either endpoint is
        untraversable.
    """
    if start == goal:
        if nav.is_traversable(*start):
            return [start]
        return None

    if not nav.is_traversable(*start) or not nav.is_traversable(*goal):
        return None

    # Heap entries are (f_score, tie_counter, cell). The tie counter makes the
    # ordering total and insertion-stable, so pops are fully deterministic.
    counter = 0
    open_heap: List[Tuple[int, int, Coord]] = [(manhattan(start, goal), counter, start)]
    came_from: Dict[Coord, Coord] = {}
    g_score: Dict[Coord, int] = {start: 0}
    closed: set = set()

    while open_heap:
        _, _, current = heapq.heappop(open_heap)
        if current == goal:
            return _reconstruct(came_from, current)
        if current in closed:
            continue
        closed.add(current)

        tentative_g = g_score[current] + 1
        for nbr in nav.neighbors4(*current):
            # A blocked cell is impassable unless it is the goal.
            if nbr in blocked and nbr != goal:
                continue
            if nbr in closed:
                continue
            if tentative_g < g_score.get(nbr, _INF):
                came_from[nbr] = current
                g_score[nbr] = tentative_g
                counter += 1
                f = tentative_g + manhattan(nbr, goal)
                heapq.heappush(open_heap, (f, counter, nbr))

    return None


def _reconstruct(came_from: Dict[Coord, Coord], current: Coord) -> List[Coord]:
    """Walk the ``came_from`` chain back to the start and return it forwards."""
    path: List[Coord] = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


# A sentinel larger than any real path length on a finite grid.
_INF = float("inf")
