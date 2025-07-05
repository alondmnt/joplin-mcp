"""
Tests for FastMCP-based Joplin MCP Server.

This module tests the FastMCP implementation of the Joplin MCP server,
focusing on tool registration, filtering, and configuration management.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock

import pytest

from joplin_mcp.config import JoplinMCPConfig


# Shared fixtures for all test classes
@pytest.fixture
def test_config_with_disabled_tools(tmp_path):
    """Create a test config with some tools disabled."""
    config_data = {
        "host": "localhost",
        "port": 41184,
        "token": "test_token_123456789",
        "timeout": 30,
        "verify_ssl": False,
        "tools": {
            "search_notes": True,
            "get_note": True,
            "create_note": True,
            "update_note": True,
            "delete_note": False,  # Disabled
            "list_notebooks": True,
            "get_notebook": True,
            "create_notebook": True,
            "update_notebook": True,
            "delete_notebook": False,  # Disabled
            "search_notebooks": True,
            "get_notes_by_notebook": True,
            "list_tags": True,
            "get_tag": True,
            "create_tag": True,
            "update_tag": True,
            "delete_tag": False,  # Disabled
            "search_tags": True,
            "get_tags_by_note": True,
            "get_notes_by_tag": True,
            "tag_note": True,
            "untag_note": True,
            "ping_joplin": True,
            "add_tag_to_note": True,
            "remove_tag_from_note": True
        }
    }
    
    config_file = tmp_path / "test_config.json"
    with open(config_file, "w") as f:
        json.dump(config_data, f)
    
    return config_file

@pytest.fixture
def test_config_all_enabled(tmp_path):
    """Create a test config with all tools enabled."""
    config_data = {
        "host": "localhost",
        "port": 41184,
        "token": "test_token_123456789",
        "timeout": 30,
        "verify_ssl": False,
        "tools": {
            "search_notes": True,
            "get_note": True,
            "create_note": True,
            "update_note": True,
            "delete_note": True,
            "list_notebooks": True,
            "get_notebook": True,
            "create_notebook": True,
            "update_notebook": True,
            "delete_notebook": True,
            "search_notebooks": True,
            "get_notes_by_notebook": True,
            "list_tags": True,
            "get_tag": True,
            "create_tag": True,
            "update_tag": True,
            "delete_tag": True,
            "search_tags": True,
            "get_tags_by_note": True,
            "get_notes_by_tag": True,
            "tag_note": True,
            "untag_note": True,
            "ping_joplin": True,
            "add_tag_to_note": True,
            "remove_tag_from_note": True
        }
    }
    
    config_file = tmp_path / "test_config_all.json"
    with open(config_file, "w") as f:
        json.dump(config_data, f)
    
    return config_file


class TestFastMCPToolFiltering:
    """Test suite for FastMCP server tool filtering functionality."""

    def test_config_loads_correctly(self, test_config_with_disabled_tools):
        """Test that configuration loads correctly with disabled tools."""
        config = JoplinMCPConfig.from_file(test_config_with_disabled_tools)
        
        assert config.host == "localhost"
        assert config.port == 41184
        assert config.token == "test_token_123456789"
        assert config.verify_ssl is False
        
        # Check tool counts
        assert len(config.tools) == 25  # Total tools
        assert len(config.get_enabled_tools()) == 22  # Enabled tools
        assert len(config.get_disabled_tools()) == 3  # Disabled tools
        
        # Check specific disabled tools
        disabled_tools = config.get_disabled_tools()
        assert "delete_note" in disabled_tools
        assert "delete_notebook" in disabled_tools
        assert "delete_tag" in disabled_tools
        
        # Check specific enabled tools
        enabled_tools = config.get_enabled_tools()
        assert "search_notes" in enabled_tools
        assert "create_note" in enabled_tools
        assert "ping_joplin" in enabled_tools

    def test_individual_tool_checks(self, test_config_with_disabled_tools):
        """Test individual tool enable/disable checks."""
        config = JoplinMCPConfig.from_file(test_config_with_disabled_tools)
        
        # Test disabled tools
        assert config.is_tool_enabled("delete_note") is False
        assert config.is_tool_enabled("delete_notebook") is False
        assert config.is_tool_enabled("delete_tag") is False
        
        # Test enabled tools
        assert config.is_tool_enabled("search_notes") is True
        assert config.is_tool_enabled("create_note") is True
        assert config.is_tool_enabled("ping_joplin") is True
        assert config.is_tool_enabled("get_note") is True
        assert config.is_tool_enabled("list_notebooks") is True

    @pytest.mark.asyncio
    async def test_fastmcp_tool_filtering(self, test_config_with_disabled_tools):
        """Test that FastMCP server correctly filters tools based on configuration."""
        # Import here to avoid circular imports
        from joplin_mcp import fastmcp_server
        
        # Load configuration
        config = JoplinMCPConfig.from_file(test_config_with_disabled_tools)
        
        # Set the global config (simulating what main() does)
        fastmcp_server._config = config
        
        # Get the FastMCP instance
        mcp = fastmcp_server.mcp
        
        # Store original tools for cleanup
        original_tools = mcp._tool_manager._tools.copy()
        
        try:
            # Apply tool filtering (simulating what main() does)
            disabled_tools = config.get_disabled_tools()
            for tool_name in disabled_tools:
                if tool_name in mcp._tool_manager._tools:
                    del mcp._tool_manager._tools[tool_name]
            
            # Get registered tools
            tools = await mcp.get_tools()
            registered_tool_names = list(tools.keys())
            
            # Verify correct number of tools
            assert len(registered_tool_names) == 22  # 25 - 3 disabled
            
            # Verify disabled tools are not registered
            for tool_name in disabled_tools:
                assert tool_name not in registered_tool_names, f"Disabled tool {tool_name} should not be registered"
            
            # Verify enabled tools are registered
            enabled_tools = config.get_enabled_tools()
            for tool_name in enabled_tools:
                assert tool_name in registered_tool_names, f"Enabled tool {tool_name} should be registered"
            
            # Verify specific tools
            assert "delete_note" not in registered_tool_names
            assert "delete_notebook" not in registered_tool_names
            assert "delete_tag" not in registered_tool_names
            assert "search_notes" in registered_tool_names
            assert "create_note" in registered_tool_names
            assert "ping_joplin" in registered_tool_names
            
        finally:
            # Restore original tools for other tests
            mcp._tool_manager._tools = original_tools

    @pytest.mark.asyncio
    async def test_fastmcp_all_tools_enabled(self, test_config_all_enabled):
        """Test that all tools are registered when all are enabled."""
        # Import here to avoid circular imports
        from joplin_mcp import fastmcp_server
        
        # Load configuration
        config = JoplinMCPConfig.from_file(test_config_all_enabled)
        
        # Set the global config
        fastmcp_server._config = config
        
        # Get the FastMCP instance
        mcp = fastmcp_server.mcp
        
        # Store original tools for cleanup
        original_tools = mcp._tool_manager._tools.copy()
        
        try:
            # Apply tool filtering (no tools should be removed)
            disabled_tools = config.get_disabled_tools()
            for tool_name in disabled_tools:
                if tool_name in mcp._tool_manager._tools:
                    del mcp._tool_manager._tools[tool_name]
            
            # Get registered tools
            tools = await mcp.get_tools()
            registered_tool_names = list(tools.keys())
            
            # Verify all tools are registered
            assert len(registered_tool_names) == 25  # All tools enabled
            assert len(config.get_disabled_tools()) == 0  # No disabled tools
            
            # Verify all expected tools are present
            expected_tools = [
                "search_notes", "get_note", "create_note", "update_note", "delete_note",
                "list_notebooks", "get_notebook", "create_notebook", "update_notebook", 
                "delete_notebook", "search_notebooks", "get_notes_by_notebook",
                "list_tags", "get_tag", "create_tag", "update_tag", "delete_tag",
                "search_tags", "get_tags_by_note", "get_notes_by_tag", "tag_note", 
                "untag_note", "ping_joplin", "add_tag_to_note", "remove_tag_from_note"
            ]
            
            for tool_name in expected_tools:
                assert tool_name in registered_tool_names, f"Tool {tool_name} should be registered"
            
        finally:
            # Restore original tools for other tests
            mcp._tool_manager._tools = original_tools

    def test_config_tool_categories(self, test_config_with_disabled_tools):
        """Test that tool categories work correctly."""
        config = JoplinMCPConfig.from_file(test_config_with_disabled_tools)
        
        # Get tool categories
        categories = config.get_tool_categories()
        
        # Verify categories exist
        assert "notes" in categories
        assert "notebooks" in categories
        assert "tags" in categories
        assert "aliases" in categories
        assert "utilities" in categories
        
        # Verify category contents
        assert "search_notes" in categories["notes"]
        assert "delete_note" in categories["notes"]
        assert "list_notebooks" in categories["notebooks"]
        assert "delete_notebook" in categories["notebooks"]
        assert "create_tag" in categories["tags"]
        assert "delete_tag" in categories["tags"]
        assert "ping_joplin" in categories["utilities"]
        assert "add_tag_to_note" in categories["aliases"]

    @pytest.mark.asyncio
    async def test_fastmcp_tool_registration_completeness(self):
        """Test that all expected tools are defined in the FastMCP server."""
        # Import here to avoid circular imports
        from joplin_mcp import fastmcp_server
        
        # Get the FastMCP instance
        mcp = fastmcp_server.mcp
        
        # Get all registered tools before any filtering
        tools = await mcp.get_tools()
        registered_tool_names = list(tools.keys())
        
        # Verify we have all 25 expected tools
        expected_tools = [
            "search_notes", "get_note", "create_note", "update_note", "delete_note",
            "list_notebooks", "get_notebook", "create_notebook", "update_notebook", 
            "delete_notebook", "search_notebooks", "get_notes_by_notebook",
            "list_tags", "get_tag", "create_tag", "update_tag", "delete_tag",
            "search_tags", "get_tags_by_note", "get_notes_by_tag", "tag_note", 
            "untag_note", "ping_joplin", "add_tag_to_note", "remove_tag_from_note"
        ]
        
        assert len(registered_tool_names) == 25, f"Expected 25 tools, got {len(registered_tool_names)}"
        
        for tool_name in expected_tools:
            assert tool_name in registered_tool_names, f"Tool {tool_name} is missing from FastMCP server"

    def test_environment_variable_tool_config(self, monkeypatch):
        """Test that tools can be configured via environment variables."""
        # Set environment variables for some tools
        monkeypatch.setenv("JOPLIN_TOOL_DELETE_NOTE", "false")
        monkeypatch.setenv("JOPLIN_TOOL_DELETE_NOTEBOOK", "false")
        monkeypatch.setenv("JOPLIN_TOOL_CREATE_NOTE", "true")
        monkeypatch.setenv("JOPLIN_TOKEN", "test_token")
        
        # Load config from environment
        config = JoplinMCPConfig.from_environment()
        
        # Verify tool configuration
        assert config.is_tool_enabled("delete_note") is False
        assert config.is_tool_enabled("delete_notebook") is False
        assert config.is_tool_enabled("create_note") is True
        
        # Verify other tools use defaults
        assert config.is_tool_enabled("search_notes") is True  # Default True
        assert config.is_tool_enabled("ping_joplin") is True  # Default True


class TestFastMCPServerIntegration:
    """Integration tests for the FastMCP server."""

    @pytest.mark.asyncio
    async def test_server_startup_with_tool_filtering(self, test_config_with_disabled_tools):
        """Test that the server starts correctly with tool filtering applied."""
        # Import here to avoid circular imports
        from joplin_mcp import fastmcp_server
        
        # Mock the get_joplin_client to avoid actual connection
        with patch('joplin_mcp.fastmcp_server.get_joplin_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.ping.return_value = "JoplinClipperServer"
            mock_get_client.return_value = mock_client
            
            # Load configuration
            config = JoplinMCPConfig.from_file(test_config_with_disabled_tools)
            
            # Store original config
            original_config = fastmcp_server._config
            
            try:
                # Set the global config
                fastmcp_server._config = config
                
                # Get the FastMCP instance
                mcp = fastmcp_server.mcp
                
                # Store original tools for cleanup
                original_tools = mcp._tool_manager._tools.copy()
                
                # Apply tool filtering (simulating what main() does)
                disabled_tools = config.get_disabled_tools()
                for tool_name in disabled_tools:
                    if tool_name in mcp._tool_manager._tools:
                        del mcp._tool_manager._tools[tool_name]
                
                # Verify the filtering worked
                tools = await mcp.get_tools()
                registered_tool_names = list(tools.keys())
                
                assert len(registered_tool_names) == 22
                assert "delete_note" not in registered_tool_names
                assert "delete_notebook" not in registered_tool_names
                assert "delete_tag" not in registered_tool_names
                assert "search_notes" in registered_tool_names
                assert "create_note" in registered_tool_names
                
                # Restore original tools
                mcp._tool_manager._tools = original_tools
                
            finally:
                # Restore original config
                fastmcp_server._config = original_config

    def test_config_validation_with_invalid_tools(self, tmp_path):
        """Test that configuration validation catches invalid tool names."""
        config_data = {
            "host": "localhost",
            "port": 41184,
            "token": "test_token_123456789",
            "tools": {
                "search_notes": True,
                "invalid_tool_name": True,  # Invalid tool
                "another_invalid_tool": False  # Another invalid tool
            }
        }
        
        config_file = tmp_path / "invalid_config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        # Should raise ConfigError due to invalid tool names
        with pytest.raises(Exception):  # ConfigError
            config = JoplinMCPConfig.from_file(config_file)
            config.validate() 