"""Server lifespan: teardown (narrative stop, intent flush, journal close)
must run on EVERY shutdown path — clean stop AND crashed simulation."""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from townsim.server.app import create_app


@pytest.fixture()
def server_cfg(cfg):
    cfg.kernel.ticks_per_second = 20   # gentle pacing so tests don't spin a core
    return cfg


class TestLifespanTeardown:
    def test_clean_shutdown_closes_journal(self, server_cfg):
        app = create_app(server_cfg)
        with TestClient(app) as client:
            state = client.get("/api/state").json()
            assert len(state["agents"]) == 6
        kernel = app.state.kernel
        assert kernel.journal._file.closed, "clean shutdown must close the journal"

    def test_crashed_sim_still_tears_down(self, server_cfg, monkeypatch):
        app = create_app(server_cfg)

        def boom():
            raise RuntimeError("intentional crash (lifecycle test)")

        # The context exit must NOT raise (the crash is logged, not propagated)
        # and the journal must still be closed by the lifespan finally.
        with TestClient(app) as client:
            kernel = app.state.kernel
            monkeypatch.setattr(kernel, "step", boom)
            client.get("/api/state")   # keep the loop turning until it crashes
        assert kernel.journal._file.closed, "crash path must still close the journal"
