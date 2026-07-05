from __future__ import annotations

import pytest

from townsim.config.models import SimConfig


@pytest.fixture()
def cfg(tmp_path) -> SimConfig:
    config = SimConfig()
    config.kernel.seed = 1234
    config.kernel.ticks_per_second = 0
    config.kernel.strict_narrative_sync = True
    config.llm.provider = "fake"
    config.paths.runs_dir = tmp_path / "runs"
    return config
