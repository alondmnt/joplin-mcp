"""Tests for Joplin MCP Client wrapper."""

import pytest  
from unittest.mock import Mock, patch, MagicMock
from joplin_mcp.client import JoplinMCPClient, JoplinClientError
from joplin_mcp.config import JoplinMCPConfig
from joplin_mcp.models import MCPNote, MCPNotebook, MCPTag, MCPSearchResult


class TestJoplinMCPClientInitialization:
    """Test JoplinMCPClient wrapper initialization."""
    
    def test_client_initializes_with_config_object(self):
        """Test that client can be initialized with a JoplinMCPConfig object."""
        config = JoplinMCPConfig(
            host="localhost",
            port=41184,
            token="test-token",
            timeout=30,
            verify_ssl=True
        )
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            client = JoplinMCPClient(config)
            
            # Should create joppy ClientApi with correct parameters
            mock_client_api.assert_called_once_with(
                token="test-token",
                url="https://localhost:41184"
            )
            
            # Check config attributes individually since Pydantic objects may not compare equal
            assert client.config.host == config.host
            assert client.config.port == config.port
            assert client.config.token == config.token
            assert client.config.timeout == config.timeout
            assert client.config.verify_ssl == config.verify_ssl
            assert client._joppy_client == mock_client_api.return_value
    
    def test_client_initializes_with_config_parameters(self):
        """Test that client can be initialized with individual config parameters."""
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            client = JoplinMCPClient(
                host="example.com",
                port=8080,
                token="my-token-123",
                timeout=60,
                verify_ssl=False
            )
            
            # Should create config object internally
            assert client.config.host == "example.com"
            assert client.config.port == 8080
            assert client.config.token == "my-token-123"
            assert client.config.timeout == 60
            assert client.config.verify_ssl == False
            
            # Should create joppy ClientApi with correct parameters
            mock_client_api.assert_called_once_with(
                token="my-token-123",
                url="http://example.com:8080"
            )
    
    def test_client_initializes_with_mixed_config_and_overrides(self):
        """Test that client can be initialized with config object and parameter overrides."""
        config = JoplinMCPConfig(
            host="localhost",
            port=41184,
            token="config-token",
            timeout=30
        )
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            client = JoplinMCPClient(config, token="override-token", port=9999)
            
            # Should use overrides where provided
            assert client.config.host == "localhost"  # from config
            assert client.config.port == 9999  # overridden
            assert client.config.token == "override-token"  # overridden
            assert client.config.timeout == 30  # from config
            
            mock_client_api.assert_called_once_with(
                token="override-token",
                url="https://localhost:9999"
            )
    
    def test_client_validates_configuration_on_init(self):
        """Test that client validates configuration during initialization."""
        with pytest.raises(JoplinClientError, match="Token is required"):
            JoplinMCPClient(host="localhost", port=41184)  # Missing token
    
    def test_client_handles_invalid_port_gracefully(self):
        """Test that client handles invalid port numbers gracefully."""
        with pytest.raises(JoplinClientError, match="Port must be between 1 and 65535"):
            JoplinMCPClient(host="localhost", port=99999, token="test-token")
    
    def test_client_auto_discovers_config_when_no_params_provided(self):
        """Test that client can auto-discover configuration when no parameters provided."""
        # Create a real config object for auto-discovery
        discovered_config = JoplinMCPConfig(
            host="localhost",
            port=41184,
            token="discovered-token-123",
            timeout=60,
            verify_ssl=True
        )
        
        with patch('joplin_mcp.config.JoplinMCPConfig.load') as mock_load:
            mock_load.return_value = discovered_config
            
            with patch('joppy.client_api.ClientApi') as mock_client_api:
                client = JoplinMCPClient()
                
                # Should call config auto-discovery
                mock_load.assert_called_once()
                assert client.config.host == discovered_config.host
                assert client.config.port == discovered_config.port
                assert client.config.token == discovered_config.token
                
                mock_client_api.assert_called_once_with(
                    token="discovered-token-123",
                    url="https://localhost:41184"
                )
    
    def test_client_exposes_connection_info_property(self):
        """Test that client exposes connection information for debugging."""
        config = JoplinMCPConfig(
            host="test-host",
            port=8080,
            token="test-token",
            verify_ssl=False
        )
        
        with patch('joppy.client_api.ClientApi'):
            client = JoplinMCPClient(config)
            
            info = client.connection_info
            assert info['host'] == "test-host"
            assert info['port'] == 8080
            assert info['base_url'] == "http://test-host:8080"
            assert info['has_token'] == True
            assert info['verify_ssl'] == False
    
    def test_client_provides_is_connected_property(self):
        """Test that client provides a property to check connection status."""
        config = JoplinMCPConfig(host="localhost", port=41184, token="test-token")
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_joppy_client = Mock()
            mock_client_api.return_value = mock_joppy_client
            
            client = JoplinMCPClient(config)
            
            # Mock successful ping
            mock_joppy_client.ping.return_value = True
            assert client.is_connected == True
            
            # Mock failed ping
            mock_joppy_client.ping.side_effect = Exception("Connection failed")
            assert client.is_connected == False
    
    def test_client_provides_ping_method(self):
        """Test that client provides a ping method to test connectivity."""
        config = JoplinMCPConfig(host="localhost", port=41184, token="test-token")
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_joppy_client = Mock()
            mock_client_api.return_value = mock_joppy_client
            
            client = JoplinMCPClient(config)
            
            # Test successful ping
            mock_joppy_client.ping.return_value = True
            result = client.ping()
            assert result == True
            mock_joppy_client.ping.assert_called_once()
    
    def test_client_handles_joppy_import_error(self):
        """Test that client handles missing joppy dependency gracefully."""
        with patch('joppy.client_api.ClientApi', side_effect=ImportError("No module named 'joppy'")):
            with pytest.raises(JoplinClientError, match="joppy library is required"):
                JoplinMCPClient(host="localhost", port=41184, token="test-token")
    
    def test_client_repr_hides_sensitive_information(self):
        """Test that client string representation hides sensitive information."""
        config = JoplinMCPConfig(host="localhost", port=41184, token="secret-token")
        
        with patch('joppy.client_api.ClientApi'):
            client = JoplinMCPClient(config)
            
            repr_str = repr(client)
            assert "secret-token" not in repr_str
            assert "***" in repr_str
            assert "localhost" in repr_str
            assert "41184" in repr_str


class TestJoplinMCPClientErrorHandling:
    """Test JoplinMCPClient error handling and exceptions."""
    
    def test_client_error_inherits_from_exception(self):
        """Test that JoplinClientError is a proper exception class."""
        error = JoplinClientError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"
    
    def test_client_wraps_joppy_exceptions(self):
        """Test that client wraps joppy exceptions in JoplinClientError."""
        config = JoplinMCPConfig(host="localhost", port=41184, token="test-token")
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_joppy_client = Mock()
            mock_client_api.return_value = mock_joppy_client
            
            client = JoplinMCPClient(config)
            
            # Mock joppy exception
            mock_joppy_client.ping.side_effect = Exception("Joppy error")
            
            with pytest.raises(JoplinClientError, match="Joppy error"):
                client.ping()
    
    def test_client_provides_helpful_error_context(self):
        """Test that client provides helpful error context in exceptions."""
        config = JoplinMCPConfig(host="unreachable-host", port=41184, token="test-token")
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_joppy_client = Mock()
            mock_client_api.return_value = mock_joppy_client
            
            client = JoplinMCPClient(config)
            
            # Mock connection error
            mock_joppy_client.ping.side_effect = Exception("Connection refused")
            
            with pytest.raises(JoplinClientError) as exc_info:
                client.ping()
            
            error_msg = str(exc_info.value)
            assert "unreachable-host" in error_msg or "Connection refused" in error_msg


class TestJoplinMCPClientBasicOperations:
    """Test basic operations that should be available on the client."""
    
    def test_client_has_get_server_info_method(self):
        """Test that client provides server information method."""
        config = JoplinMCPConfig(host="localhost", port=41184, token="test-token")
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_joppy_client = Mock()
            mock_client_api.return_value = mock_joppy_client
            
            client = JoplinMCPClient(config)
            
            # Mock server info response
            mock_joppy_client.ping.return_value = True
            
            info = client.get_server_info()
            
            # Should return structured information
            assert isinstance(info, dict)
            assert 'connected' in info
            assert 'base_url' in info
            assert 'host' in info
            assert 'port' in info
    
    def test_client_has_close_method(self):
        """Test that client provides a method to close connections."""
        config = JoplinMCPConfig(host="localhost", port=41184, token="test-token")
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_joppy_client = Mock()
            mock_client_api.return_value = mock_joppy_client
            
            client = JoplinMCPClient(config)
            
            # Should have close method
            client.close()
            
            # Should be able to call close multiple times safely
            client.close()
    
    def test_client_supports_context_manager(self):
        """Test that client can be used as a context manager."""
        config = JoplinMCPConfig(host="localhost", port=41184, token="test-token")
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_joppy_client = Mock()
            mock_client_api.return_value = mock_joppy_client
            
            # Should work as context manager
            with JoplinMCPClient(config) as client:
                assert isinstance(client, JoplinMCPClient)
                # Check config attributes individually since Pydantic objects may not compare equal
                assert client.config.host == config.host
                assert client.config.port == config.port
                assert client.config.token == config.token
                assert client.config.timeout == config.timeout
                assert client.config.verify_ssl == config.verify_ssl
            
            # Close should be called automatically
            # (We can't easily test this without more complex mocking)


class TestJoplinMCPClientDataTransformations:
    """Test MCP-specific data transformations (joppy models → MCP responses)."""
    
    def test_client_transforms_joppy_note_to_mcp_note(self):
        """Test that client can transform joppy note objects to MCPNote objects."""
        config = JoplinMCPConfig(host="localhost", port=41184, token="test-token")
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_joppy_client = Mock()
            mock_client_api.return_value = mock_joppy_client
            
            client = JoplinMCPClient(config)
            
            # Mock joppy note object (based on joppy documentation)
            mock_joppy_note = Mock()
            mock_joppy_note.id = "abcd1234567890abcd1234567890abcd"
            mock_joppy_note.title = "Test Note"
            mock_joppy_note.body = "This is a test note"
            mock_joppy_note.created_time = 1640995200000  # 2022-01-01 00:00:00 UTC
            mock_joppy_note.updated_time = 1640995260000  # 2022-01-01 00:01:00 UTC
            mock_joppy_note.parent_id = "efgh5678901234efgh5678901234efgh"
            mock_joppy_note.is_todo = 0
            mock_joppy_note.todo_completed = 0
            mock_joppy_note.is_conflict = 0
            mock_joppy_note.latitude = 0.0
            mock_joppy_note.longitude = 0.0
            mock_joppy_note.altitude = 0.0
            mock_joppy_note.markup_language = 1
            
            # Should have method to transform joppy note to MCP note
            mcp_note = client.transform_note_to_mcp(mock_joppy_note)
            
            # Should return MCPNote object
            assert isinstance(mcp_note, MCPNote)
            assert mcp_note.id == "abcd1234567890abcd1234567890abcd"
            assert mcp_note.title == "Test Note"
            assert mcp_note.body == "This is a test note"
            assert mcp_note.created_time == 1640995200000
            assert mcp_note.updated_time == 1640995260000
            assert mcp_note.parent_id == "efgh5678901234efgh5678901234efgh"
            assert mcp_note.is_todo == False
            assert mcp_note.todo_completed == False
            assert mcp_note.is_conflict == False
    
    def test_client_transforms_joppy_notebook_to_mcp_notebook(self):
        """Test that client can transform joppy notebook objects to MCPNotebook objects."""
        config = JoplinMCPConfig(host="localhost", port=41184, token="test-token")
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_joppy_client = Mock()
            mock_client_api.return_value = mock_joppy_client
            
            client = JoplinMCPClient(config)
            
            # Mock joppy notebook object
            mock_joppy_notebook = Mock()
            mock_joppy_notebook.id = "1234567890abcdef1234567890abcdef"
            mock_joppy_notebook.title = "Test Notebook"
            mock_joppy_notebook.created_time = 1640995200000
            mock_joppy_notebook.updated_time = 1640995260000
            mock_joppy_notebook.parent_id = None
            
            # Should have method to transform joppy notebook to MCP notebook
            mcp_notebook = client.transform_notebook_to_mcp(mock_joppy_notebook)
            
            # Should return MCPNotebook object
            assert isinstance(mcp_notebook, MCPNotebook)
            assert mcp_notebook.id == "1234567890abcdef1234567890abcdef"
            assert mcp_notebook.title == "Test Notebook"
            assert mcp_notebook.created_time == 1640995200000
            assert mcp_notebook.updated_time == 1640995260000
            assert mcp_notebook.parent_id is None
    
    def test_client_transforms_joppy_tag_to_mcp_tag(self):
        """Test that client can transform joppy tag objects to MCPTag objects."""
        config = JoplinMCPConfig(host="localhost", port=41184, token="test-token")
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_joppy_client = Mock()
            mock_client_api.return_value = mock_joppy_client
            
            client = JoplinMCPClient(config)
            
            # Mock joppy tag object
            mock_joppy_tag = Mock()
            mock_joppy_tag.id = "fedcba0987654321fedcba0987654321"
            mock_joppy_tag.title = "important"
            mock_joppy_tag.created_time = 1640995200000
            mock_joppy_tag.updated_time = 1640995260000
            
            # Should have method to transform joppy tag to MCP tag
            mcp_tag = client.transform_tag_to_mcp(mock_joppy_tag)
            
            # Should return MCPTag object
            assert isinstance(mcp_tag, MCPTag)
            assert mcp_tag.id == "fedcba0987654321fedcba0987654321"
            assert mcp_tag.title == "important"
            assert mcp_tag.created_time == 1640995200000
            assert mcp_tag.updated_time == 1640995260000
    
    def test_client_transforms_joppy_search_results_to_mcp_search_result(self):
        """Test that client can transform joppy search results to MCPSearchResult objects."""
        config = JoplinMCPConfig(host="localhost", port=41184, token="test-token")
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_joppy_client = Mock()
            mock_client_api.return_value = mock_joppy_client
            
            client = JoplinMCPClient(config)
            
            # Mock joppy search results (list of notes)
            mock_joppy_notes = []
            for i in range(3):
                note = Mock()
                note.id = f"{i:032x}"  # 32 hex characters
                note.title = f"Search Result {i}"
                note.body = f"Content of note {i}"
                note.created_time = 1640995200000 + i * 1000
                note.updated_time = 1640995260000 + i * 1000
                note.parent_id = "1234567890abcdef1234567890abcdef"
                mock_joppy_notes.append(note)
            
            # Should have method to transform search results to MCP search result
            mcp_search_result = client.transform_search_results_to_mcp(
                mock_joppy_notes, 
                has_more=False, 
                total_count=3
            )
            
            # Should return MCPSearchResult object
            assert isinstance(mcp_search_result, MCPSearchResult)
            assert len(mcp_search_result.items) == 3
            assert mcp_search_result.has_more == False
            assert mcp_search_result.total_count == 3
            
            # Check first item
            first_item = mcp_search_result.items[0]
            assert first_item['id'] == "00000000000000000000000000000000"
            assert first_item['title'] == "Search Result 0"
    
    def test_client_handles_missing_joppy_attributes_gracefully(self):
        """Test that client handles missing attributes in joppy objects gracefully."""
        config = JoplinMCPConfig(host="localhost", port=41184, token="test-token")
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_joppy_client = Mock()
            mock_client_api.return_value = mock_joppy_client
            
            client = JoplinMCPClient(config)
            
            # Mock joppy note with minimal attributes
            mock_joppy_note = Mock()
            mock_joppy_note.id = "abcdef1234567890abcdef1234567890"
            mock_joppy_note.title = "Minimal Note"
            mock_joppy_note.body = "Basic content"
            mock_joppy_note.created_time = 1640995200000
            mock_joppy_note.updated_time = 1640995260000
            # Missing optional attributes - Mock will return Mock objects for missing attrs
            
            # Should handle missing attributes with defaults
            mcp_note = client.transform_note_to_mcp(mock_joppy_note)
            
            assert isinstance(mcp_note, MCPNote)
            assert mcp_note.id == "abcdef1234567890abcdef1234567890"
            assert mcp_note.title == "Minimal Note"
            assert mcp_note.parent_id is None  # Should default to None
            assert mcp_note.is_todo == False  # Should default to False
            assert mcp_note.latitude == 0.0  # Should default to 0.0
    
    def test_client_transforms_batch_operations_efficiently(self):
        """Test that client can efficiently transform multiple objects in batch."""
        config = JoplinMCPConfig(host="localhost", port=41184, token="test-token")
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_joppy_client = Mock()
            mock_client_api.return_value = mock_joppy_client
            
            client = JoplinMCPClient(config)
            
            # Mock multiple joppy notes
            mock_joppy_notes = []
            for i in range(10):
                note = Mock()
                note.id = f"{i:032x}"  # 32 hex characters
                note.title = f"Batch Note {i}"
                note.body = f"Content {i}"
                note.created_time = 1640995200000 + i * 1000
                note.updated_time = 1640995260000 + i * 1000
                # Set explicit defaults for optional attributes
                note.parent_id = None
                note.is_todo = 0
                note.todo_completed = 0
                note.is_conflict = 0
                note.latitude = 0.0
                note.longitude = 0.0
                note.altitude = 0.0
                note.markup_language = 1
                mock_joppy_notes.append(note)
            
            # Should have method to transform multiple notes efficiently
            mcp_notes = client.transform_notes_to_mcp_batch(mock_joppy_notes)
            
            # Should return list of MCPNote objects
            assert isinstance(mcp_notes, list)
            assert len(mcp_notes) == 10
            assert all(isinstance(note, MCPNote) for note in mcp_notes)
            
            # Check first and last notes
            assert mcp_notes[0].title == "Batch Note 0"
            assert mcp_notes[9].title == "Batch Note 9"
    
    def test_client_preserves_joppy_metadata_in_transformations(self):
        """Test that client preserves important metadata during transformations."""
        config = JoplinMCPConfig(host="localhost", port=41184, token="test-token")
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_joppy_client = Mock()
            mock_client_api.return_value = mock_joppy_client
            
            client = JoplinMCPClient(config)
            
            # Mock joppy note with rich metadata
            mock_joppy_note = Mock()
            mock_joppy_note.id = "fedcba0987654321fedcba0987654321"
            mock_joppy_note.title = "Rich Metadata Note"
            mock_joppy_note.body = "Content with metadata"
            mock_joppy_note.created_time = 1640995200000
            mock_joppy_note.updated_time = 1640995260000
            mock_joppy_note.parent_id = "abcdef1234567890abcdef1234567890"
            mock_joppy_note.is_todo = 1
            mock_joppy_note.todo_completed = 1640995300000  # Completed timestamp
            mock_joppy_note.latitude = 37.7749
            mock_joppy_note.longitude = -122.4194
            mock_joppy_note.altitude = 100.5
            mock_joppy_note.markup_language = 1
            
            # Should preserve all metadata in transformation
            mcp_note = client.transform_note_to_mcp(mock_joppy_note)
            
            assert mcp_note.parent_id == "abcdef1234567890abcdef1234567890"
            assert mcp_note.is_todo == True
            assert mcp_note.todo_completed == True
            assert mcp_note.latitude == 37.7749
            assert mcp_note.longitude == -122.4194
            assert mcp_note.altitude == 100.5
            assert mcp_note.markup_language == 1


class TestJoplinMCPClientEnhancedSearch:
    """Test enhanced search functionality with MCP-friendly responses."""
    
    @pytest.fixture
    def client(self):
        """Create a test client with mocked joppy dependency."""
        config = JoplinMCPConfig(
            host="localhost",
            port=41184,
            token="test-token",
            timeout=30,
            verify_ssl=True
        )
        
        # Create a mock joppy client that persists
        mock_joppy_client = Mock()
        
        # Patch the joppy.client_api.ClientApi to return our mock
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_client_api.return_value = mock_joppy_client
            client = JoplinMCPClient(config)
            
            # Manually set the _joppy_client to our mock to ensure it persists
            client._joppy_client = mock_joppy_client
            
            return client
    
    @pytest.fixture
    def mock_joppy_notes(self):
        """Create mock joppy notes for testing."""
        mock1 = Mock()
        mock1.id = "1234567890abcdef1234567890abcdef"
        mock1.title = "Test Note 1"
        mock1.body = "This is test content"
        mock1.created_time = 1640995200000
        mock1.updated_time = 1641081600000
        mock1.parent_id = "abcdef1234567890abcdef1234567890"
        mock1.is_todo = False
        mock1.todo_completed = False
        mock1.is_conflict = False
        mock1.latitude = 0.0
        mock1.longitude = 0.0
        mock1.altitude = 0.0
        mock1.markup_language = 1
        
        mock2 = Mock()
        mock2.id = "abcdef1234567890abcdef1234567890"
        mock2.title = "Test Note 2"
        mock2.body = "This is more test content"
        mock2.created_time = 1640995300000
        mock2.updated_time = 1641081700000
        mock2.parent_id = "abcdef1234567890abcdef1234567890"
        mock2.is_todo = False
        mock2.todo_completed = False
        mock2.is_conflict = False
        mock2.latitude = 0.0
        mock2.longitude = 0.0
        mock2.altitude = 0.0
        mock2.markup_language = 1
        
        return [mock1, mock2]

    def test_enhanced_search_with_query_string(self, client, mock_joppy_notes):
        """Test enhanced search functionality with query string and MCP formatting."""
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes):
            result = client.enhanced_search(
                query="meeting",
                search_fields=["title", "body"],
                limit=10,
                offset=0,
                sort_by="updated_time",
                sort_order="desc"
            )
            
            assert isinstance(result, MCPSearchResult)
            assert len(result.items) <= 10
            assert hasattr(result, 'search_metadata')
            assert result.search_metadata['query'] == "meeting"

    def test_enhanced_search_with_filters(self, client, mock_joppy_notes):
        """Test enhanced search with advanced filtering options."""
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes):
            result = client.enhanced_search(
                query="project",
                filters={
                    "notebook_id": "folder1234567890abcdef12345678",
                    "is_todo": True,
                    "date_range": {
                        "start": 1640995200000,
                        "end": 1641254400000
                    }
                },
                limit=20,
                include_body=False
            )
            
            assert isinstance(result, MCPSearchResult)
            # Check that excerpts are included instead of body
            if result.items:
                assert 'excerpt' in result.items[0] or 'body' not in result.items[0]

    def test_enhanced_search_with_pagination(self, client, mock_joppy_notes):
        """Test enhanced search with pagination support."""
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes):
            result = client.enhanced_search(
                query="test",
                limit=5,
                offset=10,
                return_pagination_info=True
            )
            
            assert isinstance(result, MCPSearchResult)
            assert hasattr(result, 'pagination')
            assert result.pagination['limit'] == 5
            assert result.pagination['offset'] == 10

    def test_enhanced_search_with_highlighting(self, client, mock_joppy_notes):
        """Test enhanced search with query term highlighting in results."""
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes):
            result = client.enhanced_search(
                query="meeting",
                highlight_matches=True,
                highlight_tags=("<mark>", "</mark>")
            )
            
            assert isinstance(result, MCPSearchResult)
            # Check for highlighted fields
            if result.items:
                highlighted_fields = [k for k in result.items[0].keys() if k.endswith('_highlighted')]
                assert len(highlighted_fields) > 0

    def test_enhanced_search_with_faceted_results(self, client, mock_joppy_notes):
        """Test enhanced search with faceted results for better organization."""
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes):
            result = client.enhanced_search(
                query="project",
                include_facets=True,
                facet_fields=["notebook", "is_todo"]
            )
            
            assert isinstance(result, MCPSearchResult)
            assert hasattr(result, 'facets')
            assert 'notebook' in result.facets or 'is_todo' in result.facets

    def test_enhanced_search_with_fuzzy_matching(self, client, mock_joppy_notes):
        """Test enhanced search with fuzzy/approximate matching."""
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes):
            result = client.enhanced_search(
                query="meetng",  # Intentionally misspelled
                fuzzy_matching=True,
                fuzzy_threshold=0.8
            )
            
            assert isinstance(result, MCPSearchResult)

    def test_enhanced_search_with_related_content(self, client, mock_joppy_notes):
        """Test enhanced search that includes related content suggestions."""
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes):
            result = client.enhanced_search(
                query="meeting",
                include_related=True,
                related_limit=3
            )
            
            assert isinstance(result, MCPSearchResult)
            assert hasattr(result, 'suggestions')
            assert len(result.suggestions) <= 3

    def test_enhanced_search_returns_mcp_optimized_response(self, client, mock_joppy_notes):
        """Test that enhanced search returns MCP-optimized response structure."""
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes):
            result = client.enhanced_search(query="test")
            
            # Expected MCP-optimized structure
            assert hasattr(result, 'items')
            assert hasattr(result, 'search_metadata')
            assert isinstance(result, MCPSearchResult)

    def test_enhanced_search_with_content_scoring(self, client, mock_joppy_notes):
        """Test enhanced search with relevance scoring for results."""
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes):
            result = client.enhanced_search(
                query="important meeting",
                include_scores=True,
                boost_fields={"title": 2.0, "body": 1.0}
            )
            
            assert isinstance(result, MCPSearchResult)
            # Check for relevance scores in items
            if result.items:
                assert 'relevance_score' in result.items[0]

    def test_enhanced_search_with_boolean_operators(self, client, mock_joppy_notes):
        """Test enhanced search with boolean query operators (AND, OR, NOT)."""
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes):
            result = client.enhanced_search(
                query="(meeting AND notes) OR (project AND planning)",
                enable_boolean_operators=True
            )
            
            assert isinstance(result, MCPSearchResult)

    def test_enhanced_search_with_field_specific_queries(self, client, mock_joppy_notes):
        """Test enhanced search with field-specific query syntax."""
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes):
            result = client.enhanced_search(
                query="title:meeting body:project",
                enable_field_queries=True
            )
            
            assert isinstance(result, MCPSearchResult)

    def test_enhanced_search_with_date_range_queries(self, client, mock_joppy_notes):
        """Test enhanced search with date range query capabilities."""
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes):
            result = client.enhanced_search(
                query="created:[2022-01-01 TO 2022-12-31]",
                enable_date_queries=True
            )
            
            assert isinstance(result, MCPSearchResult)

    def test_enhanced_search_with_aggregations(self, client, mock_joppy_notes):
        """Test enhanced search with aggregation capabilities."""
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes):
            result = client.enhanced_search(
                query="meeting",
                aggregations={
                    "notes_per_notebook": {"field": "parent_id", "type": "terms"},
                    "notes_per_month": {"field": "created_time", "type": "date_histogram", "interval": "month"}
                }
            )
            
            assert isinstance(result, MCPSearchResult)

    def test_enhanced_search_with_autocomplete_suggestions(self, client, mock_joppy_notes):
        """Test enhanced search with autocomplete/suggestion functionality."""
        suggestions = client.get_search_suggestions(
            partial_query="meet",
            max_suggestions=5,
            include_recent_searches=True
        )
        
        assert isinstance(suggestions, list)
        assert len(suggestions) <= 5

    def test_enhanced_search_with_saved_searches(self, client, mock_joppy_notes):
        """Test enhanced search with saved search functionality."""
        # Save a search
        search_id = client.save_search(
            name="My Meeting Search",
            query="meeting AND project",
            filters={"is_todo": True}
        )
        
        assert isinstance(search_id, str)
        assert len(search_id) > 0
        
        # Get saved searches
        saved_searches = client.get_saved_searches()
        assert isinstance(saved_searches, list)
        # Should find our saved search
        search_names = [s['name'] for s in saved_searches]
        assert "My Meeting Search" in search_names

    def test_enhanced_search_with_export_capabilities(self, client, mock_joppy_notes):
        """Test enhanced search with export functionality."""
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes):
            result = client.enhanced_search(query="meeting")
            
            # Test JSON export
            json_export = client.export_search_results(
                result,
                format="json",
                include_metadata=True
            )
            
            assert isinstance(json_export, str)
            assert len(json_export) > 0

    def test_enhanced_search_with_streaming(self, client, mock_joppy_notes):
        """Test enhanced search with streaming capability for large results."""
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes):
            stream = client.enhanced_search(
                query="test",
                stream_results=True,
                batch_size=1
            )
            
            # Should return a generator
            batch_count = 0
            for batch in stream:
                assert isinstance(batch, MCPSearchResult)
                batch_count += 1
                if batch_count >= 2:  # Limit to avoid infinite loops
                    break

    def test_enhanced_search_cache_management(self, client, mock_joppy_notes):
        """Test enhanced search cache management functionality."""
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes):
            # Test cache stats
            stats_before = client.get_search_cache_stats()
            assert isinstance(stats_before, dict)
            
            # Perform search with caching
            result = client.enhanced_search(
                query="cached search",
                enable_cache=True,
                cache_ttl=60
            )
            
            # Check cache stats after
            stats_after = client.get_search_cache_stats()
            assert isinstance(stats_after, dict)
            
            # Clear cache
            client.clear_search_cache()
            stats_cleared = client.get_search_cache_stats()
            assert stats_cleared['total_entries'] == 0

    def test_enhanced_search_error_handling(self, client):
        """Test enhanced search error handling with invalid inputs."""
        # Empty query should raise error
        with pytest.raises(JoplinClientError, match="Search query cannot be empty"):
            client.enhanced_search(query="")
        
        # Negative limit should raise error  
        with pytest.raises(JoplinClientError, match="Limit must be non-negative"):
            client.enhanced_search(query="test", limit=-1)
        
        # Invalid sort field should raise error
        with pytest.raises(JoplinClientError, match="Invalid sort field"):
            client.enhanced_search(query="test", sort_by="invalid_field")

    def test_enhanced_search_performance_with_large_results(self, client, mock_joppy_notes):
        """Test enhanced search performance with large result sets."""
        # Create a large dataset
        large_results = mock_joppy_notes * 1000  # 2000 mock notes

        with patch.object(client, '_execute_joppy_search', return_value=large_results):
            # Test with streaming
            import time
            start_time = time.time()

            stream = client.enhanced_search(
                query="test",
                stream_results=True,
                batch_size=100
            )

            # Process all batches
            total_items = 0
            for batch in stream:
                total_items += len(batch.items)
                if total_items >= 200:  # Process only first 200 items to avoid long test
                    break

            end_time = time.time()
            
            # Performance should be reasonable
            assert (end_time - start_time) < 10  # Should complete within 10 seconds
            assert total_items >= 100  # Should have processed some items

    def test_enhanced_search_with_caching(self, client, mock_joppy_notes):
        """Test enhanced search caching functionality."""
        # First search
        with patch.object(client, '_execute_joppy_search', return_value=mock_joppy_notes) as mock_search:
            result1 = client.enhanced_search(
                query="test",
                enable_cache=True,
                cache_ttl=60
            )
            
            # Second identical search should use cache
            result2 = client.enhanced_search(
                query="test",
                enable_cache=True,
                cache_ttl=60
            )
            
            # Should have called _execute_joppy_search only once (for the first search)
            assert mock_search.call_count == 1
            
            # Results should be equivalent
            assert isinstance(result1, MCPSearchResult)
            assert isinstance(result2, MCPSearchResult)


class TestJoplinMCPClientNoteOperations:
    """Test note CRUD operations with MCP validation and error handling."""
    
    @pytest.fixture
    def client(self):
        """Create a test client with mocked joppy dependency."""
        config = JoplinMCPConfig(
            host="localhost",
            port=41184,
            token="test-token",
            timeout=30,
            verify_ssl=True
        )
        
        # Create a mock joppy client that persists
        mock_joppy_client = Mock()
        
        # Patch the joppy.client_api.ClientApi to return our mock
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_client_api.return_value = mock_joppy_client
            client = JoplinMCPClient(config)
            
            # Manually set the _joppy_client to our mock to ensure it persists
            client._joppy_client = mock_joppy_client
            
            return client

    @pytest.fixture
    def sample_note_data(self):
        """Sample note data for testing."""
        return {
            "id": "abcdef1234567890abcdef1234567890",
            "title": "Test Note",
            "body": "This is a test note content.",
            "created_time": 1640995200000,
            "updated_time": 1641081600000,
            "parent_id": "notebook1234567890abcdef12345678",
            "is_todo": False,
            "todo_completed": False,
            "is_conflict": False,
            "latitude": 0.0,
            "longitude": 0.0,
            "altitude": 0.0,
            "markup_language": 1
        }

    def test_get_note_with_valid_id(self, client, sample_note_data):
        """Test retrieving a note by ID with MCP formatting."""
        note_id = sample_note_data["id"]
        
        # Mock joppy response
        mock_joppy_note = Mock()
        for key, value in sample_note_data.items():
            setattr(mock_joppy_note, key, value)
        
        with patch.object(client.api, 'get_note', return_value=mock_joppy_note):
            result = client.get_note(note_id)
            
            # Should return MCPNote object
            assert isinstance(result, MCPNote)
            assert result.id == note_id
            assert result.title == sample_note_data["title"]
            assert result.body == sample_note_data["body"]

    def test_get_note_with_invalid_id(self, client):
        """Test error handling when retrieving note with invalid ID."""
        invalid_id = "invalid-note-id"
        
        with patch.object(client.api, 'get_note', side_effect=Exception("Note not found")):
            with pytest.raises(JoplinClientError, match="Failed to get note"):
                client.get_note(invalid_id)

    def test_get_note_with_missing_id(self, client):
        """Test error handling when note ID is missing."""
        with pytest.raises(JoplinClientError, match="Note ID is required"):
            client.get_note("")
        
        with pytest.raises(JoplinClientError, match="Note ID is required"):
            client.get_note(None)

    def test_create_note_with_valid_data(self, client, sample_note_data):
        """Test creating a note with valid data."""
        create_data = {
            "title": sample_note_data["title"],
            "body": sample_note_data["body"],
            "parent_id": sample_note_data["parent_id"]
        }
        
        # Mock the joppy client method
        with patch.object(client._joppy_client, 'add_note', return_value="note123456789012345678901234567890") as mock_add_note:
            result = client.create_note(**create_data)
            
            assert result == "note123456789012345678901234567890"
            mock_add_note.assert_called_once()

    def test_create_note_with_minimal_data(self, client):
        """Test creating a note with minimal required data."""
        minimal_data = {
            "title": "Minimal Note",
            "parent_id": "1234567890abcdef1234567890abcdef"  # Valid hex ID
        }
        
        # Mock the joppy client method
        with patch.object(client._joppy_client, 'add_note', return_value="note123456789012345678901234567890") as mock_add_note:
            result = client.create_note(**minimal_data)
            
            assert result == "note123456789012345678901234567890"
            mock_add_note.assert_called_once()

    def test_create_note_with_missing_required_fields(self, client):
        """Test creating a note without required fields raises error."""
        with pytest.raises(TypeError):
            # This should fail because title is required
            client.create_note(body="Content", parent_id="1234567890abcdef1234567890abcdef")

    def test_create_note_with_todo_flags(self, client):
        """Test creating a note with todo flags."""
        todo_data = {
            "title": "Todo Note",
            "parent_id": "1234567890abcdef1234567890abcdef",  # Valid hex ID
            "is_todo": True,
            "todo_completed": False
        }
        
        # Mock the joppy client method
        with patch.object(client._joppy_client, 'add_note', return_value="note123456789012345678901234567890") as mock_add_note:
            result = client.create_note(**todo_data)
            
            assert result == "note123456789012345678901234567890"
            mock_add_note.assert_called_once()

    def test_update_note_with_valid_data(self, client, sample_note_data):
        """Test updating a note with valid data and MCP validation."""
        note_id = sample_note_data["id"]
        update_data = {
            "title": "Updated Title",
            "body": "Updated content",
            "is_todo": True
        }
        
        with patch.object(client.api, 'modify_note', return_value=None):
            result = client.update_note(note_id, **update_data)
            
            # Should return success indicator
            assert result == True
            
            # Should have called joppy with correct parameters
            client.api.modify_note.assert_called_once()
            call_args = client.api.modify_note.call_args
            assert call_args[0][0] == note_id  # First positional arg is note_id
            assert call_args[1]["title"] == update_data["title"]
            assert call_args[1]["body"] == update_data["body"]

    def test_update_note_with_invalid_id(self, client):
        """Test error handling when updating note with invalid ID."""
        invalid_id = "invalid-note-id"
        
        with patch.object(client.api, 'modify_note', side_effect=Exception("Note not found")):
            with pytest.raises(JoplinClientError, match="Failed to update note"):
                client.update_note(invalid_id, title="New Title")

    def test_update_note_with_empty_data(self, client):
        """Test error handling when updating note with no data."""
        note_id = "abcdef1234567890abcdef1234567890"
        
        with pytest.raises(JoplinClientError, match="At least one field must be provided for update"):
            client.update_note(note_id)

    def test_update_note_partial_update(self, client):
        """Test partial update of note fields."""
        note_id = "abcdef1234567890abcdef1234567890"
        
        with patch.object(client.api, 'modify_note', return_value=None):
            # Update only title
            result = client.update_note(note_id, title="New Title Only")
            assert result == True
            
            # Update only body
            result = client.update_note(note_id, body="New content only")
            assert result == True
            
            # Update todo status
            result = client.update_note(note_id, todo_completed=True)
            assert result == True

    def test_delete_note_with_valid_id(self, client):
        """Test deleting a note with valid ID."""
        note_id = "abcdef1234567890abcdef1234567890"
        
        with patch.object(client.api, 'delete_note', return_value=None):
            result = client.delete_note(note_id)
            
            # Should return success indicator
            assert result == True
            
            # Should have called joppy with correct parameter
            client.api.delete_note.assert_called_once_with(note_id)

    def test_delete_note_with_invalid_id(self, client):
        """Test error handling when deleting note with invalid ID."""
        invalid_id = "invalid-note-id"
        
        with patch.object(client.api, 'delete_note', side_effect=Exception("Note not found")):
            with pytest.raises(JoplinClientError, match="Failed to delete note"):
                client.delete_note(invalid_id)

    def test_delete_note_with_missing_id(self, client):
        """Test error handling when note ID is missing for deletion."""
        with pytest.raises(JoplinClientError, match="Note ID is required"):
            client.delete_note("")
        
        with pytest.raises(JoplinClientError, match="Note ID is required"):
            client.delete_note(None)

    def test_note_operations_with_connection_failure(self, client):
        """Test note operations with connection failure scenarios."""
        note_id = "note1234567890abcdef12345678901234"
        
        # Mock connection failure
        with patch.object(client._joppy_client, 'get_note', side_effect=Exception("Connection failed")):
            with pytest.raises(JoplinClientError, match="Failed to get note"):
                client.get_note(note_id)
        
        # Mock connection failure during create
        with patch.object(client._joppy_client, 'add_note', side_effect=Exception("Connection failed")):
            with pytest.raises(JoplinClientError, match="Failed to create note"):
                client.create_note(title="Test", parent_id="notebook12345678901234567890123456")

    def test_bulk_note_operations(self, client):
        """Test bulk operations for multiple notes."""
        note_ids = [
            "abcdef1234567890abcdef1234567890",  # Valid 32-char hex IDs
            "bcdef1234567890abcdef12345678901",
            "cdef1234567890abcdef123456789012"
        ]
        
        # Mock successful retrieval for all notes
        mock_notes = []
        for i, note_id in enumerate(note_ids):
            mock_note = Mock()
            mock_note.id = note_id
            mock_note.title = f"Test Note {i+1}"
            mock_note.body = f"Test content {i+1}"
            mock_note.created_time = 1640995200000 + i * 1000
            mock_note.updated_time = 1641081600000 + i * 1000
            mock_note.parent_id = f"notebook1234567890abcdef1234567{i+1}"
            mock_note.is_todo = False
            mock_note.todo_completed = False
            mock_note.is_conflict = False
            mock_note.latitude = 0.0
            mock_note.longitude = 0.0
            mock_note.altitude = 0.0
            mock_note.markup_language = 1
            mock_note.tags = []
            mock_notes.append(mock_note)
        
        # Mock the joppy client to return the notes
        with patch.object(client._joppy_client, 'get_note', side_effect=mock_notes):
            with patch.object(client, 'transform_note_to_mcp', side_effect=lambda note: MCPNote(
                id=note.id,
                title=note.title,
                body=note.body,
                created_time=note.created_time,
                updated_time=note.updated_time,
                parent_id=note.parent_id,
                is_todo=note.is_todo,
                todo_completed=note.todo_completed,
                is_conflict=note.is_conflict,
                latitude=note.latitude,
                longitude=note.longitude,
                altitude=note.altitude,
                markup_language=note.markup_language,
                tags=note.tags
            )):
                results = client.get_notes_bulk(note_ids)
                
        assert len(results) == 3
        assert all(isinstance(note, MCPNote) for note in results)
        assert results[0].title == "Test Note 1"
        assert results[1].title == "Test Note 2"
        assert results[2].title == "Test Note 3"

    def test_note_validation_with_mcp_constraints(self, client):
        """Test MCP-specific validation constraints for note operations."""
        # Test title length validation
        long_title = "x" * 1000  # Very long title
        with pytest.raises(JoplinClientError, match="Title too long"):
            client.create_note(title=long_title, parent_id="notebook123")
        
        # Test body size validation for large content
        large_body = "x" * (10 * 1024 * 1024)  # 10MB body
        with pytest.raises(JoplinClientError, match="Note body too large"):
            client.create_note(title="Test", body=large_body, parent_id="notebook123")
        
        # Test invalid characters in title
        invalid_title = "Note\x00with\x01invalid\x02chars"
        with pytest.raises(JoplinClientError, match="Title contains invalid characters"):
            client.create_note(title=invalid_title, parent_id="notebook123")

    def test_note_operations_return_mcp_formatted_data(self, client):
        """Test that note operations return properly formatted MCP data."""
        note_id = "abcdef1234567890abcdef1234567890"  # Valid 32-char hex ID
        mock_note = Mock()
        mock_note.id = note_id
        mock_note.title = "Test Note"
        mock_note.body = "This is a test note content."
        mock_note.created_time = 1640995200000
        mock_note.updated_time = 1641081600000
        mock_note.parent_id = "notebook1234567890abcdef12345678"
        mock_note.markup_language = 1
        mock_note.is_todo = False
        mock_note.todo_completed = False
        mock_note.is_conflict = False
        mock_note.latitude = 0.0
        mock_note.longitude = 0.0
        mock_note.altitude = 0.0
        mock_note.tags = []
        
        with patch.object(client._joppy_client, 'get_note', return_value=mock_note):
            with patch.object(client, 'transform_note_to_mcp', return_value=MCPNote(
                id=mock_note.id,
                title=mock_note.title,
                body=mock_note.body,
                created_time=mock_note.created_time,
                updated_time=mock_note.updated_time,
                parent_id=mock_note.parent_id,
                markup_language=mock_note.markup_language,
                is_todo=mock_note.is_todo,
                todo_completed=mock_note.todo_completed,
                is_conflict=mock_note.is_conflict,
                latitude=mock_note.latitude,
                longitude=mock_note.longitude,
                altitude=mock_note.altitude,
                tags=mock_note.tags
            )):
                result = client.get_note(note_id)
        
        assert isinstance(result, MCPNote)
        assert hasattr(result, 'to_dict')
        assert hasattr(result, 'to_joplin_dict')
        assert hasattr(result, 'to_mcp_summary')
        
        # Test the to_dict method works
        note_dict = result.to_dict()
        assert isinstance(note_dict, dict)
        assert note_dict['id'] == note_id
        assert note_dict['title'] == "Test Note"

    def test_note_operations_with_custom_metadata(self, client):
        """Test note operations with custom metadata and tags."""
        note_data = {
            "title": "Note with Metadata",
            "body": "Content with custom metadata",
            "parent_id": "1234567890abcdef1234567890abcdef",
            "tags": ["important", "work", "meeting"],
            "custom_metadata": {
                "priority": "high",
                "due_date": "2024-01-01",
                "project": "MCP Implementation"
            }
        }
        
        with patch.object(client._joppy_client, 'add_note', return_value="meta123456789abcdef123456789ab") as mock_add_note:
            result = client.create_note(**note_data)
            
            assert isinstance(result, str)
            mock_add_note.assert_called_once()
            
            # Check that metadata was processed correctly
            call_args = mock_add_note.call_args[1]
            assert 'tags' in call_args or 'custom_metadata' in call_args

    def test_note_operations_with_connection_failure(self, client):
        """Test note operations when connection to Joplin fails."""
        note_id = "abcdef1234567890abcdef1234567890"
        
        # Test get_note with connection failure
        with patch.object(client.api, 'get_note', side_effect=ConnectionError("Connection failed")):
            with pytest.raises(JoplinClientError, match="Connection failed"):
                client.get_note(note_id)
        
        # Test create_note with connection failure
        with patch.object(client.api, 'add_note', side_effect=ConnectionError("Connection failed")):
            with pytest.raises(JoplinClientError, match="Connection failed"):
                client.create_note(title="Test", parent_id="1234567890abcdef1234567890abcdef")
        
        # Test update_note with connection failure
        with patch.object(client.api, 'modify_note', side_effect=ConnectionError("Connection failed")):
            with pytest.raises(JoplinClientError, match="Connection failed"):
                client.update_note(note_id, title="New Title")
        
        # Test delete_note with connection failure
        with patch.object(client.api, 'delete_note', side_effect=ConnectionError("Connection failed")):
            with pytest.raises(JoplinClientError, match="Connection failed"):
                client.delete_note(note_id)

    def test_note_operations_with_invalid_authentication(self, client):
        """Test note operations with invalid authentication."""
        note_id = "note1234567890abcdef12345678901234"
        
        # Test with authentication error
        auth_error = Exception("Unauthorized: Invalid token")
        
        with patch.object(client._joppy_client, 'get_note', side_effect=auth_error):
            with pytest.raises(JoplinClientError, match="Failed to get note"):
                client.get_note(note_id)

    def test_bulk_note_operations(self, client):
        """Test bulk operations on multiple notes."""
        note_ids = [
            "abcdef1234567890abcdef1234567890",  # Valid 32-char hex IDs
            "bcdef1234567890abcdef12345678901",
            "cdef1234567890abcdef123456789012"
        ]
        
        # Mock successful retrieval for all notes
        mock_notes = []
        for i, note_id in enumerate(note_ids):
            mock_note = Mock()
            mock_note.id = note_id
            mock_note.title = f"Test Note {i+1}"
            mock_note.body = f"Test content {i+1}"
            mock_note.created_time = 1640995200000 + i * 1000
            mock_note.updated_time = 1641081600000 + i * 1000
            mock_note.parent_id = f"notebook1234567890abcdef1234567{i+1}"
            mock_note.is_todo = False
            mock_note.todo_completed = False
            mock_note.is_conflict = False
            mock_note.latitude = 0.0
            mock_note.longitude = 0.0
            mock_note.altitude = 0.0
            mock_note.markup_language = 1
            mock_note.tags = []
            mock_notes.append(mock_note)
        
        with patch.object(client._joppy_client, 'get_note', side_effect=mock_notes):
            with patch.object(client, 'transform_note_to_mcp', side_effect=lambda note: MCPNote(
                id=note.id,
                title=note.title,
                body=note.body,
                created_time=note.created_time,
                updated_time=note.updated_time,
                parent_id=note.parent_id,
                is_todo=note.is_todo,
                todo_completed=note.todo_completed,
                is_conflict=note.is_conflict,
                latitude=note.latitude,
                longitude=note.longitude,
                altitude=note.altitude,
                markup_language=note.markup_language,
                tags=note.tags
            )):
                results = client.get_notes_bulk(note_ids)
                
        assert len(results) == 3
        assert all(isinstance(note, MCPNote) for note in results)
        assert results[0].title == "Test Note 1"
        assert results[1].title == "Test Note 2"
        assert results[2].title == "Test Note 3"

    def test_note_validation_with_mcp_constraints(self, client):
        """Test MCP-specific validation constraints for notes."""
        
        # Test title too long
        long_title = "A" * 501  # Over 500 character limit
        with pytest.raises(JoplinClientError, match="Title too long"):
            client.create_note(title=long_title, parent_id="notebook12345678901234567890123456")
        
        # Test body too large (50MB limit)
        large_body = "A" * (51 * 1024 * 1024)  # Over 50MB
        with pytest.raises(JoplinClientError, match="Note body too large"):
            client.create_note(title="Test", body=large_body, parent_id="notebook12345678901234567890123456")
        
        # Test invalid characters in title
        invalid_title = "Test\x00Note"  # Contains null character
        with pytest.raises(JoplinClientError, match="Title contains invalid characters"):
            client.create_note(title=invalid_title, parent_id="notebook12345678901234567890123456")

    def test_note_operations_return_mcp_formatted_data(self, client):
        """Test that note operations return properly formatted MCP data."""
        note_id = "abcdef1234567890abcdef1234567890"  # Valid 32-char hex ID
        mock_note = Mock()
        mock_note.id = note_id
        mock_note.title = "Test Note"
        mock_note.body = "This is a test note content."
        mock_note.created_time = 1640995200000
        mock_note.updated_time = 1641081600000
        mock_note.parent_id = "notebook1234567890abcdef12345678"
        mock_note.markup_language = 1
        mock_note.is_todo = False
        mock_note.todo_completed = False
        mock_note.is_conflict = False
        mock_note.latitude = 0.0
        mock_note.longitude = 0.0
        mock_note.altitude = 0.0
        mock_note.tags = []
        
        with patch.object(client._joppy_client, 'get_note', return_value=mock_note):
            with patch.object(client, 'transform_note_to_mcp', return_value=MCPNote(
                id=mock_note.id,
                title=mock_note.title,
                body=mock_note.body,
                created_time=mock_note.created_time,
                updated_time=mock_note.updated_time,
                parent_id=mock_note.parent_id,
                markup_language=mock_note.markup_language,
                is_todo=mock_note.is_todo,
                todo_completed=mock_note.todo_completed,
                is_conflict=mock_note.is_conflict,
                latitude=mock_note.latitude,
                longitude=mock_note.longitude,
                altitude=mock_note.altitude,
                tags=mock_note.tags
            )):
                result = client.get_note(note_id)
        
        assert isinstance(result, MCPNote)
        assert hasattr(result, 'to_dict')
        assert hasattr(result, 'to_joplin_dict')
        assert hasattr(result, 'to_mcp_summary')
        
        # Test the to_dict method works
        note_dict = result.to_dict()
        assert isinstance(note_dict, dict)
        assert note_dict['id'] == note_id
        assert note_dict['title'] == "Test Note"

    def test_note_operations_with_custom_metadata(self, client):
        """Test note operations with custom metadata handling."""
        note_data = {
            "title": "Custom Note",
            "body": "Note with custom metadata",
            "parent_id": "1234567890abcdef1234567890abcdef",  # Valid 32-char hex ID
            "custom_metadata": {
                "project": "important",
                "priority": "high",
                "tags": ["work", "urgent"]
            }
        }
        
        with patch.object(client._joppy_client, 'add_note', return_value="note123456789012345678901234567890") as mock_add_note:
            result = client.create_note(**note_data)
            
            assert result == "note123456789012345678901234567890"
            mock_add_note.assert_called_once()
            
            # Verify custom metadata was passed through
            call_args = mock_add_note.call_args[1]
            assert 'custom_metadata' in call_args
        assert call_args['custom_metadata']['project'] == 'important'

    def test_create_note_with_invalid_parent_id(self, client):
        """Test error handling when creating note with invalid parent ID."""
        invalid_data = {
            "title": "Test Note",
            "parent_id": "invalid"  # Too short, should be at least 8 characters
        }
        
        with pytest.raises(JoplinClientError, match="Invalid parent notebook ID format"):
            client.create_note(**invalid_data)


class TestJoplinMCPClientNotebookOperations:
    """Test notebook CRUD operations with MCP validation and error handling."""
    
    @pytest.fixture
    def client(self):
        """Create a test client with mocked joppy dependency."""
        config = JoplinMCPConfig(
            host="localhost",
            port=41184,
            token="test-token",
            timeout=30,
            verify_ssl=True
        )
        
        # Create a mock joppy client that persists
        mock_joppy_client = Mock()
        
        # Patch the joppy.client_api.ClientApi to return our mock
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_client_api.return_value = mock_joppy_client
            client = JoplinMCPClient(config)
            
            # Manually set the _joppy_client to our mock to ensure it persists
            client._joppy_client = mock_joppy_client
            
            return client

    @pytest.fixture
    def sample_notebook_data(self):
        """Sample notebook data for testing."""
        return {
            "id": "abcdef1234567890abcdef1234567890",  # Valid 32-char hex
            "title": "Test Notebook",
            "created_time": 1640995200000,
            "updated_time": 1641081600000,
            "parent_id": None,  # Root notebook
            "master_key_id": None
        }

    # Notebook Retrieval Tests
    
    def test_get_notebook_with_valid_id(self, client, sample_notebook_data):
        """Test retrieving a notebook by ID with MCP formatting."""
        notebook_id = sample_notebook_data["id"]
        
        # Mock joppy response
        mock_joppy_notebook = Mock()
        for key, value in sample_notebook_data.items():
            setattr(mock_joppy_notebook, key, value)
        
        with patch.object(client._joppy_client, 'get_folder', return_value=mock_joppy_notebook):
            result = client.get_notebook(notebook_id)
            
            assert isinstance(result, MCPNotebook)
            assert result.id == notebook_id
            assert result.title == sample_notebook_data["title"]

    def test_get_notebook_with_invalid_id(self, client):
        """Test error handling when retrieving notebook with invalid ID."""
        invalid_id = "invalid-notebook-id"
        
        with patch.object(client._joppy_client, 'get_folder', side_effect=Exception("Notebook not found")):
            with pytest.raises(JoplinClientError, match="Failed to get notebook"):
                client.get_notebook(invalid_id)

    def test_get_notebook_with_missing_id(self, client):
        """Test error handling when notebook ID is missing."""
        with pytest.raises(JoplinClientError, match="Notebook ID is required"):
            client.get_notebook("")
        
        with pytest.raises(JoplinClientError, match="Notebook ID is required"):
            client.get_notebook(None)

    def test_get_all_notebooks(self, client):
        """Test retrieving all notebooks with MCP formatting."""
        # Mock joppy response with a list of notebook objects
        mock_notebooks = []
        for i in range(3):
            mock_notebook = Mock()
            mock_notebook.id = f"1234567890abcdef1234567890abcd{i:02x}"
            mock_notebook.title = f"Test Notebook {i+1}"
            mock_notebook.created_time = 1640995200000 + i * 1000
            mock_notebook.updated_time = 1641081600000 + i * 1000
            mock_notebook.parent_id = None
            mock_notebooks.append(mock_notebook)
        
        with patch.object(client._joppy_client, 'get_all_folders', return_value=mock_notebooks):
            result = client.get_all_notebooks()
            
            assert isinstance(result, list)
            assert len(result) == 3
            assert all(isinstance(notebook, MCPNotebook) for notebook in result)

    def test_get_notebooks_with_hierarchy(self, client):
        """Test retrieving notebooks with parent-child relationships."""
        # Mock joppy response with parent-child notebooks
        mock_notebooks = []
        # Root notebook
        root_notebook = Mock()
        root_notebook.id = "1234567890abcdef1234567890abcdef"
        root_notebook.title = "Root Notebook"
        root_notebook.created_time = 1640995200000
        root_notebook.updated_time = 1641081600000
        root_notebook.parent_id = None
        mock_notebooks.append(root_notebook)
        
        # Child notebook
        child_notebook = Mock()
        child_notebook.id = "abcdef1234567890abcdef1234567890"
        child_notebook.title = "Child Notebook"
        child_notebook.created_time = 1640995300000
        child_notebook.updated_time = 1641081700000
        child_notebook.parent_id = "1234567890abcdef1234567890abcdef"
        mock_notebooks.append(child_notebook)
        
        with patch.object(client._joppy_client, 'get_all_folders', return_value=mock_notebooks):
            result = client.get_notebooks_with_hierarchy()
            
            assert isinstance(result, list)
            assert len(result) == 2
            # First should be root (None parent_id), then child
            assert result[0].parent_id is None
            assert result[1].parent_id == "1234567890abcdef1234567890abcdef"

    # Notebook Creation Tests
    
    def test_create_notebook_with_valid_data(self, client):
        """Test creating a notebook with valid data."""
        create_data = {
            "title": "New Test Notebook",
            "parent_id": None  # Root notebook
        }
        
        with patch.object(client._joppy_client, 'add_folder', return_value="notebook123456789012345678901234567890"):
            result = client.create_notebook(**create_data)
            
            assert isinstance(result, str)  # Returns notebook ID
            assert result == "notebook123456789012345678901234567890"

    def test_create_notebook_with_parent(self, client):
        """Test creating a child notebook."""
        create_data = {
            "title": "Child Notebook",
            "parent_id": "notebook1234567890abcdef12345678"
        }
        
        with patch.object(client._joppy_client, 'add_folder', return_value="child123456789012345678901234567890"):
            result = client.create_notebook(**create_data)
            
            assert isinstance(result, str)
            assert result == "child123456789012345678901234567890"

    def test_create_notebook_with_missing_title(self, client):
        """Test creating a notebook without title raises error."""
        with pytest.raises(JoplinClientError, match="Title is required"):
            client.create_notebook(title="")

    def test_create_notebook_with_invalid_parent_id(self, client):
        """Test error handling when creating notebook with invalid parent ID."""
        with pytest.raises(JoplinClientError, match="Invalid parent notebook ID format"):
            client.create_notebook(title="Test", parent_id="invalid")

    def test_create_notebook_with_title_validation(self, client):
        """Test notebook title validation constraints."""
        # Test title too long
        long_title = "A" * 501  # Over 500 character limit
        with pytest.raises(JoplinClientError, match="Title too long"):
            client.create_notebook(title=long_title)
        
        # Test invalid characters in title
        invalid_title = "Test\x00Notebook"  # Contains null character
        with pytest.raises(JoplinClientError, match="Title contains invalid characters"):
            client.create_notebook(title=invalid_title)

    # Notebook Update Tests
    
    def test_update_notebook_with_valid_data(self, client):
        """Test updating a notebook with valid data."""
        notebook_id = "notebook1234567890abcdef12345678"
        update_data = {
            "title": "Updated Notebook Title"
        }
        
        with patch.object(client._joppy_client, 'modify_folder', return_value=None):
            result = client.update_notebook(notebook_id, **update_data)
            
            assert result == True

    def test_update_notebook_with_invalid_id(self, client):
        """Test error handling when updating notebook with invalid ID."""
        invalid_id = "invalid-notebook-id"
        
        with patch.object(client._joppy_client, 'modify_folder', side_effect=Exception("Notebook not found")):
            with pytest.raises(JoplinClientError, match="Failed to update notebook"):
                client.update_notebook(invalid_id, title="New Title")

    def test_update_notebook_with_empty_data(self, client):
        """Test error handling when updating notebook with no data."""
        notebook_id = "notebook1234567890abcdef12345678"
        
        with pytest.raises(JoplinClientError, match="At least one field must be provided"):
            client.update_notebook(notebook_id)

    def test_update_notebook_parent_relationship(self, client):
        """Test updating notebook parent relationships."""
        notebook_id = "notebook1234567890abcdef12345678"
        new_parent_id = "parent1234567890abcdef123456789"
        
        with patch.object(client._joppy_client, 'modify_folder', return_value=None):
            result = client.update_notebook(notebook_id, parent_id=new_parent_id)
            
            assert result == True

    # Notebook Deletion Tests
    
    def test_delete_notebook_with_valid_id(self, client):
        """Test deleting a notebook with valid ID."""
        notebook_id = "notebook1234567890abcdef12345678"
        
        # Mock get_all_notebooks to return empty list (no children)
        with patch.object(client, 'get_all_notebooks', return_value=[]):
            with patch.object(client._joppy_client, 'delete_folder', return_value=None):
                result = client.delete_notebook(notebook_id)
                
                assert result == True

    def test_delete_notebook_with_invalid_id(self, client):
        """Test error handling when deleting notebook with invalid ID."""
        invalid_id = "invalid-notebook-id"
        
        with patch.object(client, 'get_all_notebooks', return_value=[]):
            with patch.object(client._joppy_client, 'delete_folder', side_effect=Exception("Notebook not found")):
                with pytest.raises(JoplinClientError, match="Failed to delete notebook"):
                    client.delete_notebook(invalid_id)

    def test_delete_notebook_with_missing_id(self, client):
        """Test error handling when notebook ID is missing for deletion."""
        with pytest.raises(JoplinClientError, match="Notebook ID is required"):
            client.delete_notebook("")

    def test_delete_notebook_with_children_protection(self, client):
        """Test preventing deletion of notebooks with child notebooks."""
        parent_notebook_id = "1234567890abcdef1234567890abcdef"
        
        # Mock get_all_notebooks to return a child notebook
        child_notebook = MCPNotebook(
            id="abcdef1234567890abcdef1234567890",
            title="Child Notebook", 
            created_time=1640995200000,
            updated_time=1641081600000,
            parent_id=parent_notebook_id
        )
        
        with patch.object(client, 'get_all_notebooks', return_value=[child_notebook]):
            with pytest.raises(JoplinClientError, match="Cannot delete notebook with children"):
                client.delete_notebook(parent_notebook_id, force=False)

    def test_delete_notebook_with_force_option(self, client):
        """Test force deletion of notebooks with children."""
        parent_notebook_id = "1234567890abcdef1234567890abcdef"
        
        # Mock get_all_notebooks to return a child notebook, but force=True should bypass this
        child_notebook = MCPNotebook(
            id="abcdef1234567890abcdef1234567890",
            title="Child Notebook",
            created_time=1640995200000,
            updated_time=1641081600000, 
            parent_id=parent_notebook_id
        )
        
        with patch.object(client, 'get_all_notebooks', return_value=[child_notebook]):
            with patch.object(client._joppy_client, 'delete_folder', return_value=None):
                result = client.delete_notebook(parent_notebook_id, force=True)
                
                assert result == True

    # Bulk Notebook Operations
    
    def test_get_notebooks_bulk(self, client):
        """Test bulk retrieval of multiple notebooks."""
        notebook_ids = [
            "1234567890abcdef1234567890abcdef",
            "abcdef1234567890abcdef1234567890",
            "fedcba0987654321fedcba0987654321"
        ]
        
        # Mock get_notebook to return MCPNotebook objects
        def mock_get_notebook(notebook_id):
            return MCPNotebook(
                id=notebook_id,
                title=f"Test Notebook {notebook_id[-1]}",
                created_time=1640995200000,
                updated_time=1641081600000,
                parent_id=None
            )
        
        with patch.object(client, 'get_notebook', side_effect=mock_get_notebook):
            results = client.get_notebooks_bulk(notebook_ids)
            
            assert len(results) == 3
            assert all(isinstance(notebook, MCPNotebook) for notebook in results)

    def test_delete_notebooks_bulk(self, client):
        """Test bulk deletion of multiple notebooks."""
        notebook_ids = [
            "1234567890abcdef1234567890abcdef",
            "abcdef1234567890abcdef1234567890"
        ]
        
        # Mock delete_notebook to return True
        with patch.object(client, 'delete_notebook', return_value=True):
            results = client.delete_notebooks_bulk(notebook_ids)
            
            assert isinstance(results, dict)
            assert all(results[notebook_id] == True for notebook_id in notebook_ids)


class TestJoplinMCPClientTagOperations:
    """Test tag CRUD operations with MCP validation and error handling."""
    
    @pytest.fixture
    def client(self):
        """Create a test client with mocked joppy dependency."""
        config = JoplinMCPConfig(
            host="localhost",
            port=41184,
            token="test-token",
            timeout=30,
            verify_ssl=True
        )
        
        # Create a mock joppy client that persists
        mock_joppy_client = Mock()
        
        # Patch the joppy.client_api.ClientApi to return our mock
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_client_api.return_value = mock_joppy_client
            client = JoplinMCPClient(config)
            
            # Manually set the _joppy_client to our mock to ensure it persists
            client._joppy_client = mock_joppy_client
            
            return client

    @pytest.fixture
    def sample_tag_data(self):
        """Sample tag data for testing."""
        return {
            "id": "abcdef1234567890abcdef1234567890",  # Valid 32-char hex
            "title": "test-tag",
            "created_time": 1640995200000,
            "updated_time": 1641081600000
        }

    # Tag Retrieval Tests
    
    def test_get_tag_with_valid_id(self, client, sample_tag_data):
        """Test retrieving a tag by ID with MCP formatting."""
        tag_id = sample_tag_data["id"]
        
        # Mock joppy response
        mock_joppy_tag = Mock()
        for key, value in sample_tag_data.items():
            setattr(mock_joppy_tag, key, value)
        
        with patch.object(client._joppy_client, 'get_tag', return_value=mock_joppy_tag):
            result = client.get_tag(tag_id)
            
            assert isinstance(result, MCPTag)
            assert result.id == tag_id
            assert result.title == sample_tag_data["title"]

    def test_get_tag_with_invalid_id(self, client):
        """Test error handling when retrieving tag with invalid ID."""
        invalid_id = "invalid-tag-id"
        
        with patch.object(client._joppy_client, 'get_tag', side_effect=Exception("Tag not found")):
            with pytest.raises(JoplinClientError, match="Failed to get tag"):
                client.get_tag(invalid_id)

    def test_get_tag_with_missing_id(self, client):
        """Test error handling when tag ID is missing."""
        with pytest.raises(JoplinClientError, match="Tag ID is required"):
            client.get_tag("")

    def test_get_all_tags(self, client):
        """Test retrieving all tags with MCP formatting."""
        # Mock joppy response with a list of tag objects
        mock_tags = []
        for i in range(3):
            mock_tag = Mock()
            mock_tag.id = f"1234567890abcdef1234567890abcd{i:02x}"
            mock_tag.title = f"test-tag-{i+1}"
            mock_tag.created_time = 1640995200000 + i * 1000
            mock_tag.updated_time = 1641081600000 + i * 1000
            mock_tags.append(mock_tag)
        
        with patch.object(client._joppy_client, 'get_all_tags', return_value=mock_tags):
            result = client.get_all_tags()
            
            assert isinstance(result, list)
            assert len(result) == 3
            assert all(isinstance(tag, MCPTag) for tag in result)

    def test_get_tags_by_note(self, client):
        """Test retrieving tags associated with a specific note."""
        note_id = "note1234567890abcdef12345678901234"
        
        # Mock joppy response with tags for the note
        mock_tags = []
        for i in range(2):
            mock_tag = Mock()
            mock_tag.id = f"abcdef1234567890abcdef12345678{i:02x}"
            mock_tag.title = f"note-tag-{i+1}"
            mock_tag.created_time = 1640995200000 + i * 1000
            mock_tag.updated_time = 1641081600000 + i * 1000
            mock_tags.append(mock_tag)
        
        with patch.object(client._joppy_client, 'get_note_tags', return_value=mock_tags):
            result = client.get_tags_by_note(note_id)
            
            assert isinstance(result, list)
            assert len(result) == 2
            assert all(isinstance(tag, MCPTag) for tag in result)

    # Tag Creation Tests
    
    def test_create_tag_with_valid_data(self, client):
        """Test creating a tag with valid data."""
        create_data = {
            "title": "new-test-tag"
        }
        
        with patch.object(client._joppy_client, 'add_tag', return_value="1234567890abcdef1234567890abcdef"):
            result = client.create_tag(**create_data)
            
            assert isinstance(result, str)  # Returns tag ID
            assert result == "1234567890abcdef1234567890abcdef"

    def test_create_tag_with_missing_title(self, client):
        """Test creating a tag without title raises error."""
        with pytest.raises(JoplinClientError, match="Title is required"):
            client.create_tag(title="")

    def test_create_tag_with_title_validation(self, client):
        """Test tag title validation and normalization."""
        # Test title normalization (should be lowercased and trimmed)
        with patch.object(client._joppy_client, 'add_tag', return_value="1234567890abcdef1234567890abcdef"):
            with patch.object(client, 'get_all_tags', return_value=[]):  # No existing tags
                result = client.create_tag(title="  Test-Tag  ")
                assert isinstance(result, str)
        
        # Test title too long
        long_title = "a" * 201  # Over 200 character limit for tags
        with pytest.raises(JoplinClientError, match="Tag title too long"):
            client.create_tag(title=long_title)

    def test_create_tag_duplicate_handling(self, client):
        """Test handling of duplicate tag creation."""
        tag_title = "duplicate-tag"
        
        # Mock existing tag with same title
        existing_tag = MCPTag(
            id="1234567890abcdef1234567890abcdef", 
            title=tag_title.lower(),
            created_time=1640995200000,
            updated_time=1641081600000
        )
        
        with patch.object(client, 'get_all_tags', return_value=[existing_tag]):
            # Should return existing tag ID instead of creating new one
            result = client.create_tag(title=tag_title)
            assert result == existing_tag.id

    def test_update_tag_with_invalid_id(self, client):
        """Test error handling when updating tag with invalid ID."""
        invalid_id = "invalid-tag-id"
        
        with patch.object(client._joppy_client, 'modify_tag', side_effect=Exception("Tag not found")):
            with pytest.raises(JoplinClientError, match="Failed to update tag"):
                client.update_tag(invalid_id, title="new-title")

    def test_delete_tag_with_invalid_id(self, client):
        """Test error handling when deleting tag with invalid ID."""
        invalid_id = "invalid-tag-id"
        
        with patch.object(client._joppy_client, 'delete_tag', side_effect=Exception("Tag not found")):
            with pytest.raises(JoplinClientError, match="Failed to delete tag"):
                client.delete_tag(invalid_id)

    def test_remove_all_tags_from_note(self, client):
        """Test removing all tags from a note."""
        note_id = "note1234567890abcdef12345678901234"
        
        # Mock current tags for the note
        current_tags = [
            MCPTag(id="1234567890abcdef1234567890abcdef", title="tag1", created_time=1640995200000, updated_time=1641081600000),
            MCPTag(id="abcdef1234567890abcdef1234567890", title="tag2", created_time=1640995200000, updated_time=1641081600000)
        ]
        
        with patch.object(client, 'get_tags_by_note', return_value=current_tags):
            with patch.object(client, 'remove_tag_from_note', return_value=True):
                result = client.remove_all_tags_from_note(note_id)
                
                assert result == True

    def test_search_tags_by_title(self, client):
        """Test searching tags by title pattern."""
        search_query = "test"
        
        # Mock all tags with some matching the query
        all_tags = [
            MCPTag(id="1234567890abcdef1234567890abcdef", title="test-tag-1", created_time=1640995200000, updated_time=1641081600000),
            MCPTag(id="abcdef1234567890abcdef1234567890", title="another-tag", created_time=1640995200000, updated_time=1641081600000),
            MCPTag(id="fedcba0987654321fedcba0987654321", title="test-tag-2", created_time=1640995200000, updated_time=1641081600000)
        ]
        
        with patch.object(client, 'get_all_tags', return_value=all_tags):
            result = client.search_tags(query=search_query)
            
            assert isinstance(result, list)
            assert len(result) == 2  # Only tags containing "test"
            assert all(isinstance(tag, MCPTag) for tag in result)
            assert all("test" in tag.title.lower() for tag in result)

    def test_get_unused_tags(self, client):
        """Test retrieving tags that are not associated with any notes."""
        # Mock all tags
        all_tags = [
            MCPTag(id="1234567890abcdef1234567890abcdef", title="used-tag", created_time=1640995200000, updated_time=1641081600000),
            MCPTag(id="abcdef1234567890abcdef1234567890", title="unused-tag", created_time=1640995200000, updated_time=1641081600000)
        ]
        
        # Mock all notes
        mock_notes = [Mock()]
        mock_notes[0].id = "note123456789012345678901234567890"
        
        with patch.object(client, 'get_all_tags', return_value=all_tags):
            with patch.object(client._joppy_client, 'get_all_notes', return_value=mock_notes):
                with patch.object(client, 'get_tags_by_note', return_value=[all_tags[0]]):  # Only first tag is used
                    result = client.get_unused_tags()
                    
                    assert isinstance(result, list)
                    assert len(result) == 1
                    assert result[0].title == "unused-tag"

    def test_get_popular_tags(self, client):
        """Test retrieving most frequently used tags."""
        # Mock all tags
        all_tags = [
            MCPTag(id="1234567890abcdef1234567890abcdef", title="popular-tag", created_time=1640995200000, updated_time=1641081600000),
            MCPTag(id="abcdef1234567890abcdef1234567890", title="less-popular", created_time=1640995200000, updated_time=1641081600000)
        ]
        
        # Mock notes
        mock_notes = [Mock(), Mock()]
        for i, note in enumerate(mock_notes):
            note.id = f"note{i}23456789012345678901234567890"
        
        def mock_get_tags_by_note(note_id):
            if note_id == "note023456789012345678901234567890":
                return [all_tags[0]]  # First note has popular tag
            else:
                return [all_tags[0]]  # Second note also has popular tag
        
        with patch.object(client, 'get_all_tags', return_value=all_tags):
            with patch.object(client._joppy_client, 'get_all_notes', return_value=mock_notes):
                with patch.object(client, 'get_tags_by_note', side_effect=mock_get_tags_by_note):
                    result = client.get_popular_tags(limit=10)
                    
                    assert isinstance(result, list)
                    assert len(result) <= 10
                    assert all(isinstance(item, dict) and 'tag' in item and 'usage_count' in item for item in result)

    # Tag Update Tests
    
    def test_update_tag_with_valid_data(self, client):
        """Test updating a tag with valid data."""
        tag_id = "1234567890abcdef1234567890abcdef"
        update_data = {
            "title": "updated-tag-title"
        }
        
        result = client.update_tag(tag_id, **update_data)
        
        assert result == True

    def test_update_tag_with_empty_data(self, client):
        """Test error handling when updating tag with no data."""
        tag_id = "1234567890abcdef1234567890abcdef"
        
        with pytest.raises(JoplinClientError, match="At least one field must be provided"):
            client.update_tag(tag_id)

    # Tag Deletion Tests
    
    def test_delete_tag_with_valid_id(self, client):
        """Test deleting a tag with valid ID."""
        tag_id = "1234567890abcdef1234567890abcdef"
        
        result = client.delete_tag(tag_id)
        
        assert result == True

    def test_delete_tag_with_invalid_id(self, client):
        """Test error handling when deleting tag with invalid ID."""
        invalid_id = "invalid-tag-id"
        
        with patch.object(client._joppy_client, 'delete_tag', side_effect=Exception("Tag not found")):
            with pytest.raises(JoplinClientError, match="Failed to delete tag"):
                client.delete_tag(invalid_id)

    def test_delete_tag_with_missing_id(self, client):
        """Test error handling when tag ID is missing for deletion."""
        with pytest.raises(JoplinClientError, match="Tag ID is required"):
            client.delete_tag("")

    # Tag-Note Association Tests
    
    def test_add_tag_to_note(self, client):
        """Test adding a tag to a note."""
        note_id = "note1234567890abcdef12345678901234"
        tag_id = "1234567890abcdef1234567890abcdef"
        
        result = client.add_tag_to_note(note_id, tag_id)
        
        assert result == True

    def test_remove_tag_from_note(self, client):
        """Test removing a tag from a note."""
        note_id = "note1234567890abcdef12345678901234"
        tag_id = "1234567890abcdef1234567890abcdef"
        
        result = client.remove_tag_from_note(note_id, tag_id)
        
        assert result == True

    def test_add_multiple_tags_to_note(self, client):
        """Test adding multiple tags to a note."""
        note_id = "note1234567890abcdef12345678901234"
        tag_ids = [
            "1234567890abcdef1234567890abcdef",
            "abcdef1234567890abcdef1234567890"
        ]
        
        result = client.add_tags_to_note(note_id, tag_ids)
        
        assert isinstance(result, dict)
        assert all(result[tag_id] == True for tag_id in tag_ids)

    def test_remove_all_tags_from_note(self, client):
        """Test removing all tags from a note."""
        note_id = "note1234567890abcdef12345678901234"
        
        # Mock current tags for the note
        current_tags = [
            MCPTag(id="1234567890abcdef1234567890abcdef", title="tag1", created_time=1640995200000, updated_time=1641081600000),
            MCPTag(id="abcdef1234567890abcdef1234567890", title="tag2", created_time=1640995200000, updated_time=1641081600000)
        ]
        
        with patch.object(client, 'get_tags_by_note', return_value=current_tags):
            with patch.object(client, 'remove_tag_from_note', return_value=True):
                result = client.remove_all_tags_from_note(note_id)
                
                assert result == True

    # Tag Search and Filtering
    
    def test_search_tags_by_title(self, client):
        """Test searching tags by title pattern."""
        search_query = "test"
        
        # Mock all tags with some matching the query
        all_tags = [
            MCPTag(id="1234567890abcdef1234567890abcdef", title="test-tag-1", created_time=1640995200000, updated_time=1641081600000),
            MCPTag(id="abcdef1234567890abcdef1234567890", title="another-tag", created_time=1640995200000, updated_time=1641081600000),
            MCPTag(id="fedcba0987654321fedcba0987654321", title="test-tag-2", created_time=1640995200000, updated_time=1641081600000)
        ]
        
        with patch.object(client, 'get_all_tags', return_value=all_tags):
            result = client.search_tags(query=search_query)
            
            assert isinstance(result, list)
            assert len(result) == 2  # Only tags containing "test"
            assert all(isinstance(tag, MCPTag) for tag in result)
            assert all("test" in tag.title.lower() for tag in result)

    def test_get_unused_tags(self, client):
        """Test retrieving tags that are not associated with any notes."""
        # Mock all tags
        all_tags = [
            MCPTag(id="1234567890abcdef1234567890abcdef", title="used-tag", created_time=1640995200000, updated_time=1641081600000),
            MCPTag(id="abcdef1234567890abcdef1234567890", title="unused-tag", created_time=1640995200000, updated_time=1641081600000)
        ]
        
        # Mock all notes
        mock_notes = [Mock()]
        mock_notes[0].id = "note123456789012345678901234567890"
        
        with patch.object(client, 'get_all_tags', return_value=all_tags):
            with patch.object(client._joppy_client, 'get_all_notes', return_value=mock_notes):
                with patch.object(client, 'get_tags_by_note', return_value=[all_tags[0]]):  # Only first tag is used
                    result = client.get_unused_tags()
                    
                    assert isinstance(result, list)
                    assert len(result) == 1
                    assert result[0].title == "unused-tag"

    def test_get_popular_tags(self, client):
        """Test retrieving most frequently used tags."""
        # Mock all tags
        all_tags = [
            MCPTag(id="1234567890abcdef1234567890abcdef", title="popular-tag", created_time=1640995200000, updated_time=1641081600000),
            MCPTag(id="abcdef1234567890abcdef1234567890", title="less-popular", created_time=1640995200000, updated_time=1641081600000)
        ]
        
        # Mock notes
        mock_notes = [Mock(), Mock()]
        for i, note in enumerate(mock_notes):
            note.id = f"note{i}23456789012345678901234567890"
        
        def mock_get_tags_by_note(note_id):
            if note_id == "note023456789012345678901234567890":
                return [all_tags[0]]  # First note has popular tag
            else:
                return [all_tags[0]]  # Second note also has popular tag
        
        with patch.object(client, 'get_all_tags', return_value=all_tags):
            with patch.object(client._joppy_client, 'get_all_notes', return_value=mock_notes):
                with patch.object(client, 'get_tags_by_note', side_effect=mock_get_tags_by_note):
                    result = client.get_popular_tags(limit=10)
                    
                    assert isinstance(result, list)
                    assert len(result) <= 10
                    assert all(isinstance(item, dict) and 'tag' in item and 'usage_count' in item for item in result)

    # Bulk Tag Operations
    
    def test_get_tags_bulk(self, client):
        """Test bulk retrieval of multiple tags."""
        tag_ids = [
            "1234567890abcdef1234567890abcdef",
            "abcdef1234567890abcdef1234567890",
            "fedcba0987654321fedcba0987654321"
        ]
        
        results = client.get_tags_bulk(tag_ids)
        
        assert len(results) == 3
        assert all(isinstance(tag, MCPTag) for tag in results)

    def test_delete_tags_bulk(self, client):
        """Test bulk deletion of multiple tags."""
        tag_ids = [
            "1234567890abcdef1234567890abcdef",
            "abcdef1234567890abcdef1234567890"
        ]
        
        results = client.delete_tags_bulk(tag_ids)
        
        assert isinstance(results, dict)
        assert all(results[tag_id] == True for tag_id in tag_ids)

    # Tag Validation and Error Handling
    
    def test_tag_operations_with_connection_failure(self, client):
        """Test tag operations with connection failure scenarios."""
        tag_id = "1234567890abcdef1234567890abcdef"
        
        with patch.object(client._joppy_client, 'get_tag', side_effect=Exception("Connection failed")):
            with pytest.raises(JoplinClientError, match="Failed to get tag"):
                client.get_tag(tag_id)

    def test_tag_operations_return_mcp_formatted_data(self, client):
        """Test that tag operations return properly formatted MCP data."""
        tag_id = "1234567890abcdef1234567890abcdef"
        
        # Mock joppy response
        mock_joppy_tag = Mock()
        mock_joppy_tag.id = tag_id
        mock_joppy_tag.title = "test-tag"
        mock_joppy_tag.created_time = 1640995200000
        mock_joppy_tag.updated_time = 1641081600000
        
        with patch.object(client._joppy_client, 'get_tag', return_value=mock_joppy_tag):
            result = client.get_tag(tag_id)
            
            assert isinstance(result, MCPTag)
            assert hasattr(result, 'to_joplin_dict')
            assert hasattr(result, 'to_mcp_summary')
            
            # Test that the methods actually work
            joplin_dict = result.to_joplin_dict()
            mcp_summary = result.to_mcp_summary()
            assert isinstance(joplin_dict, dict)
            assert isinstance(mcp_summary, dict)

    def test_tag_validation_with_mcp_constraints(self, client):
        """Test MCP-specific validation constraints for tags."""
        
        # Test title too long (reasonable limit for tags)
        long_title = "a" * 201  # Over 200 character limit for tags
        with pytest.raises(JoplinClientError, match="Tag title too long"):
            client.create_tag(title=long_title)

    def test_get_tags_bulk(self, client):
        """Test bulk retrieval of multiple tags."""
        tag_ids = [
            "1234567890abcdef1234567890abcdef",
            "abcdef1234567890abcdef1234567890",
            "fedcba0987654321fedcba0987654321"
        ]
        
        # Mock get_tag to return MCPTag objects
        def mock_get_tag(tag_id):
            return MCPTag(
                id=tag_id,
                title=f"test-tag-{tag_id[-1]}",
                created_time=1640995200000,
                updated_time=1641081600000
            )
        
        with patch.object(client, 'get_tag', side_effect=mock_get_tag):
            results = client.get_tags_bulk(tag_ids)
            
            assert len(results) == 3
            assert all(isinstance(tag, MCPTag) for tag in results)


class TestJoplinMCPClientConnectionManagement:
    """Test comprehensive connection management and health check functionality."""
    
    @pytest.fixture
    def client(self):
        """Create a test client with mocked joppy."""
        config = JoplinMCPConfig(
            host="localhost",
            port=41184,
            token="test-token",
            timeout=10
        )
        
        with patch('joppy.client_api.ClientApi') as mock_client_api:
            mock_joppy_client = Mock()
            mock_client_api.return_value = mock_joppy_client
            
            client = JoplinMCPClient(config)
            client._joppy_client = mock_joppy_client
            yield client

    def test_client_implements_connection_retry_logic(self, client):
        """Test that client implements retry logic for transient connection failures."""
        # Mock transient failures followed by success
        client._joppy_client.ping.side_effect = [
            Exception("Connection timeout"),
            Exception("Connection refused"), 
            True  # Success on third attempt
        ]
        
        # This should succeed after retries
        result = client.ping_with_retry(max_retries=3, retry_delay=0.1)
        assert result == True
        assert client._joppy_client.ping.call_count == 3

    def test_client_implements_connection_timeout_handling(self, client):
        """Test that client properly handles connection timeouts."""
        # Mock timeout scenario
        client._joppy_client.ping.side_effect = Exception("Request timeout")
        
        # Should handle timeout gracefully and return appropriate error
        with pytest.raises(JoplinClientError, match="timeout"):
            client.ping_with_timeout(timeout=5)

    def test_client_implements_health_check_monitoring(self, client):
        """Test that client provides comprehensive health check functionality."""
        # Mock various health check responses
        client._joppy_client.ping.return_value = True
        
        # Mock server info calls for health check
        with patch.object(client, 'get_server_info') as mock_server_info:
            mock_server_info.return_value = {
                'connected': True,
                'version': '2.12.0',
                'database_status': 'healthy'
            }
            
            health_status = client.get_health_status()
            
            # Should return comprehensive health information
            assert isinstance(health_status, dict)
            assert 'connection_status' in health_status
            assert 'server_info' in health_status
            assert 'last_ping_time' in health_status
            assert 'response_time_ms' in health_status

    def test_client_implements_connection_recovery(self, client):
        """Test that client can recover from connection failures."""
        # Mock connection failure then recovery
        client._joppy_client.ping.side_effect = [
            Exception("Connection lost"),
            Exception("Still down"),
            True,  # Recovered (for attempt_connection_recovery)
            True   # Additional True for is_connected check
        ]
        
        # Should detect failure and attempt recovery
        recovery_result = client.attempt_connection_recovery()
        assert recovery_result == True
        assert client.is_connected == True

    def test_client_implements_connection_pooling(self, client):
        """Test that client implements connection pooling for efficiency."""
        # Mock successful connections
        client._joppy_client.ping.return_value = True
        
        # Should manage connection pool
        pool_info = client.get_connection_pool_info()
        assert isinstance(pool_info, dict)
        assert 'active_connections' in pool_info
        assert 'max_connections' in pool_info
        assert 'connection_reuse_count' in pool_info

    def test_client_implements_ssl_certificate_validation(self, client):
        """Test that client properly validates SSL certificates."""
        # Test with valid certificate scenario
        with patch.object(client, '_validate_ssl_certificate') as mock_validate:
            mock_validate.return_value = True
            
            ssl_status = client.verify_ssl_connection()
            assert ssl_status['valid'] == True
            assert 'certificate_info' in ssl_status
            assert 'expiry_date' in ssl_status

    def test_client_implements_network_connectivity_check(self, client):
        """Test that client can check network connectivity separately from Joplin."""
        with patch('socket.create_connection') as mock_socket:
            mock_socket.return_value.__enter__.return_value = Mock()
            
            # Should test basic network connectivity
            connectivity = client.check_network_connectivity()
            assert isinstance(connectivity, dict)
            assert 'network_reachable' in connectivity
            assert 'dns_resolution' in connectivity
            assert 'port_accessible' in connectivity

    def test_client_implements_server_availability_monitoring(self, client):
        """Test that client can monitor server availability over time."""
        import time
        
        # Mock server responses over time
        client._joppy_client.ping.return_value = True
        
        # Should track availability metrics
        client.start_availability_monitoring(interval=1)
        time.sleep(0.1)  # Brief monitoring period
        client.stop_availability_monitoring()
        
        metrics = client.get_availability_metrics()
        assert isinstance(metrics, dict)
        assert 'uptime_percentage' in metrics
        assert 'average_response_time' in metrics
        assert 'total_checks' in metrics
        assert 'failed_checks' in metrics

    def test_client_implements_connection_state_persistence(self, client):
        """Test that client can persist and restore connection state."""
        # Set up connection state
        client._joppy_client.ping.return_value = True
        client.ping()  # Establish connection
        
        # Should be able to save and restore state
        state = client.get_connection_state()
        assert isinstance(state, dict)
        assert 'last_successful_connection' in state
        assert 'connection_history' in state
        
        # Should be able to restore from saved state
        new_client_instance = client.restore_from_state(state)
        assert new_client_instance.connection_info == client.connection_info

    def test_client_implements_graceful_shutdown(self, client):
        """Test that client implements graceful shutdown procedures."""
        # Mock active operations
        client._joppy_client.ping.return_value = True
        
        # Should handle graceful shutdown
        shutdown_result = client.shutdown_gracefully(timeout=5)
        assert shutdown_result == True
        
        # Should not accept new operations after shutdown
        with pytest.raises(JoplinClientError, match="client has been shut down"):
            client.ping()

    def test_client_implements_connection_diagnostics(self, client):
        """Test that client provides detailed connection diagnostics."""
        # Mock various diagnostic scenarios
        client._joppy_client.ping.return_value = True
        
        diagnostics = client.run_connection_diagnostics()
        assert isinstance(diagnostics, dict)
        assert 'ping_test' in diagnostics
        assert 'dns_resolution' in diagnostics
        assert 'port_connectivity' in diagnostics
        assert 'ssl_verification' in diagnostics
        assert 'authentication_test' in diagnostics
        assert 'response_time_analysis' in diagnostics

    def test_client_handles_concurrent_connection_requests(self, client):
        """Test that client handles concurrent connection requests safely."""
        import threading
        import concurrent.futures
        
        # Mock successful ping
        client._joppy_client.ping.return_value = True
        
        # Should handle concurrent requests without issues
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(client.ping) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
        # All requests should succeed
        assert all(result == True for result in results)
        
        # Should track concurrent request metrics
        metrics = client.get_concurrent_request_metrics()
        assert isinstance(metrics, dict)
        assert 'max_concurrent_requests' in metrics
        assert 'total_concurrent_requests' in metrics

    def test_client_implements_connection_caching(self, client):
        """Test that client implements connection result caching."""
        # Mock ping responses
        client._joppy_client.ping.return_value = True
        
        # First call should hit server
        result1 = client.ping_cached(cache_ttl=60)
        assert result1 == True
        
        # Second call should use cache
        result2 = client.ping_cached(cache_ttl=60)
        assert result2 == True
        
        # Should have cache statistics
        cache_stats = client.get_connection_cache_stats()
        assert isinstance(cache_stats, dict)
        assert 'cache_hits' in cache_stats
        assert 'cache_misses' in cache_stats
        assert 'cache_size' in cache_stats

    def test_client_implements_connection_event_logging(self, client):
        """Test that client logs connection events for monitoring."""
        # Mock connection events
        client._joppy_client.ping.side_effect = [
            Exception("Connection failed"),
            True  # Recovery
        ]
        
        # Should log connection events
        try:
            client.ping()
        except:
            pass
        
        client.ping()  # Recovery
        
        # Should have event logs
        events = client.get_connection_events()
        assert isinstance(events, list)
        assert len(events) >= 2
        assert any('failed' in str(event).lower() for event in events)
        assert any('success' in str(event).lower() for event in events)

    def test_client_implements_adaptive_timeout_management(self, client):
        """Test that client adapts timeout values based on connection performance."""
        # Mock varying response times
        response_times = [0.1, 0.5, 1.0, 0.3, 0.8]
        call_count = 0
        
        def mock_ping_with_delay():
            nonlocal call_count
            time.sleep(response_times[call_count % len(response_times)])
            call_count += 1
            return True
        
        client._joppy_client.ping.side_effect = mock_ping_with_delay
        
        # Should adapt timeout based on performance
        for _ in range(5):
            client.ping_adaptive()
        
        # Should have timeout adaptation metrics
        timeout_info = client.get_adaptive_timeout_info()
        assert isinstance(timeout_info, dict)
        assert 'current_timeout' in timeout_info
        assert 'baseline_timeout' in timeout_info
        assert 'adaptation_factor' in timeout_info
        assert 'performance_history' in timeout_info