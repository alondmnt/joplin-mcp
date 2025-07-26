#!/usr/bin/env python3
"""
Simple runner for the new FastMCP-based Joplin server.
"""

import sys
import os
import argparse
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import and run the new server
from joplin_mcp.fastmcp_server import main

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="FastMCP-based Joplin MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_fastmcp_server.py                          # Use default joplin-mcp.json with STDIO transport
  python run_fastmcp_server.py --config my-config.json  # Use custom config file with STDIO transport
  python run_fastmcp_server.py --transport http         # Use HTTP transport on default port 8000
  python run_fastmcp_server.py --transport streamable-http  # Use Streamable HTTP transport (recommended for web clients)
  python run_fastmcp_server.py --transport http --port 9000 --host 0.0.0.0  # HTTP on custom port/host
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Configuration file path (default: joplin-mcp.json if exists, otherwise auto-discovery)"
    )
    
    parser.add_argument(
        "--transport", "-t",
        type=str,
        choices=["stdio", "http", "streamable-http", "sse"],
        default="stdio",
        help="Transport protocol to use (default: stdio)"
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to for HTTP/Streamable HTTP transport (default: 127.0.0.1)"
    )
    
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="Port to bind to for HTTP/Streamable HTTP transport (default: 8000)"
    )
    
    parser.add_argument(
        "--path",
        type=str,
        default="/mcp",
        help="Path for HTTP/Streamable HTTP transport endpoint (default: /mcp)"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Logging level (default: info)"
    )
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    print("🚀 FastMCP Joplin Server Starting (PRODUCTION VERSION)")
    print("⚡ This is the optimized FastMCP server, not the debug version")
    
    if args.config:
        print(f"📋 Using config file: {args.config}")
    else:
        config_path = Path("joplin-mcp.json")
        if config_path.exists():
            print(f"📋 Using default config file: {config_path}")
        else:
            print("📋 Using auto-discovery for config")
    
    print(f"🚀 Transport: {args.transport.upper()}")
    if args.transport == "http":
        print(f"🌐 HTTP Server: {args.host}:{args.port}{args.path}")
    
    print("🔧 Press Ctrl+C to stop")
    print("-" * 50)
    
    try:
        main(
            config_file=args.config,
            transport=args.transport,
            host=args.host,
            port=args.port,
            path=args.path,
            log_level=args.log_level
        )
    except KeyboardInterrupt:
        print("\n👋 FastMCP server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1) 