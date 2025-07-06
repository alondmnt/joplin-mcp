#!/usr/bin/env python3
"""Main module for joplin-mcp package.

This allows running the package as: python -m joplin_mcp
By default, this starts the server.
"""

import sys

if __name__ == "__main__":
    # Default to running the server
    from .server import main
    sys.exit(main()) 