"""Tests for src/joplin_mcp/ui_integration.py.

Covers the parts of the install-time UI we can exercise without spawning a
real terminal: prompt branching (via patched ``input``) and configuration
persistence (via the file-system).
"""

import json
import tempfile
from pathlib import Path

from joplin_mcp.config import JoplinMCPConfig
from joplin_mcp.ui_integration import save_config_to_path


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
