"""python -m townsim — auto-bootstraps into the project's .venv.

Launching with a bare system interpreter (no deps installed) is the most
common first-run mistake. Instead of dying with ModuleNotFoundError, this
entry point detects missing dependencies BEFORE importing anything heavy
and transparently re-launches the same command inside <repo>/.venv when
one exists — so `python -m townsim serve` works from the project root with
any Python. Without a venv it prints the two setup commands.

This module must import nothing beyond the standard library at top level
(townsim/__init__.py is dependency-free too).
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Cheap canaries (find_spec — no actual imports) covering every subsystem's
# third-party imports; if all resolve, the interpreter can run townsim.
REQUIRED_MODULES = (
    "structlog", "yaml", "pydantic", "pydantic_settings", "fastapi",
    "uvicorn", "jinja2", "numpy", "tenacity", "openai", "httpx",
)

# Set in the child environment on re-exec; if deps are STILL missing then,
# the venv itself is broken and we must not loop.
BOOTSTRAP_GUARD = "TOWNSIM_BOOTSTRAPPED"


def missing_modules() -> list[str]:
    return [name for name in REQUIRED_MODULES
            if importlib.util.find_spec(name) is None]


def venv_python(root: Path = PROJECT_ROOT) -> Path | None:
    """The project venv's interpreter, if a venv exists."""
    for candidate in (root / ".venv" / "Scripts" / "python.exe",   # Windows
                      root / ".venv" / "bin" / "python"):          # POSIX
        if candidate.exists():
            return candidate
    return None


def bootstrap_command(python: Path, argv: list[str]) -> list[str]:
    return [str(python), "-m", "townsim", *argv]


def _reexec_into(python: Path, argv: list[str]) -> int:
    """Run the same command in the venv interpreter; forward its exit code.
    On Ctrl+C the child (e.g. uvicorn) gets the signal too — give it time
    to shut down gracefully instead of killing it or racing its output."""
    env = dict(os.environ)
    env[BOOTSTRAP_GUARD] = "1"
    # The child must resolve the SAME townsim package this process found,
    # regardless of the caller's working directory.
    env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(bootstrap_command(python, argv), env=env)
    try:
        return proc.wait()
    except KeyboardInterrupt:
        try:
            return proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.terminate()
            return 130


def _setup_help(missing: list[str]) -> str:
    pip_win = r".venv\Scripts\pip install -r requirements.txt"
    pip_posix = ".venv/bin/pip install -r requirements.txt"
    return (
        f"townsim: this Python ({sys.executable}) is missing required packages: "
        f"{', '.join(missing)}\n"
        "Set up the environment once, from the project root:\n"
        "  python -m venv .venv\n"
        f"  {pip_win if os.name == 'nt' else pip_posix}\n"
        "Then re-run your command — `python -m townsim ...` finds .venv automatically."
    )


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    missing = missing_modules()
    if missing:
        venv = venv_python()
        current = Path(sys.executable).resolve()
        if (venv is not None and venv.resolve() != current
                and not os.environ.get(BOOTSTRAP_GUARD)):
            return _reexec_into(venv, argv)
        print(_setup_help(missing), file=sys.stderr)
        return 1
    from townsim.cli import main as cli_main
    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
