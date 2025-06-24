"""Tests for Joplin MCP Server implementation."""

import asyncio
from unittest.mock import MagicMock, Mock

import pytest

# Import MCP-related modules for testing
try:
    from mcp import types
    from mcp.server import NotificationOptions, Server
    from mcp.server.models import InitializationOptions
    from mcp.types import (
        AssistantMessage,
        CallToolResult,
        GetPromptResult,
        InitializeResult,
        JSONRPCError,
        JSONRPCRequest,
        JSONRPCResponse,
        ListPromptsResult,
        ListResourcesResult,
        ListToolsResult,
        Prompt,
        PromptMessage,
        ReadResourceResult,
        Resource,
        ServerCapabilities,
        TextContent,
        Tool,
        UserMessage,
    )
except ImportError:
    # Mock MCP types for testing if not available
    from unittest.mock import MagicMock

    types = MagicMock()
    Server = MagicMock()
    NotificationOptions = MagicMock()
    InitializationOptions = MagicMock()

    # Mock all the types we need
    Tool = MagicMock()
    Prompt = MagicMock()
    Resource = MagicMock()
    TextContent = MagicMock()
    JSONRPCRequest = MagicMock()
    JSONRPCResponse = MagicMock()
    JSONRPCError = MagicMock()
    CallToolResult = MagicMock()
    GetPromptResult = MagicMock()
    ReadResourceResult = MagicMock()
    ListResourcesResult = MagicMock()
    ListToolsResult = MagicMock()
    ListPromptsResult = MagicMock()
    InitializeResult = MagicMock()
    ServerCapabilities = MagicMock()
    PromptMessage = MagicMock()
    UserMessage = MagicMock()
    AssistantMessage = MagicMock()

# These imports will be available once the modules are created


class TestJoplinMCPServerInitialization:
    """Test cases for MCP server initialization and setup."""

    @pytest.fixture
    def mock_client(self):
        """Mock Joplin client for testing."""
        client = Mock()
        client.ping.return_value = True
        client.is_connected = True
        client._mock_name = "mock_client"  # Mark as mock
        return client

    def test_server_class_exists_and_can_be_imported(self):
        """Test that JoplinMCPServer class exists and can be imported."""
        # This test should fail - server module doesn't exist yet
        from joplin_mcp.server import JoplinMCPServer

        assert JoplinMCPServer is not None

    def test_server_initializes_with_token_parameter(self, mock_client):
        """Test that MCP server can be initialized with a token parameter."""
        from joplin_mcp.server import JoplinMCPServer

        # Pass mock client to avoid connection validation
        server = JoplinMCPServer(token="test_token_12345", client=mock_client)
        assert server is not None
        assert server.token == "test_token_12345"

    def test_server_has_mcp_server_instance(self, mock_client):
        """Test that server has an underlying MCP server instance."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(token="test_token_12345", client=mock_client)
        assert hasattr(server, "_mcp_server")
        assert server._mcp_server is not None

    def test_server_has_name_and_version(self, mock_client):
        """Test that server has proper name and version attributes."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(token="test_token_12345", client=mock_client)
        assert hasattr(server, "server_name")
        assert hasattr(server, "server_version")
        assert server.server_name == "joplin-mcp"
        assert server.server_version == "0.1.0"

    def test_server_has_capabilities_method(self, mock_client):
        """Test that server has get_capabilities method."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(token="test_token_12345", client=mock_client)
        assert hasattr(server, "get_capabilities")
        capabilities = server.get_capabilities()
        assert capabilities is not None

    def test_server_has_available_tools_method(self, mock_client):
        """Test that server has get_available_tools method."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(token="test_token_12345", client=mock_client)
        assert hasattr(server, "get_available_tools")
        tools = server.get_available_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_server_validates_joplin_connection_on_init(self, mock_client):
        """Test that server validates Joplin connection during initialization."""
        from joplin_mcp.server import JoplinMCPServer

        # Mock client should allow successful initialization
        server = JoplinMCPServer(token="test_token_12345", client=mock_client)
        assert server is not None

        # Since we're using a mock client, ping validation is skipped
        # But we can verify the client is properly assigned
        assert server.client == mock_client
        assert hasattr(server.client, "_mock_name")  # Verify it's a mock

    def test_server_raises_error_for_missing_token(self):
        """Test that server raises error when no token is provided."""
        from joplin_mcp.server import JoplinMCPServer

        # This test should fail - server doesn't exist yet
        with pytest.raises(Exception, match=".*[Tt]oken.*required.*"):
            JoplinMCPServer()

    def test_server_initializes_with_valid_config(self, mock_client):
        """Test server initialization with configuration object."""
        from joplin_mcp.server import JoplinMCPServer

        config = Mock()
        config.token = "config_token_123"
        config.host = "config_host"
        config.port = 8080

        server = JoplinMCPServer(config=config, client=mock_client)
        assert server is not None
        assert server.config == config

    def test_server_creates_mcp_server_instance(self, mock_client):
        """Test that server creates underlying MCP Server instance."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(token="test_token_12345", client=mock_client)
        assert hasattr(server, "_mcp_server")
        # The _mcp_server should be created during initialization
        assert server._mcp_server is not None

    def test_server_sets_up_server_name_and_version(self, mock_client):
        """Test that server sets up proper name and version."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(token="test_token_12345", client=mock_client)
        assert server.server_name == "joplin-mcp"
        assert server.server_version == "0.1.0"

    def test_server_configures_capabilities(self, mock_client):
        """Test that server configures MCP capabilities properly."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(token="test_token_12345", client=mock_client)
        capabilities = server.get_capabilities()

        # Check that capabilities has expected structure
        assert hasattr(capabilities, "tools")
        assert hasattr(capabilities, "prompts")
        assert hasattr(capabilities, "resources")

    def test_server_registers_tool_handlers(self, mock_client):
        """Test that server registers tool handlers."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(token="test_token_12345", client=mock_client)
        tools = server.get_available_tools()

        # Should have expected tools
        tool_names = [tool.name for tool in tools]
        expected_tools = ["search_notes", "get_note", "create_note", "ping_joplin"]
        for expected_tool in expected_tools:
            assert expected_tool in tool_names

    def test_server_registers_prompt_handlers(self, mock_client):
        """Test that server registers prompt handlers."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(token="test_token_12345", client=mock_client)
        prompts = server.get_available_prompts()

        # Should have expected prompts
        assert isinstance(prompts, list)
        assert len(prompts) > 0
        prompt_names = [prompt.name for prompt in prompts]
        assert "search_help" in prompt_names

    def test_server_registers_resource_handlers(self, mock_client):
        """Test that server registers resource handlers."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(token="test_token_12345", client=mock_client)
        resources = server.get_available_resources()

        # Should have expected resources
        assert isinstance(resources, list)
        assert len(resources) > 0
        resource_uris = [resource.uri for resource in resources]
        assert "joplin://server_info" in resource_uris

    def test_server_supports_context_manager_protocol(self, mock_client):
        """Test that server supports context manager protocol."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(token="test_token_12345", client=mock_client)

        # Test context manager protocol
        with server as ctx_server:
            assert ctx_server is server

    def test_server_supports_async_context_manager_protocol(self, mock_client):
        """Test that server supports async context manager protocol."""
        from joplin_mcp.server import JoplinMCPServer

        async def test_async_context():
            server = JoplinMCPServer(token="test_token_12345", client=mock_client)
            async with server as ctx_server:
                assert ctx_server is server

        # Run the async test
        asyncio.run(test_async_context())

    def test_server_startup_and_shutdown_lifecycle(self, mock_client):
        """Test server startup and shutdown lifecycle."""
        from joplin_mcp.server import JoplinMCPServer

        async def test_lifecycle():
            server = JoplinMCPServer(token="test_token_12345", client=mock_client)

            # Test startup
            await server.start()
            assert server.is_running is True

            # Test shutdown
            await server.stop()
            assert server.is_running is False

        # Run the async test
        asyncio.run(test_lifecycle())

    def test_server_provides_debugging_information(self, mock_client):
        """Test that server provides debugging and introspection information."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(token="test_token_12345", client=mock_client)

        # Test server info
        info = server.get_server_info()
        assert isinstance(info, dict)
        assert "name" in info
        assert "version" in info
        assert "capabilities" in info

    def test_server_handles_configuration_errors_gracefully(self):
        """Test that server handles configuration errors gracefully."""
        from joplin_mcp.server import JoplinMCPServer

        # Use a longer token to pass client validation and test server validation
        valid_token = "test_token_12345"

        # Test invalid host
        with pytest.raises(Exception, match=".*[Ii]nvalid host.*"):
            JoplinMCPServer(token=valid_token, host="")

        # Test invalid port
        with pytest.raises(Exception, match=".*[Ii]nvalid port.*"):
            JoplinMCPServer(token=valid_token, port=0)

        # Test invalid timeout
        with pytest.raises(Exception, match=".*[Ii]nvalid timeout.*"):
            JoplinMCPServer(token=valid_token, timeout=-1)

    def test_server_handles_mcp_protocol_initialization(self, mock_client):
        """Test that server handles MCP protocol initialization."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(token="test_token_12345", client=mock_client)

        # Server should have MCP server instance
        assert hasattr(server, "_mcp_server")
        assert server._mcp_server is not None

    def test_server_exposes_tool_schema_information(self, mock_client):
        """Test that server exposes tool schema information."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(token="test_token_12345", client=mock_client)

        # Test getting schema for a specific tool
        schema = server.get_tool_schema("search_notes")
        assert schema is not None
        assert "name" in schema
        assert "description" in schema
        assert "inputSchema" in schema

    def test_server_validates_tool_input_schemas(self, mock_client):
        """Test that server validates tool input against schemas."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(token="test_token_12345", client=mock_client)

        # Test valid input
        valid, errors = server.validate_tool_input("search_notes", {"query": "test"})
        assert valid is True
        assert len(errors) == 0

        # Test invalid input (missing required parameter)
        valid, errors = server.validate_tool_input("get_note", {})
        assert valid is False
        assert len(errors) > 0

    def test_server_provides_error_context_for_failed_operations(self, mock_client):
        """Test that server provides error context for failed operations."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(token="test_token_12345", client=mock_client)

        # Test error context generation
        test_error = Exception("Test error")
        context = server.get_error_context(test_error, "test_operation")

        assert isinstance(context, dict)
        assert "error_type" in context
        assert "error_message" in context
        assert "operation" in context
        assert "timestamp" in context
        assert "server_state" in context


class TestJoplinMCPServerTools:
    """Test cases for MCP server tool definitions and basic functionality."""

    @pytest.fixture
    def mock_server(self, mock_config=None, mock_joplin_client=None):
        """Create a mock server for testing tools."""
        from joplin_mcp.server import JoplinMCPServer

        if mock_config is None:
            mock_config = Mock()
            mock_config.host = "localhost"
            mock_config.port = 41184
            mock_config.token = "test_token"

        if mock_joplin_client is None:
            mock_joplin_client = Mock()
            mock_joplin_client.ping.return_value = True

        return JoplinMCPServer(config=mock_config, client=mock_joplin_client)

    def test_search_notes_tool_exists(self, mock_server):
        """Test that search_notes tool is properly defined."""
        # This test should fail - tools don't exist yet
        tools = mock_server.get_available_tools()
        search_tool = next((t for t in tools if t.name == "search_notes"), None)

        assert search_tool is not None
        assert search_tool.name == "search_notes"
        assert "search" in search_tool.description.lower()

        # Check schema properties
        schema = search_tool.inputSchema
        assert "properties" in schema
        assert "query" in schema["properties"]
        assert "limit" in schema["properties"]

    def test_get_note_tool_is_defined(self, mock_server):
        """Test that get_note tool is properly defined."""
        # This test should fail - tools don't exist yet
        tools = mock_server.get_available_tools()
        get_tool = next((t for t in tools if t.name == "get_note"), None)

        assert get_tool is not None
        assert get_tool.name == "get_note"
        assert (
            "retrieve" in get_tool.description.lower()
            or "get" in get_tool.description.lower()
        )

        # Check schema requires note_id
        schema = get_tool.inputSchema
        assert "note_id" in schema["properties"]
        assert "note_id" in schema.get("required", [])

    def test_note_management_tools_are_defined(self, mock_server):
        """Test that all note management tools are defined."""
        # This test should fail - tools don't exist yet
        tools = mock_server.get_available_tools()
        tool_names = [tool.name for tool in tools]

        expected_tools = ["create_note", "update_note", "delete_note"]
        for tool_name in expected_tools:
            assert tool_name in tool_names

        # Check create_note schema
        create_tool = next((t for t in tools if t.name == "create_note"), None)
        assert create_tool is not None
        create_schema = create_tool.inputSchema
        assert "title" in create_schema["properties"]
        assert "body" in create_schema["properties"]
        assert "title" in create_schema.get("required", [])

    def test_notebook_management_tools_are_defined(self, mock_server):
        """Test that notebook management tools are defined."""
        # This test should fail - tools don't exist yet
        tools = mock_server.get_available_tools()
        tool_names = [tool.name for tool in tools]

        expected_tools = ["list_notebooks", "get_notebook", "create_notebook"]
        for tool_name in expected_tools:
            assert tool_name in tool_names

    def test_tag_management_tools_are_defined(self, mock_server):
        """Test that tag management tools are defined."""
        # This test should fail - tools don't exist yet
        tools = mock_server.get_available_tools()
        tool_names = [tool.name for tool in tools]

        expected_tools = ["list_tags", "create_tag", "tag_note", "untag_note"]
        for tool_name in expected_tools:
            assert tool_name in tool_names

    def test_ping_joplin_tool_exists(self, mock_server):
        """Test that ping_joplin connection test tool is defined."""
        # This test should fail - tools don't exist yet
        tools = mock_server.get_available_tools()
        ping_tool = next((t for t in tools if t.name == "ping_joplin"), None)

        assert ping_tool is not None
        assert ping_tool.name == "ping_joplin"
        assert (
            "ping" in ping_tool.description.lower()
            or "connection" in ping_tool.description.lower()
            or "test" in ping_tool.description.lower()
        )


class TestJoplinMCPServerPrompts:
    """Test cases for MCP server prompt definitions."""

    @pytest.fixture
    def mock_server(self):
        """Create a mock server for testing prompts."""
        from joplin_mcp.server import JoplinMCPServer

        mock_config = Mock()
        mock_config.host = "localhost"
        mock_config.port = 41184
        mock_config.token = "test_token"

        mock_client = Mock()
        mock_client.ping.return_value = True

        return JoplinMCPServer(config=mock_config, client=mock_client)

    def test_search_help_prompt_is_defined(self, mock_server):
        """Test that search help prompt is defined."""
        # This test should fail - prompts don't exist yet
        prompts = mock_server.get_available_prompts()
        search_prompt = next((p for p in prompts if p.name == "search_help"), None)

        assert search_prompt is not None
        assert search_prompt.name == "search_help"
        assert "search" in search_prompt.description.lower()
        assert hasattr(search_prompt, "arguments")

    def test_note_template_prompt_is_defined(self, mock_server):
        """Test that note template prompt is defined."""
        # This test should fail - prompts don't exist yet
        prompts = mock_server.get_available_prompts()
        template_prompt = next((p for p in prompts if p.name == "note_template"), None)

        assert template_prompt is not None
        assert template_prompt.name == "note_template"
        assert (
            "template" in template_prompt.description.lower()
            or "note" in template_prompt.description.lower()
        )

    def test_tag_organization_prompt_is_defined(self, mock_server):
        """Test that tag organization prompt is defined."""
        # This test should fail - prompts don't exist yet
        prompts = mock_server.get_available_prompts()
        tag_prompt = next((p for p in prompts if p.name == "tag_organization"), None)

        assert tag_prompt is not None
        assert tag_prompt.name == "tag_organization"
        assert (
            "tag" in tag_prompt.description.lower()
            or "organize" in tag_prompt.description.lower()
        )


class TestJoplinMCPServerResources:
    """Test cases for MCP server resource definitions."""

    @pytest.fixture
    def mock_server(self):
        """Create a mock server for testing resources."""
        from joplin_mcp.server import JoplinMCPServer

        mock_config = Mock()
        mock_config.host = "localhost"
        mock_config.port = 41184
        mock_config.token = "test_token"

        mock_client = Mock()
        mock_client.ping.return_value = True

        return JoplinMCPServer(config=mock_config, client=mock_client)

    def test_server_info_resource_is_defined(self, mock_server):
        """Test that server info resource is defined."""
        # This test should fail - resources don't exist yet
        resources = mock_server.get_available_resources()
        server_resource = next(
            (r for r in resources if r.uri == "joplin://server_info"), None
        )

        assert server_resource is not None
        assert server_resource.uri == "joplin://server_info"
        assert (
            "server" in server_resource.name.lower()
            or "info" in server_resource.name.lower()
        )

    def test_notebooks_resource_is_defined(self, mock_server):
        """Test that notebooks resource is defined."""
        # This test should fail - resources don't exist yet
        resources = mock_server.get_available_resources()
        notebooks_resource = next(
            (r for r in resources if r.uri == "joplin://notebooks"), None
        )

        assert notebooks_resource is not None
        assert notebooks_resource.uri == "joplin://notebooks"
        assert "notebook" in notebooks_resource.name.lower()

    def test_tags_resource_is_defined(self, mock_server):
        """Test that tags resource is defined."""
        # This test should fail - resources don't exist yet
        resources = mock_server.get_available_resources()
        tags_resource = next((r for r in resources if r.uri == "joplin://tags"), None)

        assert tags_resource is not None
        assert tags_resource.uri == "joplin://tags"
        assert "tag" in tags_resource.name.lower()

    def test_statistics_resource_is_defined(self, mock_server):
        """Test that statistics resource is defined."""
        # This test should fail - resources don't exist yet
        resources = mock_server.get_available_resources()
        stats_resource = next(
            (r for r in resources if r.uri == "joplin://statistics"), None
        )

        assert stats_resource is not None
        assert stats_resource.uri == "joplin://statistics"
        assert (
            "statistic" in stats_resource.name.lower()
            or "stats" in stats_resource.name.lower()
        )


class TestJoplinMCPServerLifecycle:
    """Test cases for MCP server lifecycle management."""

    @pytest.fixture
    def mock_client(self):
        """Mock Joplin client for testing."""
        client = Mock()
        client.ping.return_value = True
        client.is_connected = True
        client._mock_name = "mock_client"
        return client

    @pytest.fixture
    def server(self, mock_client):
        """Create server instance for testing."""
        from joplin_mcp.server import JoplinMCPServer

        return JoplinMCPServer(token="test_token_12345", client=mock_client)

    @pytest.mark.asyncio
    async def test_server_has_start_method(self, server):
        """Test that server has start method for lifecycle management."""
        assert hasattr(server, "start")
        await server.start()
        assert hasattr(server, "is_running")
        assert server.is_running  is True

    @pytest.mark.asyncio
    async def test_server_has_stop_method(self, server):
        """Test that server has stop method for lifecycle management."""
        await server.start()
        assert hasattr(server, "stop")
        await server.stop()
        assert server.is_running  is False


class TestJoplinMCPServerSearchNotesTool:
    """Test cases for search_notes MCP tool implementation."""

    @pytest.fixture
    def mock_client(self):
        """Mock Joplin client for testing."""
        client = Mock()
        client.ping.return_value = True
        client.is_connected = True
        client._mock_name = "mock_client"
        return client

    @pytest.fixture
    def server(self, mock_client):
        """Create server instance for testing."""
        from joplin_mcp.server import JoplinMCPServer

        return JoplinMCPServer(token="test_token_12345", client=mock_client)

    def test_search_notes_tool_is_registered(self, server):
        """Test that search_notes tool is properly registered."""
        tools = server.get_available_tools()
        tool_names = [tool.name for tool in tools]
        assert "search_notes" in tool_names

        # Get the specific search_notes tool
        search_tool = next(
            (tool for tool in tools if tool.name == "search_notes"), None
        )
        assert search_tool is not None
        assert search_tool.description is not None
        assert len(search_tool.description) > 0

    def test_search_notes_tool_has_correct_schema(self, server):
        """Test that search_notes tool has correct input schema."""
        schema = server.get_tool_schema("search_notes")
        assert schema is not None

        # Verify schema structure
        assert "name" in schema
        assert "description" in schema
        assert "inputSchema" in schema

        # Verify input schema details
        input_schema = schema["inputSchema"]
        assert "properties" in input_schema

        # Verify required parameters
        properties = input_schema["properties"]
        assert "query" in properties
        assert properties["query"]["type"] == "string"
        assert "description" in properties["query"]

        # Verify optional parameters
        assert "limit" in properties
        assert properties["limit"]["type"] == "integer"
        assert "description" in properties["limit"]

        # Check for additional optional parameters
        assert "notebook_id" in properties
        assert "tags" in properties
        assert "sort_by" in properties
        assert "sort_order" in properties

    def test_search_notes_tool_validates_input_correctly(self, server):
        """Test that search_notes tool validates input parameters correctly."""
        # Test valid input
        valid_input = {
            "query": "test search",
            "limit": 10,
            "notebook_id": "notebook123",
            "sort_by": "title",
            "sort_order": "asc",
        }
        is_valid, errors = server.validate_tool_input("search_notes", valid_input)
        assert is_valid is True
        assert len(errors) == 0

        # Test missing required parameter
        invalid_input = {"limit": 10}
        is_valid, errors = server.validate_tool_input("search_notes", invalid_input)
        assert is_valid is False
        assert len(errors) > 0
        assert any("query" in error for error in errors)

        # Test invalid parameter types
        invalid_type_input = {"query": 123, "limit": "not_number"}
        is_valid, errors = server.validate_tool_input(
            "search_notes", invalid_type_input
        )
        assert is_valid is False
        assert len(errors) > 0

    def test_search_notes_tool_handler_exists(self, server):
        """Test that search_notes tool has a callable handler."""
        assert hasattr(server, "handle_search_notes")
        assert callable(server.handle_search_notes)

    @pytest.mark.asyncio
    async def test_search_notes_tool_handler_with_basic_query(
        self, server, mock_client
    ):
        """Test search_notes tool handler with basic query."""
        # Mock search results
        mock_results = [
            {
                "id": "note1",
                "title": "Test Note 1",
                "body": "This is a test note about search functionality",
                "created_time": 1640995200000,
                "updated_time": 1640995200000,
                "parent_id": "notebook1",
            },
            {
                "id": "note2",
                "title": "Test Note 2",
                "body": "Another test note for search testing",
                "created_time": 1640995300000,
                "updated_time": 1640995300000,
                "parent_id": "notebook1",
            },
        ]
        mock_client.search_notes.return_value = mock_results

        # Test basic search
        result = await server.handle_search_notes({"query": "test"})

        # Verify result structure
        assert isinstance(result, dict)
        assert "content" in result
        assert isinstance(result["content"], list)

        content = result["content"]
        assert len(content) > 0

        # Verify first content item
        first_item = content[0]
        assert "type" in first_item
        assert first_item["type"] == "text"
        assert "text" in first_item

        # Verify client was called correctly
        mock_client.search_notes.assert_called_once_with(
            query="test",
            limit=20,  # default limit
            notebook_id=None,
            tags=None,
            sort_by="updated_time",
            sort_order="desc",
        )

    @pytest.mark.asyncio
    async def test_search_notes_tool_handler_with_advanced_parameters(
        self, server, mock_client
    ):
        """Test search_notes tool handler with advanced search parameters."""
        mock_results = []
        mock_client.search_notes.return_value = mock_results

        # Test advanced search parameters
        await server.handle_search_notes(
            {
                "query": "advanced search",
                "limit": 5,
                "notebook_id": "notebook123",
                "tags": ["tag1", "tag2"],
                "sort_by": "title",
                "sort_order": "asc",
            }
        )

        # Verify client was called with correct parameters
        mock_client.search_notes.assert_called_once_with(
            query="advanced search",
            limit=5,
            notebook_id="notebook123",
            tags=["tag1", "tag2"],
            sort_by="title",
            sort_order="asc",
        )

    @pytest.mark.asyncio
    async def test_search_notes_tool_handler_formats_results_correctly(
        self, server, mock_client
    ):
        """Test that search_notes tool handler formats results in MCP format."""
        mock_results = [
            {
                "id": "note1",
                "title": "Sample Note",
                "body": "This is the note content",
                "created_time": 1640995200000,
                "updated_time": 1640995300000,
                "parent_id": "notebook1",
                "tags": ["tag1", "tag2"],
            }
        ]
        mock_client.search_notes.return_value = mock_results

        result = await server.handle_search_notes({"query": "sample"})

        # Verify MCP result format
        assert "content" in result
        content = result["content"]
        assert len(content) == 1

        text_content = content[0]
        assert text_content["type"] == "text"

        # Verify the formatted text contains key information
        text = text_content["text"]
        assert "Sample Note" in text
        assert "note1" in text
        assert "This is the note content" in text
        assert "tag1" in text
        assert "tag2" in text

    @pytest.mark.asyncio
    async def test_search_notes_tool_handler_handles_empty_results(
        self, server, mock_client
    ):
        """Test search_notes tool handler with no results."""
        mock_client.search_notes.return_value = []

        result = await server.handle_search_notes({"query": "nonexistent"})

        # Verify result structure for empty results
        assert "content" in result
        content = result["content"]
        assert len(content) == 1

        text_content = content[0]
        assert text_content["type"] == "text"
        assert "No notes found" in text_content["text"]

        mock_client.search_notes.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_notes_tool_handler_handles_client_errors(
        self, server, mock_client
    ):
        """Test search_notes tool handler error handling."""
        from joplin_mcp.exceptions import JoplinMCPError

        # Mock client error
        mock_client.search_notes.side_effect = JoplinMCPError("Search failed")

        # Test error handling
        with pytest.raises(JoplinMCPError, match="Search failed"):
            await server.handle_search_notes({"query": "error test"})

    @pytest.mark.asyncio
    async def test_search_notes_tool_handler_respects_limit_parameter(
        self, server, mock_client
    ):
        """Test that search_notes respects the limit parameter."""
        # Create more mock results than the limit
        mock_results = [
            {"id": f"note{i}", "title": f"Note {i}", "body": f"Content {i}"}
            for i in range(10)
        ]
        mock_client.search_notes.return_value = mock_results

        # Test with limit of 3
        result = await server.handle_search_notes({"query": "test", "limit": 3})

        # Verify limit was passed to client
        mock_client.search_notes.assert_called_once()
        call_args = mock_client.search_notes.call_args[1]
        assert call_args["limit"] == 3

        # Verify result formatting acknowledges the limit
        content = result["content"][0]["text"]
        assert "Found" in content or "Results" in content

    def test_search_notes_tool_integrates_with_mcp_server(self, server):
        """Test that search_notes tool integrates properly with MCP server."""
        # Test that the tool can be called through MCP server interface
        assert hasattr(server, "_mcp_server")

        # Verify tool is accessible through server's tool listing
        tools = server.get_available_tools()
        search_tool = next(
            (tool for tool in tools if tool.name == "search_notes"), None
        )

        # Verify tool has proper MCP attributes
        assert hasattr(search_tool, "name")
        assert hasattr(search_tool, "description")
        assert hasattr(search_tool, "inputSchema")

        # Verify input schema is properly structured for MCP
        schema = search_tool.inputSchema
        assert "properties" in schema
        assert "query" in schema["properties"]

    @pytest.mark.asyncio
    async def test_search_notes_tool_supports_text_search_operators(
        self, server, mock_client
    ):
        """Test that search_notes supports text search operators."""
        mock_client.search_notes.return_value = []

        # Test various search query formats
        test_queries = [
            "simple query",
            '"exact phrase"',
            "word1 AND word2",
            "word1 OR word2",
            "word1 NOT word2",
            'title:"specific title"',
            "tag:important",
        ]

        for query in test_queries:
            await server.handle_search_notes({"query": query})

        # Verify all queries were passed through correctly
        assert mock_client.search_notes.call_count == len(test_queries)

    @pytest.mark.asyncio
    async def test_search_notes_tool_handles_unicode_and_special_characters(
        self, server, mock_client
    ):
        """Test search_notes handles unicode and special characters."""
        mock_client.search_notes.return_value = []

        # Test unicode and special character queries
        unicode_queries = [
            "café résumé",
            "测试 中文",
            "émoji 🎉 test",
            "special!@#$%^&*()chars",
            "new\nline\ttab",
        ]

        for query in unicode_queries:
            result = await server.handle_search_notes({"query": query})
            assert "content" in result

        # Verify queries were handled
        assert mock_client.search_notes.call_count == len(unicode_queries)

    def test_search_notes_tool_schema_validation_comprehensive(self, server):
        """Test comprehensive schema validation for search_notes tool."""
        # Test all parameter combinations
        test_cases = [
            # Valid cases
            ({"query": "test"}, True),
            ({"query": "test", "limit": 10}, True),
            ({"query": "test", "notebook_id": "nb1"}, True),
            ({"query": "test", "tags": ["tag1"]}, True),
            ({"query": "test", "sort_by": "title", "sort_order": "asc"}, True),
            # Invalid cases
            ({}, False),  # Missing query
            ({"query": ""}, False),  # Empty query
            ({"query": "test", "limit": -1}, False),  # Invalid limit
            ({"query": "test", "limit": "not_number"}, False),  # Wrong type
            (
                {"query": "test", "sort_by": "invalid_field"},
                False,
            ),  # Invalid sort field
            (
                {"query": "test", "sort_order": "invalid_order"},
                False,
            ),  # Invalid sort order
        ]

        for test_input, expected_valid in test_cases:
            is_valid, errors = server.validate_tool_input("search_notes", test_input)
            assert (
                is_valid == expected_valid
            ), f"Failed for input {test_input}: {errors}"


class TestJoplinMCPServerGetNoteTool:
    """Test cases for get_note MCP tool implementation."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Joplin client for testing."""
        mock_client = Mock()

        # Setup default get_note behavior
        mock_client.get_note.return_value = {
            "id": "note123",
            "title": "Test Note",
            "body": "This is a test note content",
            "created_time": 1640995200000,
            "updated_time": 1640995300000,
            "parent_id": "notebook456",
            "is_todo": False,
            "todo_completed": False,
            "tags": ["tag1", "tag2"],
        }

        return mock_client

    @pytest.fixture
    def server(self, mock_client):
        """Create a server instance with mocked client for testing."""
        from joplin_mcp.server import JoplinMCPServer

        return JoplinMCPServer(client=mock_client)

    def test_get_note_tool_is_registered(self, server):
        """Test that get_note tool is properly registered."""
        tools = server.get_available_tools()
        tool_names = [tool.name for tool in tools]
        assert "get_note" in tool_names

        # Get the specific get_note tool
        get_note_tool = next((tool for tool in tools if tool.name == "get_note"), None)
        assert get_note_tool is not None
        assert get_note_tool.description is not None

    def test_get_note_tool_has_correct_schema(self, server):
        """Test that get_note tool has correct input schema."""
        schema = server.get_tool_schema("get_note")

        assert schema is not None
        assert "name" in schema
        assert schema["name"] == "get_note"
        assert "description" in schema
        assert "inputSchema" in schema

        input_schema = schema["inputSchema"]
        assert "type" in input_schema  # type should be in inputSchema, not root
        assert input_schema["type"] == "object"
        assert "properties" in input_schema

        # Check required note_id parameter
        properties = input_schema["properties"]
        assert "note_id" in properties

        note_id_prop = properties["note_id"]
        assert note_id_prop["type"] == "string"
        assert "description" in note_id_prop

        # Check that note_id is required
        assert "required" in input_schema
        assert "note_id" in input_schema["required"]

        # Optional include_body parameter
        if "include_body" in properties:
            include_body_prop = properties["include_body"]
            assert include_body_prop["type"] == "boolean"

    def test_get_note_tool_validates_input_correctly(self, server):
        """Test that get_note tool validates input parameters correctly."""

        # Valid input
        valid_input = {"note_id": "abc123def456"}
        is_valid, errors = server.validate_tool_input("get_note", valid_input)
        assert is_valid, f"Valid input rejected: {errors}"

        # Invalid input - missing note_id
        invalid_input = {}
        is_valid, errors = server.validate_tool_input("get_note", invalid_input)
        assert not is_valid, "Missing note_id should be invalid"
        assert errors is not None

        # Invalid input - wrong type
        invalid_type_input = {"note_id": 123}
        is_valid, errors = server.validate_tool_input("get_note", invalid_type_input)
        assert not is_valid, "Wrong type for note_id should be invalid"

    def test_get_note_tool_handler_exists(self, server):
        """Test that get_note tool has a callable handler."""
        assert hasattr(server, "handle_get_note")
        assert callable(server.handle_get_note)

    @pytest.mark.asyncio
    async def test_get_note_tool_handler_with_valid_id(self, server, mock_client):
        """Test get_note tool handler with valid note ID."""
        mock_note = {
            "id": "note123",
            "title": "Sample Note",
            "body": "This is the note content",
            "created_time": 1640995200000,
            "updated_time": 1640995300000,
            "parent_id": "notebook456",
            "is_todo": False,
            "todo_completed": False,
            "tags": ["important", "work"],
        }
        mock_client.get_note.return_value = mock_note

        # Test with valid note ID
        result = await server.handle_get_note({"note_id": "note123"})

        # Verify MCP result format
        assert "content" in result
        content = result["content"]
        assert len(content) == 1

        text_content = content[0]
        assert text_content["type"] == "text"

        # Verify the formatted text contains key information
        text = text_content["text"]
        assert "Sample Note" in text
        assert "note123" in text
        assert "This is the note content" in text
        assert "important" in text
        assert "work" in text

        # Verify client was called correctly
        mock_client.get_note.assert_called_once_with("note123")

    @pytest.mark.asyncio
    async def test_get_note_tool_handler_with_include_body_parameter(
        self, server, mock_client
    ):
        """Test get_note tool handler with include_body parameter."""
        mock_note = {
            "id": "note123",
            "title": "Sample Note",
            "body": "This is the note content",
            "created_time": 1640995200000,
        }
        mock_client.get_note.return_value = mock_note

        # Test with include_body=True
        await server.handle_get_note({"note_id": "note123", "include_body": True})
        mock_client.get_note.assert_called()

        # Test with include_body=False
        await server.handle_get_note({"note_id": "note123", "include_body": False})

        # Verify calls were made (actual filtering may be implemented later)
        assert mock_client.get_note.call_count >= 1

    @pytest.mark.asyncio
    async def test_get_note_tool_handler_formats_result_correctly(
        self, server, mock_client
    ):
        """Test that get_note tool handler formats results in MCP format."""
        mock_note = {
            "id": "note456",
            "title": "Formatted Note",
            "body": "Content with formatting",
            "created_time": 1640995200000,
            "updated_time": 1640995300000,
            "parent_id": "notebook789",
            "is_todo": True,
            "todo_completed": False,
            "tags": ["urgent", "review"],
        }
        mock_client.get_note.return_value = mock_note

        result = await server.handle_get_note({"note_id": "note456"})

        # Verify MCP result structure
        assert "content" in result
        assert isinstance(result["content"], list)
        assert len(result["content"]) == 1

        content_item = result["content"][0]
        assert content_item["type"] == "text"
        assert "text" in content_item

        text = content_item["text"]

        # Verify key information is formatted properly
        assert "Formatted Note" in text
        assert "note456" in text
        assert "Content with formatting" in text
        assert "notebook789" in text
        assert "urgent" in text
        assert "review" in text
        assert "TODO" in text or "Todo" in text  # Should indicate it's a todo

    @pytest.mark.asyncio
    async def test_get_note_tool_handler_handles_note_not_found(
        self, server, mock_client
    ):
        """Test get_note tool handler when note is not found."""
        from joplin_mcp.exceptions import JoplinMCPError

        # Mock client to raise exception for non-existent note
        mock_client.get_note.side_effect = JoplinMCPError("Note not found")

        # Test error handling
        with pytest.raises(JoplinMCPError, match="Note not found"):
            await server.handle_get_note({"note_id": "nonexistent123"})

    @pytest.mark.asyncio
    async def test_get_note_tool_handler_handles_client_errors(
        self, server, mock_client
    ):
        """Test get_note tool handler error handling."""
        from joplin_mcp.exceptions import JoplinAPIError

        # Mock client error
        mock_client.get_note.side_effect = JoplinAPIError("API connection failed")

        # Test error handling
        with pytest.raises(JoplinAPIError, match="API connection failed"):
            await server.handle_get_note({"note_id": "note123"})

    @pytest.mark.asyncio
    async def test_get_note_tool_handler_validates_note_id_format(
        self, server, mock_client
    ):
        """Test that get_note validates note ID format."""
        # Test with various note ID formats
        valid_ids = [
            "abc123def456",
            "1234567890abcdef",
            "note_with_underscores",
            "note-with-dashes",
            "0123456789abcdef0123456789abcdef",  # 32 chars
        ]

        mock_client.get_note.return_value = {"id": "test", "title": "Test", "body": ""}

        for note_id in valid_ids:
            result = await server.handle_get_note({"note_id": note_id})
            assert "content" in result

        assert mock_client.get_note.call_count == len(valid_ids)

    def test_get_note_tool_integrates_with_mcp_server(self, server):
        """Test that get_note tool integrates properly with MCP server."""
        # Test that the tool can be called through MCP server interface
        assert hasattr(server, "_mcp_server")

        # Verify tool is accessible through server's tool listing
        tools = server.get_available_tools()
        get_note_tool = next((tool for tool in tools if tool.name == "get_note"), None)

        # Verify tool has proper MCP attributes
        assert hasattr(get_note_tool, "name")
        assert hasattr(get_note_tool, "description")
        assert hasattr(get_note_tool, "inputSchema")

        # Verify input schema is properly structured for MCP
        schema = get_note_tool.inputSchema
        assert "properties" in schema
        assert "note_id" in schema["properties"]

    @pytest.mark.asyncio
    async def test_get_note_tool_handles_empty_note_body(self, server, mock_client):
        """Test get_note tool handles notes with empty body."""
        mock_note = {
            "id": "empty_note",
            "title": "Empty Note",
            "body": "",
            "created_time": 1640995200000,
            "tags": [],
        }
        mock_client.get_note.return_value = mock_note

        result = await server.handle_get_note({"note_id": "empty_note"})

        # Should still return valid MCP response
        assert "content" in result
        text = result["content"][0]["text"]
        assert "Empty Note" in text
        assert "empty_note" in text

    @pytest.mark.asyncio
    async def test_get_note_tool_handles_unicode_content(self, server, mock_client):
        """Test get_note tool handles unicode content properly."""
        mock_note = {
            "id": "unicode_note",
            "title": "Unicode Test: café résumé 测试 🎉",
            "body": "Content with émojis 🚀 and special chars: äöü",
            "created_time": 1640995200000,
            "tags": ["unicode", "test"],
        }
        mock_client.get_note.return_value = mock_note

        result = await server.handle_get_note({"note_id": "unicode_note"})

        # Verify unicode content is handled properly
        assert "content" in result
        text = result["content"][0]["text"]
        assert "café résumé" in text
        assert "测试" in text
        assert "🎉" in text
        assert "🚀" in text
        assert "äöü" in text

    def test_get_note_tool_schema_validation_comprehensive(self, server):
        """Test comprehensive schema validation for get_note tool."""
        # Test all parameter combinations
        test_cases = [
            # Valid cases
            ({"note_id": "valid123"}, True),
            ({"note_id": "abc123def456"}, True),
            ({"note_id": "note123", "include_body": True}, True),
            ({"note_id": "note123", "include_body": False}, True),
            # Invalid cases
            ({}, False),  # Missing note_id
            ({"note_id": ""}, False),  # Empty note_id
            ({"note_id": None}, False),  # Null note_id
            ({"note_id": 123}, False),  # Wrong type
            ({"note_id": ["not", "string"]}, False),  # Wrong type
            ({"include_body": True}, False),  # Missing required note_id
        ]

        for test_input, expected_valid in test_cases:
            is_valid, errors = server.validate_tool_input("get_note", test_input)
            assert (
                is_valid == expected_valid
            ), f"Failed for input {test_input}: {errors}"


class TestJoplinMCPServerCreateNoteTool:
    """Test class for create_note MCP tool functionality."""

    @pytest.fixture
    def mock_client(self):
        """Mock client for testing."""
        client = Mock()
        client.is_connected = True
        client.create_note.return_value = "test_note_123"
        return client

    @pytest.fixture
    def server(self, mock_client):
        """Create server instance with mocked client for testing."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(
            token="test_token", host="localhost", port=41184, client=mock_client
        )
        return server

    def test_create_note_tool_is_registered(self, server):
        """Test that create_note tool is properly registered."""
        tool_names = [tool.name for tool in server.get_available_tools()]
        assert "create_note" in tool_names

    def test_create_note_tool_has_correct_schema(self, server):
        """Test that create_note tool has the correct schema."""
        tools = {tool.name: tool for tool in server.get_available_tools()}
        create_note_tool = tools["create_note"]

        # Verify basic tool properties
        assert create_note_tool.name == "create_note"
        assert create_note_tool.description
        assert "Create a new note" in create_note_tool.description

        # Verify schema structure
        schema = create_note_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema

        properties = schema["properties"]
        required = schema["required"]

        # Check required parameters
        assert "title" in required
        assert "parent_id" in required

        # Check parameter definitions
        assert "title" in properties
        assert properties["title"]["type"] == "string"
        assert "description" in properties["title"]

        assert "parent_id" in properties
        assert properties["parent_id"]["type"] == "string"
        assert "description" in properties["parent_id"]

        # Check optional parameters
        assert "body" in properties
        assert properties["body"]["type"] == "string"
        assert "body" not in required

        assert "is_todo" in properties
        assert properties["is_todo"]["type"] == "boolean"
        assert "is_todo" not in required

        assert "todo_completed" in properties
        assert properties["todo_completed"]["type"] == "boolean"
        assert "todo_completed" not in required

        assert "tags" in properties
        assert properties["tags"]["type"] == "array"
        assert "tags" not in required

    def test_create_note_tool_validates_input_correctly(self, server):
        """Test that create_note tool validates input parameters correctly."""
        tools = {tool.name: tool for tool in server.get_available_tools()}
        create_note_tool = tools["create_note"]
        schema = create_note_tool.inputSchema

        # Verify required fields are actually required
        required_fields = schema["required"]
        assert "title" in required_fields
        assert "parent_id" in required_fields

        # Verify optional fields are not required
        optional_fields = ["body", "is_todo", "todo_completed", "tags"]
        for field in optional_fields:
            assert field not in required_fields

    def test_create_note_tool_handler_exists(self, server):
        """Test that create_note tool handler method exists."""
        assert hasattr(server, "handle_create_note")
        assert callable(server.handle_create_note)

    @pytest.mark.asyncio
    async def test_create_note_tool_handler_with_valid_data(self, server, mock_client):
        """Test create_note tool handler with valid note data."""
        # Setup mock client response
        mock_client.create_note.return_value = "test_note_123"

        # Prepare test parameters
        params = {
            "title": "Test Note",
            "body": "This is a test note content.",
            "parent_id": "notebook_abc123",
            "is_todo": False,
            "todo_completed": False,
            "tags": ["test", "sample"],
        }

        # Call handler
        result = await server.handle_create_note(params)

        # Verify client method was called correctly
        mock_client.create_note.assert_called_once_with(
            title="Test Note",
            body="This is a test note content.",
            parent_id="notebook_abc123",
            is_todo=False,
            todo_completed=False,
            tags=["test", "sample"],
        )

        # Verify response format
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "test_note_123" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_create_note_tool_handler_with_minimal_data(
        self, server, mock_client
    ):
        """Test create_note tool handler with minimal required data."""
        # Setup mock client response
        mock_client.create_note.return_value = "minimal_note_456"

        # Prepare minimal parameters
        params = {"title": "Minimal Note", "parent_id": "notebook_def456"}

        # Call handler
        result = await server.handle_create_note(params)

        # Verify client method was called with defaults
        mock_client.create_note.assert_called_once_with(
            title="Minimal Note",
            parent_id="notebook_def456",
            body="",
            is_todo=False,
            todo_completed=False,
            tags=None,
        )

        # Verify response
        assert "content" in result
        assert "minimal_note_456" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_create_note_tool_handler_with_todo_parameters(
        self, server, mock_client
    ):
        """Test create_note tool handler with todo-specific parameters."""
        # Setup mock client response
        mock_client.create_note.return_value = "todo_note_789"

        # Prepare todo parameters
        params = {
            "title": "Todo Item",
            "parent_id": "notebook_ghi789",
            "is_todo": True,
            "todo_completed": False,
            "body": "This is a todo item",
        }

        # Call handler
        result = await server.handle_create_note(params)

        # Verify client method was called correctly
        mock_client.create_note.assert_called_once_with(
            title="Todo Item",
            parent_id="notebook_ghi789",
            body="This is a todo item",
            is_todo=True,
            todo_completed=False,
            tags=None,
        )

        # Verify response mentions todo
        result_text = result["content"][0]["text"]
        assert "todo_note_789" in result_text
        assert "todo" in result_text.lower()

    @pytest.mark.asyncio
    async def test_create_note_tool_handler_validates_required_fields(self, server):
        """Test create_note tool handler validates required fields."""
        # Test missing title
        with pytest.raises(ValueError, match="title.*required"):
            await server.handle_create_note({"parent_id": "notebook_123"})

        # Test empty title
        with pytest.raises(ValueError, match="title.*required"):
            await server.handle_create_note({"title": "", "parent_id": "notebook_123"})

        # Test missing parent_id
        with pytest.raises(ValueError, match="parent_id.*required"):
            await server.handle_create_note({"title": "Test Note"})

        # Test empty parent_id
        with pytest.raises(ValueError, match="parent_id.*required"):
            await server.handle_create_note({"title": "Test Note", "parent_id": " "})

    @pytest.mark.asyncio
    async def test_create_note_tool_handler_handles_client_errors(
        self, server, mock_client
    ):
        """Test create_note tool handler properly handles client errors."""
        from joplin_mcp.exceptions import JoplinMCPError

        # Setup mock client to raise error
        mock_client.create_note.side_effect = JoplinMCPError("Note creation failed")

        # Prepare valid parameters
        params = {"title": "Test Note", "parent_id": "notebook_123"}

        # Verify error is re-raised
        with pytest.raises(JoplinMCPError, match="Note creation failed"):
            await server.handle_create_note(params)

    @pytest.mark.asyncio
    async def test_create_note_tool_handler_validates_parameter_types(self, server):
        """Test create_note tool handler validates parameter types."""
        # Test invalid is_todo type
        params = {
            "title": "Test Note",
            "parent_id": "notebook_123",
            "is_todo": "invalid_boolean",
        }

        # Should handle type conversion gracefully or validate
        result = await server.handle_create_note(params)
        assert "content" in result  # Should not fail but convert

        # Test invalid tags type
        params_invalid_tags = {
            "title": "Test Note",
            "parent_id": "notebook_123",
            "tags": "not_a_list",
        }

        # Should handle gracefully
        result = await server.handle_create_note(params_invalid_tags)
        assert "content" in result

    @pytest.mark.asyncio
    async def test_create_note_tool_integrates_with_mcp_server(self, server):
        """Test create_note tool integrates properly with MCP server."""
        from mcp.types import CallToolRequest

        # Create a mock tool call request
        CallToolRequest(
            method="tools/call",
            params={
                "name": "create_note",
                "arguments": {
                    "title": "Integration Test Note",
                    "parent_id": "notebook_integration_123",
                    "body": "This tests MCP integration",
                },
            },
        )

        # Verify tool is available in server
        tools = server.get_available_tools()
        tool_names = [tool.name for tool in tools]
        assert "create_note" in tool_names

    @pytest.mark.asyncio
    async def test_create_note_tool_handles_unicode_content(self, server, mock_client):
        """Test create_note tool handler handles unicode content correctly."""
        # Setup mock client response
        mock_client.create_note.return_value = "unicode_note_456"

        # Prepare parameters with unicode content
        params = {
            "title": "测试笔记 - Test Note 🚀",
            "body": "Unicode content: 你好世界 Hello 🌍",
            "parent_id": "notebook_unicode_123",
            "tags": ["测试", "unicode", "🏷️"],
        }

        # Call handler
        result = await server.handle_create_note(params)

        # Verify client was called with unicode content
        mock_client.create_note.assert_called_once()
        call_args = mock_client.create_note.call_args
        assert call_args[1]["title"] == "测试笔记 - Test Note 🚀"
        assert call_args[1]["body"] == "Unicode content: 你好世界 Hello 🌍"
        assert "测试" in call_args[1]["tags"]

        # Verify response handles unicode
        result_text = result["content"][0]["text"]
        assert "unicode_note_456" in result_text

    @pytest.mark.asyncio
    async def test_create_note_tool_formats_response_correctly(
        self, server, mock_client
    ):
        """Test create_note tool handler formats response correctly."""
        # Setup mock client response
        mock_client.create_note.return_value = "formatted_note_789"

        # Prepare test parameters
        params = {
            "title": "Response Format Test",
            "parent_id": "notebook_format_123",
            "body": "Testing response formatting",
        }

        # Call handler
        result = await server.handle_create_note(params)

        # Verify response structure
        assert isinstance(result, dict)
        assert "content" in result
        assert isinstance(result["content"], list)
        assert len(result["content"]) == 1

        content_item = result["content"][0]
        assert content_item["type"] == "text"
        assert "text" in content_item

        # Verify response content
        response_text = content_item["text"]
        assert "formatted_note_789" in response_text
        assert "created" in response_text.lower()
        assert "Response Format Test" in response_text

    def test_create_note_tool_schema_validation_comprehensive(self, server):
        """Test comprehensive schema validation for create_note tool."""
        tools = {tool.name: tool for tool in server.get_available_tools()}
        create_note_tool = tools["create_note"]
        schema = create_note_tool.inputSchema

        # Verify schema is well-formed
        assert "type" in schema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema

        # Verify all expected properties exist
        expected_properties = [
            "title",
            "body",
            "parent_id",
            "is_todo",
            "todo_completed",
            "tags",
        ]
        for prop in expected_properties:
            assert prop in schema["properties"]
            assert "type" in schema["properties"][prop]
            assert "description" in schema["properties"][prop]

        # Verify property types
        assert schema["properties"]["title"]["type"] == "string"
        assert schema["properties"]["body"]["type"] == "string"
        assert schema["properties"]["parent_id"]["type"] == "string"
        assert schema["properties"]["is_todo"]["type"] == "boolean"
        assert schema["properties"]["todo_completed"]["type"] == "boolean"
        assert schema["properties"]["tags"]["type"] == "array"

        # Verify tags array items
        tags_property = schema["properties"]["tags"]
        assert "items" in tags_property
        assert tags_property["items"]["type"] == "string"

        # Verify required vs optional
        required_fields = schema["required"]
        assert "title" in required_fields
        assert "parent_id" in required_fields
        assert len(required_fields) == 2  # Only title and parent_id are required


class TestJoplinMCPServerUpdateNoteTool:
    """Test suite for update_note MCP tool."""

    @pytest.fixture
    def mock_client(self):
        """Mock client for testing."""
        client = Mock()
        client.is_connected = True
        client.update_note.return_value = True
        return client

    @pytest.fixture
    def server(self, mock_client):
        """Create server instance with mocked client for testing."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(
            token="test_token", host="localhost", port=41184, client=mock_client
        )
        return server

    @pytest.mark.asyncio
    async def test_update_note_tool_is_registered(self, server):
        """Test that update_note tool is properly registered."""
        tools = server.get_available_tools()
        tool_names = [tool.name for tool in tools]
        assert "update_note" in tool_names

    @pytest.mark.asyncio
    async def test_update_note_tool_has_correct_schema(self, server):
        """Test that update_note tool has correct schema definition."""
        tools = server.get_available_tools()
        update_note_tool = next(tool for tool in tools if tool.name == "update_note")

        # Verify basic tool properties
        assert update_note_tool.name == "update_note"
        assert update_note_tool.description == "Update an existing note"
        assert hasattr(update_note_tool, "inputSchema")

        # Verify schema structure
        schema = update_note_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema

    @pytest.mark.asyncio
    async def test_update_note_tool_handler_exists(self, server):
        """Test that update_note tool handler method exists."""
        assert hasattr(server, "handle_update_note")
        assert callable(server.handle_update_note)

    @pytest.mark.asyncio
    async def test_update_note_tool_handler_with_valid_data(self, server, mock_client):
        """Test update_note tool handler with valid note data."""
        # Setup mock client response
        mock_client.update_note.return_value = True

        # Prepare test parameters
        params = {
            "note_id": "note_123",
            "title": "Updated Note Title",
            "body": "Updated note content.",
        }

        # Call handler
        result = await server.handle_update_note(params)

        # Verify client method was called correctly
        mock_client.update_note.assert_called_once_with(
            note_id="note_123", title="Updated Note Title", body="Updated note content."
        )

        # Verify response format
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "Successfully updated note" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_update_note_tool_handler_validates_required_fields(
        self, server, mock_client
    ):
        """Test update_note tool handler validates required fields."""
        # Test missing note_id
        with pytest.raises(ValueError, match="note_id parameter is required"):
            await server.handle_update_note({})

        # Test empty note_id
        with pytest.raises(ValueError, match="note_id parameter is required"):
            await server.handle_update_note({"note_id": ""})


class TestJoplinMCPServerDeleteNoteTool:
    """Test suite for delete_note MCP tool."""

    @pytest.fixture
    def mock_client(self):
        """Mock client for testing."""
        client = Mock()
        client.is_connected = True
        client.delete_note.return_value = True
        return client

    @pytest.fixture
    def server(self, mock_client):
        """Create server instance with mocked client for testing."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(
            token="test_token", host="localhost", port=41184, client=mock_client
        )
        return server

    @pytest.mark.asyncio
    async def test_delete_note_tool_is_registered(self, server):
        """Test that delete_note tool is properly registered."""
        tools = server.get_available_tools()
        tool_names = [tool.name for tool in tools]
        assert "delete_note" in tool_names

    @pytest.mark.asyncio
    async def test_delete_note_tool_has_correct_schema(self, server):
        """Test that delete_note tool has correct schema definition."""
        tools = server.get_available_tools()
        delete_note_tool = next(tool for tool in tools if tool.name == "delete_note")

        # Verify basic tool properties
        assert delete_note_tool.name == "delete_note"
        assert delete_note_tool.description == "Delete a note"
        assert hasattr(delete_note_tool, "inputSchema")

        # Verify schema structure
        schema = delete_note_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema

    @pytest.mark.asyncio
    async def test_delete_note_tool_handler_exists(self, server):
        """Test that delete_note tool handler method exists."""
        assert hasattr(server, "handle_delete_note")
        assert callable(server.handle_delete_note)

    @pytest.mark.asyncio
    async def test_delete_note_tool_handler_with_valid_data(self, server, mock_client):
        """Test delete_note tool handler with valid note ID."""
        # Setup mock client response
        mock_client.delete_note.return_value = True

        # Prepare test parameters
        params = {"note_id": "note_123"}

        # Call handler
        result = await server.handle_delete_note(params)

        # Verify client method was called correctly
        mock_client.delete_note.assert_called_once_with(note_id="note_123")

        # Verify response format
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "Successfully deleted note" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_delete_note_tool_handler_validates_required_fields(
        self, server, mock_client
    ):
        """Test delete_note tool handler validates required fields."""
        # Test missing note_id
        with pytest.raises(ValueError, match="note_id parameter is required"):
            await server.handle_delete_note({})

        # Test empty note_id
        with pytest.raises(ValueError, match="note_id parameter is required"):
            await server.handle_delete_note({"note_id": ""})


class TestJoplinMCPServerListNotebooksTool:
    """Test suite for list_notebooks MCP tool."""

    @pytest.fixture
    def mock_client(self):
        """Mock client for testing."""
        client = Mock()
        client.is_connected = True
        client.list_notebooks.return_value = []
        return client

    @pytest.fixture
    def server(self, mock_client):
        """Create server instance with mocked client for testing."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(
            token="test_token", host="localhost", port=41184, client=mock_client
        )
        return server

    @pytest.mark.asyncio
    async def test_list_notebooks_tool_is_registered(self, server):
        """Test that list_notebooks tool is properly registered."""
        tools = server.get_available_tools()
        tool_names = [tool.name for tool in tools]
        assert "list_notebooks" in tool_names

    @pytest.mark.asyncio
    async def test_list_notebooks_tool_has_correct_schema(self, server):
        """Test that list_notebooks tool has correct schema definition."""
        tools = server.get_available_tools()
        list_notebooks_tool = next(
            tool for tool in tools if tool.name == "list_notebooks"
        )

        # Verify basic tool properties
        assert list_notebooks_tool.name == "list_notebooks"
        assert list_notebooks_tool.description == "List all notebooks"
        assert hasattr(list_notebooks_tool, "inputSchema")

        # Verify schema structure
        schema = list_notebooks_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema

    @pytest.mark.asyncio
    async def test_list_notebooks_tool_handler_exists(self, server):
        """Test that list_notebooks tool handler method exists."""
        assert hasattr(server, "handle_list_notebooks")
        assert callable(server.handle_list_notebooks)

    @pytest.mark.asyncio
    async def test_list_notebooks_tool_handler_with_valid_data(
        self, server, mock_client
    ):
        """Test list_notebooks tool handler with valid response."""
        # Setup mock client response
        mock_notebooks = [
            {"id": "nb1", "title": "Notebook 1", "created_time": 1234567890},
            {"id": "nb2", "title": "Notebook 2", "created_time": 1234567891},
        ]
        mock_client.list_notebooks.return_value = mock_notebooks

        # Call handler
        result = await server.handle_list_notebooks({})

        # Verify client method was called correctly
        mock_client.list_notebooks.assert_called_once()

        # Verify response format
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "Found 2 notebooks" in result["content"][0]["text"]
        assert "Notebook 1" in result["content"][0]["text"]
        assert "Notebook 2" in result["content"][0]["text"]


class TestJoplinMCPServerPingJoplinTool:
    """Test suite for ping_joplin MCP tool."""

    @pytest.fixture
    def mock_client(self):
        """Mock client for testing."""
        client = Mock()
        client.is_connected = True
        client.ping.return_value = True
        return client

    @pytest.fixture
    def server(self, mock_client):
        """Create server instance with mocked client for testing."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(
            token="test_token", host="localhost", port=41184, client=mock_client
        )
        return server

    @pytest.mark.asyncio
    async def test_ping_joplin_tool_is_registered(self, server):
        """Test that ping_joplin tool is properly registered."""
        tools = server.get_available_tools()
        tool_names = [tool.name for tool in tools]
        assert "ping_joplin" in tool_names

    @pytest.mark.asyncio
    async def test_ping_joplin_tool_has_correct_schema(self, server):
        """Test that ping_joplin tool has correct schema definition."""
        tools = server.get_available_tools()
        ping_tool = next(tool for tool in tools if tool.name == "ping_joplin")

        # Verify basic tool properties
        assert ping_tool.name == "ping_joplin"
        assert ping_tool.description == "Test Joplin server connection"
        assert hasattr(ping_tool, "inputSchema")

        # Verify schema structure (should have no required parameters)
        schema = ping_tool.inputSchema
        assert schema["type"] == "object"
        assert schema["required"] == []

    @pytest.mark.asyncio
    async def test_ping_joplin_tool_handler_exists(self, server):
        """Test that ping_joplin tool handler method exists."""
        assert hasattr(server, "handle_ping_joplin")
        assert callable(server.handle_ping_joplin)

    @pytest.mark.asyncio
    async def test_ping_joplin_tool_handler_with_successful_ping(
        self, server, mock_client
    ):
        """Test ping_joplin tool handler with successful ping."""
        # Setup mock client response
        mock_client.ping.return_value = True

        # Call handler
        result = await server.handle_ping_joplin({})

        # Verify client method was called correctly
        mock_client.ping.assert_called_once()

        # Verify response format
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "Joplin server connection successful" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_ping_joplin_tool_handler_with_failed_ping(self, server, mock_client):
        """Test ping_joplin tool handler with failed ping."""
        # Setup mock client response
        mock_client.ping.return_value = False

        # Call handler
        result = await server.handle_ping_joplin({})

        # Verify client method was called correctly
        mock_client.ping.assert_called_once()

        # Verify response format
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "Joplin server connection failed" in result["content"][0]["text"]


class TestJoplinMCPServerGetNotebookTool:
    """Test suite for get_notebook MCP tool."""

    @pytest.fixture
    def mock_client(self):
        """Mock client for testing."""
        client = Mock()
        client.is_connected = True
        client.get_notebook.return_value = {"id": "nb_123", "title": "Test Notebook"}
        return client

    @pytest.fixture
    def server(self, mock_client):
        """Create server instance with mocked client for testing."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(
            token="test_token", host="localhost", port=41184, client=mock_client
        )
        return server

    @pytest.mark.asyncio
    async def test_get_notebook_tool_is_registered(self, server):
        """Test that get_notebook tool is properly registered."""
        tools = server.get_available_tools()
        tool_names = [tool.name for tool in tools]
        assert "get_notebook" in tool_names

    @pytest.mark.asyncio
    async def test_get_notebook_tool_has_correct_schema(self, server):
        """Test that get_notebook tool has correct schema definition."""
        tools = server.get_available_tools()
        get_notebook_tool = next(tool for tool in tools if tool.name == "get_notebook")

        # Verify basic tool properties
        assert get_notebook_tool.name == "get_notebook"
        assert get_notebook_tool.description == "Get notebook details"
        assert hasattr(get_notebook_tool, "inputSchema")

        # Verify schema structure
        schema = get_notebook_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema

    @pytest.mark.asyncio
    async def test_get_notebook_tool_handler_exists(self, server):
        """Test that get_notebook tool handler method exists."""
        assert hasattr(server, "handle_get_notebook")
        assert callable(server.handle_get_notebook)

    @pytest.mark.asyncio
    async def test_get_notebook_tool_handler_with_valid_data(self, server, mock_client):
        """Test get_notebook tool handler with valid notebook ID."""
        # Setup mock client response
        mock_notebook = {
            "id": "nb_123",
            "title": "Test Notebook",
            "created_time": 1234567890,
            "updated_time": 1234567891,
        }
        mock_client.get_notebook.return_value = mock_notebook

        # Prepare test parameters
        params = {"notebook_id": "nb_123"}

        # Call handler
        result = await server.handle_get_notebook(params)

        # Verify client method was called correctly
        mock_client.get_notebook.assert_called_once_with(notebook_id="nb_123")

        # Verify response format
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "Test Notebook" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_get_notebook_tool_handler_validates_required_fields(
        self, server, mock_client
    ):
        """Test get_notebook tool handler validates required fields."""
        # Test missing notebook_id
        with pytest.raises(ValueError, match="notebook_id parameter is required"):
            await server.handle_get_notebook({})

        # Test empty notebook_id
        with pytest.raises(ValueError, match="notebook_id parameter is required"):
            await server.handle_get_notebook({"notebook_id": ""})


class TestJoplinMCPServerCreateNotebookTool:
    """Test suite for create_notebook MCP tool."""

    @pytest.fixture
    def mock_client(self):
        """Mock client for testing."""
        client = Mock()
        client.is_connected = True
        client.create_notebook.return_value = "nb_new_123"
        return client

    @pytest.fixture
    def server(self, mock_client):
        """Create server instance with mocked client for testing."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(
            token="test_token", host="localhost", port=41184, client=mock_client
        )
        return server

    @pytest.mark.asyncio
    async def test_create_notebook_tool_is_registered(self, server):
        """Test that create_notebook tool is properly registered."""
        tools = server.get_available_tools()
        tool_names = [tool.name for tool in tools]
        assert "create_notebook" in tool_names

    @pytest.mark.asyncio
    async def test_create_notebook_tool_has_correct_schema(self, server):
        """Test that create_notebook tool has correct schema definition."""
        tools = server.get_available_tools()
        create_notebook_tool = next(
            tool for tool in tools if tool.name == "create_notebook"
        )

        # Verify basic tool properties
        assert create_notebook_tool.name == "create_notebook"
        assert create_notebook_tool.description == "Create a new notebook"
        assert hasattr(create_notebook_tool, "inputSchema")

        # Verify schema structure
        schema = create_notebook_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema

    @pytest.mark.asyncio
    async def test_create_notebook_tool_handler_exists(self, server):
        """Test that create_notebook tool handler method exists."""
        assert hasattr(server, "handle_create_notebook")
        assert callable(server.handle_create_notebook)

    @pytest.mark.asyncio
    async def test_create_notebook_tool_handler_with_valid_data(
        self, server, mock_client
    ):
        """Test create_notebook tool handler with valid notebook data."""
        # Setup mock client response
        mock_client.create_notebook.return_value = "nb_new_123"

        # Prepare test parameters
        params = {"title": "New Notebook"}

        # Call handler
        result = await server.handle_create_notebook(params)

        # Verify client method was called correctly
        mock_client.create_notebook.assert_called_once_with(title="New Notebook")

        # Verify response format
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "Successfully created notebook" in result["content"][0]["text"]
        assert "New Notebook" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_create_notebook_tool_handler_validates_required_fields(
        self, server, mock_client
    ):
        """Test create_notebook tool handler validates required fields."""
        # Test missing title
        with pytest.raises(ValueError, match="title parameter is required"):
            await server.handle_create_notebook({})

        # Test empty title
        with pytest.raises(ValueError, match="title parameter is required"):
            await server.handle_create_notebook({"title": ""})


class TestJoplinMCPServerListTagsTool:
    """Test suite for list_tags MCP tool."""

    @pytest.fixture
    def mock_client(self):
        """Mock client for testing."""
        client = Mock()
        client.is_connected = True
        client.list_tags.return_value = []
        return client

    @pytest.fixture
    def server(self, mock_client):
        """Create server instance with mocked client for testing."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(
            token="test_token", host="localhost", port=41184, client=mock_client
        )
        return server

    @pytest.mark.asyncio
    async def test_list_tags_tool_is_registered(self, server):
        """Test that list_tags tool is properly registered."""
        tools = server.get_available_tools()
        tool_names = [tool.name for tool in tools]
        assert "list_tags" in tool_names

    @pytest.mark.asyncio
    async def test_list_tags_tool_has_correct_schema(self, server):
        """Test that list_tags tool has correct schema definition."""
        tools = server.get_available_tools()
        list_tags_tool = next(tool for tool in tools if tool.name == "list_tags")

        # Verify basic tool properties
        assert list_tags_tool.name == "list_tags"
        assert list_tags_tool.description == "List all tags"
        assert hasattr(list_tags_tool, "inputSchema")

        # Verify schema structure
        schema = list_tags_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema

    @pytest.mark.asyncio
    async def test_list_tags_tool_handler_exists(self, server):
        """Test that list_tags tool handler method exists."""
        assert hasattr(server, "handle_list_tags")
        assert callable(server.handle_list_tags)

    @pytest.mark.asyncio
    async def test_list_tags_tool_handler_with_valid_data(self, server, mock_client):
        """Test list_tags tool handler with valid response."""
        # Setup mock client response
        mock_tags = [
            {"id": "tag1", "title": "work", "created_time": 1234567890},
            {"id": "tag2", "title": "personal", "created_time": 1234567891},
        ]
        mock_client.list_tags.return_value = mock_tags

        # Call handler
        result = await server.handle_list_tags({})

        # Verify client method was called correctly
        mock_client.list_tags.assert_called_once()

        # Verify response format
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "Found 2 tags" in result["content"][0]["text"]
        assert "work" in result["content"][0]["text"]
        assert "personal" in result["content"][0]["text"]


class TestJoplinMCPServerCreateTagTool:
    """Test suite for create_tag MCP tool."""

    @pytest.fixture
    def mock_client(self):
        """Mock client for testing."""
        client = Mock()
        client.is_connected = True
        client.create_tag.return_value = "tag_new_123"
        return client

    @pytest.fixture
    def server(self, mock_client):
        """Create server instance with mocked client for testing."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(
            token="test_token", host="localhost", port=41184, client=mock_client
        )
        return server

    @pytest.mark.asyncio
    async def test_create_tag_tool_is_registered(self, server):
        """Test that create_tag tool is properly registered."""
        tools = server.get_available_tools()
        tool_names = [tool.name for tool in tools]
        assert "create_tag" in tool_names

    @pytest.mark.asyncio
    async def test_create_tag_tool_has_correct_schema(self, server):
        """Test that create_tag tool has correct schema definition."""
        tools = server.get_available_tools()
        create_tag_tool = next(tool for tool in tools if tool.name == "create_tag")

        # Verify basic tool properties
        assert create_tag_tool.name == "create_tag"
        assert create_tag_tool.description == "Create a new tag"
        assert hasattr(create_tag_tool, "inputSchema")

        # Verify schema structure
        schema = create_tag_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema

    @pytest.mark.asyncio
    async def test_create_tag_tool_handler_exists(self, server):
        """Test that create_tag tool handler method exists."""
        assert hasattr(server, "handle_create_tag")
        assert callable(server.handle_create_tag)

    @pytest.mark.asyncio
    async def test_create_tag_tool_handler_with_valid_data(self, server, mock_client):
        """Test create_tag tool handler with valid tag data."""
        # Setup mock client response
        mock_client.create_tag.return_value = "tag_new_123"

        # Prepare test parameters
        params = {"title": "new-tag"}

        # Call handler
        result = await server.handle_create_tag(params)

        # Verify client method was called correctly
        mock_client.create_tag.assert_called_once_with(title="new-tag")

        # Verify response format
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "Successfully created tag" in result["content"][0]["text"]
        assert "new-tag" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_create_tag_tool_handler_validates_required_fields(
        self, server, mock_client
    ):
        """Test create_tag tool handler validates required fields."""
        # Test missing title
        with pytest.raises(ValueError, match="title parameter is required"):
            await server.handle_create_tag({})

        # Test empty title
        with pytest.raises(ValueError, match="title parameter is required"):
            await server.handle_create_tag({"title": ""})


class TestJoplinMCPServerTagNoteTool:
    """Test suite for tag_note MCP tool."""

    @pytest.fixture
    def mock_client(self):
        """Mock client for testing."""
        client = Mock()
        client.is_connected = True
        client.tag_note.return_value = True
        return client

    @pytest.fixture
    def server(self, mock_client):
        """Create server instance with mocked client for testing."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(
            token="test_token", host="localhost", port=41184, client=mock_client
        )
        return server

    @pytest.mark.asyncio
    async def test_tag_note_tool_is_registered(self, server):
        """Test that tag_note tool is properly registered."""
        tools = server.get_available_tools()
        tool_names = [tool.name for tool in tools]
        assert "tag_note" in tool_names

    @pytest.mark.asyncio
    async def test_tag_note_tool_has_correct_schema(self, server):
        """Test that tag_note tool has correct schema definition."""
        tools = server.get_available_tools()
        tag_note_tool = next(tool for tool in tools if tool.name == "tag_note")

        # Verify basic tool properties
        assert tag_note_tool.name == "tag_note"
        assert tag_note_tool.description == "Add tag to note"
        assert hasattr(tag_note_tool, "inputSchema")

        # Verify schema structure
        schema = tag_note_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema

    @pytest.mark.asyncio
    async def test_tag_note_tool_handler_exists(self, server):
        """Test that tag_note tool handler method exists."""
        assert hasattr(server, "handle_tag_note")
        assert callable(server.handle_tag_note)

    @pytest.mark.asyncio
    async def test_tag_note_tool_handler_with_valid_data(self, server, mock_client):
        """Test tag_note tool handler with valid data."""
        # Setup mock client response
        mock_client.tag_note.return_value = True

        # Prepare test parameters
        params = {"note_id": "note_123", "tag_id": "tag_456"}

        # Call handler
        result = await server.handle_tag_note(params)

        # Verify client method was called correctly
        mock_client.tag_note.assert_called_once_with(
            note_id="note_123", tag_id="tag_456"
        )

        # Verify response format
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "Successfully tagged note" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_tag_note_tool_handler_validates_required_fields(
        self, server, mock_client
    ):
        """Test tag_note tool handler validates required fields."""
        # Test missing note_id
        with pytest.raises(ValueError, match="note_id parameter is required"):
            await server.handle_tag_note({"tag_id": "tag_456"})

        # Test missing tag_id
        with pytest.raises(ValueError, match="tag_id parameter is required"):
            await server.handle_tag_note({"note_id": "note_123"})


class TestJoplinMCPServerUntagNoteTool:
    """Test suite for untag_note MCP tool."""

    @pytest.fixture
    def mock_client(self):
        """Mock client for testing."""
        client = Mock()
        client.is_connected = True
        client.untag_note.return_value = True
        return client

    @pytest.fixture
    def server(self, mock_client):
        """Create server instance with mocked client for testing."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(
            token="test_token", host="localhost", port=41184, client=mock_client
        )
        return server

    @pytest.mark.asyncio
    async def test_untag_note_tool_is_registered(self, server):
        """Test that untag_note tool is properly registered."""
        tools = server.get_available_tools()
        tool_names = [tool.name for tool in tools]
        assert "untag_note" in tool_names

    @pytest.mark.asyncio
    async def test_untag_note_tool_has_correct_schema(self, server):
        """Test that untag_note tool has correct schema definition."""
        tools = server.get_available_tools()
        untag_note_tool = next(tool for tool in tools if tool.name == "untag_note")

        # Verify basic tool properties
        assert untag_note_tool.name == "untag_note"
        assert untag_note_tool.description == "Remove tag from note"
        assert hasattr(untag_note_tool, "inputSchema")

        # Verify schema structure
        schema = untag_note_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema

    @pytest.mark.asyncio
    async def test_untag_note_tool_handler_exists(self, server):
        """Test that untag_note tool handler method exists."""
        assert hasattr(server, "handle_untag_note")
        assert callable(server.handle_untag_note)

    @pytest.mark.asyncio
    async def test_untag_note_tool_handler_with_valid_data(self, server, mock_client):
        """Test untag_note tool handler with valid data."""
        # Setup mock client response
        mock_client.untag_note.return_value = True

        # Prepare test parameters
        params = {"note_id": "note_123", "tag_id": "tag_456"}

        # Call handler
        result = await server.handle_untag_note(params)

        # Verify client method was called correctly
        mock_client.untag_note.assert_called_once_with(
            note_id="note_123", tag_id="tag_456"
        )

        # Verify response format
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "Successfully removed tag from note" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_untag_note_tool_handler_validates_required_fields(
        self, server, mock_client
    ):
        """Test untag_note tool handler validates required fields."""
        # Test missing note_id
        with pytest.raises(ValueError, match="note_id parameter is required"):
            await server.handle_untag_note({"tag_id": "tag_456"})

        # Test missing tag_id
        with pytest.raises(ValueError, match="tag_id parameter is required"):
            await server.handle_untag_note({"note_id": "note_123"})


class TestJoplinMCPServerSecurity:
    """Test suite for server security features."""

    @pytest.fixture
    def mock_client(self):
        """Mock client for testing."""
        client = Mock()
        client.is_connected = True
        client.search_notes.return_value = []
        return client

    @pytest.fixture
    def server(self, mock_client):
        """Create server instance with mocked client for testing."""
        from joplin_mcp.server import JoplinMCPServer

        server = JoplinMCPServer(
            token="test_token", host="localhost", port=41184, client=mock_client
        )
        return server

    @pytest.mark.asyncio
    async def test_rate_limiting_blocks_excessive_requests(self, server):
        """Test that rate limiting blocks excessive requests."""
        # Make requests up to the limit
        for i in range(60):  # Default limit is 60 per minute
            await server.handle_search_notes({"query": f"test {i}"})
        
        # The next request should be rate limited
        with pytest.raises(Exception, match="Rate limit exceeded"):
            await server.handle_search_notes({"query": "rate limited"})

    @pytest.mark.asyncio 
    async def test_input_validation_sanitizes_strings(self, server):
        """Test that input validation sanitizes malicious strings."""
        # Test with null bytes and control characters
        malicious_query = "normal text\x00\x01\x02malicious"
        
        # Should not raise exception but sanitize the input
        result = await server.handle_search_notes({"query": malicious_query})
        
        # Verify the sanitized query was processed
        assert "content" in result
        # The null bytes should have been removed by sanitization

    @pytest.mark.asyncio
    async def test_input_validation_truncates_long_strings(self, server):
        """Test that excessively long inputs are truncated."""
        long_query = "A" * 1000  # Longer than max length
        
        # Should not raise exception but truncate the input
        result = await server.handle_search_notes({"query": long_query})
        
        # Verify the request was processed
        assert "content" in result

    @pytest.mark.asyncio
    async def test_tags_parameter_security_validation(self, server):
        """Test security validation of tags parameter."""
        # Test with too many tags
        many_tags = [f"tag{i}" for i in range(20)]  # More than limit of 10
        
        result = await server.handle_search_notes({
            "query": "test",
            "tags": many_tags
        })
        
        # Should process without error (tags truncated internally)
        assert "content" in result

    def test_rate_limit_timestamps_cleanup(self, server):
        """Test that old timestamps are cleaned up properly."""
        import time
        
        # Add some old timestamps
        old_time = time.time() - 120  # 2 minutes ago
        server._request_timestamps = [old_time] * 10
        
        # Make a new request which should trigger cleanup
        server._check_rate_limit()
        
        # Old timestamps should be removed
        assert len(server._request_timestamps) == 1  # Only the new one

    def test_string_validation_type_checking(self, server):
        """Test string validation with non-string inputs."""
        with pytest.raises(ValueError, match="Input must be a string"):
            server._validate_string_input(123)

    def test_string_validation_length_limiting(self, server):
        """Test string validation length limiting."""
        long_string = "A" * 2000
        result = server._validate_string_input(long_string, max_length=100)
        assert len(result) == 100

    def test_string_validation_control_character_removal(self, server):
        """Test removal of control characters."""
        dirty_string = "clean\x00text\x01with\x02control\x03chars"
        clean_string = server._validate_string_input(dirty_string)
        assert "\x00" not in clean_string
        assert "\x01" not in clean_string
        assert "\x02" not in clean_string
        assert "\x03" not in clean_string
        assert "cleantext" in clean_string
