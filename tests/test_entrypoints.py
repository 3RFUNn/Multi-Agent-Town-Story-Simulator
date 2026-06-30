"""Cover the headless runner + replay entrypoints (offline, no CLI/network)."""

import json

from matss.app import runner, replay


def test_runner_run_ticks_prints_summary(capsys):
    rc = runner.run(seed=42, ticks=120)
    assert rc == 0
    out = capsys.readouterr().out
    assert "MATSS v2 — headless run complete" in out
    assert "final state_hash:" in out


def test_runner_run_days(capsys):
    rc = runner.run(seed=7, days=1)
    assert rc == 0
    out = capsys.readouterr().out
    assert "town stories:     1" in out


def test_runner_persists_jsonl_and_replay_verifies(tmp_path, capsys):
    path = str(tmp_path / "run.jsonl")
    rc = runner.run(seed=123, ticks=200, jsonl=path)
    assert rc == 0
    # The file holds valid JSON lines.
    with open(path) as f:
        lines = [json.loads(line) for line in f if line.strip()]
    assert lines and all("type" in d for d in lines)

    # Replay verifies a fresh same-seed run reproduces the chain (exit 0).
    capsys.readouterr()  # clear
    rc2 = replay.replay(path, verify_seed=123)
    assert rc2 == 0
    out = capsys.readouterr().out
    assert "MATCHES the logged run" in out


def test_replay_detects_mismatched_seed(tmp_path):
    path = str(tmp_path / "run.jsonl")
    runner.run(seed=1, ticks=150, jsonl=path)
    # Verifying against a different seed must fail the reproducibility check.
    rc = replay.replay(path, verify_seed=2)
    assert rc == 1


def test_runner_main_argparse_default(capsys):
    rc = runner.main(["--seed", "5", "--ticks", "60"])
    assert rc == 0
    assert "seed:               5" in capsys.readouterr().out
