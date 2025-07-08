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
        except ValueError as e:
            if strict:
                raise ConfigError(
                    f"Invalid integer value for {field_name}: '{value}'. Use a numeric value (e.g., '30', '8080')"
                ) from e
            else:
                raise ConfigError(f"Invalid integer value for {field_name}: {value}") from e

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

    # Default tool configurations - optimized for LLMs (18 tools total)
    DEFAULT_TOOLS = {
        # Finding notes (4 tools enabled by default, 1 disabled)
        "find_notes": True,              # Find notes by text content
        "find_notes_with_tag": True,     # Find notes by tag
        "find_notes_in_notebook": True,  # Find notes by notebook
        "get_all_notes": False,          # Get all notes - disabled by default (can fill context window)
        "get_note": True,                # Get specific note by ID
        
        # Managing notes (3 tools)
        "create_note": True,             # Create new note
        "update_note": True,             # Update existing note
        "delete_note": True,             # Delete note
        
        # Managing notebooks (4 tools)
        "list_notebooks": True,          # List all notebooks
        "create_notebook": True,         # Create new notebook
        "update_notebook": False,        # Update notebook (disabled by default)
        "delete_notebook": True,         # Delete notebook
        
        # Managing tags (5 tools)
        "list_tags": True,               # List all tags
        "create_tag": True,              # Create new tag
        "update_tag": False,             # Update tag (disabled by default)
        "delete_tag": True,              # Delete tag
        "get_tags_by_note": True,        # Get tags for a note
        
        # Tag-note relationships (2 tools)
        "tag_note": True,                # Add tag to note
        "untag_note": True,              # Remove tag from note
        
        # Utility operations (1 tool)
        "ping_joplin": True,             # Test connection
        
        # Note: Redundant tools removed (search_notes, get_notebook, search_notebooks, 
        # get_notes_by_notebook, get_tag, search_tags, get_notes_by_tag)
        # update_tag and update_notebook are disabled by default but available if needed
    }

    # Tool categories for easier management
    TOOL_CATEGORIES = {
        "finding": ["find_notes", "find_notes_with_tag", "find_notes_in_notebook", "get_all_notes", "get_note"],
        "notes": ["create_note", "update_note", "delete_note"],
        "notebooks": ["list_notebooks", "create_notebook", "update_notebook", "delete_notebook"],
        "tags": ["list_tags", "create_tag", "update_tag", "delete_tag", "get_tags_by_note", "tag_note", "untag_note"],
        "utilities": ["ping_joplin"],
    }

    # Content exposure levels for privacy control
    CONTENT_EXPOSURE_LEVELS = {
        "none": "No content shown - titles and metadata only",
        "preview": "Short preview snippets (200 characters)",
        "full": "Full content access"
    }

    # Default content exposure settings
    DEFAULT_CONTENT_EXPOSURE = {
        "search_results": "preview",  # Search results show previews
        "individual_notes": "full",   # Individual note retrieval shows full content
        "listings": "none",           # Note listings show no content
        "max_preview_length": 200     # Maximum preview length in characters
    }

    def __init__(
        self,
        host: str = "localhost",
        port: int = 41184,
        token: Optional[str] = None,
        timeout: int = 60,
        verify_ssl: bool = True,
        tools: Optional[Dict[str, bool]] = None,
        content_exposure: Optional[Dict[str, Union[str, int]]] = None,
    ):
        """Initialize configuration with default values."""
        self.host = host
        self.port = port
        self.token = token
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        
        # Initialize tools configuration
        self.tools = self.DEFAULT_TOOLS.copy()
        if tools:
            self.tools.update(tools)
        
        # Initialize content exposure configuration
        self.content_exposure = self.DEFAULT_CONTENT_EXPOSURE.copy()
        if content_exposure:
            self.content_exposure.update(content_exposure)

    def is_tool_enabled(self, tool_name: str) -> bool:
        """Check if a specific tool is enabled."""
        return self.tools.get(tool_name, False)

    def enable_tool(self, tool_name: str) -> None:
        """Enable a specific tool."""
        if tool_name not in self.DEFAULT_TOOLS:
            raise ConfigError(f"Unknown tool: {tool_name}")
        self.tools[tool_name] = True

    def disable_tool(self, tool_name: str) -> None:
        """Disable a specific tool."""
        if tool_name not in self.DEFAULT_TOOLS:
            raise ConfigError(f"Unknown tool: {tool_name}")
        self.tools[tool_name] = False

    def get_content_exposure_level(self, context: str) -> str:
        """Get content exposure level for a specific context."""
        return self.content_exposure.get(context, "none")

    def set_content_exposure_level(self, context: str, level: str) -> None:
        """Set content exposure level for a specific context."""
        if level not in self.CONTENT_EXPOSURE_LEVELS:
            raise ConfigError(f"Invalid content exposure level: {level}. Must be one of: {list(self.CONTENT_EXPOSURE_LEVELS.keys())}")
        self.content_exposure[context] = level

    def get_max_preview_length(self) -> int:
        """Get maximum preview length for content snippets."""
        return self.content_exposure.get("max_preview_length", 200)

    def should_show_content(self, context: str) -> bool:
        """Check if content should be shown for a specific context."""
        level = self.get_content_exposure_level(context)
        return level in ["preview", "full"]

    def should_show_full_content(self, context: str) -> bool:
        """Check if full content should be shown for a specific context."""
        level = self.get_content_exposure_level(context)
        return level == "full"

    def enable_tool_category(self, category: str) -> None:
        """Enable all tools in a category."""
        if category not in self.TOOL_CATEGORIES:
            raise ConfigError(f"Unknown tool category: {category}")
        for tool_name in self.TOOL_CATEGORIES[category]:
            self.tools[tool_name] = True

    def disable_tool_category(self, category: str) -> None:
        """Disable all tools in a category."""
        if category not in self.TOOL_CATEGORIES:
            raise ConfigError(f"Unknown tool category: {category}")
        for tool_name in self.TOOL_CATEGORIES[category]:
            self.tools[tool_name] = False

    def get_enabled_tools(self) -> List[str]:
        """Get list of enabled tool names."""
        return [tool_name for tool_name, enabled in self.tools.items() if enabled]

    def get_disabled_tools(self) -> List[str]:
        """Get list of disabled tool names."""
        return [tool_name for tool_name, enabled in self.tools.items() if not enabled]

    def get_tool_categories(self) -> Dict[str, List[str]]:
        """Get available tool categories."""
        return self.TOOL_CATEGORIES.copy()

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

        # Load tools configuration from environment
        tools = {}
        for tool_name in cls.DEFAULT_TOOLS:
            env_var = f"{prefix}TOOL_{tool_name.upper()}"
            tool_value = os.environ.get(env_var)
            if tool_value is not None:
                tools[tool_name] = ConfigParser.parse_bool(tool_value)

        # Load content exposure configuration from environment
        content_exposure = {}
        for context in ["search_results", "individual_notes", "listings"]:
            env_var = f"{prefix}CONTENT_{context.upper()}"
            content_value = os.environ.get(env_var)
            if content_value is not None:
                content_exposure[context] = content_value

        # Load max preview length from environment
        max_preview_env = os.environ.get(f"{prefix}MAX_PREVIEW_LENGTH")
        if max_preview_env is not None:
            content_exposure["max_preview_length"] = ConfigParser.parse_int(max_preview_env, "max_preview_length")

        return cls(
            host=host, port=port, token=token, timeout=timeout, verify_ssl=verify_ssl, tools=tools, content_exposure=content_exposure
        )

    def validate(self) -> None:
        """Validate configuration and raise ConfigError if invalid."""
        ConfigValidator.validate_token_format(self.token)
        ConfigValidator.validate_port_range(self.port)
        ConfigValidator.validate_timeout_positive(self.timeout)
        
        # Validate tools configuration
        if not isinstance(self.tools, dict):
            raise ConfigError("Tools configuration must be a dictionary")
        
        for tool_name, enabled in self.tools.items():
            if tool_name not in self.DEFAULT_TOOLS:
                raise ConfigError(f"Unknown tool in configuration: {tool_name}")
            if not isinstance(enabled, bool):
                raise ConfigError(f"Tool configuration for '{tool_name}' must be boolean, got {type(enabled)}")
        
        # Validate content exposure configuration
        if not isinstance(self.content_exposure, dict):
            raise ConfigError("Content exposure configuration must be a dictionary")
        
        for key, value in self.content_exposure.items():
            if key == "max_preview_length":
                if not isinstance(value, int) or value < 0:
                    raise ConfigError(f"max_preview_length must be a non-negative integer, got {type(value)}")
            elif key in ["search_results", "individual_notes", "listings"]:
                if value not in self.CONTENT_EXPOSURE_LEVELS:
                    raise ConfigError(f"Invalid content exposure level '{value}' for '{key}'. Must be one of: {list(self.CONTENT_EXPOSURE_LEVELS.keys())}")
            else:
                raise ConfigError(f"Unknown content exposure setting: {key}")

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
            "tools": self.tools.copy(),
            "enabled_tools_count": len(self.get_enabled_tools()),
            "disabled_tools_count": len(self.get_disabled_tools()),
            "content_exposure": self.content_exposure.copy(),
        }

    def __repr__(self) -> str:
        """String representation, hiding sensitive data."""
        token_display = "***" if self.token else None
        enabled_count = len(self.get_enabled_tools())
        total_count = len(self.tools)
        content_levels = {k: v for k, v in self.content_exposure.items() if k != "max_preview_length"}
        return (
            f"JoplinMCPConfig(host='{self.host}', port={self.port}, "
            f"token={token_display}, timeout={self.timeout}, "
            f"verify_ssl={self.verify_ssl}, tools={enabled_count}/{total_count} enabled, "
            f"content_exposure={content_levels})"
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
                except json.JSONDecodeError as json_error:
                    raise ConfigError(
                        f"Invalid JSON in file {file_path}: {json_error}. Please check syntax and fix any formatting errors."
                    ) from json_error
            elif file_path.suffix.lower() in (".yaml", ".yml"):
                try:
                    data = yaml.safe_load(content)
                except yaml.YAMLError as yaml_error:
                    raise ConfigError(
                        f"Invalid YAML in file {file_path}: {yaml_error}. Please check syntax and fix any formatting errors."
                    ) from yaml_error
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
            except ConfigError as config_error:
                raise ConfigError(f"Error in file {file_path}: {config_error}") from config_error

            return cls(**validated_data)

        except OSError as os_error:
            raise ConfigError(f"Error reading configuration file {file_path}: {os_error}") from os_error

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

        # Tools - must be dictionary with boolean values
        if "tools" in data:
            if data["tools"] is None:
                # Use default for null values
                pass  # Don't add to validated, will use default
            elif isinstance(data["tools"], dict):
                tools = {}
                for tool_name, enabled in data["tools"].items():
                    if not isinstance(tool_name, str):
                        raise ConfigError(
                            f"Invalid tool name in 'tools': expected string, got {type(tool_name)}"
                        )
                    if tool_name not in cls.DEFAULT_TOOLS:
                        raise ConfigError(
                            f"Unknown tool in 'tools' configuration: {tool_name}"
                        )
                    if not isinstance(enabled, bool):
                        raise ConfigError(
                            f"Invalid data type for tool '{tool_name}': expected boolean, got {type(enabled)}"
                        )
                    tools[tool_name] = enabled
                validated["tools"] = tools
            else:
                raise ConfigError(
                    f"Invalid data type for 'tools': expected dictionary, got {type(data['tools'])}"
                )

        # Content exposure - must be dictionary with string/int values
        if "content_exposure" in data:
            if data["content_exposure"] is None:
                # Use default for null values
                pass  # Don't add to validated, will use default
            elif isinstance(data["content_exposure"], dict):
                content_exposure = {}
                for key, value in data["content_exposure"].items():
                    if not isinstance(key, str):
                        raise ConfigError(
                            f"Invalid content exposure key: expected string, got {type(key)}"
                        )
                    if key == "max_preview_length":
                        if not isinstance(value, int) or value < 0:
                            raise ConfigError(
                                f"Invalid value for 'max_preview_length': expected non-negative integer, got {type(value)}"
                            )
                    elif key in ["search_results", "individual_notes", "listings"]:
                        if not isinstance(value, str):
                            raise ConfigError(
                                f"Invalid value for '{key}': expected string, got {type(value)}"
                            )
                        if value not in cls.CONTENT_EXPOSURE_LEVELS:
                            raise ConfigError(
                                f"Invalid content exposure level '{value}' for '{key}'. Must be one of: {list(cls.CONTENT_EXPOSURE_LEVELS.keys())}"
                            )
                    else:
                        raise ConfigError(
                            f"Unknown content exposure setting: {key}"
                        )
                    content_exposure[key] = value
                validated["content_exposure"] = content_exposure
            else:
                raise ConfigError(
                    f"Invalid data type for 'content_exposure': expected dictionary, got {type(data['content_exposure'])}"
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

        # Merge tools configuration specially
        merged_tools = config.tools.copy()
        # Override with environment tools
        for tool_name, enabled in env_config.tools.items():
            env_var_name = f"{prefix}TOOL_{tool_name.upper()}"
            if env_var_name in os.environ:
                merged_tools[tool_name] = enabled
        # Override with direct tool overrides
        if "tools" in overrides:
            merged_tools.update(overrides["tools"])

        # Merge content exposure configuration specially
        merged_content_exposure = config.content_exposure.copy()
        # Override with environment content exposure
        for key, value in env_config.content_exposure.items():
            env_var_name = f"{prefix}CONTENT_{key.upper()}" if key != "max_preview_length" else f"{prefix}MAX_PREVIEW_LENGTH"
            if env_var_name in os.environ:
                merged_content_exposure[key] = value
        # Override with direct content exposure overrides
        if "content_exposure" in overrides:
            merged_content_exposure.update(overrides["content_exposure"])

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
            "tools": merged_tools,
            "content_exposure": merged_content_exposure,
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

        # Tools validation
        if not isinstance(self.tools, dict):
            errors.append(ConfigError("Tools configuration must be a dictionary"))
        else:
            for tool_name, enabled in self.tools.items():
                if tool_name not in self.DEFAULT_TOOLS:
                    errors.append(ConfigError(f"Unknown tool in configuration: {tool_name}"))
                if not isinstance(enabled, bool):
                    errors.append(ConfigError(f"Tool configuration for '{tool_name}' must be boolean, got {type(enabled)}"))

        # Content exposure validation
        if not isinstance(self.content_exposure, dict):
            errors.append(ConfigError("Content exposure configuration must be a dictionary"))
        else:
            for key, value in self.content_exposure.items():
                if key == "max_preview_length":
                    if not isinstance(value, int) or value < 0:
                        errors.append(ConfigError(f"max_preview_length must be a non-negative integer, got {type(value)}"))
                elif key in ["search_results", "individual_notes", "listings"]:
                    if value not in self.CONTENT_EXPOSURE_LEVELS:
                        errors.append(ConfigError(f"Invalid content exposure level '{value}' for '{key}'. Must be one of: {list(self.CONTENT_EXPOSURE_LEVELS.keys())}"))
                else:
                    errors.append(ConfigError(f"Unknown content exposure setting: {key}"))

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
            "tools": self.tools.copy(),
            "content_exposure": self.content_exposure.copy(),
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
            "tools": self.tools.copy(),
            "content_exposure": self.content_exposure.copy(),
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
        except OSError as os_error:
            raise ConfigError(f"Error writing configuration file {file_path}: {os_error}") from os_error

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
            "tools_summary": {
                "enabled": len(self.get_enabled_tools()),
                "disabled": len(self.get_disabled_tools()),
                "total": len(self.tools),
            },
            "content_exposure": self.content_exposure.copy(),
        }

    # === INTERACTIVE CONFIGURATION ===

    @classmethod
    def create_interactively(
        cls, 
        token: Optional[str] = None,
        include_permissions: bool = True,
        include_content_privacy: bool = True,
        **defaults
    ) -> "JoplinMCPConfig":
        """Create configuration interactively with user prompts.
        
        Args:
            token: Pre-provided token (skip token prompt if provided)
            include_permissions: Whether to prompt for tool permissions
            include_content_privacy: Whether to prompt for content privacy settings
            defaults: Default values for configuration options
        
        Returns:
            Configured JoplinMCPConfig instance
        """
        from .ui_integration import get_permission_settings, get_token_interactively, get_content_privacy_settings
        
        # Get token if not provided
        if not token:
            token = get_token_interactively()
        
        # Get permission settings if requested
        if include_permissions:
            tool_permissions = get_permission_settings()
        else:
            tool_permissions = cls.DEFAULT_TOOLS.copy()
        
        # Get content privacy settings if requested
        if include_content_privacy:
            content_privacy = get_content_privacy_settings()
        else:
            content_privacy = cls.DEFAULT_CONTENT_EXPOSURE.copy()
        
        # Create configuration with user choices and defaults
        config_kwargs = {
            "host": defaults.get("host", "localhost"),
            "port": defaults.get("port", 41184),
            "token": token,
            "timeout": defaults.get("timeout", 30),
            "verify_ssl": defaults.get("verify_ssl", False),
            "tools": tool_permissions,
            "content_exposure": content_privacy
        }
        
        return cls(**config_kwargs)

    def save_interactively(
        self, 
        suggested_path: Optional[Path] = None,
        include_token: bool = True
    ) -> Path:
        """Save configuration to a file with interactive path selection.
        
        Args:
            suggested_path: Suggested file path
            include_token: Whether to include token in saved file
        
        Returns:
            Path where config was saved
        """
        if not suggested_path:
            suggested_path = Path.cwd() / "joplin-mcp.json"
        
        config_path = suggested_path
        
        # Prepare config data
        config_data = {
            "host": self.host,
            "port": self.port,
            "timeout": self.timeout,
            "verify_ssl": self.verify_ssl,
            "tools": self.tools.copy(),
            "content_exposure": self.content_exposure.copy()
        }
        
        if include_token and self.token:
            config_data["token"] = self.token
        
        # Save configuration
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        return config_path
