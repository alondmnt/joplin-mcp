"""Tests for src/joplin_mcp/install.py.

Covers the consolidated install runner. Earlier this module also had to
police a broken top-level install.py shim and a separate
install_embedded.py; both are gone now and the runner is reached only
via the pip console script (``joplin-mcp-install``) or
``python -m joplin_mcp.install [--dev]``.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from joplin_mcp import install


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


class TestParseArgs:
    """argparse wiring for ``python -m joplin_mcp.install [--dev]``."""

    def test_no_args_defaults_to_pip_mode(self):
        args = install._parse_args([])
        assert args.dev is False

    def test_dev_flag_flips_to_development_mode(self):
        args = install._parse_args(["--dev"])
        assert args.dev is True

    def test_unknown_flag_exits(self):
        with pytest.raises(SystemExit):
            install._parse_args(["--nope"])
