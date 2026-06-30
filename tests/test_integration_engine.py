"""End-to-end engine behavior: events, movement, economy, narrative, gateway."""

import pytest

from matss.domain.enums import AgentState, EventType
from matss.eventlog import LiveWorldReadModel, NarrativeReadModel
from matss.app.gateway import SnapshotBroadcaster
from matss.sim import build_engine


def test_engine_starts_and_spawns_agents():
    e = build_engine(seed=1)
    e.start()
    assert len(e.world.agents) == 6
    spawned = [ev for ev in e.log.read() if ev.type == EventType.AGENT_SPAWNED]
    assert len(spawned) == 6
    assert any(ev.type == EventType.SIM_STARTED for ev in e.log.read())


def test_agents_move_and_act_over_a_morning():
    e = build_engine(seed=3)
    e.run(300)
    moved = sum(1 for ev in e.log.read() if ev.type == EventType.AGENT_MOVED)
    acted = sum(1 for ev in e.log.read() if ev.type == EventType.ACTIVITY_STARTED)
    assert moved > 0
    assert acted > 0
    # At least one agent ended somewhere other than its spawn home.
    assert any(a.pos != a.defn.home_pos for a in e.world.agents.values())


def test_every_tick_emits_one_tick_completed_with_hash():
    e = build_engine(seed=4)
    e.run(120)
    ticks = [ev for ev in e.log.read() if ev.type == EventType.TICK_COMPLETED]
    assert len(ticks) == len(e.state_hashes)
    for ev in ticks:
        assert ev.payload["state_hash"]
        assert "snapshot" in ev.payload


def test_economy_agents_earn_at_work():
    e = build_engine(seed=8)
    e.run(500)
    worked = [ev for ev in e.log.read() if ev.type == EventType.WORKED]
    assert worked, "expected at least one wage event during work hours"
    assert all(ev.payload["wage"] > 0 for ev in worked)


def test_narrative_is_post_hoc_and_logged():
    e = build_engine(seed=2)
    e.run_until_day(1)  # cross the first 3AM narrative trigger
    diaries = [ev for ev in e.log.read() if ev.type == EventType.DIARY_WRITTEN]
    stories = [ev for ev in e.log.read() if ev.type == EventType.STORY_COMPILED]
    assert len(diaries) == 6
    assert len(stories) == 1
    assert stories[0].payload["text"]


def test_no_agent_is_ever_on_a_wall_tile():
    e = build_engine(seed=6)
    e.run(400)
    for a in e.world.agents.values():
        assert e.world.nav.is_traversable(a.x, a.y), f"{a.id} on non-traversable tile"


def test_live_read_model_tracks_positions():
    e = build_engine(seed=10)
    e.run(200)
    rm = LiveWorldReadModel()
    for ev in e.log.read():
        rm.apply(ev)
    state = rm.state()
    assert state  # populated from AGENT_MOVED/ACTIVITY_STARTED events


def test_gateway_builds_client_state_from_bus():
    e = build_engine(seed=12)
    b = SnapshotBroadcaster(e.content)
    e.bus.subscribe(b.handle)
    e.run(100)
    state = b.latest_state()
    assert state is not None
    assert len(state["agents"]) == 6
    assert all("name" in a and "color" in a for a in state["agents"])


def test_hierarchical_narrative_runs_and_stays_deterministic():
    a = build_engine(seed=15, hierarchical_narrative=True).run_until_day(1)
    b = build_engine(seed=15, hierarchical_narrative=True).run_until_day(1)
    assert a == b
    eng = build_engine(seed=15, hierarchical_narrative=True)
    eng.run_until_day(1)
    assert [ev for ev in eng.log.read() if ev.type == EventType.STORY_COMPILED]
