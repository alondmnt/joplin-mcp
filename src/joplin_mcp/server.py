#!/usr/bin/env python3
"""Server module for joplin-mcp package.

This can be run as: python -m joplin_mcp.server
"""

import sys
from pathlib import Path

def main():
    """Main entry point for the FastMCP server."""
    try:
        # Import and run the FastMCP server
        from .fastmcp_server import main as server_main
        return server_main()
    except ImportError as e:
        print(f"❌ Failed to import FastMCP server: {e}")
        print("ℹ️  Please ensure the package is properly installed.")
        return 1
    except Exception as e:
        print(f"❌ Server failed to start: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 