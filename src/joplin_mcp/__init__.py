"""
Joplin MCP - Model Context Protocol server for Joplin note-taking application.

This package provides a comprehensive MCP server implementation that enables AI assistants
and developers to interact with Joplin data through standardized protocol interfaces.

Features:
- Complete CRUD operations for notes, notebooks, and tags
- Full-text search capabilities with Joplin syntax support
- MCP-compliant tool definitions and error handling
- Built on the proven joppy library for reliable Joplin API integration
- Comprehensive test coverage with TDD methodology

Example usage:
    >>> from joplin_mcp import JoplinMCPServer
    >>> server = JoplinMCPServer(token="your_joplin_token")
    >>> await server.start()
"""

__version__ = "0.1.0"
__author__ = "Joplin MCP Contributors"
__license__ = "MIT"
__description__ = "Model Context Protocol server for Joplin note-taking application"

# Public API exports - these will be available when importing the package
__all__ = [
    # Core server and client classes
    "JoplinMCPServer",
    "JoplinMCPClient",
    # Configuration and models
    "JoplinConfig",
    "MCPNote",
    "MCPNotebook",
    "MCPTag",
    "MCPSearchResult",
    # Exceptions
    "JoplinMCPError",
    "JoplinConnectionError",
    "JoplinAuthenticationError",
    "JoplinNotFoundError",
    # Version and metadata
    "__version__",
    "__author__",
    "__license__",
    "__description__",
]

# Import exceptions first (they have no dependencies)
try:
    from .exceptions import (
        JoplinAuthenticationError,
        JoplinConnectionError,
        JoplinMCPError,
        JoplinNotFoundError,
    )
except ImportError:
    # During development, modules might not exist yet
    # Define placeholder classes to prevent import errors
    class JoplinMCPError(Exception):
        """Base exception for Joplin MCP operations."""

        pass

    class JoplinConnectionError(JoplinMCPError):
        """Raised when connection to Joplin server fails."""

        pass

    class JoplinAuthenticationError(JoplinMCPError):
        """Raised when Joplin API authentication fails."""

        pass

    class JoplinNotFoundError(JoplinMCPError):
        """Raised when requested Joplin resource is not found."""

        pass


# Import configuration
try:
    from .config import JoplinConfig
except ImportError:
    # Placeholder during development
    JoplinConfig = None

# Import data models
try:
    from .models import (
        MCPNote,
        MCPNotebook,
        MCPSearchResult,
        MCPTag,
    )
except ImportError:
    # Placeholders during development
    MCPNote = None
    MCPNotebook = None
    MCPTag = None
    MCPSearchResult = None

# Import client and server (these depend on models and config)
try:
    from .client import JoplinMCPClient
except ImportError:
    JoplinMCPClient = None

try:
    from .server import JoplinMCPServer
except ImportError:
    JoplinMCPServer = None


def get_version() -> str:
    """Get the current version of joplin-mcp."""
    return __version__


def get_server_info() -> dict:
    """Get server information including version, supported tools, etc."""
    return {
        "name": "joplin-mcp",
        "version": __version__,
        "description": __description__,
        "author": __author__,
        "license": __license__,
        "supported_tools": [
            "search_notes",
            "get_note",
            "create_note",
            "update_note",
            "delete_note",
            "list_notebooks",
            "get_notebook",
            "create_notebook",
            "list_tags",
            "create_tag",
            "tag_note",
            "untag_note",
            "ping_joplin",
        ],
        "mcp_version": "1.0.0",
    }


# Set up logging for the package
import logging

# Package-level configuration
logging.getLogger(__name__).addHandler(logging.NullHandler())

# Optional: Add package-level configuration
_DEFAULT_LOG_LEVEL = logging.WARNING
_logger = logging.getLogger(__name__)
_logger.setLevel(_DEFAULT_LOG_LEVEL)
