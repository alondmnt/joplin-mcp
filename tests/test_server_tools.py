"""Tests for Joplin MCP server tool handlers."""

import pytest
from unittest.mock import Mock
import asyncio

from joplin_mcp.server import JoplinMCPServer
from joplin_mcp.config import JoplinMCPConfig
from joplin_mcp.models import MCPNote, MCPNotebook, MCPTag, MCPSearchResult


class TestServerToolHandlers:
    """Test server tool handlers."""

    @pytest.fixture
    def server(self):
        """Create server with mocked client."""
        config = JoplinMCPConfig(token="test-token")
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.is_connected = True
        
        server = JoplinMCPServer(config=config, client=mock_client, skip_ping=True)
        return server

    @pytest.mark.asyncio
    async def test_handle_search_notes_basic(self, server):
        """Test basic search_notes functionality."""
        # Use plain dictionaries as server expects from client
        mock_results = [{
            "id": "a" * 32,
            "title": "Test Note",
            "body": "Test content",
            "created_time": 1234567890,
            "updated_time": 1234567891,
            "parent_id": "b" * 32,
            "is_todo": False,
            "todo_completed": False,
            "is_conflict": False
        }]
        
        server.client.search_notes.return_value = mock_results
        
        params = {"query": "test"}
        result = await server.handle_search_notes(params)
        
        assert result["content"][0]["type"] == "text"
        assert "Test Note" in result["content"][0]["text"]
        server.client.search_notes.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_search_notes_empty_query(self, server):
        """Test search_notes with empty query returns no results."""
        # Set up mock to return empty results for empty query
        server.client.search_notes.return_value = []
        
        params = {"query": ""}
        result = await server.handle_search_notes(params)
        
        assert result["content"][0]["type"] == "text"
        assert "No notes found for query" in result["content"][0]["text"]
        server.client.search_notes.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_get_note_success(self, server):
        """Test successful get_note operation."""
        mock_note_data = {
            "id": "a" * 32,
            "title": "Test Note",
            "body": "Test content",
            "created_time": 1234567890,
            "updated_time": 1234567891,
            "parent_id": "b" * 32,
            "is_todo": False,
            "todo_completed": False,
            "is_conflict": False
        }
        
        server.client.get_note.return_value = mock_note_data
        
        params = {"note_id": "a" * 32}
        result = await server.handle_get_note(params)
        
        assert result["content"][0]["type"] == "text"
        assert "Test Note" in result["content"][0]["text"]
        server.client.get_note.assert_called_once_with("a" * 32)

    @pytest.mark.asyncio
    async def test_handle_get_note_empty_id(self, server):
        """Test get_note with empty note_id raises ValueError."""
        params = {"note_id": ""}
        
        with pytest.raises(ValueError, match="note_id parameter is required"):
            await server.handle_get_note(params)

    @pytest.mark.asyncio
    async def test_handle_create_note_success(self, server):
        """Test successful create_note operation."""
        server.client.create_note.return_value = "new_note_id"
        
        params = {
            "title": "New Note",
            "body": "New content",
            "notebook_id": "notebook123"
        }
        
        result = await server.handle_create_note(params)
        
        assert result["content"][0]["type"] == "text"
        assert "Successfully created" in result["content"][0]["text"]
        server.client.create_note.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_create_note_empty_title(self, server):
        """Test create_note with empty title raises ValueError."""
        params = {"title": "", "body": "Content"}
        
        with pytest.raises(ValueError, match="title parameter is required"):
            await server.handle_create_note(params)

    @pytest.mark.asyncio
    async def test_handle_ping_joplin_success(self, server):
        """Test successful ping_joplin operation."""
        server.client.ping.return_value = True
        
        params = {}
        result = await server.handle_ping_joplin(params)
        
        assert result["content"][0]["type"] == "text"
        assert "connection successful" in result["content"][0]["text"]
        server.client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_ping_joplin_failure(self, server):
        """Test ping_joplin when connection fails."""
        server.client.ping.return_value = False
        
        params = {}
        result = await server.handle_ping_joplin(params)
        
        assert result["content"][0]["type"] == "text"
        assert "connection failed" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_handle_list_notebooks_success(self, server):
        """Test successful list_notebooks operation."""
        mock_notebooks = [
            MCPNotebook(
                id="c" * 32,
                title="Test Notebook",
                created_time=1234567890,
                updated_time=1234567891,
                parent_id=""
            )
        ]
        server.client.get_all_notebooks.return_value = mock_notebooks
        
        params = {}
        result = await server.handle_list_notebooks(params)
        
        assert result["content"][0]["type"] == "text"
        assert "Test Notebook" in result["content"][0]["text"]
        server.client.get_all_notebooks.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_create_notebook_success(self, server):
        """Test successful create_notebook operation."""
        server.client.create_notebook.return_value = "new_notebook_id"
        
        params = {"title": "New Notebook"}
        result = await server.handle_create_notebook(params)
        
        assert result["content"][0]["type"] == "text"
        assert "Successfully created" in result["content"][0]["text"]
        server.client.create_notebook.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_create_tag_success(self, server):
        """Test successful create_tag operation."""
        server.client.create_tag.return_value = "new_tag_id"
        
        params = {"title": "New Tag"}
        result = await server.handle_create_tag(params)
        
        assert result["content"][0]["type"] == "text"
        assert "Successfully created" in result["content"][0]["text"]
        server.client.create_tag.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_delete_note_success(self, server):
        """Test successful delete_note operation."""
        server.client.delete_note.return_value = True
        
        params = {"note_id": "a" * 32}
        result = await server.handle_delete_note(params)
        
        assert result["content"][0]["type"] == "text"
        assert "Successfully deleted" in result["content"][0]["text"]
        server.client.delete_note.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_update_note_success(self, server):
        """Test successful update_note operation."""
        server.client.update_note.return_value = True
        
        params = {
            "note_id": "a" * 32,
            "title": "Updated Note"
        }
        
        result = await server.handle_update_note(params)
        
        assert result["content"][0]["type"] == "text"
        assert "Successfully updated" in result["content"][0]["text"]
        server.client.update_note.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_get_note_invalid_data(self, server):
        """Test get_note when client returns invalid data."""
        server.client.get_note.return_value = None
        
        params = {"note_id": "a" * 32}
        
        with pytest.raises(ValueError, match="Invalid note data"):
            await server.handle_get_note(params)

    @pytest.mark.asyncio
    async def test_handle_search_notes_client_error(self, server):
        """Test search_notes when client raises exception."""
        server.client.search_notes.side_effect = Exception("Client error")
        
        params = {"query": "test"}
        
        with pytest.raises(Exception, match="Client error"):
            await server.handle_search_notes(params) 