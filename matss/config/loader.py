"""Load + resolve validated content into typed domain objects."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..domain.agent import AgentDef, Relationship
from ..domain.world import NavGrid, Place
from .schema import ContentError, validate_content

DEFAULT_CONTENT_PATH = os.path.join(os.path.dirname(__file__), "..", "content", "world.json")

_WEEKEND = {"Saturday", "Sunday"}


@dataclass
class Content:
    """Resolved, validated world content ready to seed a simulation."""

    meta: Dict[str, Any]
    nav: NavGrid
    places: Dict[str, Place]
    activity_data: Dict[str, Dict[str, Any]]
    personality_traits: Dict[str, Dict[str, float]]
    schedule_templates: Dict[str, Dict[str, List[Dict[str, Any]]]]
    relationships: Dict[str, Dict[str, Dict[str, Any]]]
    agent_defs: List[AgentDef]
    sim_params: Dict[str, Any]
    cell_types: Dict[str, Any] = field(default_factory=dict)

    # --- resolution helpers ---------------------------------------------------

    def resolve_traits(self, personality: Tuple[str, ...]) -> Dict[str, float]:
        """Merge the numeric trait modifiers for a list of personality names."""
        merged: Dict[str, float] = {}
        for p in personality:
            merged.update(self.personality_traits.get(p, {}))
        return merged

    def relationships_for(self, agent_id: str) -> Dict[str, Relationship]:
        out: Dict[str, Relationship] = {}
        for other, rel in self.relationships.get(agent_id, {}).items():
            out[other] = Relationship(type=rel.get("type", "acquaintance"),
                                      affinity=int(rel.get("affinity", 50)))
        return out

    def schedule_activity(self, template: str, day_of_week: str, hour: int) -> Optional[str]:
        """Return the scheduled activity for a template at a given day/hour."""
        tmpl = self.schedule_templates.get(template)
        if not tmpl:
            return None
        part = "weekends" if day_of_week in _WEEKEND else "weekdays"
        for blk in tmpl.get(part, []):
            start, end = blk["start"], blk["end"]
            if start < end:
                in_block = start <= hour < end
            else:  # wraps past midnight, e.g. 22:00 -> 01:00
                in_block = hour >= start or hour < end
            if in_block:
                return blk["activity"]
        return None

    def agent_def(self, agent_id: str) -> Optional[AgentDef]:
        for d in self.agent_defs:
            if d.id == agent_id:
                return d
        return None


def load_content(source: Any = None) -> Content:
    """Load content from a path (str), a parsed dict, or the default file."""
    if source is None:
        source = os.path.normpath(DEFAULT_CONTENT_PATH)
    if isinstance(source, str):
        with open(source, "r", encoding="utf-8") as f:
            raw = json.load(f)
    elif isinstance(source, dict):
        raw = source
    else:
        raise ContentError(f"unsupported content source type: {type(source).__name__}")

    validate_content(raw)

    nav = NavGrid(raw["map"]["layout"], wall_tile=raw["map"].get("wall_tile", "G"))

    places = {
        name: Place(name=name, kind=p.get("kind", name),
                    coords=tuple((int(x), int(y)) for x, y in p["coords"]))
        for name, p in raw["places"].items()
    }

    agent_defs: List[AgentDef] = []
    for a in raw["agents"]:
        personality = tuple(a["personality"])
        traits = {}
        for p in personality:
            traits.update(raw["personality_traits"].get(p, {}))
        smr = a.get("starting_money_range", [100, 150])
        agent_defs.append(AgentDef(
            id=a["id"], name=a.get("name", a["id"]),
            icon=a.get("icon", ""), color=a.get("color", "#888888"),
            home_pos=(int(a["home_pos"][0]), int(a["home_pos"][1])),
            personality=personality, traits=traits,
            schedule_template=a["schedule_template"],
            work_location=a.get("work_location"),
            background=a.get("background", ""),
            starting_money_range=(int(smr[0]), int(smr[1])),
        ))

    return Content(
        meta=raw.get("meta", {}),
        nav=nav,
        places=places,
        activity_data={k: dict(v) for k, v in raw["activities"].items()},
        personality_traits=raw["personality_traits"],
        schedule_templates=raw["schedule_templates"],
        relationships=raw.get("relationships", {}),
        agent_defs=agent_defs,
        sim_params=raw["sim_params"],
        cell_types=raw["map"].get("cell_types", {}),
    )
