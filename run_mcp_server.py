#!/usr/bin/env python3
"""
Joplin MCP Server - Production Runner
This version provides clean MCP protocol communication for Claude Desktop
"""

import asyncio
import json
import logging
import sys
import os
from pathlib import Path

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent

# Redirect all logging to file only (in the script directory)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(SCRIPT_DIR / 'joplin-mcp.log')]
)

async def run_mcp_server():
    """Run MCP server with clean JSON protocol communication"""
    try:
        from joplin_mcp.server import JoplinMCPServer
        from joplin_mcp.config import JoplinMCPConfig
        
        # Change to script directory to find config file
        os.chdir(SCRIPT_DIR)
        
        # Load config silently
        config_path = SCRIPT_DIR / "joplin-mcp.json"
        if not config_path.exists():
            print(f"Configuration file not found: {config_path}", file=sys.stderr)
            sys.exit(1)
        
        with open(config_path) as f:
            config_data = json.load(f)
        
        config = JoplinMCPConfig(
            host=config_data.get("host", "localhost"),
            port=config_data.get("port", 41184),
            token=config_data.get("token"),
            timeout=config_data.get("timeout", 30),
            verify_ssl=config_data.get("verify_ssl", False)
        )
        
        # Create server with minimal setup
        server = JoplinMCPServer(config=config, skip_ping=True)
        
        # Start server immediately - this will only output JSON to stdout
        await server.start()
        
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(run_mcp_server())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1) 