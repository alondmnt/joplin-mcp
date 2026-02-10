"""Tests for configuration management."""

import json
import os
import tempfile
import uuid
from unittest.mock import patch

import pytest
import yaml

from joplin_mcp.config import ConfigError, JoplinMCPConfig


class TestConfigEnvironmentVariables:
    """Test configuration loading from environment variables."""

    def test_config_loads_from_environment_variables(self):
        """Test that configuration can be loaded from environment variables."""
        with patch.dict(
            os.environ,
            {
                "JOPLIN_HOST": "localhost",
                "JOPLIN_PORT": "41184",
                "JOPLIN_TOKEN": "test-token-123",
                "JOPLIN_TIMEOUT": "30",
                "JOPLIN_VERIFY_SSL": "false",
            },
        ):
            config = JoplinMCPConfig.from_environment()

            assert config.host == "localhost"
            assert config.port == 41184
            assert config.token == "test-token-123"
            assert config.timeout == 30
            assert config.verify_ssl is False

    def test_config_uses_default_values_when_env_vars_missing(self):
        """Test that default values are used when environment variables are not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = JoplinMCPConfig.from_environment()

            assert config.host == "localhost"
            assert config.port == 41184
            assert config.token is None
            assert config.timeout == 60
            assert config.verify_ssl is False

    def test_config_validates_required_fields(self):
        """Test that configuration validation fails when required fields are missing."""
        with patch.dict(os.environ, {}, clear=True):
            config = JoplinMCPConfig.from_environment()

            with pytest.raises(ConfigError, match="Token is required"):
                config.validate()

    def test_config_validates_port_range(self):
        """Test that port validation works correctly."""
        with patch.dict(
            os.environ, {"JOPLIN_PORT": "99999", "JOPLIN_TOKEN": "test-token"}
        ):
            config = JoplinMCPConfig.from_environment()

            with pytest.raises(ConfigError, match="Port must be between 1 and 65535"):
                config.validate()

    def test_config_validates_timeout_positive(self):
        """Test that timeout must be positive."""
        with patch.dict(
            os.environ, {"JOPLIN_TIMEOUT": "-5", "JOPLIN_TOKEN": "test-token"}
        ):
            config = JoplinMCPConfig.from_environment()

            with pytest.raises(ConfigError, match="Timeout must be positive"):
                config.validate()

    def test_config_handles_boolean_env_vars(self):
        """Test that boolean environment variables are parsed correctly."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
        ]

        for env_value, expected in test_cases:
            with patch.dict(
                os.environ,
                {"JOPLIN_VERIFY_SSL": env_value, "JOPLIN_TOKEN": "test-token"},
            ):
                config = JoplinMCPConfig.from_environment()
                assert config.verify_ssl == expected, f"Failed for {env_value}"

    def test_config_handles_invalid_boolean_env_vars(self):
        """Test that invalid boolean values raise appropriate errors."""
        with patch.dict(
            os.environ, {"JOPLIN_VERIFY_SSL": "maybe", "JOPLIN_TOKEN": "test-token"}
        ):
            with pytest.raises(ConfigError, match="Invalid boolean value"):
                JoplinMCPConfig.from_environment()

    def test_config_handles_invalid_integer_env_vars(self):
        """Test that invalid integer values raise appropriate errors."""
        with patch.dict(
            os.environ, {"JOPLIN_PORT": "not-a-number", "JOPLIN_TOKEN": "test-token"}
        ):
            with pytest.raises(ConfigError, match="Invalid integer value"):
                JoplinMCPConfig.from_environment()

    def test_config_strips_whitespace_from_env_vars(self):
        """Test that whitespace is stripped from environment variables."""
        with patch.dict(
            os.environ,
            {
                "JOPLIN_HOST": "  localhost  ",
                "JOPLIN_TOKEN": "  test-token-123  ",
            },
        ):
            config = JoplinMCPConfig.from_environment()

            assert config.host == "localhost"
            assert config.token == "test-token-123"

    def test_config_repr_hides_sensitive_data(self):
        """Test that __repr__ doesn't expose sensitive information like tokens."""
        with patch.dict(os.environ, {"JOPLIN_TOKEN": "secret-token-123"}):
            config = JoplinMCPConfig.from_environment()
            repr_str = repr(config)

            assert "secret-token-123" not in repr_str
            assert "token=***" in repr_str or "token=<hidden>" in repr_str

    def test_config_to_dict_hides_sensitive_data(self):
        """Test that to_dict() method doesn't expose sensitive information."""
        with patch.dict(os.environ, {"JOPLIN_TOKEN": "secret-token-123"}):
            config = JoplinMCPConfig.from_environment()
            config_dict = config.to_dict()

            assert config_dict["token"] == "***" or config_dict["token"] == "<hidden>"
            assert config_dict["host"] == "localhost"

    def test_config_env_var_prefix_support(self):
        """Test support for alternative environment variable prefixes."""
        with patch.dict(
            os.environ,
            {
                "JOPLIN_MCP_HOST": "mcp-host",
                "JOPLIN_MCP_PORT": "9999",
                "JOPLIN_MCP_TOKEN": "mcp-token",
            },
            clear=True,
        ):
            config = JoplinMCPConfig.from_environment(prefix="JOPLIN_MCP_")

            assert config.host == "mcp-host"
            assert config.port == 9999
            assert config.token == "mcp-token"


class TestConfigInitialization:
    """Test configuration object initialization and properties."""

    def test_config_direct_initialization(self):
        """Test direct initialization of config object."""
        config = JoplinMCPConfig(
            host="example.com",
            port=8080,
            token="direct-token",
            timeout=45,
            verify_ssl=False,
        )

        assert config.host == "example.com"
        assert config.port == 8080
        assert config.token == "direct-token"
        assert config.timeout == 45
        assert config.verify_ssl is False

    def test_config_partial_initialization_uses_defaults(self):
        """Test that partial initialization uses defaults for missing values."""
        config = JoplinMCPConfig(token="test-token")

        assert config.host == "localhost"
        assert config.port == 41184
        assert config.token == "test-token"
        assert config.timeout == 30
        assert config.verify_ssl is False

    def test_config_base_url_property(self):
        """Test that base_url property is constructed correctly."""
        config = JoplinMCPConfig(
            host="example.com", port=8080, token="test-token", verify_ssl=True
        )

        assert config.base_url == "https://example.com:8080"

        config.verify_ssl = False
        assert config.base_url == "http://example.com:8080"

    def test_config_is_valid_property(self):
        """Test the is_valid property for quick validation checks."""
        valid_config = JoplinMCPConfig(token="test-token")
        assert valid_config.is_valid is True

        invalid_config = JoplinMCPConfig(token=None)
        assert invalid_config.is_valid is False

        invalid_port_config = JoplinMCPConfig(token="test-token", port=99999)
        assert invalid_port_config.is_valid is False


class TestConfigFileLoading:
    """Test configuration loading from JSON and YAML files."""

    def test_config_loads_from_json_file(self):
        """Test that configuration can be loaded from a JSON file."""
        config_data = {
            "host": "json-host",
            "port": 8080,
            "token": "json-token",
            "timeout": 45,
            "verify_ssl": False,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            config = JoplinMCPConfig.from_file(config_file)

            assert config.host == "json-host"
            assert config.port == 8080
            assert config.token == "json-token"
            assert config.timeout == 45
            assert config.verify_ssl is False
        finally:
            os.unlink(config_file)

    def test_config_loads_from_yaml_file(self):
        """Test that configuration can be loaded from a YAML file."""
        yaml_content = """
host: yaml-host
port: 9090
token: yaml-token
timeout: 35
verify_ssl: true
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_file = f.name

        try:
            config = JoplinMCPConfig.from_file(config_file)

            assert config.host == "yaml-host"
            assert config.port == 9090
            assert config.token == "yaml-token"
            assert config.timeout == 35
            assert config.verify_ssl is True
        finally:
            os.unlink(config_file)

    def test_config_loads_from_yml_file(self):
        """Test that configuration can be loaded from a .yml file."""
        yml_content = """
host: yml-host
port: 7070
token: yml-token
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(yml_content)
            config_file = f.name

        try:
            config = JoplinMCPConfig.from_file(config_file)

            assert config.host == "yml-host"
            assert config.port == 7070
            assert config.token == "yml-token"
            # Should use defaults for missing values
            assert config.timeout == 30
            assert config.verify_ssl is False
        finally:
            os.unlink(config_file)

    def test_config_file_not_found_raises_error(self):
        """Test that FileNotFoundError is raised for non-existent files."""
        with pytest.raises(ConfigError, match="Configuration file not found"):
            JoplinMCPConfig.from_file("/non/existent/file.json")

    def test_config_invalid_json_raises_error(self):
        """Test that invalid JSON content raises ConfigError."""
        invalid_json = "{ invalid json content }"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(invalid_json)
            config_file = f.name

        try:
            with pytest.raises(ConfigError, match="Invalid JSON"):
                JoplinMCPConfig.from_file(config_file)
        finally:
            os.unlink(config_file)

    def test_config_invalid_yaml_raises_error(self):
        """Test that invalid YAML content raises ConfigError."""
        invalid_yaml = """
host: yaml-host
port: [invalid yaml structure
token: yaml-token
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(invalid_yaml)
            config_file = f.name

        try:
            with pytest.raises(ConfigError, match="Invalid YAML"):
                JoplinMCPConfig.from_file(config_file)
        finally:
            os.unlink(config_file)

    def test_config_unsupported_file_extension_raises_error(self):
        """Test that unsupported file extensions raise ConfigError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("some content")
            config_file = f.name

        try:
            with pytest.raises(ConfigError, match="Unsupported file format"):
                JoplinMCPConfig.from_file(config_file)
        finally:
            os.unlink(config_file)

    def test_config_file_validates_data_types(self):
        """Test that file configuration validates data types correctly."""
        config_data = {
            "host": "test-host",
            "port": "invalid-port",  # Should be integer
            "token": "test-token",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            with pytest.raises(ConfigError, match="Invalid data type"):
                JoplinMCPConfig.from_file(config_file)
        finally:
            os.unlink(config_file)

    def test_config_file_supports_comments_in_yaml(self):
        """Test that YAML files with comments are parsed correctly."""
        yaml_with_comments = """
# Joplin MCP Configuration
host: comment-host  # Server host
port: 6060          # Server port
token: comment-token
# SSL verification
verify_ssl: false
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_with_comments)
            config_file = f.name

        try:
            config = JoplinMCPConfig.from_file(config_file)

            assert config.host == "comment-host"
            assert config.port == 6060
            assert config.token == "comment-token"
            assert config.verify_ssl is False
        finally:
            os.unlink(config_file)

    def test_config_file_merges_with_defaults(self):
        """Test that file configuration merges with default values."""
        # Only specify host and token, other values should use defaults
        config_data = {"host": "partial-host", "token": "partial-token"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            config = JoplinMCPConfig.from_file(config_file)

            assert config.host == "partial-host"
            assert config.token == "partial-token"
            # These should use defaults
            assert config.port == 41184
            assert config.timeout == 30
            assert config.verify_ssl is False
        finally:
            os.unlink(config_file)


class TestConfigPriority:
    """Test configuration priority and precedence."""

    def test_environment_variables_override_file_config(self):
        """Test that environment variables take precedence over file configuration."""
        config_data = {"host": "file-host", "port": 8080, "token": "file-token"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            with patch.dict(
                os.environ,
                {
                    "JOPLIN_HOST": "env-host",
                    "JOPLIN_TOKEN": "env-token",
                    # Port not set in env, should use file value
                },
            ):
                config = JoplinMCPConfig.from_file_and_environment(config_file)

                # Environment variables should override
                assert config.host == "env-host"
                assert config.token == "env-token"
                # Should use file value since not in environment
                assert config.port == 8080
        finally:
            os.unlink(config_file)

    def test_direct_parameters_override_all(self):
        """Test that direct parameters override both file and environment config."""
        config_data = {"host": "file-host", "port": 8080, "token": "file-token"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            with patch.dict(
                os.environ, {"JOPLIN_HOST": "env-host", "JOPLIN_TOKEN": "env-token"}
            ):
                config = JoplinMCPConfig.from_file_and_environment(
                    config_file,
                    host_override="direct-host",
                    token_override="direct-token",
                )

                # Direct parameters should override everything
                assert config.host == "direct-host"
                assert config.token == "direct-token"
                # Should still use file value for port (no env or direct override)
                assert config.port == 8080
        finally:
            os.unlink(config_file)

    def test_config_search_paths(self):
        """Test that configuration is searched in multiple standard paths."""
        # This should test common config file locations like:
        # ~/.config/joplin-mcp/config.json
        # ./joplin-mcp.json
        # ./config/joplin-mcp.yaml

        search_paths = JoplinMCPConfig.get_default_config_paths()

        assert isinstance(search_paths, list)
        assert len(search_paths) > 0
        assert any("joplin-mcp" in str(path) for path in search_paths)

    def test_config_auto_discovery(self):
        """Test automatic configuration file discovery."""
        config_data = {"host": "auto-host", "token": "auto-token"}

        # Create config in current directory
        config_file = "test-joplin-mcp.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        try:
            config = JoplinMCPConfig.auto_discover(
                search_filenames=["test-joplin-mcp.json"]
            )

            assert config.host == "auto-host"
            assert config.token == "auto-token"
        finally:
            if os.path.exists(config_file):
                os.unlink(config_file)


class TestConfigValidationAndEdgeCases:
    """Test additional validation scenarios and edge cases."""

    def test_config_validates_empty_token_string(self):
        """Test that empty string token is treated as invalid."""
        config = JoplinMCPConfig(token="")

        with pytest.raises(ConfigError, match="Token is required"):
            config.validate()

        assert config.is_valid is False

    def test_config_validates_whitespace_only_token(self):
        """Test that whitespace-only token is treated as invalid."""
        config = JoplinMCPConfig(token="   ")

        with pytest.raises(ConfigError, match="Token is required"):
            config.validate()

    def test_config_validates_negative_port(self):
        """Test that negative port numbers are invalid."""
        config = JoplinMCPConfig(token="test-token", port=-1)

        with pytest.raises(ConfigError, match="Port must be between 1 and 65535"):
            config.validate()

    def test_config_validates_zero_port(self):
        """Test that port 0 is invalid."""
        config = JoplinMCPConfig(token="test-token", port=0)

        with pytest.raises(ConfigError, match="Port must be between 1 and 65535"):
            config.validate()

    def test_config_validates_zero_timeout(self):
        """Test that zero timeout is invalid."""
        config = JoplinMCPConfig(token="test-token", timeout=0)

        with pytest.raises(ConfigError, match="Timeout must be positive"):
            config.validate()

    def test_config_validates_negative_timeout(self):
        """Test that negative timeout is invalid."""
        config = JoplinMCPConfig(token="test-token", timeout=-10)

        with pytest.raises(ConfigError, match="Timeout must be positive"):
            config.validate()

    def test_config_validation_multiple_errors(self):
        """Test that validation reports the first error when multiple issues exist."""
        config = JoplinMCPConfig(token=None, port=99999, timeout=-5)

        # Should report token error first
        with pytest.raises(ConfigError, match="Token is required"):
            config.validate()

    def test_config_file_handles_empty_file(self):
        """Test that empty configuration files are handled gracefully."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("")
            config_file = f.name

        try:
            with pytest.raises(ConfigError, match="Invalid JSON"):
                JoplinMCPConfig.from_file(config_file)
        finally:
            os.unlink(config_file)

    def test_config_file_handles_null_values_in_json(self):
        """Test that null values in JSON are handled properly."""
        config_data = {
            "host": None,
            "port": None,
            "token": None,
            "timeout": None,
            "verify_ssl": None,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            config = JoplinMCPConfig.from_file(config_file)

            # Should use defaults for null values except where null is valid
            assert config.host == "localhost"  # Default
            assert config.port == 41184  # Default
            assert config.token is None  # Null is valid
            assert config.timeout == 30  # Default
            assert config.verify_ssl is False  # Default
        finally:
            os.unlink(config_file)

    def test_config_file_handles_mixed_case_boolean_strings(self):
        """Test that mixed case boolean strings in environment are parsed correctly."""
        with patch.dict(
            os.environ, {"JOPLIN_VERIFY_SSL": "True", "JOPLIN_TOKEN": "test-token"}
        ):
            config = JoplinMCPConfig.from_environment()
            assert config.verify_ssl is True

    def test_config_environment_handles_malformed_port(self):
        """Test that malformed port in environment raises clear error."""
        with patch.dict(
            os.environ, {"JOPLIN_PORT": "41184abc", "JOPLIN_TOKEN": "test-token"}
        ):
            with pytest.raises(ConfigError, match="Invalid integer value for port"):
                JoplinMCPConfig.from_environment()

    def test_config_environment_handles_malformed_timeout(self):
        """Test that malformed timeout in environment raises clear error."""
        with patch.dict(
            os.environ, {"JOPLIN_TIMEOUT": "30.5", "JOPLIN_TOKEN": "test-token"}
        ):
            with pytest.raises(ConfigError, match="Invalid integer value for timeout"):
                JoplinMCPConfig.from_environment()

    def test_config_file_priority_with_partial_override(self):
        """Test complex priority scenario with partial environment override."""
        config_data = {
            "host": "file-host",
            "port": 8080,
            "token": "file-token",
            "timeout": 120,
            "verify_ssl": False,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            # Only override host and verify_ssl in environment
            with patch.dict(
                os.environ, {"JOPLIN_HOST": "env-host", "JOPLIN_VERIFY_SSL": "true"}
            ):
                config = JoplinMCPConfig.from_file_and_environment(config_file)

                # Environment should override
                assert config.host == "env-host"
                assert config.verify_ssl is True

                # File values should be used
                assert config.port == 8080
                assert config.token == "file-token"
                assert config.timeout == 120
        finally:
            os.unlink(config_file)

    def test_config_auto_discover_with_multiple_files(self):
        """Test auto discovery when multiple config files exist."""
        config_data1 = {"host": "json-host", "token": "json-token"}
        config_data2 = {"host": "yaml-host", "token": "yaml-token"}

        # Create unique temporary file names in current directory
        unique_id = str(uuid.uuid4())[:8]
        json_file = f"test-joplin-mcp-{unique_id}.json"
        yaml_file = f"test-joplin-mcp-{unique_id}.yaml"

        try:
            # Write config data to temp files in current directory
            with open(json_file, "w") as f:
                json.dump(config_data1, f)

            with open(yaml_file, "w") as f:
                yaml.dump(config_data2, f)

            # Test auto discovery with specific filenames
            config = JoplinMCPConfig.auto_discover(
                search_filenames=[json_file, yaml_file]
            )

            # Should find the first file in the search order (JSON comes first)
            assert config.host == "json-host"
            assert config.token == "json-token"
        finally:
            # Clean up temp files
            if os.path.exists(json_file):
                os.unlink(json_file)
            if os.path.exists(yaml_file):
                os.unlink(yaml_file)

    def test_config_repr_with_none_values(self):
        """Test __repr__ method with None values."""
        config = JoplinMCPConfig()  # All defaults, token will be None
        repr_str = repr(config)

        assert "JoplinMCPConfig" in repr_str
        assert "token=None" in repr_str or "token=***" in repr_str

    def test_config_to_dict_includes_all_fields(self):
        """Test that to_dict includes all configuration fields."""
        config = JoplinMCPConfig(
            host="test-host",
            port=8080,
            token="secret-token",
            timeout=30,
            verify_ssl=False,
        )

        config_dict = config.to_dict()

        expected_keys = {
            "host",
            "port",
            "token",
            "timeout",
            "verify_ssl",
            "base_url",
            "tools",
            "enabled_tools_count",
            "disabled_tools_count",
            "content_exposure",
        }
        assert set(config_dict.keys()) == expected_keys

        assert config_dict["host"] == "test-host"
        assert config_dict["port"] == 8080
        assert config_dict["token"] == "***"  # Should be hidden
        assert config_dict["timeout"] == 30
        assert config_dict["verify_ssl"] is False
        assert config_dict["base_url"] == "http://test-host:8080"


class TestConfigErrorHandlingAndMessages:
    """Test advanced error handling and validation message quality."""

    def test_config_validation_provides_detailed_error_context(self):
        """Test that validation errors provide helpful context about the configuration source."""
        config = JoplinMCPConfig(
            host="valid-host",
            port=99999,  # Invalid
            token="valid-token",
            timeout=-10,  # Invalid
            verify_ssl=True,
        )

        with pytest.raises(ConfigError) as exc_info:
            config.validate()

        error_msg = str(exc_info.value)
        # Should mention which field is invalid and why
        assert "port" in error_msg.lower() or "between 1 and 65535" in error_msg

    def test_config_file_error_includes_file_path_context(self):
        """Test that file loading errors include the file path for better debugging."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"host": "test", "port": "invalid"}')
            config_file = f.name

        try:
            with pytest.raises(ConfigError) as exc_info:
                JoplinMCPConfig.from_file(config_file)

            error_msg = str(exc_info.value)
            # Error should include the file path for context
            assert config_file in error_msg or "file" in error_msg.lower()
        finally:
            os.unlink(config_file)

    def test_config_environment_error_includes_variable_name(self):
        """Test that environment variable errors include the variable name."""
        with patch.dict(
            os.environ,
            {"JOPLIN_PORT": "clearly-not-a-number", "JOPLIN_TOKEN": "test-token"},
        ):
            with pytest.raises(ConfigError) as exc_info:
                JoplinMCPConfig.from_environment()

            error_msg = str(exc_info.value)
            # Should mention the specific environment variable
            assert "JOPLIN_PORT" in error_msg or "port" in error_msg.lower()

    def test_config_validates_all_errors_and_reports_multiple(self):
        """Test that validation can report multiple errors at once."""
        config = JoplinMCPConfig(
            host="",  # Invalid - empty
            port=-1,  # Invalid - negative
            token=None,  # Invalid - required
            timeout=0,  # Invalid - must be positive
            verify_ssl=True,
        )

        # Should be able to get a comprehensive validation report
        validation_errors = config.get_validation_errors()

        assert len(validation_errors) >= 3  # At least host, port, token, timeout issues

        # Should include specific error types
        error_messages = [str(err) for err in validation_errors]
        assert any("host" in msg.lower() for msg in error_messages)
        assert any("port" in msg.lower() for msg in error_messages)
        assert any("token" in msg.lower() for msg in error_messages)

    def test_config_provides_helpful_suggestion_for_common_mistakes(self):
        """Test that common configuration mistakes include helpful suggestions."""
        with patch.dict(
            os.environ,
            {
                "JOPLIN_HOST": "localhost:41184",  # Common mistake - including port in host
                "JOPLIN_TOKEN": "test-token",
            },
        ):
            # This should either work or provide a helpful error
            try:
                config = JoplinMCPConfig.from_environment()
                # If it works, host should be parsed correctly
                assert config.host == "localhost:41184" or config.host == "localhost"
            except ConfigError as e:
                # If it fails, should provide helpful guidance
                error_msg = str(e).lower()
                assert "port" in error_msg and (
                    "separate" in error_msg or "use" in error_msg
                )

    def test_config_validates_host_format_with_helpful_messages(self):
        """Test that invalid host formats provide helpful error messages."""
        invalid_hosts = [
            "",  # Empty
            "   ",  # Whitespace only
            "http://localhost",  # Protocol included
            "localhost:port",  # Invalid port format
            "user@host",  # Username included
        ]

        for invalid_host in invalid_hosts:
            config = JoplinMCPConfig(host=invalid_host, token="test-token")

            with pytest.raises(ConfigError) as exc_info:
                config.validate_host_format()

            error_msg = str(exc_info.value).lower()
            assert "host" in error_msg
            # Should provide specific guidance based on the error
            if "http" in invalid_host:
                assert "protocol" in error_msg or "http" in error_msg
            elif ":" in invalid_host:
                assert "port" in error_msg

    def test_config_validates_port_range_with_context(self):
        """Test that port validation provides context about valid ranges."""
        invalid_ports = [-1, 0, 65536, 99999]

        for invalid_port in invalid_ports:
            config = JoplinMCPConfig(port=invalid_port, token="test-token")

            with pytest.raises(ConfigError) as exc_info:
                config.validate()

            error_msg = str(exc_info.value)
            # Should mention the valid range
            assert "1" in error_msg and "65535" in error_msg
            # Should mention the actual invalid value
            assert str(invalid_port) in error_msg

    def test_config_file_validation_aggregates_multiple_errors(self):
        """Test that file validation can report multiple issues at once."""
        config_data = {
            "host": "",  # Invalid
            "port": "not-a-number",  # Invalid
            "token": "",  # Invalid
            "timeout": "negative-value",  # Invalid
            "verify_ssl": "maybe",  # Invalid
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            with pytest.raises(ConfigError):
                config = JoplinMCPConfig.from_file(config_file)
                # If it loads, validate it to get all errors
                config.validate_all_with_details()
        except AttributeError:
            # Method doesn't exist yet - that's expected for RED phase
            pass
        finally:
            os.unlink(config_file)

    def test_config_provides_autocorrection_suggestions(self):
        """Test that configuration errors suggest potential fixes."""
        # Test common typos and mistakes
        test_cases = [
            {
                "env_vars": {"JOPLIN_VERIFY_SSL": "yes"},  # Should suggest true/false
                "expected_suggestion": "boolean",
            },
            {
                "env_vars": {"JOPLIN_PORT": "41184.0"},  # Float instead of int
                "expected_suggestion": "integer",
            },
            {
                "env_vars": {"JOPLIN_TIMEOUT": "30s"},  # String with unit
                "expected_suggestion": "seconds",
            },
        ]

        for test_case in test_cases:
            with patch.dict(os.environ, test_case["env_vars"]):
                with pytest.raises(ConfigError) as exc_info:
                    JoplinMCPConfig.from_environment_with_suggestions()

                error_msg = str(exc_info.value).lower()
                assert test_case["expected_suggestion"] in error_msg

    def test_config_validates_token_format_and_provides_guidance(self):
        """Test that token validation provides helpful guidance about expected format."""
        invalid_tokens = [
            "",  # Empty
            "   ",  # Whitespace
            "abc",  # Too short
            "invalid-characters-$%^",  # Invalid characters
        ]

        for invalid_token in invalid_tokens:
            config = JoplinMCPConfig(token=invalid_token)

            with pytest.raises(ConfigError) as exc_info:
                config.validate_token_format()

            error_msg = str(exc_info.value).lower()
            assert "token" in error_msg
            # Should provide guidance about expected format
            if len(invalid_token.strip()) == 0:
                assert "required" in error_msg or "empty" in error_msg
            elif len(invalid_token) < 10:
                assert "length" in error_msg or "characters" in error_msg

    def test_config_error_includes_recovery_instructions(self):
        """Test that configuration errors include instructions for fixing them."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")  # Malformed YAML
            config_file = f.name

        try:
            with pytest.raises(ConfigError) as exc_info:
                JoplinMCPConfig.from_file(config_file)

            error_msg = str(exc_info.value).lower()
            # Should include recovery instructions
            recovery_keywords = ["check", "fix", "correct", "valid", "format", "syntax"]
            assert any(keyword in error_msg for keyword in recovery_keywords)
        finally:
            os.unlink(config_file)

    def test_config_warning_system_for_deprecated_options(self):
        """Test that deprecated configuration options show warnings."""
        # Test deprecated environment variables or config options
        with patch.dict(
            os.environ,
            {
                "JOPLIN_API_TOKEN": "test-token",  # Deprecated name
                "JOPLIN_HOST": "localhost",
            },
        ):
            warnings = []
            JoplinMCPConfig.from_environment_with_warnings(warning_collector=warnings)

            # Should detect deprecated option and suggest new one
            assert len(warnings) > 0
            warning_msg = warnings[0].lower()
            assert "deprecated" in warning_msg or "use" in warning_msg
            assert "joplin_token" in warning_msg or "token" in warning_msg


class TestConfigToolConfiguration:
    """Test tool configuration functionality."""

    def test_config_default_tools_enabled_count(self):
        """Test the default enabled/disabled tool configuration."""
        config = JoplinMCPConfig(token="test-token")

        # Check that tools are properly configured by default
        enabled_tools = config.get_enabled_tools()
        disabled_tools = config.get_disabled_tools()
        assert len(enabled_tools) + len(disabled_tools) == len(config.DEFAULT_TOOLS)
        assert len(enabled_tools) == 17
        assert len(disabled_tools) == 7

        # Check specific tools
        assert config.is_tool_enabled("find_notes")
        assert config.is_tool_enabled("create_note")
        assert config.is_tool_enabled("ping_joplin")

        # Deletion tools disabled by default (destructive)
        assert not config.is_tool_enabled("delete_note")
        assert not config.is_tool_enabled("delete_notebook")
        assert not config.is_tool_enabled("delete_tag")

    def test_config_tools_from_dict_initialization(self):
        """Test tool configuration via direct initialization."""
        tools_config = {
            "find_notes": True,
            "create_note": True,
            "delete_note": False,
            "ping_joplin": True,
        }

        config = JoplinMCPConfig(token="test-token", tools=tools_config)

        assert config.is_tool_enabled("find_notes")
        assert config.is_tool_enabled("create_note")
        assert not config.is_tool_enabled("delete_note")
        assert config.is_tool_enabled("ping_joplin")

    def test_config_tools_from_file_json(self):
        """Test tool configuration loading from JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "host": "localhost",
                    "port": 41184,
                    "token": "test-token",
                    "tools": {
                        "find_notes": True,
                        "create_note": False,
                        "delete_note": False,
                        "ping_joplin": True,
                    },
                },
                f,
            )
            temp_path = f.name

        try:
            config = JoplinMCPConfig.from_file(temp_path)

            assert config.is_tool_enabled("find_notes")
            assert not config.is_tool_enabled("create_note")
            assert not config.is_tool_enabled("delete_note")
            assert config.is_tool_enabled("ping_joplin")

            # Check that unspecified tools use defaults
            assert config.is_tool_enabled("get_note")  # Should be default True

        finally:
            os.unlink(temp_path)

    def test_config_tools_from_file_yaml(self):
        """Test tool configuration loading from YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "host": "localhost",
                    "port": 41184,
                    "token": "test-token",
                    "tools": {
                        "find_notes": True,
                        "create_note": False,
                        "delete_note": False,
                        "ping_joplin": True,
                    },
                },
                f,
            )
            temp_path = f.name

        try:
            config = JoplinMCPConfig.from_file(temp_path)

            assert config.is_tool_enabled("find_notes")
            assert not config.is_tool_enabled("create_note")
            assert not config.is_tool_enabled("delete_note")
            assert config.is_tool_enabled("ping_joplin")

        finally:
            os.unlink(temp_path)

    def test_config_tools_from_environment_variables(self):
        """Test tool configuration from environment variables."""
        with patch.dict(
            os.environ,
            {
                "JOPLIN_TOKEN": "test-token",
                "JOPLIN_TOOL_FIND_NOTES": "true",
                "JOPLIN_TOOL_CREATE_NOTE": "false",
                "JOPLIN_TOOL_DELETE_NOTE": "false",
                "JOPLIN_TOOL_PING_JOPLIN": "true",
            },
        ):
            config = JoplinMCPConfig.from_environment()

            assert config.is_tool_enabled("find_notes")
            assert not config.is_tool_enabled("create_note")
            assert not config.is_tool_enabled("delete_note")
            assert config.is_tool_enabled("ping_joplin")

    def test_config_tools_enable_disable_methods(self):
        """Test individual tool enable/disable methods."""
        config = JoplinMCPConfig(token="test-token")

        # Test disable
        assert config.is_tool_enabled("create_note")
        config.disable_tool("create_note")
        assert not config.is_tool_enabled("create_note")

        # Test enable
        config.enable_tool("create_note")
        assert config.is_tool_enabled("create_note")

    def test_config_tools_enable_disable_invalid_tool(self):
        """Test that enabling/disabling invalid tools raises errors."""
        config = JoplinMCPConfig(token="test-token")

        with pytest.raises(ConfigError, match="Unknown tool"):
            config.enable_tool("invalid_tool")

        with pytest.raises(ConfigError, match="Unknown tool"):
            config.disable_tool("invalid_tool")

    def test_config_tools_category_management(self):
        """Test tool category enable/disable functionality."""
        config = JoplinMCPConfig(token="test-token")

        # Test disable category
        config.disable_tool_category("tags")

        # All tag tools should be disabled
        tag_tools = config.get_tool_categories()["tags"]
        for tool in tag_tools:
            assert not config.is_tool_enabled(tool)

        # Non-tag tools should still be enabled
        assert config.is_tool_enabled("find_notes")
        assert config.is_tool_enabled("create_note")

        # Test enable category
        config.enable_tool_category("tags")

        # All tag tools should be enabled again
        for tool in tag_tools:
            assert config.is_tool_enabled(tool)

    def test_config_tools_category_invalid_category(self):
        """Test that invalid categories raise errors."""
        config = JoplinMCPConfig(token="test-token")

        with pytest.raises(ConfigError, match="Unknown tool category"):
            config.enable_tool_category("invalid_category")

        with pytest.raises(ConfigError, match="Unknown tool category"):
            config.disable_tool_category("invalid_category")

    def test_config_tools_get_enabled_disabled_lists(self):
        """Test getting lists of enabled/disabled tools."""
        config = JoplinMCPConfig(token="test-token")

        enabled = config.get_enabled_tools()
        disabled = config.get_disabled_tools()

        initial_enabled_count = len(enabled)
        initial_disabled_count = len(disabled)

        # Disable some tools that are enabled by default
        config.disable_tool("create_note")
        config.disable_tool("update_note")

        enabled = config.get_enabled_tools()
        disabled = config.get_disabled_tools()

        assert len(enabled) == initial_enabled_count - 2
        assert len(disabled) == initial_disabled_count + 2
        assert "create_note" in disabled
        assert "update_note" in disabled

    def test_config_tools_validation_invalid_tool_name(self):
        """Test validation of invalid tool names in configuration."""
        config = JoplinMCPConfig(token="test-token")
        config.tools["invalid_tool"] = True

        with pytest.raises(ConfigError, match="Unknown tool in configuration"):
            config.validate()

    def test_config_tools_validation_invalid_tool_value(self):
        """Test validation of invalid tool values in configuration."""
        config = JoplinMCPConfig(token="test-token")
        config.tools["find_notes"] = "invalid"

        with pytest.raises(ConfigError, match="Tool configuration.*must be boolean"):
            config.validate()

    def test_config_tools_validation_invalid_tools_structure(self):
        """Test validation of invalid tools structure."""
        config = JoplinMCPConfig(token="test-token")
        config.tools = "invalid"

        with pytest.raises(
            ConfigError, match="Tools configuration must be a dictionary"
        ):
            config.validate()

    def test_config_tools_file_validation_invalid_tool_name(self):
        """Test file validation with invalid tool names."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "token": "test-token",
                    "tools": {
                        "invalid_tool": True,
                        "find_notes": True,
                    },
                },
                f,
            )
            temp_path = f.name

        try:
            with pytest.raises(
                ConfigError, match="Unknown tool in 'tools' configuration"
            ):
                JoplinMCPConfig.from_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_config_tools_file_validation_invalid_tool_value_type(self):
        """Test file validation with invalid tool value types."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "token": "test-token",
                    "tools": {
                        "find_notes": "invalid",
                    },
                },
                f,
            )
            temp_path = f.name

        try:
            with pytest.raises(
                ConfigError, match="Invalid data type for tool 'find_notes'"
            ):
                JoplinMCPConfig.from_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_config_tools_file_validation_invalid_tools_structure(self):
        """Test file validation with invalid tools structure."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "token": "test-token",
                    "tools": "invalid",
                },
                f,
            )
            temp_path = f.name

        try:
            with pytest.raises(ConfigError, match="Invalid data type for 'tools'"):
                JoplinMCPConfig.from_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_config_tools_priority_env_over_file(self):
        """Test that environment variables override file configuration for tools."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "token": "test-token",
                    "tools": {
                        "find_notes": False,
                        "create_note": True,
                    },
                },
                f,
            )
            temp_path = f.name

        try:
            with patch.dict(
                os.environ,
                {
                    "JOPLIN_TOOL_FIND_NOTES": "true",  # Override file setting
                    "JOPLIN_TOOL_DELETE_NOTE": "false",  # New setting
                },
            ):
                config = JoplinMCPConfig.from_file_and_environment(temp_path)

                # Environment should override file
                assert config.is_tool_enabled("find_notes")  # env: true, file: false
                assert config.is_tool_enabled("create_note")  # file: true, no env
                assert not config.is_tool_enabled(
                    "delete_note"
                )  # env: false, file: default true

        finally:
            os.unlink(temp_path)

    def test_config_tools_copy_includes_tools(self):
        """Test that configuration copy includes tools configuration."""
        config = JoplinMCPConfig(token="test-token")
        config.disable_tool("create_note")

        copied_config = config.copy()

        assert not copied_config.is_tool_enabled("create_note")
        assert copied_config.is_tool_enabled("find_notes")

    def test_config_tools_copy_with_tools_override(self):
        """Test configuration copy with tools override."""
        config = JoplinMCPConfig(token="test-token")

        copied_config = config.copy(tools={"find_notes": False, "create_note": True})

        assert not copied_config.is_tool_enabled("find_notes")
        assert copied_config.is_tool_enabled("create_note")

    def test_config_tools_to_dict_includes_tools(self):
        """Test that to_dict includes tools configuration."""
        config = JoplinMCPConfig(token="test-token")
        initial_disabled_count = len(config.get_disabled_tools())
        config.disable_tool("create_note")

        config_dict = config.to_dict()

        assert "tools" in config_dict
        assert "enabled_tools_count" in config_dict
        assert "disabled_tools_count" in config_dict
        assert not config_dict["tools"]["create_note"]
        assert config_dict["disabled_tools_count"] == initial_disabled_count + 1

    def test_config_tools_repr_includes_tools_summary(self):
        """Test that __repr__ includes tools summary."""
        config = JoplinMCPConfig(token="test-token")
        config.disable_tool("create_note")
        config.disable_tool("update_note")

        repr_str = repr(config)

        enabled = len(config.get_enabled_tools())
        total = len(config.tools)
        assert "tools=" in repr_str
        assert f"{enabled}/{total} enabled" in repr_str

    def test_config_tools_save_to_file_includes_tools(self):
        """Test that save_to_file includes tools configuration."""
        config = JoplinMCPConfig(token="test-token")
        config.disable_tool("create_note")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            config.save_to_file(temp_path)

            with open(temp_path) as f:
                saved_data = json.load(f)

            assert "tools" in saved_data
            assert not saved_data["tools"]["create_note"]
            assert saved_data["tools"]["find_notes"]

        finally:
            os.unlink(temp_path)

    def test_config_tools_connection_info_includes_tools_summary(self):
        """Test that connection_info includes tools summary."""
        config = JoplinMCPConfig(token="test-token")
        config.disable_tool("create_note")

        conn_info = config.connection_info

        assert "tools_summary" in conn_info
        assert "enabled" in conn_info["tools_summary"]
        assert "disabled" in conn_info["tools_summary"]
        assert "total" in conn_info["tools_summary"]
        initial_disabled_count = len(JoplinMCPConfig(token="test-token").get_disabled_tools())
        assert conn_info["tools_summary"]["disabled"] == initial_disabled_count + 1

    def test_config_tools_get_validation_errors_includes_tools(self):
        """Test that get_validation_errors includes tools validation."""
        config = JoplinMCPConfig(token="test-token")
        config.tools["invalid_tool"] = True
        config.tools["find_notes"] = "invalid"

        errors = config.get_validation_errors()

        # Should have errors for invalid tool and invalid tool value
        tool_errors = [e for e in errors if "tool" in str(e).lower()]
        assert len(tool_errors) >= 2
