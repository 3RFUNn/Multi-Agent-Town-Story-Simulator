"""Town map: layout grid + named places, loaded once from map_data.json."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

Coord = tuple[int, int]


@dataclass(frozen=True)
class Place:
    key: str
    kind: str
    coords: tuple[Coord, ...]


class TownMap:
    def __init__(self, layout: list[list[str]], places: dict[str, Place],
                 cell_types: dict[str, dict]) -> None:
        self.layout = layout
        self.places = places
        self.cell_types = cell_types
        self.height = len(layout)
        self.width = len(layout[0]) if layout else 0
        self._place_of: dict[Coord, str] = {}
        for place in places.values():
            for coord in place.coords:
                self._place_of[coord] = place.key

    @classmethod
    def load(cls, path: Path) -> "TownMap":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        places = {
            key: Place(key=key, kind=raw.get("type", key),
                       coords=tuple((int(x), int(y)) for x, y in raw["coords"]))
            for key, raw in data["places"].items()
        }
        return cls(layout=data["layout"], places=places, cell_types=data.get("cell_types", {}))

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= y < self.height and 0 <= x < self.width

    def walkable(self, x: int, y: int) -> bool:
        """Grass ('G') is impassable scenery; everything else is walkable."""
        return self.in_bounds(x, y) and self.layout[y][x] != "G"

    def place_at(self, coord: Coord) -> str | None:
        return self._place_of.get(coord)

    def place_coords(self, key: str) -> tuple[Coord, ...]:
        return self.places[key].coords

    def to_dict(self) -> dict:
        return {
            "layout": self.layout,
            "cell_types": self.cell_types,
            "places": {k: {"type": p.kind, "coords": [list(c) for c in p.coords]}
                       for k, p in self.places.items()},
        }
