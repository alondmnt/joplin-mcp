"""Configuration management for Joplin MCP server."""

import json
import os
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml


class ConfigError(Exception):
    """Configuration-related errors."""

    pass


class ConfigParser:
    """Helper class for parsing configuration values."""

    @staticmethod
    def parse_bool(value: str, strict: bool = False) -> bool:
        """Parse boolean value from string.

        Args:
            value: String value to parse
            strict: If True, only accept 'true'/'false' and '1'/'0'
        """
        value_lower = value.lower()

        if strict:
            # Strict mode for suggestions - only exact values
            if value_lower in ("true", "1"):
                return True
            elif value_lower in ("false", "0"):
                return False
            else:
                suggestions = []
                if value_lower in ("y", "yes", "on", "enable", "enabled"):
                    suggestions.append("Use 'true' or '1' for boolean values")
                elif value_lower in ("n", "no", "off", "disable", "disabled"):
                    suggestions.append("Use 'false' or '0' for boolean values")
                else:
                    suggestions.append(
                        "Use 'true'/'false' or '1'/'0' for boolean values"
                    )

                raise ConfigError(f"Invalid boolean value '{value}'. {suggestions[0]}")
        else:
            # Lenient mode for normal parsing
            if value_lower in ("true", "1", "yes"):
                return True
            elif value_lower in ("false", "0", "no"):
                return False
            else:
                raise ConfigError(f"Invalid boolean value: {value}")

    @staticmethod
    def parse_int(value: str, field_name: str, strict: bool = False) -> int:
        """Parse integer value from string.

        Args:
            value: String value to parse
            field_name: Name of the field for error messages
            strict: If True, provide detailed suggestions for common mistakes
        """
        try:
            if strict:
                # Handle common mistakes in strict mode
                if "." in value:
                    raise ConfigError(
                        f"Invalid integer value for {field_name}: '{value}'. Remove decimal point - use whole numbers only"
                    )

                if value.endswith(("s", "sec", "seconds", "ms", "milliseconds")):
                    clean_value = value.rstrip("smilecon")
                    if clean_value.isdigit():
                        raise ConfigError(
                            f"Invalid integer value for {field_name}: '{value}'. Use numeric value only (e.g., '{clean_value}') - seconds are assumed"
                        )

            return int(value)
        except ValueError:
            if strict:
                raise ConfigError(
                    f"Invalid integer value for {field_name}: '{value}'. Use a numeric value (e.g., '30', '8080')"
                )
            else:
                raise ConfigError(f"Invalid integer value for {field_name}: {value}")

    @staticmethod
    def get_env_var(name: str, prefix: str = "JOPLIN_") -> Optional[str]:
        """Get environment variable and strip whitespace."""
        value = os.environ.get(f"{prefix}{name}")
        return value.strip() if value else None


class ConfigValidator:
    """Helper class for configuration validation."""

    @staticmethod
    def validate_host_format(host: str) -> None:
        """Validate host format and provide helpful error messages."""
        if not host or not host.strip():
            raise ConfigError("Host cannot be empty")

        host = host.strip()

        # Check for common mistakes
        if host.startswith(("http://", "https://")):
            raise ConfigError(
                f"Host should not include protocol, got '{host}'. Use host name only (e.g., 'localhost')"
            )

        if "@" in host:
            raise ConfigError(
                f"Host should not include username, got '{host}'. Use host name only"
            )

        if ":" in host and not ConfigValidator._is_valid_ipv6(host):
            # Check if it looks like host:port
            parts = host.split(":")
            if len(parts) == 2 and parts[1].isdigit():
                raise ConfigError(
                    f"Host should not include port, got '{host}'. Use the 'port' configuration separately"
                )
            else:
                raise ConfigError(
                    f"Invalid host format, got '{host}'. Use a valid hostname or IP address"
                )

    @staticmethod
    def _is_valid_ipv6(host: str) -> bool:
        """Check if host is a valid IPv6 address."""
        return host.startswith("[") and host.endswith("]")

    @staticmethod
    def validate_token_format(token: Optional[str]) -> None:
        """Validate token format and provide guidance."""
        if not token:
            raise ConfigError("Token is required")

        token = token.strip()

        if len(token) == 0:
            raise ConfigError("Token is required")

        if len(token) < 10:
            raise ConfigError(
                f"Token appears to be too short ({len(token)} characters). Expected at least 10 characters"
            )

        # Check for obviously invalid characters that might indicate encoding issues
        if any(c in token for c in ["$", "%", "^", "&", "*", "(", ")", " "]):
            raise ConfigError(
                "Token contains invalid characters. Ensure it's properly copied without spaces or special characters"
            )

    @staticmethod
    def validate_port_range(port: int) -> None:
        """Validate port is in valid range."""
        if not (1 <= port <= 65535):
            raise ConfigError(f"Port must be between 1 and 65535, got {port}")

    @staticmethod
    def validate_timeout_positive(timeout: int) -> None:
        """Validate timeout is positive."""
        if timeout <= 0:
            raise ConfigError(f"Timeout must be positive, got {timeout}")


class JoplinMCPConfig:
    """Configuration for Joplin MCP server."""

    # Default configuration paths for auto-discovery
    DEFAULT_CONFIG_PATHS = [
        Path.home() / ".joplin-mcp.json",
        Path.home() / ".joplin-mcp.yaml",
        Path.home() / ".joplin-mcp.yml",
        Path.home() / ".config" / "joplin-mcp" / "config.json",
        Path.home() / ".config" / "joplin-mcp" / "config.yaml",
        Path.home() / ".config" / "joplin-mcp" / "config.yml",
        Path.cwd() / "joplin-mcp.json",
        Path.cwd() / "joplin-mcp.yaml",
        Path.cwd() / "joplin-mcp.yml",
    ]

    # Deprecated environment variable mappings
    DEPRECATED_ENV_VARS = {
        "JOPLIN_API_TOKEN": "JOPLIN_TOKEN",
        "JOPLIN_SERVER_HOST": "JOPLIN_HOST",
        "JOPLIN_SERVER_PORT": "JOPLIN_PORT",
        "JOPLIN_REQUEST_TIMEOUT": "JOPLIN_TIMEOUT",
        "JOPLIN_SSL_VERIFY": "JOPLIN_VERIFY_SSL",
    }

    def __init__(
        self,
        host: str = "localhost",
        port: int = 41184,
        token: Optional[str] = None,
        timeout: int = 60,
        verify_ssl: bool = True,
    ):
        """Initialize configuration with default values."""
        self.host = host
        self.port = port
        self.token = token
        self.timeout = timeout
        self.verify_ssl = verify_ssl

    @classmethod
    def from_environment(cls, prefix: str = "JOPLIN_") -> "JoplinMCPConfig":
        """Load configuration from environment variables."""
        # Load values from environment
        host = ConfigParser.get_env_var("HOST", prefix) or "localhost"

        port_str = ConfigParser.get_env_var("PORT", prefix)
        port = ConfigParser.parse_int(port_str, "port") if port_str else 41184

        token = ConfigParser.get_env_var("TOKEN", prefix)

        timeout_str = ConfigParser.get_env_var("TIMEOUT", prefix)
        timeout = ConfigParser.parse_int(timeout_str, "timeout") if timeout_str else 60

        verify_ssl_str = ConfigParser.get_env_var("VERIFY_SSL", prefix)
        verify_ssl = ConfigParser.parse_bool(verify_ssl_str) if verify_ssl_str else True

        return cls(
            host=host, port=port, token=token, timeout=timeout, verify_ssl=verify_ssl
        )

    def validate(self) -> None:
        """Validate configuration and raise ConfigError if invalid."""
        ConfigValidator.validate_token_format(self.token)
        ConfigValidator.validate_port_range(self.port)
        ConfigValidator.validate_timeout_positive(self.timeout)

    @property
    def is_valid(self) -> bool:
        """Check if configuration is valid without raising exceptions."""
        try:
            self.validate()
            return True
        except ConfigError:
            return False

    @property
    def base_url(self) -> str:
        """Get the base URL for Joplin API."""
        protocol = "https" if self.verify_ssl else "http"
        return f"{protocol}://{self.host}:{self.port}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary, hiding sensitive data."""
        return {
            "host": self.host,
            "port": self.port,
            "token": "***" if self.token else None,
            "timeout": self.timeout,
            "verify_ssl": self.verify_ssl,
            "base_url": self.base_url,
        }

    def __repr__(self) -> str:
        """String representation, hiding sensitive data."""
        token_display = "***" if self.token else None
        return (
            f"JoplinMCPConfig(host='{self.host}', port={self.port}, "
            f"token={token_display}, timeout={self.timeout}, "
            f"verify_ssl={self.verify_ssl})"
        )

    @classmethod
    def from_file(cls, file_path: Union[str, Path]) -> "JoplinMCPConfig":
        """Load configuration from a JSON or YAML file."""
        file_path = Path(file_path)

        if not file_path.exists():
            raise ConfigError(f"Configuration file not found: {file_path}")

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Determine file format by extension
            if file_path.suffix.lower() == ".json":
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as e:
                    raise ConfigError(
                        f"Invalid JSON in file {file_path}: {e}. Please check syntax and fix any formatting errors."
                    )
            elif file_path.suffix.lower() in (".yaml", ".yml"):
                try:
                    data = yaml.safe_load(content)
                except yaml.YAMLError as e:
                    raise ConfigError(
                        f"Invalid YAML in file {file_path}: {e}. Please check syntax and fix any formatting errors."
                    )
            else:
                raise ConfigError(
                    f"Unsupported file format '{file_path.suffix}' for file {file_path}. Use .json, .yaml, or .yml files."
                )

            # Validate data structure
            if not isinstance(data, dict):
                raise ConfigError(
                    f"Configuration file {file_path} must contain a dictionary/object, got {type(data)}. Check file format."
                )

            # Validate and convert data types with file context
            try:
                validated_data = cls._validate_file_data(data)
            except ConfigError as e:
                raise ConfigError(f"Error in file {file_path}: {e}")

            return cls(**validated_data)

        except OSError as e:
            raise ConfigError(f"Error reading configuration file {file_path}: {e}")

    @classmethod
    def _validate_file_data(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and convert data types from configuration file."""
        validated = {}

        # Host - must be string
        if "host" in data:
            if data["host"] is None:
                # Use default for null values
                pass  # Don't add to validated, will use default
            elif not isinstance(data["host"], str):
                raise ConfigError(
                    f"Invalid data type for 'host': expected string, got {type(data['host'])}"
                )
            else:
                validated["host"] = data["host"]

        # Port - must be integer
        if "port" in data:
            if data["port"] is None:
                # Use default for null values
                pass  # Don't add to validated, will use default
            elif isinstance(data["port"], int):
                validated["port"] = data["port"]
            elif isinstance(data["port"], str) and data["port"].isdigit():
                validated["port"] = int(data["port"])
            else:
                raise ConfigError(
                    f"Invalid data type for 'port': expected integer, got {type(data['port'])}"
                )

        # Token - must be string or None
        if "token" in data:
            if data["token"] is None or isinstance(data["token"], str):
                validated["token"] = data["token"]
            else:
                raise ConfigError(
                    f"Invalid data type for 'token': expected string, got {type(data['token'])}"
                )

        # Timeout - must be integer
        if "timeout" in data:
            if data["timeout"] is None:
                # Use default for null values
                pass  # Don't add to validated, will use default
            elif isinstance(data["timeout"], int):
                validated["timeout"] = data["timeout"]
            elif isinstance(data["timeout"], str) and data["timeout"].isdigit():
                validated["timeout"] = int(data["timeout"])
            else:
                raise ConfigError(
                    f"Invalid data type for 'timeout': expected integer, got {type(data['timeout'])}"
                )

        # verify_ssl - must be boolean
        if "verify_ssl" in data:
            if data["verify_ssl"] is None:
                # Use default for null values
                pass  # Don't add to validated, will use default
            elif isinstance(data["verify_ssl"], bool):
                validated["verify_ssl"] = data["verify_ssl"]
            else:
                raise ConfigError(
                    f"Invalid data type for 'verify_ssl': expected boolean, got {type(data['verify_ssl'])}"
                )

        return validated

    @classmethod
    def from_file_and_environment(
        cls, file_path: Union[str, Path], prefix: str = "JOPLIN_", **overrides
    ) -> "JoplinMCPConfig":
        """Load configuration from file, then override with environment variables and direct parameters."""
        # Start with file configuration
        config = cls.from_file(file_path)

        # Override with environment variables
        env_config = cls.from_environment(prefix=prefix)

        # Merge configurations with priority: direct overrides > env vars > file
        def get_value(
            key: str,
            override_key: str,
            env_value: Any,
            file_value: Any,
            default_value: Any,
        ):
            """Get value with proper priority: override > env (if not default) > file > default."""
            if override_key in overrides:
                return overrides[override_key]
            else:
                # Check if environment variable was explicitly set (not using default)
                env_var_name = f"{prefix}{key.upper()}"
                if env_var_name in os.environ:
                    return env_value
                else:
                    return file_value

        merged_data = {
            "host": get_value(
                "host", "host_override", env_config.host, config.host, "localhost"
            ),
            "port": get_value(
                "port", "port_override", env_config.port, config.port, 41184
            ),
            "token": get_value(
                "token", "token_override", env_config.token, config.token, None
            ),
            "timeout": get_value(
                "timeout", "timeout_override", env_config.timeout, config.timeout, 60
            ),
            "verify_ssl": get_value(
                "verify_ssl",
                "verify_ssl_override",
                env_config.verify_ssl,
                config.verify_ssl,
                True,
            ),
        }

        return cls(**merged_data)

    @classmethod
    def get_default_config_paths(cls) -> List[Path]:
        """Get list of default configuration file paths to search."""
        return cls.DEFAULT_CONFIG_PATHS.copy()

    @classmethod
    def auto_discover(
        cls, search_filenames: Optional[List[str]] = None
    ) -> "JoplinMCPConfig":
        """Automatically discover and load configuration from standard locations."""
        if search_filenames:
            # Search for custom filenames in current directory
            for filename in search_filenames:
                file_path = Path.cwd() / filename
                if file_path.exists():
                    return cls.from_file(file_path)
        else:
            # Search default paths
            for path in cls.get_default_config_paths():
                if path.exists():
                    return cls.from_file(path)

        # If no file found, return default configuration
        return cls.from_environment()

    def get_validation_errors(self) -> List[ConfigError]:
        """Get all validation errors without raising exceptions."""
        errors = []

        # Token validation
        if not self.token or not self.token.strip():
            errors.append(ConfigError("Token is required"))

        # Host validation
        try:
            ConfigValidator.validate_host_format(self.host)
        except ConfigError as e:
            errors.append(e)

        # Port validation
        if not (1 <= self.port <= 65535):
            errors.append(
                ConfigError(f"Port must be between 1 and 65535, got {self.port}")
            )

        # Timeout validation
        if self.timeout <= 0:
            errors.append(ConfigError(f"Timeout must be positive, got {self.timeout}"))

        # Token format validation
        try:
            ConfigValidator.validate_token_format(self.token)
        except ConfigError as e:
            errors.append(e)

        return errors

    def validate_host_format(self) -> None:
        """Validate host format and provide helpful error messages."""
        ConfigValidator.validate_host_format(self.host)

    def validate_token_format(self) -> None:
        """Validate token format and provide guidance."""
        ConfigValidator.validate_token_format(self.token)

    def validate_all_with_details(self) -> None:
        """Validate all configuration and provide detailed error report."""
        errors = self.get_validation_errors()
        if errors:
            error_messages = [str(err) for err in errors]
            combined_message = "Configuration validation failed:\n" + "\n".join(
                f"  - {msg}" for msg in error_messages
            )
            raise ConfigError(combined_message)

    @classmethod
    def from_environment_with_suggestions(
        cls, prefix: str = "JOPLIN_"
    ) -> "JoplinMCPConfig":
        """Load configuration from environment with autocorrection suggestions."""
        # Load values from environment with strict parsing
        host = ConfigParser.get_env_var("HOST", prefix) or "localhost"

        port_str = ConfigParser.get_env_var("PORT", prefix)
        port = (
            ConfigParser.parse_int(port_str, "port", strict=True) if port_str else 41184
        )

        token = ConfigParser.get_env_var("TOKEN", prefix)

        timeout_str = ConfigParser.get_env_var("TIMEOUT", prefix)
        timeout = (
            ConfigParser.parse_int(timeout_str, "timeout", strict=True)
            if timeout_str
            else 60
        )

        verify_ssl_str = ConfigParser.get_env_var("VERIFY_SSL", prefix)
        verify_ssl = (
            ConfigParser.parse_bool(verify_ssl_str, strict=True)
            if verify_ssl_str
            else True
        )

        return cls(
            host=host, port=port, token=token, timeout=timeout, verify_ssl=verify_ssl
        )

    @classmethod
    def from_environment_with_warnings(
        cls, prefix: str = "JOPLIN_", warning_collector: Optional[List[str]] = None
    ) -> "JoplinMCPConfig":
        """Load configuration from environment with deprecation warnings."""
        if warning_collector is None:
            warning_collector = []

        # Collect warnings for deprecated variables
        for old_name, new_name in cls.DEPRECATED_ENV_VARS.items():
            if old_name in os.environ:
                warning_msg = f"Environment variable '{old_name}' is deprecated. Please use '{new_name}' instead."
                warning_collector.append(warning_msg)
                warnings.warn(warning_msg, DeprecationWarning, stacklevel=2)

                # Use the deprecated value if new one is not set
                if new_name not in os.environ:
                    os.environ[new_name] = os.environ[old_name]

        # Load with normal method
        return cls.from_environment(prefix=prefix)

    # Convenience methods for common use cases

    @classmethod
    def load(
        cls, config_file: Optional[Union[str, Path]] = None, **overrides
    ) -> "JoplinMCPConfig":
        """Convenient method to load configuration with automatic fallback.

        Priority: overrides > environment > config_file > auto-discovery > defaults
        """
        if config_file:
            # Load from specific file with environment overrides
            return cls.from_file_and_environment(config_file, **overrides)
        else:
            # Auto-discover configuration
            try:
                return cls.auto_discover()
            except ConfigError:
                # Fall back to environment only
                return cls.from_environment()

    def copy(self, **overrides) -> "JoplinMCPConfig":
        """Create a copy of this configuration with optional overrides."""
        current_values = {
            "host": self.host,
            "port": self.port,
            "token": self.token,
            "timeout": self.timeout,
            "verify_ssl": self.verify_ssl,
        }
        current_values.update(overrides)
        return self.__class__(**current_values)

    def save_to_file(self, file_path: Union[str, Path], format: str = "auto") -> None:
        """Save current configuration to a file.

        Args:
            file_path: Path to save the configuration file
            format: File format ('json', 'yaml', or 'auto' to detect from extension)
        """
        file_path = Path(file_path)

        # Determine format
        if format == "auto":
            if file_path.suffix.lower() == ".json":
                format = "json"
            elif file_path.suffix.lower() in (".yaml", ".yml"):
                format = "yaml"
            else:
                raise ConfigError(
                    f"Cannot auto-detect format for {file_path}. Use explicit format parameter."
                )

        # Prepare data (exclude sensitive information)
        config_data = {
            "host": self.host,
            "port": self.port,
            "timeout": self.timeout,
            "verify_ssl": self.verify_ssl,
            # Note: token is intentionally excluded for security
        }

        # Create directory if it doesn't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                if format == "json":
                    json.dump(config_data, f, indent=2)
                elif format == "yaml":
                    yaml.safe_dump(config_data, f, default_flow_style=False, indent=2)
                else:
                    raise ConfigError(f"Unsupported format: {format}")
        except OSError as e:
            raise ConfigError(f"Error writing configuration file {file_path}: {e}")

    def test_connection(self) -> bool:
        """Test if the configuration allows successful connection to Joplin.

        Returns:
            True if connection test passes, False otherwise
        """
        try:
            import httpx

            # Validate configuration first
            self.validate()

            # Test connection with a simple ping
            with httpx.Client(verify=self.verify_ssl, timeout=self.timeout) as client:
                response = client.get(
                    f"{self.base_url}/ping",
                    headers={"Authorization": f"Bearer {self.token}"},
                )
                return response.status_code == 200

        except Exception:
            return False

    @property
    def connection_info(self) -> Dict[str, Any]:
        """Get connection information for debugging."""
        return {
            "base_url": self.base_url,
            "host": self.host,
            "port": self.port,
            "verify_ssl": self.verify_ssl,
            "timeout": self.timeout,
            "has_token": bool(self.token),
            "token_length": len(self.token) if self.token else 0,
        }
