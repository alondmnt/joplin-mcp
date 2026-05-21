#!/usr/bin/env python3
"""Bootstrap the joplin-mcp dev install (cross-platform).

Usage:
    python bootstrap.py            # offers to create ./venv if none is active
    python bootstrap.py --no-venv  # use whichever Python invoked this script

Replaces the previous install.sh / install.bat pair. The steps are:

1. Make sure we're in the repo root (pyproject.toml present).
2. If no virtual environment is active and no ``venv/`` exists, prompt to
   create one. If ``venv/`` already exists, re-exec into it.
3. ``pip install -e .`` so ``joplin_mcp`` is importable.
4. Hand off to ``joplin_mcp.install.main(is_development=True)`` for the
   interactive setup (token, permissions, allowlist, chat-interface
   integration, connection test).
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent


def _in_venv() -> bool:
    """True if the current interpreter is already inside a virtualenv."""
    return bool(os.environ.get("VIRTUAL_ENV")) or sys.prefix != sys.base_prefix


def _venv_python(venv_dir: Path) -> Path:
    """Path to the python executable inside ``venv_dir`` for this platform."""
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _reexec_in(python: Path) -> None:
    """Re-run this script under ``python`` and propagate its exit code.

    We use subprocess rather than os.execv for portability -- execv has
    quirks on Windows where the parent shell may not see the new exit
    code cleanly.
    """
    result = subprocess.run([str(python), str(Path(__file__).resolve()), *sys.argv[1:]])
    sys.exit(result.returncode)


def _ensure_venv(repo_root: Path) -> None:
    """Ask about creating a venv, then re-exec inside it.

    No-ops if we're already in a venv. If ``venv/`` already exists but is
    not active, re-exec into it without asking (the user clearly intended
    to use it).
    """
    if _in_venv():
        return

    venv_dir = repo_root / "venv"
    if venv_dir.exists():
        _reexec_in(_venv_python(venv_dir))

    answer = input(
        "No virtual environment detected. Create one at ./venv? (y/n) [recommended]: "
    ).strip().lower()
    if answer not in ("y", "yes", ""):
        print("Continuing with the current Python interpreter.")
        return

    print(f"Creating virtual environment at {venv_dir} ...")
    subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
    _reexec_in(_venv_python(venv_dir))


def _pip_install_editable(repo_root: Path) -> None:
    print("Installing joplin-mcp (editable) ...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-e", str(repo_root)]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python bootstrap.py",
        description="Bootstrap the joplin-mcp dev install.",
    )
    parser.add_argument(
        "--no-venv",
        action="store_true",
        help="Skip the venv prompt; install into whichever Python is active.",
    )
    args = parser.parse_args(argv)

    if not (REPO_ROOT / "pyproject.toml").exists():
        print("ERROR: run bootstrap.py from the joplin-mcp repo root.", file=sys.stderr)
        return 1

    if not args.no_venv:
        _ensure_venv(REPO_ROOT)

    _pip_install_editable(REPO_ROOT)

    # joplin_mcp is now importable -- hand off to the interactive installer.
    from joplin_mcp.install import main as run_installer

    return run_installer(is_development=True)


if __name__ == "__main__":
    sys.exit(main())
