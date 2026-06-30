"""Pathfinding for MATSS v2: A* + precomputed flow-fields on the static grid.

This package replaces the prototype's per-move BFS (``find_path_bfs`` in
``simulation/manager.py``) with two complementary strategies over the immutable
:class:`~matss.domain.world.NavGrid`:

* :func:`astar` — deterministic A* for one-off, dynamically-blocked paths.
* :class:`FlowField` / :class:`FlowFieldCache` — precomputed, reusable flow
  fields for shared destinations (cafe, office, home).
* :class:`PathPlanner` — the high-level facade the simulation calls.
"""

from .astar import astar, manhattan
from .flowfield import FlowField, FlowFieldCache
from .planner import PathPlanner

__all__ = [
    "astar",
    "manhattan",
    "FlowField",
    "FlowFieldCache",
    "PathPlanner",
]
