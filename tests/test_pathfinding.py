"""Tests for :mod:`matss.pathfinding` (A*, flow-fields, planner).

Coverage:
  (a) A* paths are valid (adjacent + traversable steps) and optimal-length,
      checked against an inline reference BFS.
  (b) A* returns ``None`` for unreachable goals.
  (c) Blocked cells are avoided, but a "blocked" goal stays reachable.
  (d) Chained ``FlowField.next_step`` reaches the goal at A*-optimal length.
  (e) ``FlowFieldCache.get`` memoises (identical object) and reuses fields.
  (f) Determinism: repeated A* calls return byte-identical paths.
"""

from __future__ import annotations

from collections import deque
from typing import FrozenSet, List, Optional, Set, Tuple

import pytest

from matss.domain.world import NavGrid
from matss.pathfinding import (
    FlowField,
    FlowFieldCache,
    PathPlanner,
    astar,
)

Coord = Tuple[int, int]


# ---------------------------------------------------------------------------
# Inline reference implementations + helpers
# ---------------------------------------------------------------------------

def reference_bfs(
    nav: NavGrid,
    start: Coord,
    goal: Coord,
    blocked: FrozenSet[Coord] = frozenset(),
) -> Optional[List[Coord]]:
    """A straightforward BFS, used as the optimal-length oracle for A*."""
    if not nav.is_traversable(*start) or not nav.is_traversable(*goal):
        return None
    if start == goal:
        return [start]
    came_from = {start: None}
    queue: deque[Coord] = deque([start])
    while queue:
        cur = queue.popleft()
        if cur == goal:
            break
        for nbr in nav.neighbors4(*cur):
            if nbr in blocked and nbr != goal:
                continue
            if nbr in came_from:
                continue
            came_from[nbr] = cur
            queue.append(nbr)
    if goal not in came_from:
        return None
    path = [goal]
    while came_from[path[-1]] is not None:
        path.append(came_from[path[-1]])
    path.reverse()
    return path


def assert_valid_path(
    nav: NavGrid,
    path: List[Coord],
    start: Coord,
    goal: Coord,
    blocked: FrozenSet[Coord] = frozenset(),
) -> None:
    """Assert a path is well-formed: endpoints, adjacency, traversability."""
    assert path[0] == start
    assert path[-1] == goal
    for cell in path:
        assert nav.is_traversable(*cell), f"non-traversable cell {cell}"
    for cell in path[:-1]:  # the goal is exempt from the blocked rule
        assert cell not in blocked, f"path steps through blocked cell {cell}"
    for a, b in zip(path, path[1:]):
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])
        assert dx + dy == 1, f"non-adjacent step {a} -> {b}"


# ---------------------------------------------------------------------------
# Hand-built tiny grids
# ---------------------------------------------------------------------------

@pytest.fixture
def open_grid() -> NavGrid:
    """A 5x5 fully-open room ('.' traversable, 'G' wall)."""
    return NavGrid(["....."] * 5)


@pytest.fixture
def wall_grid() -> NavGrid:
    """A 5x5 grid with a vertical wall leaving a single gap at the bottom.

    Layout (y=0 top):
        . . . G .
        . . . G .
        . . . G .
        . . . G .
        . . . . .
    A path from (0,0) to (4,0) must detour down to row 4 and back up.
    """
    return NavGrid([
        "...G.",
        "...G.",
        "...G.",
        "...G.",
        ".....",
    ])


# ---------------------------------------------------------------------------
# (a) A* validity + optimality
# ---------------------------------------------------------------------------

def test_astar_open_grid_optimal(open_grid: NavGrid) -> None:
    start, goal = (0, 0), (4, 4)
    path = astar(open_grid, start, goal)
    assert path is not None
    assert_valid_path(open_grid, path, start, goal)
    ref = reference_bfs(open_grid, start, goal)
    assert ref is not None
    assert len(path) == len(ref)
    # Manhattan distance is 8, so 9 cells including both endpoints.
    assert len(path) == 9


def test_astar_around_wall_optimal(wall_grid: NavGrid) -> None:
    start, goal = (0, 0), (4, 0)
    path = astar(wall_grid, start, goal)
    assert path is not None
    assert_valid_path(wall_grid, path, start, goal)
    ref = reference_bfs(wall_grid, start, goal)
    assert ref is not None
    assert len(path) == len(ref)


def test_astar_same_cell(open_grid: NavGrid) -> None:
    path = astar(open_grid, (2, 2), (2, 2))
    assert path == [(2, 2)]


def test_astar_on_content_grid(content) -> None:
    nav = content.nav
    # Pick two traversable cells deterministically by scanning the grid.
    traversable = [
        (x, y)
        for y in range(nav.rows)
        for x in range(nav.cols)
        if nav.is_traversable(x, y)
    ]
    assert len(traversable) >= 2
    start, goal = traversable[0], traversable[-1]
    path = astar(nav, start, goal)
    ref = reference_bfs(nav, start, goal)
    # Both should agree on reachability.
    assert (path is None) == (ref is None)
    if path is not None:
        assert_valid_path(nav, path, start, goal)
        assert len(path) == len(ref)


# ---------------------------------------------------------------------------
# (b) unreachable -> None
# ---------------------------------------------------------------------------

def test_astar_unreachable_returns_none() -> None:
    # Two open cells separated by a full wall column.
    nav = NavGrid([
        ".G.",
        ".G.",
        ".G.",
    ])
    assert astar(nav, (0, 0), (2, 0)) is None
    assert reference_bfs(nav, (0, 0), (2, 0)) is None


def test_astar_untraversable_endpoint_none() -> None:
    nav = NavGrid(["..G", "...", "..."])
    assert astar(nav, (0, 0), (2, 0)) is None  # goal is a wall


# ---------------------------------------------------------------------------
# (c) blocked cells avoided; blocked goal still reachable
# ---------------------------------------------------------------------------

def test_astar_avoids_blocked(open_grid: NavGrid) -> None:
    start, goal = (0, 0), (2, 0)
    # Block the direct line; A* must detour but still reach the goal.
    blocked = frozenset({(1, 0)})
    path = astar(open_grid, start, goal, blocked)
    assert path is not None
    assert_valid_path(open_grid, path, start, goal, blocked)
    assert (1, 0) not in path


def test_astar_blocked_goal_still_reachable(open_grid: NavGrid) -> None:
    start, goal = (0, 0), (2, 0)
    # The goal itself is in the blocked set -> must remain reachable.
    blocked = frozenset({(2, 0)})
    path = astar(open_grid, start, goal, blocked)
    assert path is not None
    assert path[-1] == goal
    assert_valid_path(open_grid, path, start, goal, blocked)


def test_astar_blocked_makes_unreachable(open_grid: NavGrid) -> None:
    # Wall off the goal's only approaches with blocked cells.
    start, goal = (0, 0), (4, 4)
    blocked = frozenset({(3, 4), (4, 3)})
    assert astar(open_grid, start, goal, blocked) is None


# ---------------------------------------------------------------------------
# (d) FlowField next_step chaining reaches goal at A* length
# ---------------------------------------------------------------------------

def test_flowfield_next_step_chain(wall_grid: NavGrid) -> None:
    goal = (4, 0)
    field = FlowField(wall_grid, [goal])
    start = (0, 0)

    # Chain next_step manually and confirm it reaches the goal.
    chained = [start]
    cur = start
    guard = 0
    while cur != goal:
        nxt = field.next_step(cur)
        assert nxt is not None
        chained.append(nxt)
        cur = nxt
        guard += 1
        assert guard < 100
    assert chained[-1] == goal

    # full_path should agree with the manual chain.
    fp = field.full_path(start)
    assert fp == chained

    # Length must equal the A* optimal length.
    apath = astar(wall_grid, start, goal)
    assert apath is not None
    assert len(fp) == len(apath)
    assert_valid_path(wall_grid, fp, start, goal)


def test_flowfield_goal_and_unreachable() -> None:
    nav = NavGrid([".G.", ".G.", ".G."])
    field = FlowField(nav, [(0, 0)])
    assert field.next_step((0, 0)) is None  # at goal
    assert field.distance((0, 0)) == 0
    assert field.full_path((0, 0)) == [(0, 0)]
    # Right side is sealed off.
    assert field.next_step((2, 0)) is None
    assert field.distance((2, 0)) is None
    assert field.full_path((2, 0)) is None
    assert not field.reaches((2, 0))


def test_flowfield_multi_goal_nearest(open_grid: NavGrid) -> None:
    # Two goals; a start should flow to the nearer one.
    field = FlowField(open_grid, [(0, 0), (4, 4)])
    near = (1, 0)
    assert field.distance(near) == 1
    path = field.full_path(near)
    assert path is not None
    assert path[-1] in {(0, 0), (4, 4)}


# ---------------------------------------------------------------------------
# (e) FlowFieldCache memoisation + reuse
# ---------------------------------------------------------------------------

def test_flowfield_cache_memoises(open_grid: NavGrid) -> None:
    cache = FlowFieldCache(open_grid)
    f1 = cache.get([(0, 0)])
    f2 = cache.get([(0, 0)])
    assert f1 is f2  # identical object on repeat
    assert len(cache) == 1

    # Order-independent key: same goal-set in different order -> same object.
    f3 = cache.get([(4, 4), (0, 0)])
    f4 = cache.get([(0, 0), (4, 4)])
    assert f3 is f4
    assert len(cache) == 2  # distinct goal-set from f1

    # Reused field yields identical paths.
    p1 = f1.full_path((3, 3))
    p2 = f2.full_path((3, 3))
    assert p1 == p2


def test_flowfield_cache_dedups_duplicates(open_grid: NavGrid) -> None:
    cache = FlowFieldCache(open_grid)
    a = cache.get([(2, 2), (2, 2)])
    b = cache.get([(2, 2)])
    assert a is b


# ---------------------------------------------------------------------------
# (f) Determinism
# ---------------------------------------------------------------------------

def test_astar_deterministic_repeat(open_grid: NavGrid) -> None:
    start, goal = (0, 0), (4, 4)
    paths = [astar(open_grid, start, goal) for _ in range(10)]
    for p in paths[1:]:
        assert p == paths[0]


def test_astar_deterministic_on_content(content) -> None:
    nav = content.nav
    traversable = [
        (x, y)
        for y in range(nav.rows)
        for x in range(nav.cols)
        if nav.is_traversable(x, y)
    ]
    start, goal = traversable[0], traversable[len(traversable) // 2]
    p1 = astar(nav, start, goal)
    p2 = astar(nav, start, goal)
    assert p1 == p2


# ---------------------------------------------------------------------------
# PathPlanner facade
# ---------------------------------------------------------------------------

def test_planner_plan_matches_astar(wall_grid: NavGrid) -> None:
    planner = PathPlanner(wall_grid)
    start, goal = (0, 0), (4, 0)
    assert planner.plan(start, goal) == astar(wall_grid, start, goal)


def test_planner_flow_to_uses_cache(open_grid: NavGrid) -> None:
    planner = PathPlanner(open_grid)
    p1 = planner.flow_to((3, 3), [(0, 0)])
    p2 = planner.flow_to((3, 3), [(0, 0)])
    assert p1 == p2
    assert p1 is not None
    assert_valid_path(open_grid, p1, (3, 3), (0, 0))
    # Length should be A*-optimal.
    apath = astar(open_grid, (3, 3), (0, 0))
    assert len(p1) == len(apath)


def test_planner_plan_blocked_detour(open_grid: NavGrid) -> None:
    planner = PathPlanner(open_grid)
    blocked = frozenset({(1, 0)})
    path = planner.plan((0, 0), (2, 0), blocked)
    assert path is not None
    assert (1, 0) not in path


def test_planner_nearest_free(open_grid: NavGrid) -> None:
    planner = PathPlanner(open_grid)
    # Target free -> returns target.
    assert planner.nearest_free((2, 2), set()) == (2, 2)
    # Target occupied -> returns an adjacent free traversable cell.
    occupied: Set[Coord] = {(2, 2)}
    res = planner.nearest_free((2, 2), occupied)
    assert res is not None
    assert res != (2, 2)
    assert open_grid.is_traversable(*res)
    assert res not in occupied
    # Deterministic.
    assert planner.nearest_free((2, 2), {(2, 2)}) == res


def test_planner_nearest_free_none_when_surrounded() -> None:
    # A single open cell surrounded by walls; if it is occupied there is nowhere.
    nav = NavGrid(["GGG", "G.G", "GGG"])
    planner = PathPlanner(nav)
    assert planner.nearest_free((1, 1), {(1, 1)}) is None


# ---------------------------------------------------------------------------
# Strengthened edge cases + stronger determinism / cross-strategy agreement
# ---------------------------------------------------------------------------

def test_astar_start_untraversable_none() -> None:
    # The start tile is a wall -> no path can originate there.
    nav = NavGrid(["G..", "...", "..."])
    assert astar(nav, (0, 0), (2, 2)) is None


def test_astar_start_blocked_returns_none() -> None:
    # Start (not == goal) is itself in the blocked set: it has no usable
    # outgoing edges because the first move must leave a blocked cell, but the
    # start is never re-entered. A* must still find a path *out* of start since
    # only the start cell is blocked, not the route.  We assert the route never
    # re-enters the blocked start.
    grid = NavGrid(["....."] * 5)
    start, goal = (0, 0), (4, 0)
    blocked = frozenset({start})
    path = astar(grid, start, goal, blocked)
    # Start is blocked but it is the origin; reference BFS treats it the same.
    ref = reference_bfs(grid, start, goal, blocked)
    assert (path is None) == (ref is None)
    if path is not None:
        assert path[0] == start
        assert path[-1] == goal
        # The blocked start must not be revisited mid-path.
        assert start not in path[1:]


def test_astar_exact_path_is_deterministic_full_equality(open_grid: NavGrid) -> None:
    # Many optimal paths exist on an open grid; A* must always pick the SAME one
    # (not merely the same length). The fixed neighbours4 order + insertion
    # counter pins the choice. We assert byte-for-byte equality of the cells.
    start, goal = (0, 0), (4, 4)
    p = astar(open_grid, start, goal)
    assert p is not None
    # neighbours4 order is (0,1),(0,-1),(1,0),(-1,0) -> "down" (y+1) is explored
    # before "right" (x+1), so the deterministic optimal path goes down first.
    expected = [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4),
                (1, 4), (2, 4), (3, 4), (4, 4)]
    assert p == expected
    # And it is stable across repeats.
    assert all(astar(open_grid, start, goal) == expected for _ in range(5))


def test_astar_path_equals_reference_on_content(content) -> None:
    nav = content.nav
    trav = [
        (x, y)
        for y in range(nav.rows)
        for x in range(nav.cols)
        if nav.is_traversable(x, y)
    ]
    start, goal = trav[0], trav[-1]
    p = astar(nav, start, goal)
    ref = reference_bfs(nav, start, goal)
    assert (p is None) == (ref is None)
    if p is not None:
        # Same optimal length on the real fixture grid.
        assert len(p) == len(ref)
        assert_valid_path(nav, p, start, goal)


def test_flowfield_matches_astar_length_on_content(content) -> None:
    nav = content.nav
    trav = [
        (x, y)
        for y in range(nav.rows)
        for x in range(nav.cols)
        if nav.is_traversable(x, y)
    ]
    goal = trav[-1]
    start = trav[0]
    field = FlowField(nav, [goal])
    fp = field.full_path(start)
    apath = astar(nav, start, goal)
    assert (fp is None) == (apath is None)
    if fp is not None:
        assert_valid_path(nav, fp, start, goal)
        # Flow field path is shortest -> equal length to A*.
        assert len(fp) == len(apath)


def test_flowfield_cache_reuse_matches_fresh_field(open_grid: NavGrid) -> None:
    # A cached field must produce identical paths to an independently-built one.
    cache = FlowFieldCache(open_grid)
    cached = cache.get([(0, 0)])
    fresh = FlowField(open_grid, [(0, 0)])
    for start in [(4, 4), (2, 3), (0, 4), (3, 1)]:
        assert cached.full_path(start) == fresh.full_path(start)


def test_flowfield_multi_source_tie_break_deterministic(open_grid: NavGrid) -> None:
    # A cell equidistant from two goals must resolve deterministically across
    # repeated rebuilds (BFS source/insertion order is fixed).
    goals = [(0, 0), (4, 0)]
    f1 = FlowField(open_grid, goals)
    f2 = FlowField(open_grid, goals)
    mid = (2, 0)  # distance 2 to each goal
    assert f1.distance(mid) == 2
    assert f1.full_path(mid) == f2.full_path(mid)
    # Equidistant cell still produces a valid shortest path to *some* goal.
    p = f1.full_path(mid)
    assert p is not None
    assert p[-1] in {(0, 0), (4, 0)}
    assert len(p) == 3


def test_planner_flow_to_unreachable_returns_none() -> None:
    nav = NavGrid([".G.", ".G.", ".G."])
    planner = PathPlanner(nav)
    # Goal on the sealed-off right column; start on the left.
    assert planner.flow_to((0, 0), [(2, 2)]) is None


def test_planner_flow_to_matches_astar_on_content(content) -> None:
    nav = content.nav
    planner = PathPlanner(nav)
    trav = [
        (x, y)
        for y in range(nav.rows)
        for x in range(nav.cols)
        if nav.is_traversable(x, y)
    ]
    start, goal = trav[0], trav[len(trav) // 3]
    fp = planner.flow_to(start, [goal])
    apath = astar(nav, start, goal)
    assert (fp is None) == (apath is None)
    if fp is not None:
        assert len(fp) == len(apath)
        assert_valid_path(nav, fp, start, goal)


def test_nearest_free_deterministic_tie_break(open_grid: NavGrid) -> None:
    # Target occupied; several neighbours are free. The result must be the
    # deterministic first free neighbour in neighbours4 order: (0,1),(0,-1),
    # (1,0),(-1,0) -> from (2,2) that is (2,3).
    planner = PathPlanner(open_grid)
    res = planner.nearest_free((2, 2), {(2, 2)})
    assert res == (2, 3)
    # Stable across repeats.
    assert all(planner.nearest_free((2, 2), {(2, 2)}) == (2, 3) for _ in range(5))


def test_core_is_stdlib_only() -> None:
    # Guard the "stdlib-only core" contract: the pathfinding modules must not
    # pull in global-state sources (random/time) in core logic.
    import importlib

    for name in (
        "matss.pathfinding.astar",
        "matss.pathfinding.flowfield",
        "matss.pathfinding.planner",
    ):
        mod = importlib.import_module(name)
        with open(mod.__file__, encoding="utf-8") as fh:
            src = fh.read()
        assert "import random" not in src, f"{name} uses random"
        assert "import time" not in src, f"{name} uses time"
        assert "from time" not in src, f"{name} uses time"
        assert "from random" not in src, f"{name} uses random"
