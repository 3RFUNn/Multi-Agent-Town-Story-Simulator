"""Tests for :mod:`matss.eventlog` — bus, logs, and CQRS projections.

These cover the contract conformance against the frozen ports, the integrity
hash chain, JSONL round-tripping, fault isolation in the bus, and the replay /
read-model projections built on the integrator's ``TICK_COMPLETED`` shape.
"""

from __future__ import annotations

from typing import List

from matss.determinism.hashing import hash_events
from matss.domain.enums import EventType
from matss.domain.events import Event
from matss.eventlog import (
    InMemoryEventLog,
    InProcessEventBus,
    JsonlEventLog,
    LiveWorldReadModel,
    NarrativeReadModel,
    reconstruct_world_canonical,
    replay_state_hashes,
)
from matss.ports import EventBus, EventLog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_event(
    event_type: str,
    *,
    tick: int = 0,
    agent_id=None,
    payload=None,
    sim_minute: int = 0,
    day_index: int = 0,
    day_of_week: str = "Monday",
) -> Event:
    """Build an Event via the domain constructor with sensible defaults."""
    return Event(
        type=event_type,
        tick=tick,
        sim_minute=sim_minute,
        day_index=day_index,
        day_of_week=day_of_week,
        agent_id=agent_id,
        payload=payload or {},
    )


def tick_completed(tick: int, state_hash: str, snapshot) -> Event:
    """Build a synthetic TICK_COMPLETED event matching the integrator contract."""
    return make_event(
        EventType.TICK_COMPLETED,
        tick=tick,
        payload={"state_hash": state_hash, "snapshot": snapshot, "tick": tick},
    )


# ---------------------------------------------------------------------------
# (a) InMemoryEventLog: seq, read filtering, head_hash
# ---------------------------------------------------------------------------

def test_inmemory_log_is_eventlog_protocol():
    log = InMemoryEventLog()
    assert isinstance(log, EventLog)


def test_inmemory_assigns_monotonic_seq():
    log = InMemoryEventLog()
    a = log.append(make_event(EventType.AGENT_MOVED, tick=1))
    b = log.append(make_event(EventType.AGENT_MOVED, tick=2))
    c = log.append(make_event(EventType.AGENT_MOVED, tick=3))
    assert (a.seq, b.seq, c.seq) == (0, 1, 2)
    assert len(log) == 3
    # seq is assigned by the log, overriding any incoming seq.
    stamped = log.append(make_event(EventType.ATE).with_seq(999))
    assert stamped.seq == 3


def test_inmemory_append_many():
    log = InMemoryEventLog()
    events = [make_event(EventType.WORKED, tick=i) for i in range(4)]
    stamped = log.append_many(events)
    assert [e.seq for e in stamped] == [0, 1, 2, 3]
    assert len(log) == 4


def test_inmemory_read_from_seq_filters():
    log = InMemoryEventLog()
    for i in range(5):
        log.append(make_event(EventType.AGENT_MOVED, tick=i))
    all_events = list(log.read())
    assert [e.seq for e in all_events] == [0, 1, 2, 3, 4]
    tail = list(log.read(from_seq=3))
    assert [e.seq for e in tail] == [3, 4]
    assert list(log.read(from_seq=99)) == []


def test_inmemory_head_hash_changes_and_is_order_sensitive():
    e1 = make_event(EventType.ATE, tick=1, agent_id="alex")
    e2 = make_event(EventType.RESTED, tick=2, agent_id="bea")

    log_a = InMemoryEventLog()
    assert log_a.head_hash == ""
    log_a.append(e1)
    h1 = log_a.head_hash
    assert h1 != ""
    log_a.append(e2)
    h2 = log_a.head_hash
    assert h2 != h1  # head_hash changes on append

    # Same two events appended in reverse order -> different head hash.
    log_b = InMemoryEventLog()
    log_b.append(e2)
    log_b.append(e1)
    assert log_b.head_hash != log_a.head_hash

    # Same events, same order -> identical head hash (determinism).
    log_c = InMemoryEventLog()
    log_c.append(e1)
    log_c.append(e2)
    assert log_c.head_hash == log_a.head_hash


# ---------------------------------------------------------------------------
# (b) Bus: ordered delivery + fault isolation
# ---------------------------------------------------------------------------

def test_bus_is_eventbus_protocol():
    assert isinstance(InProcessEventBus(), EventBus)


def test_bus_publishes_in_registration_order():
    bus = InProcessEventBus()
    order: List[str] = []
    bus.subscribe(lambda ev: order.append("first"))
    bus.subscribe(lambda ev: order.append("second"))
    bus.subscribe(lambda ev: order.append("third"))
    bus.publish(make_event(EventType.SIM_STARTED))
    assert order == ["first", "second", "third"]
    assert bus.subscriber_count == 3


def test_bus_survives_throwing_handler():
    bus = InProcessEventBus()
    seen: List[str] = []

    def boom(ev: Event) -> None:
        raise RuntimeError("handler exploded")

    bus.subscribe(lambda ev: seen.append("before"))
    bus.subscribe(boom)
    bus.subscribe(lambda ev: seen.append("after"))

    # Must not raise, and the later handler still runs.
    bus.publish(make_event(EventType.TICK_COMPLETED))
    assert seen == ["before", "after"]
    assert bus.error_count == 1


def test_bus_delivers_each_published_event():
    bus = InProcessEventBus()
    received: List[Event] = []
    bus.subscribe(received.append)
    e1 = make_event(EventType.AGENT_MOVED, tick=1)
    e2 = make_event(EventType.ATE, tick=2)
    bus.publish(e1)
    bus.publish(e2)
    assert received == [e1, e2]


# ---------------------------------------------------------------------------
# (c) JsonlEventLog: round-trip through a tmp file
# ---------------------------------------------------------------------------

def test_jsonl_log_is_eventlog_protocol(tmp_path):
    log = JsonlEventLog(tmp_path / "events.jsonl")
    assert isinstance(log, EventLog)


def test_jsonl_round_trips_events(tmp_path):
    path = tmp_path / "events.jsonl"
    log = JsonlEventLog(path)
    originals = [
        make_event(
            EventType.AGENT_MOVED,
            tick=1,
            agent_id="alex",
            payload={"to": [3, 4], "from": [3, 3]},
        ),
        make_event(
            EventType.MONEY_CHANGED,
            tick=2,
            agent_id="bea",
            payload={"money": 42.5, "delta": -7.5},
        ),
        make_event(EventType.DAY_ROLLOVER, tick=3, day_index=1, day_of_week="Tuesday"),
    ]
    log.append_many(originals)
    assert len(log) == 3

    # Re-open from disk: a fresh adapter reads what was persisted.
    reopened = JsonlEventLog(path)
    assert len(reopened) == 3
    read_back = list(reopened.read())
    assert [e.seq for e in read_back] == [0, 1, 2]
    for orig, got in zip(originals, read_back):
        assert got.type == orig.type
        assert got.tick == orig.tick
        assert got.agent_id == orig.agent_id
        assert got.payload == orig.payload
        assert got.day_of_week == orig.day_of_week


def test_jsonl_append_assigns_seq_and_resumes(tmp_path):
    path = tmp_path / "events.jsonl"
    log = JsonlEventLog(path)
    s0 = log.append(make_event(EventType.ATE))
    s1 = log.append(make_event(EventType.RESTED))
    assert (s0.seq, s1.seq) == (0, 1)

    # A second adapter over the same file resumes the sequence.
    log2 = JsonlEventLog(path)
    s2 = log2.append(make_event(EventType.WORKED))
    assert s2.seq == 2
    assert [e.seq for e in JsonlEventLog(path).read()] == [0, 1, 2]


def test_jsonl_read_from_seq_filters(tmp_path):
    path = tmp_path / "events.jsonl"
    log = JsonlEventLog(path)
    log.append_many([make_event(EventType.AGENT_MOVED, tick=i) for i in range(5)])
    tail = list(log.read(from_seq=2))
    assert [e.seq for e in tail] == [2, 3, 4]


# ---------------------------------------------------------------------------
# (d) replay_state_hashes
# ---------------------------------------------------------------------------

def test_replay_state_hashes_in_order():
    events = [
        make_event(EventType.SIM_STARTED),
        tick_completed(0, "hashA", {"tick": 0}),
        make_event(EventType.AGENT_MOVED, tick=1, payload={"to": [1, 1]}),
        tick_completed(1, "hashB", {"tick": 1}),
        tick_completed(2, "hashC", {"tick": 2}),
    ]
    assert replay_state_hashes(events) == ["hashA", "hashB", "hashC"]


def test_replay_state_hashes_empty_and_no_ticks():
    assert replay_state_hashes([]) == []
    assert replay_state_hashes([make_event(EventType.ATE)]) == []


def test_replay_state_hashes_through_a_log():
    log = InMemoryEventLog()
    log.append(make_event(EventType.SIM_STARTED))
    log.append(tick_completed(0, "h0", {"tick": 0}))
    log.append(tick_completed(1, "h1", {"tick": 1}))
    assert replay_state_hashes(log.read()) == ["h0", "h1"]


# ---------------------------------------------------------------------------
# (e) reconstruct_world_canonical
# ---------------------------------------------------------------------------

def test_reconstruct_world_at_tick():
    events = [
        tick_completed(0, "h0", {"tick": 0, "agents": {}}),
        tick_completed(1, "h1", {"tick": 1, "agents": {"alex": 1}}),
        tick_completed(2, "h2", {"tick": 2, "agents": {"alex": 2}}),
    ]
    assert reconstruct_world_canonical(events, at_tick=1) == {
        "tick": 1,
        "agents": {"alex": 1},
    }
    # at_tick below first completed tick -> nothing.
    assert reconstruct_world_canonical(events, at_tick=-1) is None
    # at_tick beyond last -> clamps to last completed snapshot.
    assert reconstruct_world_canonical(events, at_tick=99) == {
        "tick": 2,
        "agents": {"alex": 2},
    }


def test_reconstruct_world_latest_when_none():
    events = [
        tick_completed(0, "h0", {"tick": 0}),
        tick_completed(5, "h5", {"tick": 5}),
    ]
    assert reconstruct_world_canonical(events) == {"tick": 5}
    assert reconstruct_world_canonical([]) is None


# ---------------------------------------------------------------------------
# (f) LiveWorldReadModel + NarrativeReadModel
# ---------------------------------------------------------------------------

def test_live_world_read_model_updates():
    model = LiveWorldReadModel()
    events = [
        make_event(EventType.AGENT_MOVED, agent_id="alex", payload={"to": [2, 3]}),
        make_event(
            EventType.ACTIVITY_STARTED, agent_id="alex", payload={"activity": "eat"}
        ),
        make_event(EventType.MONEY_CHANGED, agent_id="alex", payload={"money": 100.0}),
        make_event(
            EventType.INTERACTION_STARTED, agent_id="alex", payload={"with": "bea"}
        ),
        make_event(EventType.AGENT_MOVED, agent_id="bea", payload={"to": [9, 9]}),
    ]
    for ev in events:
        model.apply(ev)

    state = model.state()
    assert state["alex"] == {
        "position": [2, 3],
        "current_activity": "eat",
        "money": 100.0,
        "interacting_with": "bea",
    }
    assert state["bea"]["position"] == [9, 9]

    # Latest-wins on a later move + interaction finishing.
    model.apply(make_event(EventType.AGENT_MOVED, agent_id="alex", payload={"to": [5, 5]}))
    model.apply(make_event(EventType.INTERACTION_FINISHED, agent_id="alex"))
    state2 = model.state()
    assert state2["alex"]["position"] == [5, 5]
    assert state2["alex"]["interacting_with"] is None


def test_live_world_read_model_ignores_unknown_and_copies():
    model = LiveWorldReadModel()
    model.apply(make_event(EventType.AGENT_MOVED, agent_id="alex", payload={"to": [1, 1]}))
    model.apply(make_event(EventType.NUDGE_APPLIED, payload={"foo": "bar"}))
    state = model.state()
    assert set(state) == {"alex"}
    # Returned state is a copy: mutating it does not corrupt the model.
    state["alex"]["position"] = [0, 0]
    assert model.state()["alex"]["position"] == [1, 1]


def test_narrative_read_model():
    model = NarrativeReadModel()
    events = [
        make_event(
            EventType.DIARY_WRITTEN,
            payload={"agent_id": "alex", "day": "Mon", "day_number": 0, "text": "good day"},
        ),
        make_event(
            EventType.DIARY_WRITTEN,
            payload={"agent_id": "bea", "day": "Mon", "day_number": 0, "text": "tiring"},
        ),
        make_event(
            EventType.DIARY_WRITTEN,
            payload={"agent_id": "alex", "day": "Tue", "day_number": 1, "text": "rainy"},
        ),
        make_event(
            EventType.STORY_COMPILED,
            payload={"day": "Mon", "day_number": 0, "text": "The town awoke."},
        ),
    ]
    for ev in events:
        model.apply(ev)

    assert model.diaries_for_day(0) == {"alex": "good day", "bea": "tiring"}
    assert model.diaries_for_day(1) == {"alex": "rainy"}
    assert model.diaries_for_day(99) == {}
    assert model.story_for_day(0) == "The town awoke."
    assert model.story_for_day(1) is None


def test_narrative_read_model_returns_copies():
    model = NarrativeReadModel()
    model.apply(
        make_event(
            EventType.DIARY_WRITTEN,
            payload={"agent_id": "alex", "day_number": 0, "text": "hi"},
        )
    )
    d = model.diaries_for_day(0)
    d["alex"] = "tampered"
    assert model.diaries_for_day(0) == {"alex": "hi"}


# ---------------------------------------------------------------------------
# (g) Hardening: explicit determinism + edge cases
# ---------------------------------------------------------------------------

def test_head_hash_equals_reference_chain():
    """head_hash must equal an independent hash_events fold of the same order."""
    evs = [
        make_event(EventType.AGENT_MOVED, tick=1, agent_id="alex"),
        make_event(EventType.ATE, tick=2, agent_id="alex"),
        make_event(EventType.WORKED, tick=3, agent_id="bea"),
    ]
    log = InMemoryEventLog()
    stamped = log.append_many(evs)
    # The reference chain folds the *stamped* events (seq-bearing) in order.
    assert log.head_hash == hash_events(stamped)


def test_two_logs_same_input_same_head_hash_repeatedly():
    """Determinism: building the same log twice yields the identical head hash."""
    evs = [make_event(EventType.AGENT_MOVED, tick=i, agent_id="a") for i in range(10)]

    def build() -> str:
        log = InMemoryEventLog()
        log.append_many(evs)
        return log.head_hash

    first = build()
    assert first == build()
    assert first == build()
    assert first != ""


def test_empty_log_reads_nothing_and_has_empty_head():
    log = InMemoryEventLog()
    assert len(log) == 0
    assert log.head_hash == ""
    assert list(log.read()) == []
    assert list(log.read(from_seq=0)) == []


def test_jsonl_empty_and_append_many_resumes(tmp_path):
    """A fresh JSONL log is empty; append_many resumes seq after existing lines."""
    path = tmp_path / "events.jsonl"
    log = JsonlEventLog(path)
    assert len(log) == 0
    assert list(log.read()) == []

    log.append(make_event(EventType.ATE))
    # A second batch via append_many must continue the sequence, not restart.
    stamped = log.append_many(
        [make_event(EventType.RESTED), make_event(EventType.WORKED)]
    )
    assert [e.seq for e in stamped] == [1, 2]
    assert [e.seq for e in JsonlEventLog(path).read()] == [0, 1, 2]


def test_jsonl_preserves_seq_field_on_disk(tmp_path):
    """The persisted seq is the stamped one, re-read verbatim (not recomputed)."""
    path = tmp_path / "events.jsonl"
    log = JsonlEventLog(path)
    log.append_many([make_event(EventType.AGENT_MOVED, tick=i) for i in range(3)])
    seqs = [e.seq for e in JsonlEventLog(path).read(from_seq=1)]
    assert seqs == [1, 2]


def test_bus_no_subscribers_is_a_noop():
    bus = InProcessEventBus()
    # Publishing with zero subscribers must not raise.
    bus.publish(make_event(EventType.SIM_STARTED))
    assert bus.subscriber_count == 0
    assert bus.error_count == 0


def test_bus_counts_multiple_handler_errors():
    bus = InProcessEventBus()
    seen: List[str] = []

    def boom(ev: Event) -> None:
        raise ValueError("nope")

    bus.subscribe(boom)
    bus.subscribe(lambda ev: seen.append("ok"))
    bus.subscribe(boom)
    bus.publish(make_event(EventType.TICK_COMPLETED))
    bus.publish(make_event(EventType.TICK_COMPLETED))
    # Two throwing handlers x two publishes = four swallowed errors.
    assert bus.error_count == 4
    assert seen == ["ok", "ok"]


def test_replay_skips_tick_completed_without_state_hash():
    events = [
        tick_completed(0, "h0", {"tick": 0}),
        # Malformed: TICK_COMPLETED with no state_hash entry -> skipped.
        make_event(EventType.TICK_COMPLETED, tick=1, payload={"snapshot": {}, "tick": 1}),
        tick_completed(2, "h2", {"tick": 2}),
    ]
    assert replay_state_hashes(events) == ["h0", "h2"]


def test_reconstruct_exact_tick_boundary():
    events = [
        tick_completed(0, "h0", {"tick": 0}),
        tick_completed(2, "h2", {"tick": 2}),
        tick_completed(4, "h4", {"tick": 4}),
    ]
    # at_tick falls between completed ticks -> latest completed <= at_tick.
    assert reconstruct_world_canonical(events, at_tick=3) == {"tick": 2}
    # Exact match.
    assert reconstruct_world_canonical(events, at_tick=4) == {"tick": 4}
    assert reconstruct_world_canonical(events, at_tick=0) == {"tick": 0}


def test_reconstruct_falls_back_to_event_tick_when_payload_tick_missing():
    """If a TICK_COMPLETED payload omits 'tick', the domain event.tick is used."""
    e = make_event(
        EventType.TICK_COMPLETED,
        tick=7,
        payload={"state_hash": "h7", "snapshot": {"v": 7}},  # no payload['tick']
    )
    assert reconstruct_world_canonical([e]) == {"v": 7}
    assert reconstruct_world_canonical([e], at_tick=7) == {"v": 7}
    assert reconstruct_world_canonical([e], at_tick=6) is None


def test_live_world_ignores_agentless_transitions():
    """Agent-keyed transitions without an agent_id must not create phantom rows."""
    model = LiveWorldReadModel()
    model.apply(make_event(EventType.AGENT_MOVED, payload={"to": [1, 1]}))  # no agent_id
    model.apply(make_event(EventType.MONEY_CHANGED, payload={"money": 5}))  # no agent_id
    assert model.state() == {}


def test_live_world_interaction_finished_before_started():
    """INTERACTION_FINISHED for an unseen agent just records a cleared partner."""
    model = LiveWorldReadModel()
    model.apply(make_event(EventType.INTERACTION_FINISHED, agent_id="alex"))
    assert model.state()["alex"]["interacting_with"] is None
