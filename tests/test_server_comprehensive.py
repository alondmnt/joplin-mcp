"""Comprehensive tests for Joplin MCP server functionality to improve coverage."""

import pytest
from unittest.mock import Mock, patch

from joplin_mcp.server import JoplinMCPServer
from joplin_mcp.config import JoplinMCPConfig
from joplin_mcp.exceptions import JoplinMCPError


class TestJoplinMCPServerComprehensive:
    """Comprehensive tests for server functionality."""

    def test_server_initialization_with_default_config(self):
        """Test server initialization with default config."""
        config = JoplinMCPConfig(token="test-token")
        server = JoplinMCPServer(config=config, skip_ping=True)
        
        assert server.config == config
        assert server.server_name == "joplin-mcp"
        assert server.server_version == "0.1.0"
        assert hasattr(server, '_mcp_server')
        assert hasattr(server, 'client')

    def test_server_get_capabilities(self):
        """Test server capabilities method."""
        config = JoplinMCPConfig(token="test-token")
        server = JoplinMCPServer(config=config, skip_ping=True)
        
        capabilities = server.get_capabilities()
        
        # The capabilities might be a Mock object or dict depending on MCP availability
        assert capabilities is not None
        assert hasattr(capabilities, '__dict__') or isinstance(capabilities, dict)

    def test_server_get_available_tools(self):
        """Test server available tools method."""
        config = JoplinMCPConfig(token="test-token")
        server = JoplinMCPServer(config=config, skip_ping=True)
        
        tools = server.get_available_tools()
        
        assert isinstance(tools, list)
        assert len(tools) > 0
        # Check that basic tools are present - tools are Tool objects, not dicts
        tool_names = [tool.name for tool in tools]
        assert "search_notes" in tool_names
        assert "get_note" in tool_names
        assert "ping_joplin" in tool_names

    def test_server_format_single_search_result(self):
        """Test single search result formatting."""
        config = JoplinMCPConfig(token="test-token")
        server = JoplinMCPServer(config=config, skip_ping=True)
        
        note_data = {
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
        
        formatted = server._format_single_search_result(note_data)
        
        assert isinstance(formatted, str)
        assert "Test Note" in formatted
        assert "Test content" in formatted

    def test_server_format_notebooks_list(self):
        """Test notebooks list formatting."""
        config = JoplinMCPConfig(token="test-token")
        server = JoplinMCPServer(config=config, skip_ping=True)
        
        notebooks_data = [
            {
                "id": "a" * 32,
                "title": "Notebook 1",
                "created_time": 1234567890,
                "updated_time": 1234567891
            },
            {
                "id": "b" * 32,
                "title": "Notebook 2", 
                "created_time": 1234567892,
                "updated_time": 1234567893
            }
        ]
        
        formatted = server._format_notebooks_list(notebooks_data)
        
        assert isinstance(formatted, str)
        assert "Notebook 1" in formatted
        assert "Notebook 2" in formatted
        assert "notebooks found" in formatted or "2 notebooks" in formatted

    def test_server_validate_string_input(self):
        """Test string input validation."""
        config = JoplinMCPConfig(token="test-token")
        server = JoplinMCPServer(config=config, skip_ping=True)
        
        # Test valid string
        result = server._validate_string_input("test string", max_length=100)
        assert result == "test string"
        
        # Test string with length limit
        long_string = "a" * 2000
        result = server._validate_string_input(long_string, max_length=100)
        assert len(result) <= 100
        
        # Test non-string input should raise ValueError
        with pytest.raises(ValueError):
            server._validate_string_input(123, max_length=100)

    def test_server_rate_limit_check(self):
        """Test rate limiting functionality."""
        config = JoplinMCPConfig(token="test-token")
        server = JoplinMCPServer(config=config, skip_ping=True)
        
        # Test that rate limit check doesn't raise exception initially
        server._check_rate_limit()
        
        # Test multiple rapid calls
        for i in range(10):
            server._check_rate_limit()
        
        # Should not raise exception for normal usage
        assert True

    @patch('joplin_mcp.server.JoplinMCPClient')
    def test_server_client_creation(self, mock_client_class):
        """Test client creation with mocked client."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        config = JoplinMCPConfig(token="test-token")
        server = JoplinMCPServer(config=config, skip_ping=True)
        
        # Check that client was created with config
        mock_client_class.assert_called_once_with(config=config)
        assert server.client == mock_client 