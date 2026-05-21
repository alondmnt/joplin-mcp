"""Tests for the cross-platform dev-install bootstrap.

bootstrap.py lives at the repo root and isn't importable as a package
module, so we load it via importlib. We exercise the pure helpers
(_in_venv, _venv_python, argparse routing) and a few key branches of
main() with the subprocess-driven steps mocked out. The real subprocess
work (venv creation, pip install, re-exec) wraps well-understood stdlib
calls and is left to manual run validation.
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


@pytest.fixture
def stubbed_pipeline(bootstrap, monkeypatch):
    """Replace the side-effectful steps of bootstrap.main() with recorders.

    Yields a dict that each fake writes into, so tests can assert exactly
    which steps ran and what they were called with.
    """
    called: dict = {}

    def record_venv(repo_root):
        called["venv"] = repo_root

    def record_pip(repo_root):
        called["pip"] = repo_root

    def record_installer(*, is_development):
        called["installer_dev"] = is_development
        return 0

    monkeypatch.setattr(bootstrap, "_ensure_venv", record_venv)
    monkeypatch.setattr(bootstrap, "_pip_install_editable", record_pip)

    import joplin_mcp.install as installer_module

    monkeypatch.setattr(installer_module, "main", record_installer)

    yield called


class TestMainRouting:
    """main()'s argv routes which side-effectful steps fire and what flag
    flows through to the canonical installer."""

    def test_default_invocation_runs_venv_then_pip_then_installer(
        self, bootstrap, stubbed_pipeline, monkeypatch
    ):
        monkeypatch.chdir(REPO_ROOT)
        assert bootstrap.main([]) == 0
        assert set(stubbed_pipeline) == {"venv", "pip", "installer_dev"}
        assert stubbed_pipeline["installer_dev"] is True

    def test_no_venv_flag_skips_venv_step(
        self, bootstrap, stubbed_pipeline, monkeypatch
    ):
        monkeypatch.chdir(REPO_ROOT)
        assert bootstrap.main(["--no-venv"]) == 0
        assert "venv" not in stubbed_pipeline
        assert "pip" in stubbed_pipeline
        assert stubbed_pipeline["installer_dev"] is True

    def test_wrong_directory_errors_before_any_side_effects(
        self, bootstrap, monkeypatch, tmp_path, capsys
    ):
        # Point REPO_ROOT at an empty dir; the pyproject check should fail
        # and main() should return 1 before invoking any pipeline step.
        # No stubbing of _ensure_venv / _pip_install_editable here -- if the
        # early return regresses, the real subprocess calls would fire and
        # blow the test up with a clearer signal than a missing assertion.
        monkeypatch.setattr(bootstrap, "REPO_ROOT", tmp_path)

        assert bootstrap.main(["--no-venv"]) == 1
        assert "repo root" in capsys.readouterr().err

    def test_unknown_flag_exits(self, bootstrap):
        with pytest.raises(SystemExit):
            bootstrap.main(["--bogus"])


class TestVenvHelpers:
    def test_venv_python_path_posix(self, bootstrap, monkeypatch, tmp_path):
        monkeypatch.setattr(os, "name", "posix")
        assert bootstrap._venv_python(tmp_path) == tmp_path / "bin" / "python"

    def test_venv_python_path_windows(self, bootstrap, monkeypatch, tmp_path):
        monkeypatch.setattr(os, "name", "nt")
        assert (
            bootstrap._venv_python(tmp_path)
            == tmp_path / "Scripts" / "python.exe"
        )

    def test_in_venv_returns_bool(self, bootstrap):
        assert isinstance(bootstrap._in_venv(), bool)


class TestEnsureVenvBrokenVenvFallback:
    """When ./venv exists but its interpreter is missing, _ensure_venv must
    NOT silently re-exec into a broken path -- it should warn and fall
    through to the regular create-a-venv prompt."""

    def test_existing_venv_without_python_warns_and_prompts(
        self, bootstrap, monkeypatch, tmp_path, capsys
    ):
        # Force "not in a venv" so we exercise the fallback branch.
        monkeypatch.setattr(bootstrap, "_in_venv", lambda: False)

        # Create venv/ but NOT venv/bin/python -- the stale-checkout case.
        venv_dir = tmp_path / "venv"
        venv_dir.mkdir()

        reexec_calls: list = []
        monkeypatch.setattr(
            bootstrap, "_reexec_in", lambda p: reexec_calls.append(p)
        )

        # Decline the venv-creation prompt so the function returns cleanly.
        monkeypatch.setattr("builtins.input", lambda *_: "n")

        bootstrap._ensure_venv(tmp_path)

        assert reexec_calls == [], "must not re-exec into a venv with no python"
        assert "missing" in capsys.readouterr().out.lower()

    def test_existing_venv_with_python_reexecs(
        self, bootstrap, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(bootstrap, "_in_venv", lambda: False)

        venv_dir = tmp_path / "venv"
        bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
        bin_dir.mkdir(parents=True)
        python_name = "python.exe" if os.name == "nt" else "python"
        venv_python = bin_dir / python_name
        venv_python.write_text("")  # any file is enough for is_file()

        reexec_calls: list = []
        monkeypatch.setattr(
            bootstrap, "_reexec_in", lambda p: reexec_calls.append(p)
        )

        bootstrap._ensure_venv(tmp_path)

        assert reexec_calls == [venv_python]
