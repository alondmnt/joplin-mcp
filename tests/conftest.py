"""
Pytest configuration and fixtures for Joplin MCP testing.

This module provides comprehensive fixtures for testing the Joplin MCP implementation,
including mock Joplin server responses, test data, and testing utilities.
"""

import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

# Test data constants
TEST_TOKEN = "test_token_123456789"
TEST_SERVER_URL = "http://localhost:41184"

# Sample test data
SAMPLE_NOTE_DATA = {
    "id": "12345678901234567890123456789012",
    "title": "Test Note",
    "body": "This is a **test** note with some markdown content.\n\n- Item 1\n- Item 2",
    "parent_id": "abcdef12345678901234567890123456",
    "created_time": 1609459200000,  # 2021-01-01 00:00:00 UTC
    "updated_time": 1609545600000,  # 2021-01-02 00:00:00 UTC
    "user_created_time": 1609459200000,
    "user_updated_time": 1609545600000,
    "markup_language": 1,
    "is_conflict": 0,
    "latitude": 0.0,
    "longitude": 0.0,
    "altitude": 0.0,
    "author": "",
    "source_url": "",
    "is_todo": 0,
    "todo_due": 0,
    "todo_completed": 0,
    "source": "joplin-mcp-test",
    "source_application": "net.cozic.joplin-desktop",
    "application_data": "",
    "order": 0,
    "encryption_cipher_text": "",
    "encryption_applied": 0,
    "is_shared": 0,
    "share_id": "",
    "conflict_original_id": "",
    "master_key_id": "",
}

SAMPLE_NOTEBOOK_DATA = {
    "id": "abcdef12345678901234567890123456",
    "title": "Test Notebook",
    "created_time": 1609459200000,
    "updated_time": 1609545600000,
    "user_created_time": 1609459200000,
    "user_updated_time": 1609545600000,
    "encryption_cipher_text": "",
    "encryption_applied": 0,
    "parent_id": "",
    "is_shared": 0,
    "share_id": "",
    "master_key_id": "",
    "icon": "",
}

SAMPLE_TAG_DATA = {
    "id": "fedcba09876543210987654321098765",
    "title": "test-tag",
    "created_time": 1609459200000,
    "updated_time": 1609545600000,
    "user_created_time": 1609459200000,
    "user_updated_time": 1609545600000,
    "encryption_cipher_text": "",
    "encryption_applied": 0,
    "is_shared": 0,
    "master_key_id": "",
}

SAMPLE_SEARCH_RESULT = {
    "items": [
        {
            "id": "12345678901234567890123456789012",
            "title": "Test Note",
            "body": "This is a **test** note with some markdown content.",
            "parent_id": "abcdef12345678901234567890123456",
            "updated_time": 1609545600000,
        }
    ],
    "has_more": False,
}


@pytest.fixture
def test_token() -> str:
    """Return a test Joplin API token."""
    return TEST_TOKEN


@pytest.fixture
def test_server_url() -> str:
    """Return a test Joplin server URL."""
    return TEST_SERVER_URL


@pytest.fixture
def sample_note_data() -> Dict[str, Any]:
    """Return sample note data for testing."""
    return SAMPLE_NOTE_DATA.copy()


@pytest.fixture
def sample_notebook_data() -> Dict[str, Any]:
    """Return sample notebook data for testing."""
    return SAMPLE_NOTEBOOK_DATA.copy()


@pytest.fixture
def sample_tag_data() -> Dict[str, Any]:
    """Return sample tag data for testing."""
    return SAMPLE_TAG_DATA.copy()


@pytest.fixture
def sample_search_result() -> Dict[str, Any]:
    """Return sample search result data for testing."""
    return SAMPLE_SEARCH_RESULT.copy()


@pytest.fixture
def multiple_notes_data() -> List[Dict[str, Any]]:
    """Return multiple sample notes for testing pagination and bulk operations."""
    notes = []
    for i in range(5):
        note = SAMPLE_NOTE_DATA.copy()
        note["id"] = f"1234567890123456789012345678901{i:1d}"
        note["title"] = f"Test Note {i+1}"
        note["body"] = f"This is test note number {i+1} with some content."
        notes.append(note)
    return notes


@pytest.fixture
def multiple_notebooks_data() -> List[Dict[str, Any]]:
    """Return multiple sample notebooks for testing."""
    notebooks = []
    for i in range(3):
        notebook = SAMPLE_NOTEBOOK_DATA.copy()
        notebook["id"] = f"abcdef123456789012345678901234567{i:1d}0"
        notebook["title"] = f"Test Notebook {i+1}"
        notebooks.append(notebook)
    return notebooks


@pytest.fixture
def multiple_tags_data() -> List[Dict[str, Any]]:
    """Return multiple sample tags for testing."""
    tags = []
    tag_names = ["work", "personal", "project-alpha", "important"]
    for i, name in enumerate(tag_names):
        tag = SAMPLE_TAG_DATA.copy()
        tag["id"] = f"fedcba098765432109876543210987654{i:02d}"
        tag["title"] = name
        tags.append(tag)
    return tags


@pytest.fixture
def mock_joppy_client():
    """Create a mock joppy ClientApi instance for testing."""
    mock_client = MagicMock()

    # Mock basic connection methods
    mock_client.ping = MagicMock(return_value="JoplinClipperServer")

    # Mock note operations
    mock_client.get_note = MagicMock()
    mock_client.add_note = MagicMock()
    mock_client.modify_note = MagicMock()
    mock_client.delete_note = MagicMock()
    mock_client.get_all_notes = MagicMock()

    # Mock notebook operations
    mock_client.get_folder = MagicMock()
    mock_client.add_folder = MagicMock()
    mock_client.modify_folder = MagicMock()
    mock_client.delete_folder = MagicMock()
    mock_client.get_all_folders = MagicMock()

    # Mock tag operations
    mock_client.get_tag = MagicMock()
    mock_client.add_tag = MagicMock()
    mock_client.modify_tag = MagicMock()
    mock_client.delete_tag = MagicMock()
    mock_client.get_all_tags = MagicMock()

    # Mock search operations
    mock_client.search = MagicMock()

    return mock_client


@pytest.fixture
def mock_joppy_responses(
    sample_note_data,
    sample_notebook_data,
    sample_tag_data,
    sample_search_result,
    multiple_notes_data,
    multiple_notebooks_data,
    multiple_tags_data,
):
    """Configure mock joppy client with realistic response data."""

    def configure_mock(mock_client):
        # Configure note responses
        mock_client.get_note.return_value = MagicMock(**sample_note_data)
        mock_client.add_note.return_value = sample_note_data["id"]
        mock_client.get_all_notes.return_value = [
            MagicMock(**note) for note in multiple_notes_data
        ]

        # Configure notebook responses
        mock_client.get_folder.return_value = MagicMock(**sample_notebook_data)
        mock_client.add_folder.return_value = sample_notebook_data["id"]
        mock_client.get_all_folders.return_value = [
            MagicMock(**nb) for nb in multiple_notebooks_data
        ]

        # Configure tag responses
        mock_client.get_tag.return_value = MagicMock(**sample_tag_data)
        mock_client.add_tag.return_value = sample_tag_data["id"]
        mock_client.get_all_tags.return_value = [
            MagicMock(**tag) for tag in multiple_tags_data
        ]

        # Configure search responses
        search_results = [MagicMock(**item) for item in sample_search_result["items"]]
        mock_client.search.return_value = search_results

        return mock_client

    return configure_mock


@pytest.fixture
def mock_mcp_server():
    """Create a mock MCP server for testing."""
    mock_server = AsyncMock()
    mock_server.list_tools = AsyncMock()
    mock_server.call_tool = AsyncMock()
    return mock_server


@pytest.fixture
def sample_mcp_tool_request():
    """Return a sample MCP tool request for testing."""
    return {"name": "find_notes", "arguments": {"query": "test", "limit": 10}}


@pytest.fixture
def sample_mcp_tool_response():
    """Return a sample MCP tool response for testing."""
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "results": [
                            {
                                "id": "note123456789abcdef",
                                "title": "Test Note",
                                "body": "This is a **test** note with some markdown content.",
                                "updated_time": 1609545600000,
                            }
                        ],
                        "has_more": False,
                    }
                ),
            }
        ]
    }


@pytest.fixture
def test_config():
    """Return test configuration data."""
    return {
        "joplin_token": TEST_TOKEN,
        "joplin_host": "localhost",
        "joplin_port": 41184,
        "joplin_base_url": TEST_SERVER_URL,
    }


@pytest.fixture(autouse=True)
def reset_mocks():
    """Automatically reset all mocks after each test."""
    yield
    # This runs after each test to ensure clean state


# === ALLOWLIST TEST HELPERS ===
# Shared by test_pathspec_patterns.py, test_notebook_allowlist_access.py,
# and test_integration_allowlist.py.


def make_notebook_map(paths):
    """Build a notebook map from a dict of {notebook_id: "Parent/Child/Leaf"} paths.

    Returns a map suitable for get_notebook_map_cached, where each notebook ID
    maps to {title, parent_id} and the hierarchy is reconstructed from paths.
    """
    from types import SimpleNamespace

    nb_map = {}
    path_to_id = {}

    for nb_id, path_str in paths.items():
        parts = path_str.split("/")
        parent_id = None
        for i, part in enumerate(parts):
            partial_path = "/".join(parts[: i + 1])
            if partial_path not in path_to_id:
                if i == len(parts) - 1:
                    node_id = nb_id
                else:
                    node_id = f"auto_{partial_path.replace('/', '_').lower()}"
                path_to_id[partial_path] = node_id
                nb_map[node_id] = {
                    "title": part,
                    "parent_id": parent_id,
                }
            parent_id = path_to_id[partial_path]

    return nb_map


def mock_client_fn(nb_map):
    """Create a mock client_fn that returns a client whose get_all_notebooks
    returns notebook objects matching the given map."""
    from types import SimpleNamespace

    notebooks = []
    for nb_id, info in nb_map.items():
        nb = SimpleNamespace(
            id=nb_id,
            title=info["title"],
            parent_id=info["parent_id"] or "",
        )
        notebooks.append(nb)

    mock_client = MagicMock()
    mock_client.get_all_notebooks.return_value = notebooks
    return lambda: mock_client


@pytest.fixture
def allowlist_config():
    """Create a JoplinMCPConfig with notebook_allowlist for integration tests.

    Returns a config with a realistic allowlist containing exact path, glob,
    and negation patterns. Tests can override the allowlist attribute as needed.
    """
    from joplin_mcp.config import JoplinMCPConfig

    config = JoplinMCPConfig(
        token="test_token_for_allowlist",
        notebook_allowlist=["Projects", "Projects/*", "AI"],
    )
    return config


@pytest.fixture
def mock_notebook_hierarchy():
    """Set up a mock notebook tree for allowlist integration tests.

    Hierarchy:
        Root
        +-- Projects (id: proj_root_id_00000000000000000)
        |   +-- Work (id: proj_work_id_00000000000000000)
        |   +-- Fun  (id: proj_fun_id_000000000000000000)
        +-- Personal (id: personal_id_000000000000000000)
        |   +-- Diary (id: diary_id_00000000000000000000)
        +-- AI (id: ai_id_000000000000000000000000)

    Returns a dict with:
        - notebooks: list of SimpleNamespace objects
        - nb_map: dict mapping id -> {title, parent_id}
        - ids: dict mapping friendly name -> id
    """
    from types import SimpleNamespace

    ids = {
        "Projects": "proj_root_id_00000000000000000",
        "Work": "proj_work_id_00000000000000000",
        "Fun": "proj_fun_id_000000000000000000",
        "Personal": "personal_id_000000000000000000",
        "Diary": "diary_id_00000000000000000000",
        "AI": "ai_id_000000000000000000000000",
    }

    notebooks = [
        SimpleNamespace(id=ids["Projects"], title="Projects", parent_id=""),
        SimpleNamespace(id=ids["Work"], title="Work", parent_id=ids["Projects"]),
        SimpleNamespace(id=ids["Fun"], title="Fun", parent_id=ids["Projects"]),
        SimpleNamespace(id=ids["Personal"], title="Personal", parent_id=""),
        SimpleNamespace(id=ids["Diary"], title="Diary", parent_id=ids["Personal"]),
        SimpleNamespace(id=ids["AI"], title="AI", parent_id=""),
    ]

    nb_map = {}
    for nb in notebooks:
        nb_map[nb.id] = {
            "title": nb.title,
            "parent_id": nb.parent_id or None,
        }

    return {"notebooks": notebooks, "nb_map": nb_map, "ids": ids}


@pytest.fixture(autouse=True)
def _no_notebook_allowlist():
    """Disable notebook allowlist for all tests by default.

    This prevents any real allowlist configuration from leaking into tests.
    Tests that need an allowlist should patch _module_config themselves.
    """
    from unittest.mock import patch

    targets = [
        "joplin_mcp.tools.notes._module_config",
        "joplin_mcp.tools.notebooks._module_config",
        "joplin_mcp.tools.tags._module_config",
    ]
    patches = []
    for target in targets:
        try:
            p = patch(target)
            mock_cfg = p.start()
            mock_cfg.has_notebook_allowlist = False
            mock_cfg.notebook_allowlist = None
            # Preserve other config attributes that tools may need
            mock_cfg.should_show_content.return_value = True
            mock_cfg.should_show_full_content.return_value = True
            mock_cfg.get_max_preview_length.return_value = 300
            mock_cfg.is_smart_toc_enabled.return_value = False
            mock_cfg.get_smart_toc_threshold.return_value = 2000
            mock_cfg.tools = {}
            patches.append(p)
        except ModuleNotFoundError:
            continue
        except Exception as exc:
            pytest.fail(f"Failed to patch {target} in _no_notebook_allowlist: {exc}")
    yield
    for p in patches:
        p.stop()


@pytest.fixture
def anyio_backend():
    """Configure anyio backend for async testing."""
    return "asyncio"


# Custom pytest markers for test categorization
pytest_plugins = []


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary config file for testing."""
    config_data = {"joplin": {"token": TEST_TOKEN, "host": "localhost", "port": 41184}}
    config_file = tmp_path / "test_config.json"
    config_file.write_text(json.dumps(config_data, indent=2))
    return config_file
