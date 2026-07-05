"""`python -m townsim` venv bootstrap: a bare system interpreter must hop
into <repo>/.venv instead of dying with ModuleNotFoundError."""
from __future__ import annotations

import sys
from pathlib import Path

import townsim.__main__ as entry


class TestCanaries:
    def test_all_dependencies_present_in_test_env(self):
        assert entry.missing_modules() == []

    def test_required_covers_every_townsim_subsystem(self):
        # cli/config/server/llm/templates each have a canary
        assert {"structlog", "yaml", "fastapi", "openai", "jinja2"} <= set(
            entry.REQUIRED_MODULES)


class TestVenvDiscovery:
    def test_no_venv_returns_none(self, tmp_path):
        assert entry.venv_python(tmp_path) is None

    def test_finds_windows_layout(self, tmp_path):
        exe = tmp_path / ".venv" / "Scripts" / "python.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"")
        assert entry.venv_python(tmp_path) == exe

    def test_finds_posix_layout(self, tmp_path):
        exe = tmp_path / ".venv" / "bin" / "python"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"")
        assert entry.venv_python(tmp_path) == exe

    def test_command_shape(self):
        cmd = entry.bootstrap_command(Path("v/python.exe"), ["serve", "--seed", "7"])
        assert cmd == [str(Path("v/python.exe")), "-m", "townsim", "serve", "--seed", "7"]


class TestMainDispatch:
    def test_deps_present_delegates_to_cli(self, monkeypatch):
        import townsim.cli
        monkeypatch.setattr(townsim.cli, "main", lambda argv=None: 42)
        assert entry.main(["serve"]) == 42

    def test_missing_deps_reexecs_into_venv(self, monkeypatch, tmp_path):
        fake_venv = tmp_path / "python.exe"
        fake_venv.write_bytes(b"")
        calls = {}

        def fake_reexec(python, argv):
            calls["cmd"] = (python, argv)
            return 7
        monkeypatch.setattr(entry, "missing_modules", lambda: ["structlog"])
        monkeypatch.setattr(entry, "venv_python", lambda root=None: fake_venv)
        monkeypatch.setattr(entry, "_reexec_into", fake_reexec)
        assert entry.main(["serve", "--seed", "1"]) == 7
        assert calls["cmd"] == (fake_venv, ["serve", "--seed", "1"])

    def test_guard_env_prevents_reexec_loop(self, monkeypatch, tmp_path, capsys):
        fake_venv = tmp_path / "python.exe"
        fake_venv.write_bytes(b"")
        monkeypatch.setattr(entry, "missing_modules", lambda: ["structlog"])
        monkeypatch.setattr(entry, "venv_python", lambda root=None: fake_venv)
        monkeypatch.setenv(entry.BOOTSTRAP_GUARD, "1")
        assert entry.main(["serve"]) == 1
        err = capsys.readouterr().err
        assert "missing required packages" in err and "structlog" in err

    def test_no_venv_prints_setup_help(self, monkeypatch, capsys):
        monkeypatch.setattr(entry, "missing_modules", lambda: ["structlog", "fastapi"])
        monkeypatch.setattr(entry, "venv_python", lambda root=None: None)
        assert entry.main(["serve"]) == 1
        err = capsys.readouterr().err
        assert "python -m venv .venv" in err
        assert "requirements.txt" in err

    def test_current_interpreter_is_the_venv_no_loop(self, monkeypatch, capsys):
        monkeypatch.setattr(entry, "missing_modules", lambda: ["structlog"])
        monkeypatch.setattr(entry, "venv_python",
                            lambda root=None: Path(sys.executable))
        assert entry.main(["serve"]) == 1   # broken venv: report, don't re-exec self
        assert "missing required packages" in capsys.readouterr().err
