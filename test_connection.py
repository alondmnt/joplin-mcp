#!/usr/bin/env python3
"""
Simple test script to verify Joplin connection and API methods.
"""

import json
from pathlib import Path

def test_joplin_connection():
    """Test basic connection to Joplin."""
    print("🔍 Testing Joplin Connection...")
    
    # Load config
    config_file = Path("joplin-mcp.json")
    if not config_file.exists():
        print("❌ joplin-mcp.json not found")
        return
    
    with open(config_file) as f:
        config_data = json.load(f)
    
    token = config_data.get("token")
    host = config_data.get("host", "localhost")
    port = config_data.get("port", 41184)
    
    print(f"📡 Connecting to {host}:{port}")
    
    # Test with direct joppy
    try:
        from joppy.client_api import ClientApi
        print("✅ joppy imported successfully")
        
        # Create joppy client
        client = ClientApi(token=token, url=f"http://{host}:{port}")
        print("✅ joppy client created")
        
        # Test ping
        try:
            result = client.ping()
            print(f"✅ Ping successful: {result}")
        except Exception as e:
            print(f"❌ Ping failed: {e}")
            return
        
        # Test get_all_notebooks
        try:
            notebooks = client.get_all_notebooks()
            print(f"✅ Found {len(notebooks)} folders/notebooks")
            if notebooks:
                print(f"   First notebook: {notebooks[0].title if hasattr(notebooks[0], 'title') else notebooks[0]}")
        except Exception as e:
            print(f"❌ get_all_notebooks failed: {e}")
        
        # Test search
        try:
            notes = client.search(query="*")  # Use wildcard to get all notes
            if hasattr(notes, 'items'):
                note_list = notes.items
            elif hasattr(notes, '__iter__'):
                note_list = list(notes)
            else:
                note_list = [notes]
            
            print(f"✅ Found {len(note_list)} notes (sample)")
            if note_list:
                print(f"   First note: {note_list[0].title if hasattr(note_list[0], 'title') else note_list[0]}")
        except Exception as e:
            print(f"❌ Search failed: {e}")
            
    except ImportError as e:
        print(f"❌ Failed to import joppy: {e}")
        return
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return
    
    # Test with our MCP client
    print("\n🔍 Testing MCP Client...")
    try:
        from joplin_mcp.config import JoplinMCPConfig
        from joplin_mcp.client import JoplinMCPClient
        
        config = JoplinMCPConfig(
            host=host,
            port=port,
            token=token,
            timeout=30,
            verify_ssl=False
        )
        
        mcp_client = JoplinMCPClient(config=config)
        print("✅ MCP client created")
        
        # Test ping
        if mcp_client.ping():
            print("✅ MCP client ping successful")
        else:
            print("❌ MCP client ping failed")
            
        # Test get_all_notebooks
        try:
            notebooks = mcp_client.get_all_notebooks()
            print(f"✅ MCP client found {len(notebooks)} notebooks")
        except Exception as e:
            print(f"❌ MCP get_all_notebooks failed: {e}")
            
    except Exception as e:
        print(f"❌ MCP client test failed: {e}")

if __name__ == "__main__":
    test_joplin_connection() 