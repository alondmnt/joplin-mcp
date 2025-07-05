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
  python run_fastmcp_server.py                          # Use default joplin-mcp.json
  python run_fastmcp_server.py --config my-config.json  # Use custom config file
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Configuration file path (default: joplin-mcp.json if exists, otherwise auto-discovery)"
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
    
    print("🔧 Press Ctrl+C to stop")
    print("-" * 50)
    
    try:
        main(config_file=args.config)
    except KeyboardInterrupt:
        print("\n👋 FastMCP server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1) 