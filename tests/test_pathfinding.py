from __future__ import annotations

from townsim.config.models import SimConfig
from townsim.world.grid import TownMap
from townsim.world.pathfinding import astar
from townsim.world.spatial import SpatialHash


def load_map() -> TownMap:
    return TownMap.load(SimConfig().paths.map_file)


class TestAstar:
    def test_path_excludes_start(self):
        """V1's BFS included the start cell, wasting a movement tick (F30)."""
        town = load_map()
        path = astar(town, (3, 3), (3, 5))
        assert path is not None
        assert path[0] != (3, 3)
        assert path[-1] == (3, 5)

    def test_trivial_path(self):
        town = load_map()
        assert astar(town, (3, 3), (3, 3)) == []

    def test_unreachable_returns_none(self):
        town = load_map()
        assert astar(town, (3, 3), (0, 0)) is None  # (0,0) is grass

    def test_path_is_connected_and_walkable(self):
        town = load_map()
        start, goal = (3, 3), (23, 15)  # north house -> college
        path = astar(town, start, goal)
        assert path is not None
        prev = start
        for cell in path:
            assert abs(cell[0] - prev[0]) + abs(cell[1] - prev[1]) == 1
            assert town.walkable(*cell)
            prev = cell
        assert prev == goal

    def test_blocked_cells_avoided(self):
        town = load_map()
        free = astar(town, (2, 2), (4, 2))
        assert free is not None
        blocked = astar(town, (2, 2), (4, 2), blocked=frozenset({(3, 2)}))
        assert blocked is not None
        assert (3, 2) not in blocked


class TestSpatialHash:
    def test_neighbors_within(self):
        hash_ = SpatialHash(cell_size=4)
        hash_.upsert("a", (10, 10))
        hash_.upsert("b", (12, 12))
        hash_.upsert("c", (20, 20))
        assert hash_.neighbors_within((10, 10), 3, exclude="a") == ["b"]
        assert hash_.neighbors_within((10, 10), 15, exclude="a") == ["b", "c"]

    def test_upsert_moves(self):
        hash_ = SpatialHash(cell_size=4)
        hash_.upsert("a", (0, 0))
        hash_.upsert("a", (30, 30))
        assert hash_.neighbors_within((0, 0), 5) == []
        assert hash_.neighbors_within((30, 30), 0) == ["a"]
