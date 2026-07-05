"""A* pathfinding on the town grid (F30).

- heapq frontier with Manhattan heuristic and parent-pointer reconstruction
  (no per-node path copies, no list.pop(0)).
- The returned path EXCLUDES the start cell, so following it never wastes a
  tick re-entering the current position.
- Static obstacles only (grass); dynamic agent collisions are resolved at
  step time by the movement system, which avoids V1's walking-toward-each-
  other livelocks by design.
"""
from __future__ import annotations

import heapq

from townsim.world.grid import TownMap

Coord = tuple[int, int]
_DIRECTIONS = ((0, 1), (0, -1), (1, 0), (-1, 0))


def astar(town: TownMap, start: Coord, goal: Coord,
          blocked: frozenset[Coord] = frozenset()) -> list[Coord] | None:
    """Shortest 4-connected path start -> goal. `blocked` cells are avoided
    except the goal itself. Returns waypoints excluding `start`, or None."""
    if start == goal:
        return []
    if not town.walkable(*goal):
        return None

    def h(c: Coord) -> int:
        return abs(c[0] - goal[0]) + abs(c[1] - goal[1])

    frontier: list[tuple[int, int, Coord]] = [(h(start), 0, start)]
    came_from: dict[Coord, Coord] = {}
    g_score: dict[Coord, int] = {start: 0}

    while frontier:
        _, g, current = heapq.heappop(frontier)
        if current == goal:
            path: list[Coord] = []
            while current != start:
                path.append(current)
                current = came_from[current]
            path.reverse()
            return path
        if g > g_score.get(current, g):
            continue  # stale entry
        for dx, dy in _DIRECTIONS:
            nxt = (current[0] + dx, current[1] + dy)
            if not town.walkable(*nxt):
                continue
            if nxt in blocked and nxt != goal:
                continue
            tentative = g + 1
            if tentative < g_score.get(nxt, 1 << 30):
                g_score[nxt] = tentative
                came_from[nxt] = current
                heapq.heappush(frontier, (tentative + h(nxt), tentative, nxt))
    return None
