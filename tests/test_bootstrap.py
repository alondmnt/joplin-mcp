"""Tests for the cross-platform dev-install bootstrap.

bootstrap.py lives at the repo root and isn't importable as a package
module, so we load it via importlib. We exercise the pure helpers
(_in_venv, _venv_python, argparse). The subprocess-driven steps
(venv creation, pip install, re-exec) aren't unit-tested -- they wrap
well-understood stdlib calls and would require mocking the world to
cover usefully.
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def bootstrap():
    """Load bootstrap.py as a module so its functions are addressable."""
    path = REPO_ROOT / "bootstrap.py"
    assert path.exists(), "bootstrap.py missing at repo root"
    spec = importlib.util.spec_from_file_location("_bootstrap_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("_bootstrap_under_test", None)


class TestArgparse:
    def test_default(self, bootstrap):
        args = bootstrap.argparse.ArgumentParser  # confirms argparse imported
        assert args is not None

    def test_no_venv_flag_defaults_false(self, bootstrap, monkeypatch):
        # Build a fresh parser via main()'s path: easiest is to call
        # the public entry point with our own argv and stop before any
        # subprocess work runs.
        monkeypatch.chdir(REPO_ROOT)
        called = {}

        def fake_install(repo_root):
            called["pip"] = True

        def fake_ensure_venv(repo_root):
            called["venv"] = True

        def fake_run_installer(*, is_development):
            called["installer_dev"] = is_development
            return 0

        monkeypatch.setattr(bootstrap, "_pip_install_editable", fake_install)
        monkeypatch.setattr(bootstrap, "_ensure_venv", fake_ensure_venv)
        # Patch the installer import target lazily by injecting into sys.modules
        import joplin_mcp.install as installer_module

        monkeypatch.setattr(installer_module, "main", fake_run_installer)

        assert bootstrap.main([]) == 0
        assert called == {"venv": True, "pip": True, "installer_dev": True}

    def test_no_venv_flag_skips_venv_prompt(self, bootstrap, monkeypatch):
        monkeypatch.chdir(REPO_ROOT)
        called = {}

        monkeypatch.setattr(
            bootstrap, "_pip_install_editable", lambda r: called.setdefault("pip", True)
        )
        monkeypatch.setattr(
            bootstrap,
            "_ensure_venv",
            lambda r: called.setdefault("venv", True),
        )
        import joplin_mcp.install as installer_module

        monkeypatch.setattr(installer_module, "main", lambda *, is_development: 0)

        assert bootstrap.main(["--no-venv"]) == 0
        assert "pip" in called
        assert "venv" not in called

    def test_wrong_directory_errors(self, bootstrap, monkeypatch, tmp_path, capsys):
        # Move REPO_ROOT view to an empty dir so the pyproject.toml check fails.
        monkeypatch.setattr(bootstrap, "REPO_ROOT", tmp_path)
        # Block any further work so a failure here doesn't escape.
        monkeypatch.setattr(bootstrap, "_ensure_venv", lambda r: None)
        monkeypatch.setattr(bootstrap, "_pip_install_editable", lambda r: None)

        assert bootstrap.main(["--no-venv"]) == 1
        err = capsys.readouterr().err
        assert "pyproject.toml" in err or "repo root" in err


class TestVenvHelpers:
    def test_venv_python_path_posix(self, bootstrap, monkeypatch, tmp_path):
        monkeypatch.setattr(os, "name", "posix")
        assert (
            bootstrap._venv_python(tmp_path) == tmp_path / "bin" / "python"
        )

    def test_venv_python_path_windows(self, bootstrap, monkeypatch, tmp_path):
        monkeypatch.setattr(os, "name", "nt")
        assert (
            bootstrap._venv_python(tmp_path)
            == tmp_path / "Scripts" / "python.exe"
        )

    def test_in_venv_returns_bool(self, bootstrap):
        assert isinstance(bootstrap._in_venv(), bool)
