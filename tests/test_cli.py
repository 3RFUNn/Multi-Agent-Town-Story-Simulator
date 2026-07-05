"""CLI entry points: `serve` must tell the user WHERE the dashboard is."""
from __future__ import annotations

import uvicorn

import townsim.server.app as server_app
from townsim import cli


class TestDashboardUrl:
    def test_plain_host(self):
        assert cli._dashboard_url("127.0.0.1", 8000) == "http://127.0.0.1:8000"

    def test_bind_all_becomes_loopback(self):
        assert cli._dashboard_url("0.0.0.0", 9000) == "http://127.0.0.1:9000"
        assert cli._dashboard_url("::", 9000) == "http://127.0.0.1:9000"
        assert cli._dashboard_url("", 8000) == "http://127.0.0.1:8000"

    def test_named_host_kept(self):
        assert cli._dashboard_url("townsim.local", 80) == "http://townsim.local:80"


class TestServePrintsUrl:
    def test_cmd_serve_prints_dashboard_url(self, monkeypatch, capsys, cfg):
        served = {}
        monkeypatch.setattr(cli, "load_config", lambda path=None: cfg)
        monkeypatch.setattr(server_app, "create_app", lambda c: "stub-app")
        monkeypatch.setattr(uvicorn, "run",
                            lambda app, **kw: served.update(app=app, **kw))
        rc = cli.main(["serve", "--provider", "fake"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "http://127.0.0.1:8000" in out, "terminal must print the dashboard URL"
        assert served["app"] == "stub-app"
        assert served["host"] == "127.0.0.1" and served["port"] == 8000
