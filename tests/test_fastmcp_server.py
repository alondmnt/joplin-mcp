#!/usr/bin/env python3
"""
Simple test script for the new FastMCP-based Joplin server.
This script tests the basic functionality without requiring a full test suite.
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest

# Add src directory to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from fastmcp import Client

from joplin_mcp.fastmcp_server import mcp


@pytest.mark.asyncio
async def test_basic_functionality():
    """Test basic FastMCP server functionality."""
    print("🧪 Testing FastMCP Joplin Server...")

    # Check if we have the required environment variables
    if not os.getenv("JOPLIN_TOKEN"):
        print("⚠️  JOPLIN_TOKEN not set. Setting a dummy token for testing...")
        os.environ["JOPLIN_TOKEN"] = "dummy_token_for_testing"

    try:
        # Test server initialization
        print("1. Testing server initialization...")
        async with Client(mcp) as client:
            print("   ✅ FastMCP server initialized successfully")

            # Test listing tools
            print("2. Testing tool listing...")
            tools = await client.list_tools()
            print(f"   ✅ Found {len(tools)} tools:")
            for tool in tools:
                print(f"      - {tool.name}: {tool.description}")

            # Test ping (this might fail if Joplin isn't running, but that's okay)
            print("3. Testing ping tool...")
            try:
                result = await client.call_tool("ping_joplin")
                print(f"   ✅ Ping successful: {str(result)[:100]}...")
            except Exception as e:
                print(
                    f"   ⚠️  Ping failed (expected if Joplin not running): {str(e)[:100]}..."
                )

            # Test resources
            print("4. Testing resources...")
            resources = await client.list_resources()
            print(f"   ✅ Found {len(resources)} resources:")
            for resource in resources:
                print(f"      - {resource.uri}: {resource.name}")

            print("\n🎉 All basic tests passed! FastMCP server is working correctly.")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise


@pytest.mark.asyncio
async def test_tool_schemas():
    """Test that tool schemas are generated correctly."""
    print("\n🔍 Testing tool schemas...")

    async with Client(mcp) as client:
        tools = await client.list_tools()

        # Test a few key tools have proper schemas
        tool_names = {tool.name for tool in tools}

        expected_tools = {
            "ping_joplin",
            "get_note",
            "create_note",
            "find_notes",
            "list_notebooks",
            "create_notebook",
            "list_tags",
            "create_tag",
            "tag_note",
        }

        missing_tools = expected_tools - tool_names
        if missing_tools:
            print(f"❌ Missing expected tools: {missing_tools}")
        else:
            print("✅ All expected tools found")

        # Check that create_note has the expected parameters
        for tool in tools:
            if tool.name == "create_note":
                schema = tool.inputSchema
                if schema and "properties" in schema:
                    properties = schema["properties"]
                    required = schema.get("required", [])

                    print(f"   create_note required params: {required}")
                    print(f"   create_note optional params: {list(properties.keys())}")

                    if "title" in required and "parent_id" in required:
                        print("   ✅ create_note schema looks correct")
                    else:
                        print(
                            "   ⚠️  create_note schema might be missing required params"
                        )
                break


# === Tests for timestamp_converter ===


def test_timestamp_converter_with_none():
    """Test timestamp_converter returns None for None input."""
    from joplin_mcp.fastmcp_server import timestamp_converter

    result = timestamp_converter(None, "todo_due")
    assert result is None


def test_timestamp_converter_with_int():
    """Test timestamp_converter returns int unchanged."""
    from joplin_mcp.fastmcp_server import timestamp_converter

    result = timestamp_converter(1735660800000, "todo_due")
    assert result == 1735660800000


def test_timestamp_converter_with_zero():
    """Test timestamp_converter handles zero (used to clear due date)."""
    from joplin_mcp.fastmcp_server import timestamp_converter

    result = timestamp_converter(0, "todo_due")
    assert result == 0


def test_timestamp_converter_with_iso_string():
    """Test timestamp_converter parses ISO 8601 string."""
    from joplin_mcp.fastmcp_server import timestamp_converter

    # Test with timezone-naive string
    result = timestamp_converter("2024-12-31T17:00:00", "todo_due")
    assert isinstance(result, int)
    assert result > 0


def test_timestamp_converter_with_iso_string_utc():
    """Test timestamp_converter parses ISO 8601 string with Z suffix."""
    from joplin_mcp.fastmcp_server import timestamp_converter

    result = timestamp_converter("2024-12-31T17:00:00Z", "todo_due")
    assert isinstance(result, int)
    assert result > 0


def test_timestamp_converter_with_empty_string():
    """Test timestamp_converter returns None for empty string."""
    from joplin_mcp.fastmcp_server import timestamp_converter

    result = timestamp_converter("", "todo_due")
    assert result is None
    result = timestamp_converter("   ", "todo_due")
    assert result is None


def test_timestamp_converter_with_invalid_string():
    """Test timestamp_converter raises ValueError for invalid string."""
    from joplin_mcp.fastmcp_server import timestamp_converter

    with pytest.raises(ValueError) as exc_info:
        timestamp_converter("not-a-date", "todo_due")
    assert "todo_due" in str(exc_info.value)
    assert "ISO 8601" in str(exc_info.value)


def test_timestamp_converter_with_invalid_type():
    """Test timestamp_converter raises ValueError for invalid type."""
    from joplin_mcp.fastmcp_server import timestamp_converter

    with pytest.raises(ValueError) as exc_info:
        timestamp_converter(3.14, "todo_due")  # type: ignore
    assert "todo_due" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_note_has_todo_due_param():
    """Test that create_note tool schema includes todo_due parameter."""
    async with Client(mcp) as client:
        tools = await client.list_tools()
        for tool in tools:
            if tool.name == "create_note":
                schema = tool.inputSchema
                assert schema and "properties" in schema
                properties = schema["properties"]
                assert "todo_due" in properties, "create_note should have todo_due parameter"
                assert "description" in properties["todo_due"]
                break
        else:
            pytest.fail("create_note tool not found")


@pytest.mark.asyncio
async def test_update_note_has_todo_due_param():
    """Test that update_note tool schema includes todo_due parameter."""
    async with Client(mcp) as client:
        tools = await client.list_tools()
        for tool in tools:
            if tool.name == "update_note":
                schema = tool.inputSchema
                assert schema and "properties" in schema
                properties = schema["properties"]
                assert "todo_due" in properties, "update_note should have todo_due parameter"
                assert "description" in properties["todo_due"]
                break
        else:
            pytest.fail("update_note tool not found")


def main():
    """Main test runner."""
    print("FastMCP Joplin Server Test Suite")
    print("=" * 40)

    try:
        # Run async tests
        asyncio.run(test_basic_functionality())
        asyncio.run(test_tool_schemas())

        print("\n🎉 All tests completed successfully!")
        print("\nTo test with a real Joplin instance:")
        print("1. Make sure Joplin is running with Web Clipper enabled")
        print("2. Set JOPLIN_TOKEN environment variable")
        print("3. Run: python -m joplin_mcp.fastmcp_server")

    except Exception as e:
        print(f"\n❌ Tests failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
