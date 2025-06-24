"""Joplin MCP specific exceptions."""


class JoplinMCPError(Exception):
    """Base exception for Joplin MCP operations."""

    pass


class JoplinConnectionError(JoplinMCPError):
    """Raised when connection to Joplin fails."""

    pass


class JoplinConfigurationError(JoplinMCPError):
    """Raised when Joplin configuration is invalid."""

    pass


class JoplinAPIError(JoplinMCPError):
    """Raised when Joplin API operations fail."""

    pass


class JoplinServerError(JoplinMCPError):
    """Raised when MCP server operations fail."""

    pass
