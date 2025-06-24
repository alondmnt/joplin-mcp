#!/usr/bin/env python3
"""
Joplin MCP Server - Local Deployment Script

This script runs the Joplin MCP server for local development and testing.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

try:
    from joplin_mcp.server import JoplinMCPServer
    from joplin_mcp.config import JoplinMCPConfig
except ImportError as e:
    print(f"❌ Error importing joplin_mcp: {e}")
    print("Make sure you're in the correct environment and the package is installed.")
    sys.exit(1)


def setup_logging(level: str = "INFO"):
    """Set up logging for the MCP server."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('joplin-mcp.log')
        ]
    )


def load_config(config_path: str = "joplin-mcp.json") -> JoplinMCPConfig:
    """Load configuration from file."""
    config_file = Path(config_path)
    
    if not config_file.exists():
        print(f"❌ Configuration file not found: {config_path}")
        print("Please create a joplin-mcp.json file with your Joplin API token.")
        print("Example:")
        print(json.dumps({
            "host": "localhost",
            "port": 41184,
            "token": "YOUR_JOPLIN_API_TOKEN_HERE",
            "timeout": 30,
            "verify_ssl": False,
            "log_level": "INFO"
        }, indent=2))
        sys.exit(1)
    
    try:
        with open(config_file) as f:
            config_data = json.load(f)
        
        if config_data.get("token") == "YOUR_JOPLIN_API_TOKEN_HERE":
            print("❌ Please update the token in joplin-mcp.json with your actual Joplin API token")
            print("You can find this in Joplin: Tools → Options → Web Clipper → Authorization token")
            sys.exit(1)
        
        return JoplinMCPConfig(
            host=config_data.get("host", "localhost"),
            port=config_data.get("port", 41184),
            token=config_data.get("token"),
            timeout=config_data.get("timeout", 30),
            verify_ssl=config_data.get("verify_ssl", False)
        )
    
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        sys.exit(1)


async def test_connection(config: JoplinMCPConfig):
    """Test connection to Joplin."""
    print("🔍 Testing connection to Joplin...")
    
    try:
        from joplin_mcp.client import JoplinMCPClient
        
        client = JoplinMCPClient(config=config)
        
        if client.ping():
            print("✅ Successfully connected to Joplin!")
            
            # Get some basic info
            try:
                # Test basic API access
                from joplin_mcp.client import JoplinMCPClient
                
                # Try to get notebooks using the correct joppy method
                api_client = client._joppy_client
                notebooks = api_client.get_all_notebooks()
                
                # Try a simple search
                search_results = client.search_notes("*", limit=10)
                
                print(f"📚 Found {len(notebooks)} notebooks")
                print(f"📝 Found {len(search_results)} notes (sample)")
                
            except Exception as e:
                print(f"⚠️ Connected but couldn't retrieve detailed data: {e}")
                print("✅ Basic connection works - this is normal for initial setup")
        else:
            print("❌ Failed to connect to Joplin")
            print("Please check:")
            print("1. Joplin is running")
            print("2. Web Clipper service is enabled in Joplin settings")
            print("3. The API token is correct")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        sys.exit(1)


async def run_server():
    """Run the MCP server."""
    print("🚀 Starting Joplin MCP Server...")
    print("=" * 50)
    
    # Load configuration
    config = load_config()
    setup_logging("INFO")
    
    # Test connection
    await test_connection(config)
    
    # Create and start server
    try:
        # Create the server with config object, skipping ping since we already tested it
        server = JoplinMCPServer(config=config, skip_ping=True)
        
        print(f"🎯 Server starting on {config.host}:{config.port}")
        print("📋 Available tools:")
        tools = server.get_available_tools()
        for tool in tools:
            print(f"  • {tool.name}: {tool.description}")
        
        print("\n🔗 To use with Ollama or other MCP clients:")
        print("   Configure your client to connect to this MCP server")
        print("\n📝 Logs are being written to: joplin-mcp.log")
        print("\n⏹️  Press Ctrl+C to stop the server")
        print("=" * 50)
        
        # Start the server (this will block)
        await server.start()
        
    except KeyboardInterrupt:
        print("\n👋 Shutting down Joplin MCP Server...")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1) 