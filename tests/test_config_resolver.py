"""Tests for the config resolver (get_config / set_config).

The resolver mediates all reads of the live JoplinMCPConfig; set_config
replaces wholesale, not by merge.
"""

import pytest

from joplin_mcp.config import (
    JoplinMCPConfig,
    get_config,
    set_config,
)


@pytest.fixture(autouse=True)
def _restore_config():
    """Snapshot the live config before each test and restore on exit.

    Tests in this file mutate a module global; without this fixture they
    would leak state into one another (and into other tests in the suite).
    """
    snapshot = get_config()
    try:
        yield
    finally:
        set_config(snapshot)


class TestConfigResolver:
    """Interface tests for joplin_mcp.config.get_config / set_config."""

    def test_get_config_returns_eager_load(self):
        """After import, get_config returns a JoplinMCPConfig instance."""
        cfg = get_config()
        assert isinstance(cfg, JoplinMCPConfig)

    def test_set_config_replaces_wholesale(self):
        """set_config replaces the live config; fields from the previous
        config must not persist (the wholesale-replace invariant)."""
        with_allowlist = JoplinMCPConfig(
            token="test-token", notebook_allowlist=["AI"]
        )
        set_config(with_allowlist)
        assert get_config().notebook_allowlist == ["AI"]
        assert get_config().has_notebook_allowlist is True

        # Replace with a config that has no allowlist. The previous
        # allowlist must NOT carry over.
        plain = JoplinMCPConfig(token="test-token")
        set_config(plain)
        assert get_config().notebook_allowlist == JoplinMCPConfig.ALLOW_ALL
        assert get_config().has_notebook_allowlist is False
