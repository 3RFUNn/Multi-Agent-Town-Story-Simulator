"""Tests for data-driven content loading/validation and the domain model."""

import copy

import pytest

from matss.config import load_content, validate_content, ContentError
from matss.config.loader import load_content as _load
from matss.domain import Agent, Event, EventType, WorldState, MemoryRecord


def test_content_loads_and_resolves(content):
    assert len(content.agent_defs) == 6
    assert "downtown_cafe" in content.places
    alex = content.agent_def("alex")
    assert alex is not None
    # personality -> merged numeric traits
    assert alex.trait("social_motivation") > 1.0  # extrovert
    assert content.relationships_for("alex")["charlie"].affinity == 85


def test_schedule_resolution_weekday_and_wraparound(content):
    alex = content.agent_def("alex")
    assert content.schedule_activity(alex.schedule_template, "Monday", 10) == "work_at_office"
    # 22:00->01:00 wrap block must resolve at 23:00 on a weekend.
    assert content.schedule_activity(alex.schedule_template, "Saturday", 23) == "party_at_bar"
    # outside any block -> None
    assert content.schedule_activity(alex.schedule_template, "Monday", 4) is None


def test_nav_grid_traversability(content):
    nav = content.nav
    assert nav.cols == 30 and nav.rows == 23
    assert not nav.is_traversable(0, 0)        # border wall 'G'
    assert nav.is_traversable(2, 2)            # a house tile
    assert not nav.in_bounds(-1, 0)


def test_validation_rejects_bad_content():
    bad = {"map": {"layout": [["G"]]}}  # missing required keys
    with pytest.raises(ContentError):
        validate_content(bad)


def test_validation_reports_unknown_trait(content):
    raw_path_obj = load_content()  # sanity that default is valid
    bad = {
        "map": {"layout": [["G", "P"], ["P", "P"]], "wall_tile": "G"},
        "places": {"home": {"coords": [[1, 1]]}},
        "personality_traits": {"calm": {}},
        "schedule_templates": {"t": {"weekdays": [], "weekends": []}},
        "activities": {"rest": {"cost": 0}},
        "agents": [{"id": "a", "name": "A", "home_pos": [1, 1],
                    "personality": ["nonexistent"], "schedule_template": "t"}],
        "sim_params": {},
    }
    with pytest.raises(ContentError) as ei:
        validate_content(bad)
    assert "personality" in str(ei.value)


def test_agent_canonical_and_view(content):
    alex = content.agent_def("alex")
    ag = Agent(alex, money=120, relationships=content.relationships_for("alex"))
    canon = ag.to_canonical()
    assert canon["id"] == "alex" and canon["money"] == 120.0
    view = ag.to_view()
    assert view["name"] == alex.name and "personality" in view


def test_agent_affinity_clamped(content):
    ag = Agent(content.agent_def("alex"), 100, content.relationships_for("alex"))
    ag.set_affinity("charlie", 999)
    assert ag.get_relationship("charlie").affinity == 100
    ag.set_affinity("charlie", -50)
    assert ag.get_relationship("charlie").affinity == 0


def test_event_roundtrip():
    ev = Event(type=EventType.AGENT_MOVED, tick=3, sim_minute=6, day_index=0,
               day_of_week="Monday", agent_id="alex", payload={"to": [3, 4]})
    again = Event.from_dict(ev.to_dict())
    assert again.to_canonical() == ev.to_canonical()
    # seq excluded from canonical identity
    assert ev.with_seq(10).to_canonical() == ev.to_canonical()


def test_world_canonical_is_id_sorted(content):
    a = Agent(content.agent_def("bella"), 100, {})
    b = Agent(content.agent_def("alex"), 100, {})
    ws = WorldState(nav=content.nav, places=content.places,
                    activity_data=content.activity_data, agents={"bella": a, "alex": b})
    canon = ws.to_canonical()
    assert list(canon["agents"].keys()) == ["alex", "bella"]


def test_memory_record_to_dict():
    m = MemoryRecord(id="m1", agent_id="alex", text="hi", tick=1, day="Monday", importance=5)
    d = m.to_dict()
    assert d["id"] == "m1" and d["importance"] == 5
