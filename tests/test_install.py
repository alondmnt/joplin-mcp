"""Tests for src/joplin_mcp/install.py and the top-level install.py shim.

Covers the consolidated install runner that replaces the old trio of
install.py / install_embedded.py / src install.py-with-cwd-bridge.
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from joplin_mcp import install


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestConfigPath:
    def test_pip_mode_writes_to_home(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            assert install._config_path(is_development=False) == (
                tmp_path / ".joplin-mcp.json"
            )

    def test_dev_mode_writes_to_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert install._config_path(is_development=True) == (
            tmp_path / "joplin-mcp.json"
        )


class TestWelcomeMessage:
    def test_pip_and_dev_messages_differ(self):
        pip = install._welcome_message(is_development=False)
        dev = install._welcome_message(is_development=True)
        assert pip != dev
        assert "pip install" in pip
        assert "set up" in dev


class TestMainRoutesFlag:
    """``main`` must forward ``is_development`` and the matching welcome
    string to ``run_installation_process`` -- this is what differentiates
    the pip and dev install paths."""

    def _run_main(self, *, is_development, monkeypatch):
        captured = {}

        def fake_run(*, config_path_resolver, is_development, welcome_message):
            captured["resolver"] = config_path_resolver
            captured["is_development"] = is_development
            captured["welcome_message"] = welcome_message
            return 0

        monkeypatch.setattr(install, "run_installation_process", fake_run)
        assert install.main(is_development=is_development) == 0
        return captured

    def test_pip_path(self, monkeypatch):
        captured = self._run_main(is_development=False, monkeypatch=monkeypatch)
        assert captured["is_development"] is False
        assert "pip install" in captured["welcome_message"]
        assert callable(captured["resolver"])

    def test_dev_path(self, monkeypatch):
        captured = self._run_main(is_development=True, monkeypatch=monkeypatch)
        assert captured["is_development"] is True
        assert "set up" in captured["welcome_message"]
        assert callable(captured["resolver"])

    def test_default_is_pip_mode(self, monkeypatch):
        # Both the console script (joplin-mcp-install) and `python -m
        # joplin_mcp.install` call main() with no args -- they must default
        # to pip mode.
        captured = {}
        monkeypatch.setattr(
            install,
            "run_installation_process",
            lambda **kw: captured.update(kw) or 0,
        )
        install.main()
        assert captured["is_development"] is False


class TestTopLevelShim:
    """The top-level install.py used to call non-existent JoplinMCPConfig
    methods; importing it crashed. This test catches a regression."""

    def test_top_level_install_imports_and_exposes_main(self):
        shim_path = REPO_ROOT / "install.py"
        assert shim_path.exists(), "top-level install.py missing"

        spec = importlib.util.spec_from_file_location(
            "_top_level_install_smoke", shim_path
        )
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            assert module.main is install.main, (
                "top-level shim should delegate to joplin_mcp.install.main"
            )
        finally:
            sys.modules.pop("_top_level_install_smoke", None)
