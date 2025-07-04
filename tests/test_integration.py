"""
Integration tests for Joplin MCP Server.

This module contains comprehensive end-to-end tests that verify the complete
MCP server functionality, including tool interactions, workflow scenarios,
and cross-tool dependencies.
"""

import asyncio
from unittest.mock import Mock

import pytest

from joplin_mcp.server import JoplinMCPServer


class TestJoplinMCPServerIntegration:
    """Integration tests for complete MCP server functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a comprehensive mock client for integration testing."""
        client = Mock()
        client.ping.return_value = True
        client.is_connected = True
        client._mock_name = "mock_client"

        # Mock all client methods used by the server
        client.search_notes.return_value = []
        client.get_note.return_value = {}
        client.create_note.return_value = "note_123"
        client.update_note.return_value = True
        client.delete_note.return_value = True
        client.get_all_notebooks.return_value = []
        client.get_notebook.return_value = {}
        client.create_notebook.return_value = "notebook_123"
        client.get_all_tags.return_value = []
        client.create_tag.return_value = "tag_123"
        client.tag_note.return_value = True
        client.untag_note.return_value = True

        return client

    @pytest.fixture
    def server(self, mock_client):
        """Create server instance for integration testing."""
        return JoplinMCPServer(token="integration_test_token", client=mock_client, skip_ping=True)

    def test_server_initialization_and_capabilities(self, server):
        """Test complete server initialization and capability reporting."""
        # Test server initialization
        assert server.token == "integration_test_token"
        assert server.is_running is False  # Server starts in stopped state

        # Test server info
        server_info = server.get_server_info()
        assert server_info["name"] == "joplin-mcp"
        assert server_info["version"] == "0.1.0"
        assert "capabilities" in server_info
        assert "joplin_connection" in server_info

        # Test capabilities
        capabilities = server.get_capabilities()
        assert hasattr(capabilities, "tools")
        assert hasattr(capabilities, "prompts")
        assert hasattr(capabilities, "resources")

        # Test available tools
        tools = server.get_available_tools()
        assert len(tools) >= 13  # Should have at least the core tools

        tool_names = [tool.name for tool in tools]
        expected_tools = [
            "search_notes",
            "get_note",
            "create_note",
            "update_note",
            "delete_note",
            "list_notebooks",
            "get_notebook",
            "create_notebook",
            "list_tags",
            "create_tag",
            "tag_note",
            "untag_note",
            "ping_joplin",
        ]

        for expected_tool in expected_tools:
            assert expected_tool in tool_names

    @pytest.mark.asyncio
    async def test_complete_note_lifecycle_workflow(self, server, mock_client):
        """Test complete note lifecycle: create -> get -> update -> delete."""
        # Step 1: Create a note
        create_params = {
            "title": "Integration Test Note",
            "body": "This is a test note for integration testing.",
            "parent_id": "notebook_456",
            "is_todo": False,
        }

        mock_client.create_note.return_value = "note_integration_123"
        create_result = await server.handle_create_note(create_params)

        assert "content" in create_result
        assert len(create_result["content"]) == 1
        assert "Successfully created" in create_result["content"][0]["text"]

        # Verify client was called correctly
        mock_client.create_note.assert_called_with(
            title="Integration Test Note",
            parent_id="notebook_456",
            body="This is a test note for integration testing.",
            is_todo=False,
            todo_completed=False,
            tags=None,
        )

        # Step 2: Get the created note
        get_params = {"note_id": "note_integration_123", "include_body": True}

        mock_client.get_note.return_value = {
            "id": "note_integration_123",
            "title": "Integration Test Note",
            "body": "This is a test note for integration testing.",
            "created_time": 1640995200000,
            "updated_time": 1640995200000,
            "parent_id": "notebook_456",
        }

        get_result = await server.handle_get_note(get_params)

        assert "content" in get_result
        assert "Integration Test Note" in get_result["content"][0]["text"]

        # Step 3: Update the note
        update_params = {
            "note_id": "note_integration_123",
            "title": "Updated Integration Test Note",
            "body": "This note has been updated during integration testing.",
        }

        mock_client.update_note.return_value = True
        update_result = await server.handle_update_note(update_params)

        assert "Successfully updated" in update_result["content"][0]["text"]

        # Step 4: Delete the note
        delete_params = {"note_id": "note_integration_123"}

        mock_client.delete_note.return_value = True
        delete_result = await server.handle_delete_note(delete_params)

        assert "Successfully deleted" in delete_result["content"][0]["text"]
        assert "permanently removed" in delete_result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_notebook_management_workflow(self, server, mock_client):
        """Test complete notebook management workflow."""
        # Step 1: List existing notebooks
        mock_client.get_all_notebooks.return_value = [
            {
                "id": "notebook_existing_1",
                "title": "Existing Notebook 1",
                "created_time": 1640995200000,
            },
            {
                "id": "notebook_existing_2",
                "title": "Existing Notebook 2",
                "created_time": 1640995300000,
            },
        ]

        list_result = await server.handle_list_notebooks({})

        assert "Found 2 notebook" in list_result["content"][0]["text"]
        assert "Existing Notebook 1" in list_result["content"][0]["text"]
        assert "Existing Notebook 2" in list_result["content"][0]["text"]

        # Step 2: Create a new notebook
        create_params = {
            "title": "Integration Test Notebook",
            "parent_id": "notebook_existing_1",
        }

        mock_client.create_notebook.return_value = "notebook_integration_123"
        create_result = await server.handle_create_notebook(create_params)

        assert "Successfully created notebook" in create_result["content"][0]["text"]
        assert "Integration Test Notebook" in create_result["content"][0]["text"]

        # Step 3: Get the created notebook details
        get_params = {"notebook_id": "notebook_integration_123"}

        mock_client.get_notebook.return_value = {
            "id": "notebook_integration_123",
            "title": "Integration Test Notebook",
            "parent_id": "notebook_existing_1",
            "created_time": 1640995400000,
            "updated_time": 1640995400000,
        }

        get_result = await server.handle_get_notebook(get_params)

        assert "Integration Test Notebook" in get_result["content"][0]["text"]
        assert "notebook_integration_123" in get_result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_tag_management_and_note_tagging_workflow(self, server, mock_client):
        """Test complete tag management and note tagging workflow."""
        # Step 1: List existing tags
        mock_client.get_all_tags.return_value = [
            {
                "id": "tag_existing_1",
                "title": "important",
                "created_time": 1640995200000,
            },
            {"id": "tag_existing_2", "title": "work", "created_time": 1640995300000},
        ]

        list_result = await server.handle_list_tags({})

        assert "Found 2 tag" in list_result["content"][0]["text"]
        assert "important" in list_result["content"][0]["text"]
        assert "work" in list_result["content"][0]["text"]

        # Step 2: Create a new tag
        create_params = {"title": "integration-test"}

        mock_client.create_tag.return_value = "tag_integration_123"
        create_result = await server.handle_create_tag(create_params)

        assert "Successfully created tag" in create_result["content"][0]["text"]
        assert "integration-test" in create_result["content"][0]["text"]

        # Step 3: Tag a note with the new tag
        tag_params = {"note_id": "note_test_456", "tag_id": "tag_integration_123"}

        mock_client.tag_note.return_value = True
        tag_result = await server.handle_tag_note(tag_params)

        assert "Successfully tagged note" in tag_result["content"][0]["text"]
        assert "note_test_456" in tag_result["content"][0]["text"]
        assert "tag_integration_123" in tag_result["content"][0]["text"]

        # Step 4: Untag the note
        untag_params = {"note_id": "note_test_456", "tag_id": "tag_integration_123"}

        mock_client.untag_note.return_value = True
        untag_result = await server.handle_untag_note(untag_params)

        assert (
            "Successfully removed tag from note" in untag_result["content"][0]["text"]
        )
        assert "note_test_456" in untag_result["content"][0]["text"]
        assert "tag_integration_123" in untag_result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_search_and_retrieval_workflow(self, server, mock_client):
        """Test search and note retrieval workflow."""
        # Step 1: Search for notes
        search_params = {
            "query": "integration test",
            "limit": 5,
            "sort_by": "updated_time",
            "sort_order": "desc",
        }

        mock_client.search_notes.return_value = [
            {
                "id": "note_search_1",
                "title": "Integration Test Note 1",
                "body": "This note contains integration test content.",
                "created_time": 1640995200000,
                "updated_time": 1640995200000,
                "parent_id": "notebook_test",
            },
            {
                "id": "note_search_2",
                "title": "Integration Test Note 2",
                "body": "Another note for integration testing.",
                "created_time": 1640995300000,
                "updated_time": 1640995300000,
                "parent_id": "notebook_test",
            },
        ]

        search_result = await server.handle_search_notes(search_params)

        assert (
            'Found 2 note(s) for query: "integration test"'
            in search_result["content"][0]["text"]
        )
        assert "Integration Test Note 1" in search_result["content"][0]["text"]
        assert "Integration Test Note 2" in search_result["content"][0]["text"]

        # Verify client was called with correct parameters
        mock_client.search_notes.assert_called_with(
            query="integration test",
            limit=5,
            notebook_id=None,
            tags=None,
            sort_by="updated_time",
            sort_order="desc",
        )

        # Step 2: Retrieve specific notes from search results
        for note_id in ["note_search_1", "note_search_2"]:
            get_params = {"note_id": note_id, "include_body": True}

            mock_client.get_note.return_value = {
                "id": note_id,
                "title": f"Integration Test Note {note_id[-1]}",
                "body": f"Content for note {note_id}",
                "created_time": 1640995200000,
                "updated_time": 1640995200000,
                "parent_id": "notebook_test",
            }

            get_result = await server.handle_get_note(get_params)

            assert note_id in get_result["content"][0]["text"]
            assert (
                f"Integration Test Note {note_id[-1]}"
                in get_result["content"][0]["text"]
            )

    @pytest.mark.asyncio
    async def test_todo_note_workflow(self, server, mock_client):
        """Test todo note creation and management workflow."""
        # Step 1: Create a todo note
        create_params = {
            "title": "Integration Test Todo",
            "body": "This is a todo item for integration testing.",
            "parent_id": "notebook_todos",
            "is_todo": True,
            "todo_completed": False,
            "tags": ["urgent", "integration-test"],
        }

        mock_client.create_note.return_value = "todo_integration_123"
        create_result = await server.handle_create_note(create_params)

        assert "Successfully created todo" in create_result["content"][0]["text"]
        assert "Integration Test Todo" in create_result["content"][0]["text"]
        assert "**Todo Status:** 📝 Pending" in create_result["content"][0]["text"]

        # Verify client was called with correct parameters
        mock_client.create_note.assert_called_with(
            title="Integration Test Todo",
            parent_id="notebook_todos",
            body="This is a todo item for integration testing.",
            is_todo=True,
            todo_completed=False,
            tags=["urgent", "integration-test"],
        )

        # Step 2: Update todo to completed
        update_params = {"note_id": "todo_integration_123", "todo_completed": True}

        mock_client.update_note.return_value = True
        update_result = await server.handle_update_note(update_params)

        assert "Successfully updated note" in update_result["content"][0]["text"]

        # Verify client was called with correct parameters
        mock_client.update_note.assert_called_with(
            note_id="todo_integration_123", todo_completed=True
        )

    @pytest.mark.asyncio
    async def test_connection_and_error_handling(self, server, mock_client):
        """Test connection testing and error handling scenarios."""
        # Step 1: Test successful connection
        mock_client.ping.return_value = True
        ping_result = await server.handle_ping_joplin({})

        assert (
            "Joplin server connection successful" in ping_result["content"][0]["text"]
        )
        assert "responding and accessible" in ping_result["content"][0]["text"]

        # Step 2: Test failed connection
        mock_client.ping.return_value = False
        ping_result = await server.handle_ping_joplin({})

        assert "Joplin server connection failed" in ping_result["content"][0]["text"]
        assert "check your connection settings" in ping_result["content"][0]["text"]

        # Step 3: Test parameter validation errors
        with pytest.raises(ValueError, match="note_id parameter is required"):
            await server.handle_get_note({})

        with pytest.raises(ValueError, match="title parameter is required"):
            await server.handle_create_note({"parent_id": "test"})

        with pytest.raises(ValueError, match="notebook_id parameter is required"):
            await server.handle_get_notebook({})

    @pytest.mark.asyncio
    async def test_tool_schema_validation_integration(self, server):
        """Test tool schema validation across all tools."""
        # Test all tools have proper schemas
        tools = server.get_available_tools()

        for tool in tools:
            schema = server.get_tool_schema(tool.name)
            assert schema is not None
            assert "name" in schema
            assert "description" in schema
            assert "inputSchema" in schema

            # Test schema validation for each tool
            input_schema = schema["inputSchema"]
            assert "properties" in input_schema

            # Test required parameters validation
            if "required" in input_schema:
                for required_param in input_schema["required"]:
                    assert required_param in input_schema["properties"]

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, server, mock_client):
        """Test concurrent MCP operations."""
        # Setup mock responses
        mock_client.ping.return_value = True
        mock_client.get_all_notebooks.return_value = []
        mock_client.get_all_tags.return_value = []
        mock_client.search_notes.return_value = []

        # Create multiple concurrent operations
        operations = [
            server.handle_ping_joplin({}),
            server.handle_list_notebooks({}),
            server.handle_list_tags({}),
            server.handle_search_notes({"query": "test"}),
        ]

        # Execute all operations concurrently
        results = await asyncio.gather(*operations)

        # Verify all operations completed successfully
        assert len(results) == 4

        # Verify ping result
        assert "connection successful" in results[0]["content"][0]["text"]

        # Verify list results
        assert "No notebooks found" in results[1]["content"][0]["text"]
        assert "No tags found" in results[2]["content"][0]["text"]

        # Verify search result
        assert 'No notes found for query: "test"' in results[3]["content"][0]["text"]

    def test_server_context_managers(self, server):
        """Test server context manager functionality."""
        # Test synchronous context manager
        with server as ctx_server:
            assert ctx_server is server
            assert hasattr(ctx_server, "handle_ping_joplin")

        # Note: Async context manager testing removed since we don't need it for this integration test

    def test_server_info_and_debugging(self, server):
        """Test server information and debugging capabilities."""
        # Test server info
        server_info = server.get_server_info()

        assert "name" in server_info
        assert "version" in server_info
        assert "capabilities" in server_info
        assert "joplin_connection" in server_info

        assert server_info["name"] == "joplin-mcp"
        assert server_info["version"] == "0.1.0"

        # Test error context
        test_error = ValueError("Test error")
        error_context = server.get_error_context(test_error, "test_operation")

        assert "error_type" in error_context
        assert "error_message" in error_context
        assert "operation" in error_context
        assert "timestamp" in error_context
        assert "server_state" in error_context

        assert error_context["error_type"] == "ValueError"
        assert error_context["error_message"] == "Test error"
        assert error_context["operation"] == "test_operation"
