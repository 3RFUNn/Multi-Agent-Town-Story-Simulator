"""Regression tests for defects found by the adversarial QA bug-hunt.

Each test fails against the pre-fix code and passes after the fix.
"""

import json

import pytest

from matss.cognition.llm import CachingLLMProvider, MockLLMProvider, TieredRouter
from matss.domain.enums import AgentState, EventType
from matss.eventlog import JsonlEventLog, LiveWorldReadModel
from matss.ports import LLMRequest, ModelTier
from matss.sim import build_engine


# --- Fix 1: caching cache-key must include tier + sampling params -------------

def test_cache_key_distinguishes_tier():
    cheap = MockLLMProvider(words=4)
    frontier = MockLLMProvider(words=40)
    router = TieredRouter({ModelTier.CHEAP: cheap, ModelTier.FRONTIER: frontier})
    cache = CachingLLMProvider(router)

    r_cheap = cache.complete(LLMRequest(prompt="X", tier=ModelTier.CHEAP))
    r_frontier = cache.complete(LLMRequest(prompt="X", tier=ModelTier.FRONTIER))

    # The frontier request must NOT be served the cheap response.
    assert r_frontier.tier == ModelTier.FRONTIER
    assert not r_frontier.cached
    assert frontier.call_count == 1
    assert r_cheap.text != r_frontier.text


def test_cache_key_distinguishes_max_tokens():
    inner = MockLLMProvider()
    cache = CachingLLMProvider(inner)
    a = cache.complete(LLMRequest(prompt="X", max_tokens=10))
    b = cache.complete(LLMRequest(prompt="X", max_tokens=2000))
    assert not b.cached
    assert a.text != b.text


def test_cache_still_hits_on_identical_request():
    inner = MockLLMProvider()
    cache = CachingLLMProvider(inner)
    one = cache.complete(LLMRequest(prompt="X", tier=ModelTier.BALANCED, max_tokens=100))
    two = cache.complete(LLMRequest(prompt="X", tier=ModelTier.BALANCED, max_tokens=100))
    assert two.cached and two.text == one.text
    assert inner.call_count == 1


# --- Fix 2: LiveWorldReadModel money projection ------------------------------

def test_live_read_model_tracks_money_from_real_engine_events():
    e = build_engine(seed=42)
    e.run(600)
    rm = LiveWorldReadModel()
    for ev in e.log.read():
        rm.apply(ev)
    state = rm.state()
    moneyed = [v["money"] for v in state.values() if v.get("money") is not None]
    assert moneyed, "expected at least one agent's money to be projected"
    # Spent/earned agents should reflect a real balance, not None.
    assert any(m != 0 for m in moneyed)


def test_worked_event_updates_projected_money():
    rm = LiveWorldReadModel()
    from matss.domain import Event
    rm.apply(Event(type=EventType.WORKED, tick=1, sim_minute=2, day_index=0,
                   day_of_week="Monday", agent_id="alex", payload={"wage": 0.5, "balance": 120.5}))
    assert rm.state()["alex"]["money"] == 120.5


# --- Fix 3: JsonlEventLog tolerates corrupt lines, seq not inflated ----------

def test_jsonl_skips_corrupt_trailing_line(tmp_path):
    path = str(tmp_path / "log.jsonl")
    log = JsonlEventLog(path)
    from matss.domain import Event
    log.append(Event(type=EventType.TICK_COMPLETED, tick=0, sim_minute=0, day_index=0,
                     day_of_week="Monday", payload={"state_hash": "a", "snapshot": {}}))
    # Append a truncated/corrupt line directly.
    with open(path, "a", encoding="utf-8") as fh:
        fh.write('{"seq": 1, "type": "tick", "tick": 1, "sim_min\n')

    events = list(log.read())  # must NOT raise; the good event survives.
    assert len(events) == 1 and events[0].type == EventType.TICK_COMPLETED

    # The corrupt line must not inflate the next sequence number.
    nxt = log.append(Event(type=EventType.DAY_ROLLOVER, tick=2, sim_minute=4, day_index=1,
                           day_of_week="Tuesday", payload={}))
    assert nxt.seq == 1


def test_jsonl_strict_mode_raises_on_corrupt_line(tmp_path):
    path = str(tmp_path / "log.jsonl")
    log = JsonlEventLog(path)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("not json at all\n")
    with pytest.raises(ValueError):
        list(log.read(strict=True))


# --- Fix 4: head-on swap / standoff liveness ---------------------------------

@pytest.mark.parametrize("seed", [42, 1, 7])
def test_no_agent_freezes_while_moving(seed):
    """No agent may stall in MOVING state longer than the give-up threshold."""
    e = build_engine(seed=seed)
    e.start()
    last_pos = {a.id: a.pos for a in e.world.agents.values()}
    stall = {a.id: 0 for a in e.world.agents.values()}
    max_stall = 0
    for _ in range(3000):
        e.tick()
        for a in e.world.agents.values():
            if a.state == AgentState.MOVING and a.pos == last_pos[a.id]:
                stall[a.id] += 1
            else:
                stall[a.id] = 0
            last_pos[a.id] = a.pos
            max_stall = max(max_stall, stall[a.id])
    # The fix caps any no-progress-while-moving streak at the threshold.
    assert max_stall <= e._max_blocked, f"agent frozen for {max_stall} ticks (seed {seed})"


def test_liveness_fix_preserves_determinism():
    assert build_engine(seed=42).run(3000) == build_engine(seed=42).run(3000)
