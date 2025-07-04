"""Additional server tests to increase coverage."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from joplin_mcp.server import JoplinMCPServer
from joplin_mcp.config import JoplinMCPConfig


class TestServerAdditional:
    """Additional server tests for maximum coverage."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = JoplinMCPConfig(token="test-token")
        config.is_tool_enabled = Mock(return_value=True)
        return config

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        client = Mock()
        client.ping.return_value = True
        client.is_connected = True
        client.search_notes.return_value = []
        client.get_note.return_value = None
        client.create_note.return_value = {"id": "a" * 32}
        client.update_note.return_value = True
        client.delete_note.return_value = True
        client.get_all_notebooks.return_value = []
        client.get_notebook.return_value = None
        client.create_notebook.return_value = {"id": "b" * 32}
        client.update_notebook.return_value = True
        client.delete_notebook.return_value = True
        client.get_all_tags.return_value = []
        client.get_tag.return_value = None
        client.create_tag.return_value = {"id": "c" * 32}
        client.update_tag.return_value = True
        client.delete_tag.return_value = True
        client.tag_note.return_value = True
        client.untag_note.return_value = True
        return client

    @pytest.fixture
    def server(self, mock_config, mock_client):
        """Create server with mocked dependencies."""
        return JoplinMCPServer(config=mock_config, client=mock_client, skip_ping=True)

    # Test server initialization edge cases
    def test_server_init_with_mock_client_detection(self):
        """Test server initialization with mock client detection."""
        mock_client = Mock()
        mock_client._mock_name = "MockClient"
        mock_client.ping.return_value = False
        
        # Should not raise exception with mock client
        server = JoplinMCPServer(token="test", client=mock_client)
        assert server.client is mock_client

    def test_server_init_ping_failure_with_real_client(self):
        """Test server initialization with ping failure on real client."""
        with patch('joplin_mcp.server.JoplinMCPClient') as mock_client_class:
            mock_client = Mock()
            mock_client.ping.return_value = False
            mock_client_class.return_value = mock_client
            
            # Should continue anyway even if ping fails
            server = JoplinMCPServer(token="test-token")
            assert server.client is mock_client

    # Test search_notes with various scenarios
    @pytest.mark.asyncio
    async def test_handle_search_notes_with_results(self, server):
        """Test search_notes with actual results."""
        mock_notes = [
            {
                "id": "a" * 32,
                "title": "First Note",
                "body": "First content",
                "created_time": 1234567890,
                "updated_time": 1234567891,
                "parent_id": "b" * 32,
                "tags": ["tag1", "tag2"]
            },
            {
                "id": "b" * 32,
                "title": "Second Note",
                "body": "Second content",
                "created_time": 1234567892,
                "updated_time": 1234567893,
                "parent_id": "c" * 32,
                "tags": []
            }
        ]
        server.client.search_notes.return_value = mock_notes
        
        params = {"query": "test", "limit": 10}
        result = await server.handle_search_notes(params)
        
        assert result["content"][0]["type"] == "text"
        text_content = result["content"][0]["text"]
        assert "First Note" in text_content
        assert "Second Note" in text_content
        assert "Found 2 notes" in text_content

    @pytest.mark.asyncio
    async def test_handle_search_notes_empty_results(self, server):
        """Test search_notes with no results."""
        server.client.search_notes.return_value = []
        
        params = {"query": "nonexistent", "limit": 10}
        result = await server.handle_search_notes(params)
        
        assert result["content"][0]["type"] == "text"
        text_content = result["content"][0]["text"]
        assert "No notes found" in text_content
        assert "nonexistent" in text_content

    # Test get_note scenarios
    @pytest.mark.asyncio
    async def test_handle_get_note_with_body(self, server):
        """Test get_note with body included."""
        mock_note = {
            "id": "a" * 32,
            "title": "Test Note",
            "body": "This is the note body content",
            "created_time": 1234567890,
            "updated_time": 1234567891,
            "parent_id": "b" * 32,
            "tags": ["important", "work"]
        }
        server.client.get_note.return_value = mock_note
        
        params = {"note_id": "a" * 32, "include_body": True}
        result = await server.handle_get_note(params)
        
        text_content = result["content"][0]["text"]
        assert "Test Note" in text_content
        assert "This is the note body content" in text_content
        assert "important" in text_content

    @pytest.mark.asyncio
    async def test_handle_get_note_without_body(self, server):
        """Test get_note without body included."""
        mock_note = {
            "id": "a" * 32,
            "title": "Test Note",
            "body": "This is the note body content",
            "created_time": 1234567890,
            "updated_time": 1234567891,
            "parent_id": "b" * 32,
            "tags": []
        }
        server.client.get_note.return_value = mock_note
        
        params = {"note_id": "a" * 32, "include_body": False}
        result = await server.handle_get_note(params)
        
        text_content = result["content"][0]["text"]
        assert "Test Note" in text_content
        assert "This is the note body content" not in text_content

    # Test create_note scenarios
    @pytest.mark.asyncio
    async def test_handle_create_note_with_todo(self, server):
        """Test create_note with todo functionality."""
        server.client.create_note.return_value = {"id": "a" * 32}
        
        params = {
            "title": "Todo Item",
            "body": "Todo content",
            "is_todo": True,
            "todo_completed": False
        }
        result = await server.handle_create_note(params)
        
        text_content = result["content"][0]["text"]
        assert "Successfully created" in text_content
        assert "todo" in text_content.lower()

    @pytest.mark.asyncio
    async def test_handle_create_note_with_tags(self, server):
        """Test create_note with tags."""
        server.client.create_note.return_value = {"id": "a" * 32}
        
        params = {
            "title": "Tagged Note",
            "body": "Content",
            "tags": ["tag1", "tag2"]
        }
        result = await server.handle_create_note(params)
        
        text_content = result["content"][0]["text"]
        assert "Successfully created" in text_content

    @pytest.mark.asyncio
    async def test_handle_create_note_client_error(self, server):
        """Test create_note with client error."""
        server.client.create_note.side_effect = Exception("Creation failed")
        
        params = {"title": "Test Note", "body": "Content"}
        result = await server.handle_create_note(params)
        
        text_content = result["content"][0]["text"]
        assert "Error creating note" in text_content

    # Test update_note scenarios
    @pytest.mark.asyncio
    async def test_handle_update_note_success(self, server):
        """Test update_note with successful update."""
        server.client.update_note.return_value = True
        
        params = {
            "note_id": "a" * 32,
            "title": "Updated Title",
            "body": "Updated content"
        }
        result = await server.handle_update_note(params)
        
        text_content = result["content"][0]["text"]
        assert "Successfully updated note" in text_content

    @pytest.mark.asyncio
    async def test_handle_update_note_missing_id(self, server):
        """Test update_note with missing note ID."""
        params = {"title": "Updated Title"}
        result = await server.handle_update_note(params)
        
        text_content = result["content"][0]["text"]
        assert "Note ID is required" in text_content

    # Test delete_note scenarios
    @pytest.mark.asyncio
    async def test_handle_delete_note_success(self, server):
        """Test delete_note with successful deletion."""
        server.client.delete_note.return_value = True
        
        params = {"note_id": "a" * 32}
        result = await server.handle_delete_note(params)
        
        text_content = result["content"][0]["text"]
        assert "Successfully deleted note" in text_content

    @pytest.mark.asyncio
    async def test_handle_delete_note_client_error(self, server):
        """Test delete_note with client error."""
        server.client.delete_note.side_effect = Exception("Deletion failed")
        
        params = {"note_id": "a" * 32}
        result = await server.handle_delete_note(params)
        
        text_content = result["content"][0]["text"]
        assert "Error deleting note" in text_content

    # Test notebook operations
    @pytest.mark.asyncio
    async def test_handle_list_notebooks_with_results(self, server):
        """Test list_notebooks with results."""
        mock_notebooks = [
            {"id": "b" * 32, "title": "Work", "created_time": 1234567890},
            {"id": "c" * 32, "title": "Personal", "created_time": 1234567891}
        ]
        server.client.get_all_notebooks.return_value = mock_notebooks
        
        params = {}
        result = await server.handle_list_notebooks(params)
        
        text_content = result["content"][0]["text"]
        assert "Work" in text_content
        assert "Personal" in text_content

    @pytest.mark.asyncio
    async def test_handle_create_notebook_success(self, server):
        """Test create_notebook with successful creation."""
        server.client.create_notebook.return_value = {"id": "b" * 32}
        
        params = {"title": "New Notebook"}
        result = await server.handle_create_notebook(params)
        
        text_content = result["content"][0]["text"]
        assert "Successfully created notebook" in text_content

    @pytest.mark.asyncio
    async def test_handle_create_notebook_empty_title(self, server):
        """Test create_notebook with empty title."""
        params = {"title": ""}
        result = await server.handle_create_notebook(params)
        
        text_content = result["content"][0]["text"]
        assert "Title is required" in text_content

    # Test rate limiting
    def test_rate_limiting_normal_operation(self, server):
        """Test rate limiting under normal conditions."""
        # Simulate normal request rate
        server._request_timestamps = [time.time() - 30] * 30  # 30 requests in last 30 seconds
        
        # Should not raise exception
        server._check_rate_limit()
        
        # Should add new timestamp
        assert len(server._request_timestamps) == 31

    def test_rate_limiting_cleanup_old_timestamps(self, server):
        """Test rate limiting cleans up old timestamps."""
        current_time = time.time()
        old_time = current_time - 120  # 2 minutes ago
        
        with patch('time.time', return_value=current_time):
            server._request_timestamps = [old_time, current_time - 30, current_time - 10]
            server._check_rate_limit()
            
            # Old timestamp should be removed
            assert old_time not in server._request_timestamps
            assert len(server._request_timestamps) == 3  # 2 existing + 1 new

    # Test string validation
    def test_validate_string_input_unicode(self, server):
        """Test string validation with unicode characters."""
        unicode_str = "Test with émojis 🚀 and üñíçøðé"
        result = server._validate_string_input(unicode_str)
        assert "émojis" in result
        assert "🚀" in result
        assert "üñíçøðé" in result

    def test_validate_string_input_very_long(self, server):
        """Test string validation with very long input."""
        long_str = "x" * 2000
        result = server._validate_string_input(long_str, max_length=100)
        assert len(result) <= 103  # 100 + "..."
        assert result.endswith("...")

    # Test error context generation
    def test_get_error_context_with_attributes(self, server):
        """Test error context with exception attributes."""
        error = ValueError("Invalid value")
        error.code = 400
        error.details = "Additional details"
        
        context = server.get_error_context(error, "test_operation")
        
        assert context["error_type"] == "ValueError"
        assert context["error_message"] == "Invalid value"
        assert context["operation"] == "test_operation"

    # Test tool schema and validation
    def test_get_tool_schema_all_tools(self, server):
        """Test getting schemas for all available tools."""
        tools = ["search_notes", "get_note", "create_note", "update_note", "delete_note",
                "list_notebooks", "get_notebook", "create_notebook", "ping_joplin"]
        
        for tool_name in tools:
            schema = server.get_tool_schema(tool_name)
            assert schema is not None
            assert schema["name"] == tool_name
            assert "description" in schema
            assert "inputSchema" in schema

    def test_validate_tool_input_missing_required(self, server):
        """Test tool input validation with missing required parameters."""
        # search_notes requires 'query'
        input_data = {"limit": 10}
        is_valid, errors = server.validate_tool_input("search_notes", input_data)
        
        assert not is_valid
        assert len(errors) > 0
        assert any("query" in error for error in errors)

    # Test server capabilities and info
    def test_get_capabilities(self, server):
        """Test getting server capabilities."""
        capabilities = server.get_capabilities()
        assert capabilities is not None

    def test_get_available_tools(self, server):
        """Test getting available tools list."""
        tools = server.get_available_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    # Test parameter defaults and enhancement
    def test_add_intelligent_defaults_create_note(self, server):
        """Test intelligent defaults for create_note."""
        params = {"title": "Test Note"}
        enhanced = server._add_intelligent_defaults("create_note", params)
        
        assert enhanced["title"] == "Test Note"
        assert "is_todo" in enhanced
        assert "todo_completed" in enhanced

    def test_add_intelligent_defaults_unknown_tool(self, server):
        """Test intelligent defaults for unknown tool."""
        params = {"param": "value"}
        enhanced = server._add_intelligent_defaults("unknown_tool", params)
        
        # Should return original params unchanged
        assert enhanced == params

    # Test parameter validation and enhancement
    def test_validate_and_enhance_parameters_success(self, server):
        """Test parameter validation and enhancement success case."""
        params = {"query": "test"}
        result = server._validate_and_enhance_parameters("search_notes", params)
        
        assert result["enhanced_params"] is not None
        assert "limit" in result["enhanced_params"]
        assert result["enhanced_params"]["query"] == "test"

    def test_validate_and_enhance_parameters_with_correction(self, server):
        """Test parameter enhancement with automatic correction."""
        # Use 'q' instead of 'query'
        params = {"q": "test"}
        result = server._validate_and_enhance_parameters("search_notes", params)
        
        assert result["enhanced_params"] is not None
        # Should correct 'q' to 'query'
        assert "query" in result["enhanced_params"]

    # Test response formatting
    def test_format_single_search_result_with_tags(self, server):
        """Test formatting search result with tags."""
        note = {
            "id": "a" * 32,
            "title": "Tagged Note",
            "body": "Content with tags",
            "created_time": 1234567890,
            "updated_time": 1234567891,
            "parent_id": "b" * 32,
            "tags": ["important", "work", "project"]
        }
        
        result = server._format_single_search_result(note)
        assert "Tagged Note" in result
        assert "important" in result
        assert "work" in result
        assert "project" in result

    def test_format_single_search_result_long_body(self, server):
        """Test formatting search result with long body."""
        note = {
            "id": "a" * 32,
            "title": "Long Note",
            "body": "x" * 500,  # Very long body
            "created_time": 1234567890,
            "updated_time": 1234567891,
            "parent_id": "b" * 32,
            "tags": []
        }
        
        result = server._format_single_search_result(note)
        assert "Long Note" in result
        # Body should be truncated
        assert len(result) < 600  # Much shorter than original body

    # Test timestamp formatting
    def test_format_timestamp_edge_cases(self, server):
        """Test timestamp formatting edge cases."""
        # Test with string timestamp
        result = server._format_timestamp("1234567890")
        assert result is not None
        
        # Test with float timestamp
        result = server._format_timestamp(1234567890.5)
        assert result is not None
        
        # Test with zero timestamp
        result = server._format_timestamp(0)
        assert result is not None

    # Test metadata building
    def test_build_note_metadata_minimal(self, server):
        """Test building note metadata with minimal data."""
        metadata = server._build_note_metadata(
            created_time=None,
            updated_time=None,
            parent_id="",
            tags=None
        )
        assert isinstance(metadata, list)
        # Should still return some metadata even with minimal data

    def test_build_note_metadata_full(self, server):
        """Test building note metadata with full data."""
        metadata = server._build_note_metadata(
            created_time=1234567890,
            updated_time=1234567891,
            parent_id="b" * 32,
            tags=["tag1", "tag2", "tag3"]
        )
        assert isinstance(metadata, list)
        assert len(metadata) > 0
        
        # Convert to string to check content
        metadata_str = " ".join(metadata)
        assert "tag1" in metadata_str
        assert "tag2" in metadata_str

    # Test tags parameter sanitization
    def test_sanitize_tags_parameter_string_variants(self, server):
        """Test tags parameter sanitization with various string formats."""
        # Test comma-separated with spaces
        result = server._sanitize_tags_parameter("tag1, tag2, tag3")
        assert result == ["tag1", "tag2", "tag3"]
        
        # Test semicolon-separated
        result = server._sanitize_tags_parameter("tag1;tag2;tag3")
        assert result == ["tag1", "tag2", "tag3"]
        
        # Test mixed separators
        result = server._sanitize_tags_parameter("tag1, tag2;tag3")
        expected = ["tag1", "tag2", "tag3"]
        assert result == expected or result == ["tag1", "tag2;tag3"]  # Either is acceptable

    def test_sanitize_tags_parameter_empty_values(self, server):
        """Test tags parameter sanitization with empty values."""
        # Test empty string
        result = server._sanitize_tags_parameter("")
        assert result == []
        
        # Test whitespace only
        result = server._sanitize_tags_parameter("   ")
        assert result == []
        
        # Test list with empty strings
        result = server._sanitize_tags_parameter(["tag1", "", "tag2"])
        assert result == ["tag1", "tag2"]

    # Test parameter validation methods
    def test_validate_create_note_params_edge_cases(self, server):
        """Test create note parameter validation edge cases."""
        # Test with minimal valid params
        params = {"title": "Minimal Note"}
        validated = server._validate_create_note_params(params)
        assert validated["title"] == "Minimal Note"
        assert "is_todo" in validated
        assert "todo_completed" in validated
        
        # Test with boolean string values
        params = {
            "title": "Test",
            "is_todo": "true",
            "todo_completed": "false"
        }
        validated = server._validate_create_note_params(params)
        assert validated["is_todo"] is True
        assert validated["todo_completed"] is False

    def test_validate_update_note_params_edge_cases(self, server):
        """Test update note parameter validation edge cases."""
        # Test with only note_id
        params = {"note_id": "a" * 32}
        validated = server._validate_update_note_params(params)
        assert validated["note_id"] == "a" * 32
        
        # Test with empty updates (should still be valid)
        params = {"note_id": "a" * 32, "title": "", "body": ""}
        validated = server._validate_update_note_params(params)
        assert validated["note_id"] == "a" * 32 