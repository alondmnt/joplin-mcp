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

# Import configuration
from .config import JoplinMCPConfig

__version__ = "0.6.0"
__author__ = "Alon Diament"
__license__ = "MIT"
__description__ = "Model Context Protocol server for the Joplin note-taking application"

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


# Package-level logging configuration
logging.getLogger(__name__).addHandler(logging.NullHandler())

# Optional: Add package-level configuration
_DEFAULT_LOG_LEVEL = logging.WARNING
_logger = logging.getLogger(__name__)
_logger.setLevel(_DEFAULT_LOG_LEVEL)
