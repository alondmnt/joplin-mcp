"""Tests for notebook allowlist configuration parsing."""

import json
import os
from unittest.mock import patch

import pytest
import yaml

from joplin_mcp.config import JoplinMCPConfig


class TestNotebookAllowlistConfig:
    """Test notebook allowlist configuration loading from various sources."""

    def test_allowlist_parses_from_json_config(self, tmp_path):
        """Test that notebook_allowlist is correctly parsed from a JSON config file."""
        config_data = {
            "token": "test-token-1234567890",
            "notebook_allowlist": ["Projects/*", "Work/**", "!Work/Secret"],
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        config = JoplinMCPConfig.from_file(config_file)

        assert config.notebook_allowlist == ["Projects/*", "Work/**", "!Work/Secret"]

    def test_allowlist_parses_from_yaml_config(self, tmp_path):
        """Test that notebook_allowlist is correctly parsed from a YAML config file."""
        config_data = {
            "token": "test-token-1234567890",
            "notebook_allowlist": ["Projects/*", "Personal/Journal"],
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config = JoplinMCPConfig.from_file(config_file)

        assert config.notebook_allowlist == ["Projects/*", "Personal/Journal"]

    def test_allowlist_parses_from_environment(self):
        """Test that JOPLIN_NOTEBOOK_ALLOWLIST env var is parsed as comma-separated list."""
        with patch.dict(
            os.environ,
            {"JOPLIN_NOTEBOOK_ALLOWLIST": "Projects/*,Work/**,!Work/Secret"},
            clear=False,
        ):
            config = JoplinMCPConfig.from_environment()

        assert config.notebook_allowlist == ["Projects/*", "Work/**", "!Work/Secret"]

    def test_allowlist_env_strips_whitespace(self):
        """Test that whitespace is stripped from comma-separated env var entries."""
        with patch.dict(
            os.environ,
            {"JOPLIN_NOTEBOOK_ALLOWLIST": " Projects/* , Work/** , !Work/Secret "},
            clear=False,
        ):
            config = JoplinMCPConfig.from_environment()

        assert config.notebook_allowlist == ["Projects/*", "Work/**", "!Work/Secret"]

    def test_allowlist_defaults_to_none(self):
        """Test that notebook_allowlist defaults to None when not configured."""
        config = JoplinMCPConfig(token="test-token-1234567890")

        assert config.notebook_allowlist is None

    def test_allowlist_defaults_to_none_from_environment(self):
        """Test that notebook_allowlist is None when env var is not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = JoplinMCPConfig.from_environment()

        assert config.notebook_allowlist is None

    def test_has_notebook_allowlist_true(self):
        """Test has_notebook_allowlist returns True for non-empty allowlist."""
        config = JoplinMCPConfig(
            token="test-token-1234567890",
            notebook_allowlist=["Projects/*"],
        )

        assert config.has_notebook_allowlist is True

    def test_has_notebook_allowlist_false_none(self):
        """Test has_notebook_allowlist returns False when allowlist is None."""
        config = JoplinMCPConfig(token="test-token-1234567890")

        assert config.has_notebook_allowlist is False

    def test_has_notebook_allowlist_true_empty(self):
        """Test has_notebook_allowlist returns True for empty list (deny all is still configured)."""
        config = JoplinMCPConfig(
            token="test-token-1234567890",
            notebook_allowlist=[],
        )

        assert config.has_notebook_allowlist is True

    def test_allowlist_in_to_dict(self):
        """Test that to_dict includes notebook_allowlist."""
        patterns = ["Projects/*", "Work/**"]
        config = JoplinMCPConfig(
            token="test-token-1234567890",
            notebook_allowlist=patterns,
        )

        result = config.to_dict()

        assert "notebook_allowlist" in result
        assert result["notebook_allowlist"] == patterns

    def test_allowlist_none_in_to_dict(self):
        """Test that to_dict includes notebook_allowlist as None when not configured."""
        config = JoplinMCPConfig(token="test-token-1234567890")

        result = config.to_dict()

        assert "notebook_allowlist" in result
        assert result["notebook_allowlist"] is None
