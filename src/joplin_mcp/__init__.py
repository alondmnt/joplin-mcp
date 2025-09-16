"""
Joplin MCP - Model Context Protocol server for Joplin note-taking application.

This package provides a comprehensive MCP server implementation that enables AI assistants
and developers to interact with Joplin data through standardized protocol interfaces.

Features:
- Complete CRUD operations for notes, notebooks, and tags
- Full-text search capabilities with Joplin syntax support
- MCP-compliant tool definitions and error handling
- Built on the proven joppy library for reliable Joplin API integration
- FastMCP-based server implementation

Example usage:
    >>> from joplin_mcp.fastmcp_server import main
    >>> main()  # Start the FastMCP server
"""

import logging
from typing import Optional

# Import configuration
from .config import JoplinMCPConfig

__version__ = "0.4.0"
__author__ = "Joplin MCP Contributors"
__license__ = "MIT"
__description__ = "Model Context Protocol server for Joplin note-taking application"

# Public API exports - these will be available when importing the package
__all__ = [
    # Configuration
    "JoplinMCPConfig",
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
            "import_from_file",
        ],
        "mcp_version": "1.0.0",
    }


# Package-level logging configuration
logging.getLogger(__name__).addHandler(logging.NullHandler())

# Optional: Add package-level configuration
_DEFAULT_LOG_LEVEL = logging.WARNING
_logger = logging.getLogger(__name__)
_logger.setLevel(_DEFAULT_LOG_LEVEL)
