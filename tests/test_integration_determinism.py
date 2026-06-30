"""The headline integration property: bit-reproducible, event-sourced runs.

This file is the CI reproducibility gate. It proves the claim the prototype could
not make: two independent runs of the same seed produce an identical per-tick
``state_hash`` chain, and the run replays exactly from its event log.
"""

import pytest

from matss.sim import build_engine
from matss.eventlog import (
    InMemoryEventLog,
    JsonlEventLog,
    reconstruct_world_canonical,
    replay_state_hashes,
)


def test_same_seed_identical_state_hash_chain():
    a = build_engine(seed=42).run(500)
    b = build_engine(seed=42).run(500)
    assert a == b
    assert len(a) == 501  # 500 ticks + the initial baseline frame


def test_different_seed_diverges():
    a = build_engine(seed=42).run(500)
    b = build_engine(seed=43).run(500)
    assert a != b


def test_replay_state_hashes_matches_live_chain():
    engine = build_engine(seed=11)
    live = engine.run(600)
    replayed = replay_state_hashes(list(engine.log.read()))
    assert replayed == live


def test_reconstructed_snapshot_matches_live_world():
    engine = build_engine(seed=5)
    engine.run(600)
    recon = reconstruct_world_canonical(list(engine.log.read()))
    assert recon == engine.world.to_canonical()


def test_jsonl_persisted_log_round_trips_and_reproduces(tmp_path):
    path = str(tmp_path / "run.jsonl")
    # Run A persists to JSONL.
    log = JsonlEventLog(path)
    a = build_engine(seed=99, event_log=log).run(400)
    # Reload the persisted log and verify its chain matches.
    reloaded = JsonlEventLog(path)
    replayed = replay_state_hashes(list(reloaded.read()))
    assert replayed == a
    # A completely fresh run of the same seed reproduces the same chain.
    b = build_engine(seed=99).run(400)
    assert b == a


def test_determinism_holds_across_a_day_boundary_with_narrative():
    a = build_engine(seed=21).run_until_day(2)
    b = build_engine(seed=21).run_until_day(2)
    assert a == b
    # Narrative was produced and did NOT perturb the Tier-1 hash chain.
    a_stories = [e for e in build_engine(seed=21).run_until_day(2)]  # smoke
    eng = build_engine(seed=21)
    eng.run_until_day(2)
    stories = [e for e in eng.log.read() if e.type == "story_compiled"]
    assert len(stories) == 2


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 1234])
def test_reproducible_for_many_seeds(seed):
    assert build_engine(seed=seed).run(200) == build_engine(seed=seed).run(200)
