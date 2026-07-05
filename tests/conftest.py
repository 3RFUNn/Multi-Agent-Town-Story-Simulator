from __future__ import annotations

import os

import pytest

from townsim.config.models import SimConfig


@pytest.fixture(autouse=True)
def _isolate_townsim_env(monkeypatch):
    """R25: ambient TOWNSIM_* variables must never leak into tests."""
    for key in list(os.environ):
        if key.startswith("TOWNSIM_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture()
def cfg(tmp_path) -> SimConfig:
    config = SimConfig()
    config.kernel.seed = 1234
    config.kernel.ticks_per_second = 0
    config.kernel.strict_narrative_sync = True
    config.llm.provider = "fake"
    config.paths.runs_dir = tmp_path / "runs"
    return config
