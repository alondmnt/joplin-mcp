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

import logging
from typing import Optional

# Import exceptions first (they have no dependencies)
from .exceptions import (
    JoplinAPIError,
    JoplinConfigurationError,
    JoplinConnectionError,
    JoplinMCPError,
    JoplinServerError,
)

# Import configuration
from .config import JoplinMCPConfig

# Import data models
from .models import (
    MCPNote,
    MCPNotebook,
    MCPSearchResult,
    MCPTag,
    MCPPaginatedResponse,
    MCPErrorResponse,
    MCPAPIResponse,
    NotePriority,
    JoplinTimestamp,
)

# Legacy client and server removed - using FastMCP implementation
# from .client import JoplinMCPClient  # REMOVED
# from .server import JoplinMCPServer  # REMOVED

__version__ = "0.1.1"
__author__ = "Joplin MCP Contributors"
__license__ = "MIT"
__description__ = "Model Context Protocol server for Joplin note-taking application"

# Public API exports - these will be available when importing the package
__all__ = [
    # Core classes (legacy server/client removed - use FastMCP implementation)
    # "JoplinMCPServer",  # REMOVED - use run_fastmcp_server.py
    # "JoplinMCPClient",  # REMOVED - use FastMCP directly
    # Configuration and models
    "JoplinMCPConfig",
    "MCPNote",
    "MCPNotebook",
    "MCPTag",
    "MCPSearchResult",
    "MCPPaginatedResponse",
    "MCPErrorResponse",
    "MCPAPIResponse",
    "NotePriority",
    "JoplinTimestamp",
    # Exceptions
    "JoplinMCPError",
    "JoplinConnectionError",
    "JoplinConfigurationError",
    "JoplinAPIError",
    "JoplinServerError",
    # Version and metadata
    "__version__",
    "__author__",
    "__license__",
    "__description__",
]

def get_version() -> str:
    """Get the current version of joplin-mcp."""
    return __version__


def get_server_info() -> dict:
    """Get server information including version, supported tools, etc."""
    return {
        "name": "joplin-mcp",
        "version": __version__,
        "description": "FastMCP-based " + __description__,
        "author": __author__,
        "license": __license__,
        "implementation": "FastMCP",
        "supported_tools": [
            "find_notes",
            "find_notes_with_tag",
            "find_notes_in_notebook",
            "get_all_notes",
            "get_note",
            "create_note",
            "update_note",
            "delete_note",
            "list_notebooks",
            "create_notebook",
            "update_notebook",
            "delete_notebook",
            "list_tags",
            "create_tag",
            "update_tag",
            "delete_tag",
            "get_tags_by_note",
            "tag_note",
            "untag_note",
            "ping_joplin",
        ],
        "mcp_version": "1.0.0",
    }


# Package-level logging configuration
logging.getLogger(__name__).addHandler(logging.NullHandler())

# Optional: Add package-level configuration
_DEFAULT_LOG_LEVEL = logging.WARNING
_logger = logging.getLogger(__name__)
_logger.setLevel(_DEFAULT_LOG_LEVEL)
