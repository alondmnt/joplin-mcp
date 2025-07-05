#!/usr/bin/env python3
"""
Test Joplin MCP Server with MCP Inspector
Simple testing without complex Ollama bridge
"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_joplin_mcp():
    """Test the Joplin MCP server directly."""
    print("🔬 Testing Joplin MCP Server with MCP Inspector")
    print("=" * 50)
    
    # Connect to server
    server_params = StdioServerParameters(
        command="python",
        args=["/Users/alondmnt/projects/joplin/mcp/run_mcp_server.py"],
        env={"PYTHONPATH": "/Users/alondmnt/projects/joplin/mcp"}
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()
            print("✅ Connected to MCP server")
            
            # List available tools
            tools_response = await session.list_tools()
            print(f"\n📋 Available tools ({len(tools_response.tools)}):")
            for tool in tools_response.tools:
                print(f"  • {tool.name}: {tool.description}")
            
            # Test basic operations
            print("\n🧪 Testing basic operations...")
            
            # Test 1: Create a notebook
            print("\n1️⃣ Creating test notebook...")
            try:
                result = await session.call_tool("create_notebook", {
                    "title": "MCP Test Notebook"
                })
                print(f"✅ Notebook created: {result}")
                
                # Extract notebook ID from response
                notebook_id = None
                if hasattr(result, 'content') and result.content:
                    for content in result.content:
                        if hasattr(content, 'text'):
                            text = content.text
                            # Look for notebook ID in response
                            if 'created_notebook_id' in text:
                                import re
                                match = re.search(r'"created_notebook_id":\s*"([^"]+)"', text)
                                if match:
                                    notebook_id = match.group(1)
                                    print(f"📝 Extracted notebook ID: {notebook_id}")
                            
            except Exception as e:
                print(f"❌ Error creating notebook: {e}")
                return
            
            # Test 2: Create a note
            if notebook_id:
                print("\n2️⃣ Creating test note...")
                try:
                    result = await session.call_tool("create_note", {
                        "title": "MCP Test Note",
                        "body": "This is a test note created via MCP",
                        "parent_id": notebook_id
                    })
                    print(f"✅ Note created: {result}")
                    
                    # Extract note ID
                    note_id = None
                    if hasattr(result, 'content') and result.content:
                        for content in result.content:
                            if hasattr(content, 'text'):
                                text = content.text
                                if 'created_note_id' in text:
                                    import re
                                    match = re.search(r'"created_note_id":\s*"([^"]+)"', text)
                                    if match:
                                        note_id = match.group(1)
                                        print(f"📝 Extracted note ID: {note_id}")
                    
                except Exception as e:
                    print(f"❌ Error creating note: {e}")
            
            # Test 3: Search notes
            print("\n3️⃣ Searching for notes...")
            try:
                result = await session.call_tool("search_notes", {
                    "query": "MCP",
                    "limit": 5
                })
                print(f"✅ Search completed: {result}")
                
            except Exception as e:
                print(f"❌ Error searching notes: {e}")
            
            # Test 4: Create and assign tag
            if note_id:
                print("\n4️⃣ Creating and assigning tag...")
                try:
                    # Create tag
                    tag_result = await session.call_tool("create_tag", {
                        "title": "mcp-test"
                    })
                    print(f"✅ Tag created: {tag_result}")
                    
                    # Extract tag ID
                    tag_id = None
                    if hasattr(tag_result, 'content') and tag_result.content:
                        for content in tag_result.content:
                            if hasattr(content, 'text'):
                                text = content.text
                                if 'created_tag_id' in text:
                                    import re
                                    match = re.search(r'"created_tag_id":\s*"([^"]+)"', text)
                                    if match:
                                        tag_id = match.group(1)
                                        print(f"🏷️ Extracted tag ID: {tag_id}")
                    
                    # Assign tag to note
                    if tag_id:
                        assign_result = await session.call_tool("add_tag_to_note", {
                            "note_id": note_id,
                            "tag_id": tag_id
                        })
                        print(f"✅ Tag assigned: {assign_result}")
                    
                except Exception as e:
                    print(f"❌ Error with tagging: {e}")
            
            print("\n🎉 MCP testing completed!")


if __name__ == "__main__":
    asyncio.run(test_joplin_mcp()) 