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


# === Tests for path-based notebook resolution ===


def test_resolve_notebook_by_path_simple():
    """Test _resolve_notebook_by_path with a simple single-level path."""
    from unittest.mock import patch
    from joplin_mcp.notebook_utils import _resolve_notebook_by_path

    mock_map = {
        "nb1": {"title": "Work", "parent_id": None},
        "nb2": {"title": "Personal", "parent_id": None},
    }

    with patch("joplin_mcp.notebook_utils.notebook_resolver.get_map", return_value=mock_map):
        result = _resolve_notebook_by_path("Work")
        assert result == "nb1"


def test_resolve_notebook_by_path_nested():
    """Test _resolve_notebook_by_path with nested path like 'Parent/Child'."""
    from unittest.mock import patch
    from joplin_mcp.notebook_utils import _resolve_notebook_by_path

    mock_map = {
        "parent1": {"title": "Project A", "parent_id": None},
        "parent2": {"title": "Project B", "parent_id": None},
        "child1": {"title": "tasks", "parent_id": "parent1"},
        "child2": {"title": "tasks", "parent_id": "parent2"},
    }

    with patch("joplin_mcp.notebook_utils.notebook_resolver.get_map", return_value=mock_map):
        # Should find the correct 'tasks' notebook under 'Project A'
        result = _resolve_notebook_by_path("Project A/tasks")
        assert result == "child1"

        # Should find the correct 'tasks' notebook under 'Project B'
        result = _resolve_notebook_by_path("Project B/tasks")
        assert result == "child2"


def test_resolve_notebook_by_path_deeply_nested():
    """Test _resolve_notebook_by_path with deeply nested path."""
    from unittest.mock import patch
    from joplin_mcp.notebook_utils import _resolve_notebook_by_path

    mock_map = {
        "root": {"title": "Projects", "parent_id": None},
        "mid": {"title": "Work", "parent_id": "root"},
        "leaf": {"title": "Tasks", "parent_id": "mid"},
    }

    with patch("joplin_mcp.notebook_utils.notebook_resolver.get_map", return_value=mock_map):
        result = _resolve_notebook_by_path("Projects/Work/Tasks")
        assert result == "leaf"


def test_resolve_notebook_by_path_case_insensitive():
    """Test _resolve_notebook_by_path is case-insensitive."""
    from unittest.mock import patch
    from joplin_mcp.notebook_utils import _resolve_notebook_by_path

    mock_map = {
        "nb1": {"title": "Work Projects", "parent_id": None},
    }

    with patch("joplin_mcp.notebook_utils.notebook_resolver.get_map", return_value=mock_map):
        result = _resolve_notebook_by_path("work projects")
        assert result == "nb1"
        result = _resolve_notebook_by_path("WORK PROJECTS")
        assert result == "nb1"


def test_resolve_notebook_by_path_not_found():
    """Test _resolve_notebook_by_path raises ValueError when notebook not found."""
    from unittest.mock import patch
    from joplin_mcp.notebook_utils import _resolve_notebook_by_path

    mock_map = {
        "nb1": {"title": "Work", "parent_id": None},
    }

    with patch("joplin_mcp.notebook_utils.notebook_resolver.get_map", return_value=mock_map):
        with pytest.raises(ValueError) as exc_info:
            _resolve_notebook_by_path("NonExistent/tasks")
        assert "NonExistent" in str(exc_info.value)
        assert "not found" in str(exc_info.value)


def test_resolve_notebook_by_path_empty():
    """Test _resolve_notebook_by_path raises ValueError for empty path."""
    from joplin_mcp.notebook_utils import _resolve_notebook_by_path

    with pytest.raises(ValueError) as exc_info:
        _resolve_notebook_by_path("")
    assert "Empty notebook path" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        _resolve_notebook_by_path("   /   /   ")
    assert "Empty notebook path" in str(exc_info.value)


def test_resolve_notebook_by_path_handles_whitespace():
    """Test _resolve_notebook_by_path handles whitespace in path components."""
    from unittest.mock import patch
    from joplin_mcp.notebook_utils import _resolve_notebook_by_path

    mock_map = {
        "nb1": {"title": "Work", "parent_id": None},
        "nb2": {"title": "Tasks", "parent_id": "nb1"},
    }

    with patch("joplin_mcp.notebook_utils.notebook_resolver.get_map", return_value=mock_map):
        # Extra whitespace around components should be handled
        result = _resolve_notebook_by_path("  Work  /  Tasks  ")
        assert result == "nb2"


def test_get_notebook_id_by_name_uses_path_for_slash():
    """Test get_notebook_id_by_name uses path resolution when '/' is present."""
    from unittest.mock import patch
    from joplin_mcp.notebook_utils import get_notebook_id_by_name

    mock_map = {
        "parent": {"title": "Projects", "parent_id": None},
        "child": {"title": "Work", "parent_id": "parent"},
    }

    with patch("joplin_mcp.notebook_utils.notebook_resolver.get_map", return_value=mock_map):
        result = get_notebook_id_by_name("Projects/Work")
        assert result == "child"


# === Tests for notebook suggestions ===


def test_find_notebook_suggestions_basic():
    """Test _find_notebook_suggestions returns matching notebooks."""
    from joplin_mcp.notebook_utils import _find_notebook_suggestions

    mock_map = {
        "nb1": {"title": "Personal", "parent_id": None},
        "nb2": {"title": "Work", "parent_id": None},
        "nb3": {"title": "personal-notes", "parent_id": None},
    }

    suggestions = _find_notebook_suggestions("personal", mock_map)
    assert len(suggestions) == 2
    assert "Personal" in suggestions
    assert "personal-notes" in suggestions


def test_find_notebook_suggestions_returns_full_paths():
    """Test _find_notebook_suggestions returns full paths for nested notebooks."""
    from joplin_mcp.notebook_utils import _find_notebook_suggestions

    mock_map = {
        "gtd": {"title": "GTD", "parent_id": None},
        "projects": {"title": "projects", "parent_id": "gtd"},
        "refs": {"title": "references", "parent_id": "gtd"},
        "personal1": {"title": "personal", "parent_id": "projects"},
        "personal2": {"title": "personal", "parent_id": "refs"},
    }

    suggestions = _find_notebook_suggestions("personal", mock_map)
    assert len(suggestions) == 2
    assert "GTD/projects/personal" in suggestions
    assert "GTD/references/personal" in suggestions


def test_find_notebook_suggestions_limits_results():
    """Test _find_notebook_suggestions respects limit parameter."""
    from joplin_mcp.notebook_utils import _find_notebook_suggestions

    mock_map = {f"nb{i}": {"title": f"test{i}", "parent_id": None} for i in range(10)}

    suggestions = _find_notebook_suggestions("test", mock_map, limit=3)
    assert len(suggestions) == 3


def test_find_notebook_suggestions_exact_match_first():
    """Test _find_notebook_suggestions puts exact matches first."""
    from joplin_mcp.notebook_utils import _find_notebook_suggestions

    mock_map = {
        "nb1": {"title": "personal-notes", "parent_id": None},
        "nb2": {"title": "personal", "parent_id": None},
        "nb3": {"title": "my-personal-stuff", "parent_id": None},
    }

    suggestions = _find_notebook_suggestions("personal", mock_map)
    assert suggestions[0] == "personal"  # Exact match first


def test_get_notebook_id_by_name_flat_hides_denied_notebooks(override_config):
    """Flat-name not-found error must not leak titles of allowlist-denied notebooks."""
    from unittest.mock import patch
    from joplin_mcp.notebook_utils import get_notebook_id_by_name

    # Two top-level notebooks; only "Work" is allowlisted.
    full_map = {
        "work_id": {"title": "Work", "parent_id": None},
        "secret_id": {"title": "Secrets", "parent_id": None},
    }

    with override_config(notebook_allowlist=["Work"]), patch(
        "joplin_mcp.notebook_utils.notebook_resolver.get_map",
        return_value=full_map,
    ):
        with pytest.raises(ValueError) as exc_info:
            get_notebook_id_by_name("NonExistent")
        msg = str(exc_info.value)
        assert "Secrets" not in msg
        assert "Available notebooks" not in msg


def test_get_notebook_id_by_name_flat_resolves_allowlisted(override_config):
    """Flat name in the allowlisted set must still resolve."""
    from unittest.mock import patch
    from joplin_mcp.notebook_utils import get_notebook_id_by_name

    full_map = {
        "work_id": {"title": "Work", "parent_id": None},
        "secret_id": {"title": "Secrets", "parent_id": None},
    }

    with override_config(notebook_allowlist=["Work"]), patch(
        "joplin_mcp.notebook_utils.notebook_resolver.get_map",
        return_value=full_map,
    ):
        assert get_notebook_id_by_name("Work") == "work_id"


def test_get_notebook_id_by_name_flat_multi_match_only_lists_accessible(override_config):
    """Multi-match disambiguation must not surface denied notebook paths."""
    from unittest.mock import patch
    from joplin_mcp.notebook_utils import get_notebook_id_by_name

    # Two notebooks both named "Inbox": one under allowed Work, one under denied Personal.
    full_map = {
        "work_id": {"title": "Work", "parent_id": None},
        "work_inbox_id": {"title": "Inbox", "parent_id": "work_id"},
        "personal_id": {"title": "Personal", "parent_id": None},
        "personal_inbox_id": {"title": "Inbox", "parent_id": "personal_id"},
    }

    with override_config(notebook_allowlist=["Work", "Work/**"]), patch(
        "joplin_mcp.notebook_utils.notebook_resolver.get_map",
        return_value=full_map,
    ):
        # Only Work/Inbox is accessible — single match, should resolve cleanly.
        assert get_notebook_id_by_name("Inbox") == "work_inbox_id"


def test_get_notebook_id_by_name_flat_multi_match_disambiguation_filtered(override_config):
    """When multiple accessible notebooks share a name, paths come from the filtered map."""
    from unittest.mock import patch
    from joplin_mcp.notebook_utils import get_notebook_id_by_name

    full_map = {
        "work_id": {"title": "Work", "parent_id": None},
        "work_inbox_id": {"title": "Inbox", "parent_id": "work_id"},
        "ai_id": {"title": "AI", "parent_id": None},
        "ai_inbox_id": {"title": "Inbox", "parent_id": "ai_id"},
        "personal_id": {"title": "Personal", "parent_id": None},
        "personal_inbox_id": {"title": "Inbox", "parent_id": "personal_id"},
    }

    with override_config(
        notebook_allowlist=["Work", "Work/**", "AI", "AI/**"]
    ), patch(
        "joplin_mcp.notebook_utils.notebook_resolver.get_map",
        return_value=full_map,
    ):
        with pytest.raises(ValueError) as exc_info:
            get_notebook_id_by_name("Inbox")
        msg = str(exc_info.value)
        assert "Work/Inbox" in msg
        assert "AI/Inbox" in msg
        assert "Personal/Inbox" not in msg
        assert "Personal" not in msg


def test_resolve_notebook_by_path_suggests_on_not_found():
    """Test _resolve_notebook_by_path provides suggestions when path component not found."""
    from unittest.mock import patch
    from joplin_mcp.notebook_utils import _resolve_notebook_by_path

    mock_map = {
        "gtd": {"title": "GTD", "parent_id": None},
        "projects": {"title": "projects", "parent_id": "gtd"},
    }

    with patch("joplin_mcp.notebook_utils.notebook_resolver.get_map", return_value=mock_map):
        with pytest.raises(ValueError) as exc_info:
            _resolve_notebook_by_path("projects/personal")
        error_msg = str(exc_info.value)
        assert "not found" in error_msg
        assert "Did you mean" in error_msg
        assert "GTD/projects" in error_msg


# === Tests for notebook_utils edge cases ===


def test_build_notebook_map_skips_notebooks_without_id():
    """Test _build_notebook_map skips notebooks without id."""
    from joplin_mcp.notebook_utils import _build_notebook_map
    from unittest.mock import MagicMock

    # Notebook with no id attribute
    nb_no_id = MagicMock(spec=[])  # No attributes
    nb_with_id = MagicMock()
    nb_with_id.id = "nb1"
    nb_with_id.title = "Test"
    nb_with_id.parent_id = None

    result = _build_notebook_map([nb_no_id, nb_with_id])
    assert "nb1" in result
    assert len(result) == 1


def test_build_notebook_map_handles_exception():
    """Test _build_notebook_map handles exceptions gracefully."""
    from joplin_mcp.notebook_utils import _build_notebook_map

    # Object that raises exception when accessed
    class BadNotebook:
        @property
        def id(self):
            raise RuntimeError("Bad notebook")

    good_nb = type("Notebook", (), {"id": "nb1", "title": "Good", "parent_id": None})()
    result = _build_notebook_map([BadNotebook(), good_nb])
    assert "nb1" in result


def test_compute_notebook_path_returns_none_for_empty():
    """Test _compute_notebook_path returns None for empty notebook_id."""
    from joplin_mcp.notebook_utils import _compute_notebook_path

    assert _compute_notebook_path(None, {}) is None
    assert _compute_notebook_path("", {}) is None


def test_invalidate_resets_resolver_cache():
    """NotebookResolver.invalidate clears the cached map and allowlist specs."""
    from joplin_mcp.notebook_utils import notebook_resolver

    # Seed cache state via the resolver's instance attrs
    notebook_resolver._map = {"test": "value"}
    notebook_resolver._map_built_at = 999.0
    notebook_resolver._allowlist_entries = ["Work"]
    notebook_resolver._allowlist_built_at = 999.0

    notebook_resolver.invalidate()

    assert notebook_resolver._map is None
    assert notebook_resolver._map_built_at == 0.0
    assert notebook_resolver._allowlist_entries is None
    assert notebook_resolver._allowlist_built_at == 0.0


def test_get_notebook_cache_ttl_from_env():
    """Test _get_notebook_cache_ttl reads from environment."""
    import os
    from joplin_mcp.notebook_utils import _get_notebook_cache_ttl

    # Test with valid env value
    os.environ["JOPLIN_MCP_NOTEBOOK_CACHE_TTL"] = "120"
    assert _get_notebook_cache_ttl() == 120

    # Test clamping to max
    os.environ["JOPLIN_MCP_NOTEBOOK_CACHE_TTL"] = "9999"
    assert _get_notebook_cache_ttl() == 3600

    # Test clamping to min
    os.environ["JOPLIN_MCP_NOTEBOOK_CACHE_TTL"] = "1"
    assert _get_notebook_cache_ttl() == 5

    # Test invalid value falls back to default
    os.environ["JOPLIN_MCP_NOTEBOOK_CACHE_TTL"] = "invalid"
    assert _get_notebook_cache_ttl() == 90

    # Cleanup
    del os.environ["JOPLIN_MCP_NOTEBOOK_CACHE_TTL"]


# === Tests for register_tools (config-driven tool gating) ===


def _all_enabled_config():
    """Build a JoplinMCPConfig with an empty tools dict so every registry
    entry resolves to ``True`` via ``config.tools.get(name, True)``."""
    from joplin_mcp.config import JoplinMCPConfig

    cfg = JoplinMCPConfig()
    cfg.tools = {}
    return cfg


@pytest.fixture
def _restore_all_tools():
    """Re-register every tool after a gating test mutates ``mcp``.

    Uses an all-enabled config so subsequent tests (including ones that
    don't touch register_tools at all) see the full tool surface that
    eager decoration originally produced.
    """
    yield
    from joplin_mcp.fastmcp_server import mcp, register_tools

    register_tools(mcp, _all_enabled_config())


@pytest.mark.asyncio
async def test_register_tools_enables_all_by_default(_restore_all_tools):
    """An empty tools dict means every registry entry resolves True; the
    public MCP client surface lists every one."""
    from joplin_mcp.fastmcp_server import _tool_registry, mcp, register_tools

    enabled = register_tools(mcp, _all_enabled_config())
    assert set(enabled) == {name for name, _ in _tool_registry}

    async with Client(mcp) as client:
        listed = {tool.name for tool in await client.list_tools()}
    assert listed == set(enabled)


@pytest.mark.asyncio
async def test_register_tools_removes_disabled(_restore_all_tools):
    """A tool flagged False in config disappears from both the internal
    manager and the public MCP client surface."""
    from joplin_mcp.fastmcp_server import mcp, register_tools

    cfg = _all_enabled_config()
    cfg.tools["get_note"] = False
    enabled = register_tools(mcp, cfg)

    assert "get_note" not in enabled
    async with Client(mcp) as client:
        listed = {tool.name for tool in await client.list_tools()}
    assert "get_note" not in listed
    # Sanity: another tool that's not disabled is still present.
    assert "list_notebooks" in listed


@pytest.mark.asyncio
async def test_register_tools_is_idempotent_under_recall(_restore_all_tools):
    """Disabling then re-enabling restores the tool; register_tools is the
    only state machine, no leftover state from prior calls."""
    from joplin_mcp.fastmcp_server import mcp, register_tools

    cfg_off = _all_enabled_config()
    cfg_off.tools["get_note"] = False
    register_tools(mcp, cfg_off)
    async with Client(mcp) as client:
        listed_off = {tool.name for tool in await client.list_tools()}
    assert "get_note" not in listed_off

    register_tools(mcp, _all_enabled_config())
    async with Client(mcp) as client:
        listed_on = {tool.name for tool in await client.list_tools()}
    assert "get_note" in listed_on


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
