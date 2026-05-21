"""Tests for src/joplin_mcp/ui_integration.py.

Covers the parts of the install-time UI we can exercise without spawning a
real terminal: prompt branching (via patched ``input``) and configuration
persistence (via the file-system).
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from joplin_mcp.config import JoplinMCPConfig
from joplin_mcp.ui_integration import (
    create_config_interactively,
    get_notebook_allowlist_settings,
    save_config_to_path,
)


class TestSaveConfigToPathAllowlist:
    """``save_config_to_path`` must round-trip ``notebook_allowlist``.

    Before this was fixed the function silently dropped the field on save,
    so any config built with an allowlist in memory would lose it the next
    time it hit disk.
    """

    def _write_and_reload(self, cfg: JoplinMCPConfig) -> tuple[dict, JoplinMCPConfig]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "joplin-mcp.json"
            save_config_to_path(cfg, path, include_token=False)
            raw = json.loads(path.read_text())
            reloaded = JoplinMCPConfig.from_file(path)
        return raw, reloaded

    def test_unrestricted_config_omits_allowlist_key(self):
        cfg = JoplinMCPConfig(token="t", notebook_allowlist=None)
        raw, reloaded = self._write_and_reload(cfg)

        assert "notebook_allowlist" not in raw
        assert reloaded.has_notebook_allowlist is False

    def test_populated_allowlist_persists(self):
        cfg = JoplinMCPConfig(token="t", notebook_allowlist=["work", "projects"])
        raw, reloaded = self._write_and_reload(cfg)

        assert raw["notebook_allowlist"] == ["work", "projects"]
        assert reloaded.has_notebook_allowlist is True
        assert reloaded.notebook_allowlist == ["work", "projects"]

    def test_empty_allowlist_persists_as_empty_list(self):
        # An empty list is "deny all" -- distinct from None ("allow all").
        # The installer doesn't produce this state, but the file loader does,
        # so the save path must preserve the distinction.
        cfg = JoplinMCPConfig(token="t", notebook_allowlist=[])
        raw, reloaded = self._write_and_reload(cfg)

        assert raw["notebook_allowlist"] == []
        assert reloaded.has_notebook_allowlist is True
        assert reloaded.notebook_allowlist == []


class TestGetNotebookAllowlistSettings:
    """Branches of the install-time allowlist prompt."""

    @pytest.mark.parametrize("decline_input", ["", "n", "no", "N", "NO"])
    def test_decline_returns_none(self, decline_input):
        with patch("builtins.input", side_effect=[decline_input]):
            assert get_notebook_allowlist_settings() is None

    def test_opt_in_single_entry(self):
        with patch("builtins.input", side_effect=["y", "work"]):
            assert get_notebook_allowlist_settings() == ["work"]

    def test_opt_in_multiple_entries_strips_whitespace_and_drops_blanks(self):
        with patch(
            "builtins.input",
            side_effect=["y", "  work , projects ,  ,reading "],
        ):
            assert get_notebook_allowlist_settings() == [
                "work",
                "projects",
                "reading",
            ]

    def test_opt_in_blank_input_re_prompts_until_non_empty(self):
        # The whole point of the verification: opting in must not be allowed
        # to produce an empty allowlist (which would lock out every notebook).
        with patch(
            "builtins.input",
            side_effect=["y", "", "   ", ",,,", "finally"],
        ):
            assert get_notebook_allowlist_settings() == ["finally"]

    def test_first_prompt_rejects_garbage_then_accepts_decline(self):
        with patch("builtins.input", side_effect=["huh?", "n"]):
            assert get_notebook_allowlist_settings() is None


class TestCreateConfigInteractivelyAllowlistWiring:
    """The ``include_notebook_allowlist`` flag must gate the prompt and the
    resulting config value should land on ``JoplinMCPConfig`` unchanged."""

    def test_include_false_skips_prompt_and_leaves_unrestricted(self):
        # No input side-effect: if the prompt fires, the test fails with
        # StopIteration. That's the assertion that we skipped it.
        with patch("builtins.input", side_effect=[]):
            cfg = create_config_interactively(
                token="dummy-token-1234567890",
                include_permissions=False,
                include_content_privacy=False,
                include_notebook_allowlist=False,
            )
        assert cfg.has_notebook_allowlist is False

    def test_include_true_decline_path(self):
        with patch("builtins.input", side_effect=["n"]):
            cfg = create_config_interactively(
                token="dummy-token-1234567890",
                include_permissions=False,
                include_content_privacy=False,
                include_notebook_allowlist=True,
            )
        assert cfg.has_notebook_allowlist is False

    def test_include_true_opt_in_path_flows_through_to_config(self):
        with patch("builtins.input", side_effect=["y", "work, journal"]):
            cfg = create_config_interactively(
                token="dummy-token-1234567890",
                include_permissions=False,
                include_content_privacy=False,
                include_notebook_allowlist=True,
            )
        assert cfg.has_notebook_allowlist is True
        assert cfg.notebook_allowlist == ["work", "journal"]
