"""Extended tests for Joplin MCP server to achieve high coverage."""

import pytest
from unittest.mock import Mock
import asyncio

from joplin_mcp.server import JoplinMCPServer
from joplin_mcp.config import JoplinMCPConfig
from joplin_mcp.models import MCPTag, MCPNotebook


class TestServerExtended:
    """Extended server tests for maximum coverage."""

    @pytest.fixture
    def server(self):
        """Create server with mocked client."""
        config = JoplinMCPConfig(token="test-token")
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.is_connected = True
        
        server = JoplinMCPServer(config=config, client=mock_client, skip_ping=True)
        return server

    # Notebook Handler Tests
    @pytest.mark.asyncio
    async def test_handle_get_notebook_success(self, server):
        """Test successful get_notebook operation."""
        mock_notebook = {
            "id": "c" * 32,
            "title": "Test Notebook",
            "created_time": 1234567890,
            "updated_time": 1234567891,
            "parent_id": ""
        }
        
        server.client.get_notebook.return_value = mock_notebook
        
        params = {"notebook_id": "c" * 32}
        result = await server.handle_get_notebook(params)
        
        assert result["content"][0]["type"] == "text"
        assert "Test Notebook" in result["content"][0]["text"]
        server.client.get_notebook.assert_called_once_with(notebook_id="c" * 32)

    @pytest.mark.asyncio
    async def test_handle_update_notebook_success(self, server):
        """Test successful update_notebook operation."""
        server.client.update_notebook.return_value = True
        
        params = {
            "notebook_id": "c" * 32,
            "title": "Updated Notebook"
        }
        
        result = await server.handle_update_notebook(params)
        
        assert result["content"][0]["type"] == "text"
        assert "Successfully updated" in result["content"][0]["text"]
        server.client.update_notebook.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_delete_notebook_success(self, server):
        """Test successful delete_notebook operation."""
        server.client.delete_notebook.return_value = True
        
        params = {"notebook_id": "c" * 32}
        result = await server.handle_delete_notebook(params)
        
        assert result["content"][0]["type"] == "text"
        assert "Successfully deleted" in result["content"][0]["text"]
        server.client.delete_notebook.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_search_notebooks_success(self, server):
        """Test successful search_notebooks operation."""
        mock_notebooks = [Mock()]
        mock_notebooks[0].id = "c" * 32
        mock_notebooks[0].title = "Found Notebook"
        mock_notebooks[0].created_time = 1234567890
        mock_notebooks[0].updated_time = 1234567891
        mock_notebooks[0].parent_id = ""
        
        server.client.get_all_notebooks.return_value = mock_notebooks
        
        params = {"query": "Found"}
        result = await server.handle_search_notebooks(params)
        
        assert result["content"][0]["type"] == "text"
        assert "Found Notebook" in result["content"][0]["text"]
        server.client.get_all_notebooks.assert_called_once()

    # Tag Handler Tests
    @pytest.mark.asyncio
    async def test_handle_list_tags_success(self, server):
        """Test successful list_tags operation."""
        mock_tags = [
            MCPTag(
                id="d" * 32,
                title="Test Tag",
                created_time=1234567890,
                updated_time=1234567891
            )
        ]
        server.client.get_all_tags.return_value = mock_tags
        
        params = {}
        result = await server.handle_list_tags(params)
        
        assert result["content"][0]["type"] == "text"
        assert "test tag" in result["content"][0]["text"]  # Server formats tags as lowercase
        server.client.get_all_tags.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_get_tag_success(self, server):
        """Test successful get_tag operation."""
        mock_tag = MCPTag(
            id="d" * 32,
            title="Test Tag",
            created_time=1234567890,
            updated_time=1234567891
        )
        
        server.client.get_tag.return_value = mock_tag
        
        params = {"tag_id": "d" * 32}
        result = await server.handle_get_tag(params)
        
        assert result["content"][0]["type"] == "text"
        assert "test tag" in result["content"][0]["text"]  # Server formats tags as lowercase
        server.client.get_tag.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_update_tag_success(self, server):
        """Test successful update_tag operation."""
        server.client.update_tag.return_value = True
        
        params = {
            "tag_id": "d" * 32,
            "title": "Updated Tag"
        }
        
        result = await server.handle_update_tag(params)
        
        assert result["content"][0]["type"] == "text"
        assert "Successfully updated" in result["content"][0]["text"]
        server.client.update_tag.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_delete_tag_success(self, server):
        """Test successful delete_tag operation."""
        server.client.delete_tag.return_value = True
        
        params = {"tag_id": "d" * 32}
        result = await server.handle_delete_tag(params)
        
        assert result["content"][0]["type"] == "text"
        assert "Successfully deleted" in result["content"][0]["text"]
        server.client.delete_tag.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_tag_note_success(self, server):
        """Test successful tag_note operation."""
        server.client.tag_note.return_value = True
        
        params = {
            "note_id": "a" * 32,
            "tag_id": "d" * 32
        }
        
        result = await server.handle_tag_note(params)
        
        assert result["content"][0]["type"] == "text"
        assert "Successfully tagged note" in result["content"][0]["text"]
        server.client.tag_note.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_untag_note_success(self, server):
        """Test successful untag_note operation."""
        server.client.untag_note.return_value = True
        
        params = {
            "note_id": "a" * 32,
            "tag_id": "d" * 32
        }
        
        result = await server.handle_untag_note(params)
        
        assert result["content"][0]["type"] == "text"
        assert "Successfully removed tag" in result["content"][0]["text"]
        server.client.untag_note.assert_called_once()

    # Server Utility Tests
    def test_get_server_info(self, server):
        """Test get_server_info method."""
        info = server.get_server_info()
        
        assert isinstance(info, dict)
        assert info["name"] == "joplin-mcp"
        assert info["version"] == "0.1.0"
        assert "capabilities" in info
        assert "joplin_connection" in info

    def test_get_tool_schema_existing_tool(self, server):
        """Test get_tool_schema for existing tool."""
        schema = server.get_tool_schema("search_notes")
        
        assert schema is not None
        assert schema["name"] == "search_notes"
        assert "description" in schema
        assert "inputSchema" in schema

    def test_get_tool_schema_nonexistent_tool(self, server):
        """Test get_tool_schema for non-existent tool."""
        schema = server.get_tool_schema("nonexistent_tool")
        
        assert schema is None

    def test_get_available_prompts(self, server):
        """Test get_available_prompts method."""
        prompts = server.get_available_prompts()
        
        assert isinstance(prompts, list)
        assert len(prompts) > 0
        
        # Check first prompt has required attributes
        prompt = prompts[0]
        assert hasattr(prompt, 'name')
        assert hasattr(prompt, 'description')

    def test_get_available_resources(self, server):
        """Test get_available_resources method."""
        resources = server.get_available_resources()
        
        assert isinstance(resources, list)
        assert len(resources) > 0
        
        # Check first resource has required attributes
        resource = resources[0]
        assert hasattr(resource, 'uri')
        assert hasattr(resource, 'name')

    def test_validate_string_input_valid(self, server):
        """Test _validate_string_input with valid input."""
        result = server._validate_string_input("test string", max_length=100)
        assert result == "test string"

    def test_validate_string_input_too_long(self, server):
        """Test _validate_string_input with too long input."""
        long_string = "a" * 200
        result = server._validate_string_input(long_string, max_length=100)
        assert len(result) <= 100

    def test_validate_string_input_non_string(self, server):
        """Test _validate_string_input with non-string input."""
        with pytest.raises(ValueError, match="Input must be a string"):
            server._validate_string_input(123, max_length=100)

    # Context Manager Tests
    def test_context_manager_sync(self, server):
        """Test synchronous context manager."""
        with server as ctx_server:
            assert ctx_server is server

    @pytest.mark.asyncio
    async def test_context_manager_async(self, server):
        """Test asynchronous context manager."""
        async with server as ctx_server:
            assert ctx_server is server 