"""Stdlib-only structural validation for world content.

Raises :class:`ContentError` with a precise path on the first violation. This is
the validation layer the prototype lacked — content is now data that is checked
before it can break a run.
"""

from __future__ import annotations

from typing import Any, Dict, List


class ContentError(ValueError):
    """Raised when world content fails validation."""


def _require(cond: bool, path: str, msg: str) -> None:
    if not cond:
        raise ContentError(f"{path}: {msg}")


def _is_int_pair(v: Any) -> bool:
    return (isinstance(v, (list, tuple)) and len(v) == 2
            and all(isinstance(n, int) for n in v))


def validate_content(c: Dict[str, Any]) -> None:
    """Validate a parsed world-content dict. Raises :class:`ContentError`."""
    _require(isinstance(c, dict), "<root>", "content must be an object")

    for key in ("map", "places", "personality_traits", "schedule_templates",
                "activities", "agents", "sim_params"):
        _require(key in c, "<root>", f"missing required key '{key}'")

    # --- map ---
    m = c["map"]
    _require(isinstance(m, dict), "map", "must be an object")
    _require("layout" in m and isinstance(m["layout"], list) and m["layout"],
             "map.layout", "must be a non-empty list of rows")
    width = len(m["layout"][0])
    for i, row in enumerate(m["layout"]):
        _require(isinstance(row, list) and len(row) == width,
                 f"map.layout[{i}]", f"every row must have width {width}")
        _require(all(isinstance(ch, str) and len(ch) == 1 for ch in row),
                 f"map.layout[{i}]", "rows must contain single-character tiles")
    _require(isinstance(m.get("wall_tile", "G"), str), "map.wall_tile", "must be a string")

    # --- places ---
    places = c["places"]
    _require(isinstance(places, dict) and places, "places", "must be a non-empty object")
    for name, p in places.items():
        _require(isinstance(p, dict), f"places.{name}", "must be an object")
        _require("coords" in p and isinstance(p["coords"], list) and p["coords"],
                 f"places.{name}.coords", "must be a non-empty list")
        for j, co in enumerate(p["coords"]):
            _require(_is_int_pair(co), f"places.{name}.coords[{j}]", "must be an [x, y] int pair")

    # --- personality traits ---
    pt = c["personality_traits"]
    _require(isinstance(pt, dict) and pt, "personality_traits", "must be a non-empty object")
    for tname, tvals in pt.items():
        _require(isinstance(tvals, dict), f"personality_traits.{tname}", "must be an object")

    # --- schedule templates ---
    st = c["schedule_templates"]
    _require(isinstance(st, dict) and st, "schedule_templates", "must be a non-empty object")
    for sname, parts in st.items():
        _require(isinstance(parts, dict), f"schedule_templates.{sname}", "must be an object")
        for part in ("weekdays", "weekends"):
            _require(part in parts and isinstance(parts[part], list),
                     f"schedule_templates.{sname}.{part}", "must be a list of blocks")
            for k, blk in enumerate(parts[part]):
                base = f"schedule_templates.{sname}.{part}[{k}]"
                _require(isinstance(blk, dict), base, "must be an object")
                for f in ("start", "end", "activity"):
                    _require(f in blk, base, f"missing '{f}'")
                _require(isinstance(blk["start"], int) and isinstance(blk["end"], int),
                         base, "start/end must be ints")
                # ``end`` may be <= ``start`` to denote a block that wraps past
                # midnight (e.g. start=22, end=1), as in the source schedules.
                _require(0 <= blk["start"] <= 23, base, "require 0 <= start <= 23")
                _require(1 <= blk["end"] <= 24, base, "require 1 <= end <= 24")

    # --- activities ---
    acts = c["activities"]
    _require(isinstance(acts, dict) and acts, "activities", "must be a non-empty object")
    for aname, a in acts.items():
        _require(isinstance(a, dict), f"activities.{aname}", "must be an object")
        _require("cost" in a, f"activities.{aname}.cost", "missing cost")
        _require(isinstance(a["cost"], (int, float)), f"activities.{aname}.cost", "must be numeric")

    # --- agents ---
    agents = c["agents"]
    _require(isinstance(agents, list) and agents, "agents", "must be a non-empty list")
    seen = set()
    for idx, a in enumerate(agents):
        base = f"agents[{idx}]"
        _require(isinstance(a, dict), base, "must be an object")
        for f in ("id", "name", "home_pos", "personality", "schedule_template"):
            _require(f in a, base, f"missing '{f}'")
        _require(a["id"] not in seen, base, f"duplicate agent id '{a['id']}'")
        seen.add(a["id"])
        _require(_is_int_pair(a["home_pos"]), f"{base}.home_pos", "must be an [x, y] int pair")
        _require(isinstance(a["personality"], list) and a["personality"],
                 f"{base}.personality", "must be a non-empty list")
        for trait in a["personality"]:
            _require(trait in pt, f"{base}.personality", f"unknown trait '{trait}'")
        _require(a["schedule_template"] in st, f"{base}.schedule_template",
                 f"unknown schedule template '{a['schedule_template']}'")
        wl = a.get("work_location")
        if wl is not None:
            _require(wl in places, f"{base}.work_location", f"unknown place '{wl}'")

    # --- referential integrity: every activity location must be a place or "home" ---
    for aname, a in acts.items():
        loc = a.get("location")
        if loc is not None and loc != "home":
            _require(loc in places, f"activities.{aname}.location",
                     f"unknown place '{loc}'")
