#!/usr/bin/env python3
"""Server module for joplin-mcp package.

This can be run as: python -m joplin_mcp.server
"""

import os
import sys
import logging
from pathlib import Path


def main():
    """Main entry point for the FastMCP server."""
    import argparse

    # Parse command line arguments for transport options
    parser = argparse.ArgumentParser(description="Joplin MCP Server")
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to configuration file (e.g., joplin-mcp.json)",
    )
    parser.add_argument(
        "--transport",
        "-t",
        choices=["stdio", "http", "streamable-http", "sse"],
        default="stdio",
        help="Transport protocol",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host for HTTP/Streamable HTTP transport"
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8000,
        help="Port for HTTP/Streamable HTTP transport",
    )
    parser.add_argument(
        "--path", default="/mcp", help="Path for HTTP/Streamable HTTP transport"
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Log level",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        help="Write logs to this file (created if missing). Logs still go to stderr if not provided.",
    )
    args = parser.parse_args()

    try:
        # Configure logging BEFORE importing the server so import-time logs are captured
        level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
        }
        log_level = level_map.get(args.log_level, logging.INFO)

        handlers = []
        if args.log_file:
            try:
                log_path = Path(args.log_file)
                if log_path.parent:
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
            except Exception:
                # Fall back to stderr only if file handler fails
                handlers.append(logging.StreamHandler(sys.stderr))
        else:
            handlers.append(logging.StreamHandler(sys.stderr))

        # Reset root handlers to avoid duplicates across restarts
        root_logger = logging.getLogger()
        for h in list(root_logger.handlers):
            root_logger.removeHandler(h)
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=handlers,
        )

        # Ensure config path is honored during import-time tool registration
        if args.config:
            os.environ["JOPLIN_MCP_CONFIG"] = args.config

        # Import and run the FastMCP server
        from .fastmcp_server import main as server_main

        return server_main(
            config_file=args.config,
            transport=args.transport,
            host=args.host,
            port=args.port,
            path=args.path,
            log_level=args.log_level,
        )
    except ImportError as e:
        print(f"❌ Failed to import FastMCP server: {e}", file=sys.stderr)
        print("ℹ️  Please ensure the package is properly installed.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Server failed to start: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
