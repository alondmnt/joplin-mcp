#!/usr/bin/env python3
"""Server module for joplin-mcp package.

This can be run as: python -m joplin_mcp.server
"""

import sys
from pathlib import Path

def main():
    """Main entry point for the FastMCP server."""
    import sys
    import argparse
    
    # Parse command line arguments for transport options
    parser = argparse.ArgumentParser(description="Joplin MCP Server")
    parser.add_argument("--transport", "-t", choices=["stdio", "http"], default="stdio", help="Transport protocol")
    parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP transport")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port for HTTP transport")
    parser.add_argument("--path", default="/mcp", help="Path for HTTP transport")
    parser.add_argument("--log-level", choices=["debug", "info", "warning", "error"], default="info", help="Log level")
    args = parser.parse_args()
    
    try:
        # Import and run the FastMCP server
        from .fastmcp_server import main as server_main
        return server_main(
            transport=args.transport,
            host=args.host,
            port=args.port,
            path=args.path,
            log_level=args.log_level
        )
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