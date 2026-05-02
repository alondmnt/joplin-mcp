"""Integration tests for end-to-end notebook allowlist workflow.

These tests exercise the full stack from config through notebook_utils
through tools, with only the Joplin API mocked. They verify:
- D2: Hierarchical access (parent allowlist grants child access)
- D3: Startup validation (server starts with valid/invalid allowlist)
- D4: All enforcement points (full tool chain exercised)
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from joplin_mcp.config import JoplinMCPConfig
from joplin_mcp.notebook_utils import (
    filter_accessible_notebooks,
    invalidate_notebook_map_cache,
    is_notebook_accessible,
    validate_notebook_access,
    validate_allowlist_at_startup,
)


def _get_tool_fn(tool):
    """Get the underlying function from a tool (handles both wrapped and unwrapped)."""
    if hasattr(tool, "fn"):
        return tool.fn
    return tool


def _make_mock_client(notebooks):
    """Create a mock Joplin client that returns the given notebook list."""
    client = MagicMock()
    client.get_all_notebooks.return_value = notebooks
    client.ping.return_value = "JoplinClipperServer"
    return client


# ---------------------------------------------------------------------------
# Test 1: End-to-end allowlist workflow
# Config -> startup validation -> tool call -> access check
# ---------------------------------------------------------------------------


class TestEndToEndAllowlistWorkflow:
    """Integration test: config with allowlist, startup, tool calls, access checks."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_config_to_access_check_flow(self, mock_notebook_hierarchy):
        """Full workflow: create config, validate startup, check access.

        Exercises: JoplinMCPConfig -> validate_allowlist_at_startup ->
        is_notebook_accessible for allowed and denied notebooks.
        """
        ids = mock_notebook_hierarchy["ids"]
        notebooks = mock_notebook_hierarchy["notebooks"]
        client = _make_mock_client(notebooks)

        # Step 1: Create config with allowlist
        config = JoplinMCPConfig(
            token="test_token",
            notebook_allowlist=["Projects", "AI"],
        )
        assert config.has_notebook_allowlist is True
        assert config.notebook_allowlist == ["Projects", "AI"]

        # Step 2: Validate at startup (should not raise)
        validate_allowlist_at_startup(config, client)

        # Step 3: Check access for allowlisted notebooks
        client_fn = lambda: client  # noqa: E731
        invalidate_notebook_map_cache()

        assert is_notebook_accessible(
            ids["Projects"], allowlist_entries=config.notebook_allowlist,
            client_fn=client_fn,
        ) is True

        assert is_notebook_accessible(
            ids["AI"], allowlist_entries=config.notebook_allowlist,
            client_fn=client_fn,
        ) is True

        # Step 4: Check access denied for non-allowlisted notebooks
        assert is_notebook_accessible(
            ids["Personal"], allowlist_entries=config.notebook_allowlist,
            client_fn=client_fn,
        ) is False

        assert is_notebook_accessible(
            ids["Diary"], allowlist_entries=config.notebook_allowlist,
            client_fn=client_fn,
        ) is False

    @pytest.mark.asyncio
    async def test_tool_call_with_allowlist_allowed(self, mock_notebook_hierarchy):
        """Tool call succeeds for note in allowlisted notebook."""
        ids = mock_notebook_hierarchy["ids"]
        notebooks = mock_notebook_hierarchy["notebooks"]
        client = _make_mock_client(notebooks)
        client_fn = lambda: client  # noqa: E731

        # Mock note in an allowlisted notebook (Projects/Work)
        mock_note = MagicMock()
        mock_note.parent_id = ids["Work"]
        mock_note.title = "Work Note"
        mock_note.body = "Work content"
        mock_note.id = "a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0"
        mock_note.created_time = 1609459200000
        mock_note.updated_time = 1609545600000
        mock_note.is_todo = 0
        mock_note.todo_completed = 0
        client.get_note.return_value = mock_note

        allowlist = ["Projects"]

        with (
            patch("joplin_mcp.tools.notes._module_config") as mock_cfg,
            patch("joplin_mcp.tools.notes.get_joplin_client", return_value=client),
            patch(
                "joplin_mcp.tools.notes.validate_notebook_access",
                side_effect=lambda nb_id, allowlist_entries=None, **kw: (
                    # Use real validation with our mock client
                    validate_notebook_access(
                        nb_id,
                        allowlist_entries=allowlist_entries,
                        client_fn=client_fn,
                    )
                ),
            ),
        ):
            mock_cfg.has_notebook_allowlist = True
            mock_cfg.notebook_allowlist = allowlist
            mock_cfg.should_show_content.return_value = True
            mock_cfg.should_show_full_content.return_value = True
            mock_cfg.get_max_preview_length.return_value = 300
            mock_cfg.is_smart_toc_enabled.return_value = False
            mock_cfg.get_smart_toc_threshold.return_value = 2000
            mock_cfg.tools = {}

            from joplin_mcp.tools.notes import get_note

            fn = _get_tool_fn(get_note)
            result = await fn(note_id="a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0")

            assert "Work Note" in result

    @pytest.mark.asyncio
    async def test_tool_call_with_allowlist_denied(self, mock_notebook_hierarchy):
        """Tool call raises ValueError for note in non-allowlisted notebook."""
        ids = mock_notebook_hierarchy["ids"]
        notebooks = mock_notebook_hierarchy["notebooks"]
        client = _make_mock_client(notebooks)
        client_fn = lambda: client  # noqa: E731

        # Mock note in a non-allowlisted notebook (Personal/Diary)
        mock_note = MagicMock()
        mock_note.parent_id = ids["Diary"]
        client.get_note.return_value = mock_note

        allowlist = ["Projects"]

        with (
            patch("joplin_mcp.tools.notes._module_config") as mock_cfg,
            patch("joplin_mcp.tools.notes.get_joplin_client", return_value=client),
            patch(
                "joplin_mcp.tools.notes.validate_notebook_access",
                side_effect=lambda nb_id, allowlist_entries=None, **kw: (
                    validate_notebook_access(
                        nb_id,
                        allowlist_entries=allowlist_entries,
                        client_fn=client_fn,
                    )
                ),
            ),
        ):
            mock_cfg.has_notebook_allowlist = True
            mock_cfg.notebook_allowlist = allowlist
            mock_cfg.should_show_content.return_value = True
            mock_cfg.should_show_full_content.return_value = True
            mock_cfg.get_max_preview_length.return_value = 300
            mock_cfg.is_smart_toc_enabled.return_value = False
            mock_cfg.get_smart_toc_threshold.return_value = 2000
            mock_cfg.tools = {}

            from joplin_mcp.tools.notes import get_note

            fn = _get_tool_fn(get_note)
            with pytest.raises(ValueError, match="Notebook not accessible"):
                await fn(note_id="b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1")


# ---------------------------------------------------------------------------
# Test 2: Hierarchical access integration (D2)
# Allowlist parent, verify child notebook note operations work
# ---------------------------------------------------------------------------


class TestHierarchicalAccessIntegration:
    """Integration test: allowlist parent grants access to child notebook notes."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_parent_allowlist_grants_child_access(self, mock_notebook_hierarchy):
        """Allowlisting 'Projects' grants access to notes in Projects/Work and Projects/Fun."""
        ids = mock_notebook_hierarchy["ids"]
        notebooks = mock_notebook_hierarchy["notebooks"]
        client = _make_mock_client(notebooks)
        client_fn = lambda: client  # noqa: E731

        allowlist = ["Projects"]

        # Direct child: Projects/Work
        assert is_notebook_accessible(
            ids["Work"], allowlist_entries=allowlist, client_fn=client_fn,
        ) is True

        invalidate_notebook_map_cache()
        # Direct child: Projects/Fun
        assert is_notebook_accessible(
            ids["Fun"], allowlist_entries=allowlist, client_fn=client_fn,
        ) is True

        invalidate_notebook_map_cache()
        # Non-child: Personal
        assert is_notebook_accessible(
            ids["Personal"], allowlist_entries=allowlist, client_fn=client_fn,
        ) is False

    def test_deep_hierarchy_access(self):
        """Allowlisting top-level grants access through multiple levels."""
        invalidate_notebook_map_cache()

        # Build a 3-level hierarchy: Root > Middle > Deep
        notebooks = [
            SimpleNamespace(id="root_id_000000000000000000000", title="Root", parent_id=""),
            SimpleNamespace(id="mid_id_0000000000000000000000", title="Middle", parent_id="root_id_000000000000000000000"),
            SimpleNamespace(id="deep_id_000000000000000000000", title="Deep", parent_id="mid_id_0000000000000000000000"),
        ]
        client = _make_mock_client(notebooks)
        client_fn = lambda: client  # noqa: E731

        # Allowlist only "Root" -- should grant access to Root/Middle/Deep
        assert is_notebook_accessible(
            "deep_id_000000000000000000000",
            allowlist_entries=["Root"],
            client_fn=client_fn,
        ) is True

    @pytest.mark.asyncio
    async def test_create_note_in_child_of_allowlisted_parent(
        self, mock_notebook_hierarchy
    ):
        """create_note succeeds when target notebook is child of allowlisted parent."""
        ids = mock_notebook_hierarchy["ids"]
        notebooks = mock_notebook_hierarchy["notebooks"]
        client = _make_mock_client(notebooks)
        client.add_note.return_value = "new_note_in_work_id"
        client_fn = lambda: client  # noqa: E731

        allowlist = ["Projects"]

        with (
            patch("joplin_mcp.tools.notes._module_config") as mock_cfg,
            patch("joplin_mcp.tools.notes.get_joplin_client", return_value=client),
            patch(
                "joplin_mcp.tools.notes.get_notebook_id_by_name",
                return_value=ids["Work"],
            ),
            patch(
                "joplin_mcp.tools.notes.validate_notebook_access",
                side_effect=lambda nb_id, allowlist_entries=None, **kw: (
                    validate_notebook_access(
                        nb_id,
                        allowlist_entries=allowlist_entries,
                        client_fn=client_fn,
                    )
                ),
            ),
        ):
            mock_cfg.has_notebook_allowlist = True
            mock_cfg.notebook_allowlist = allowlist
            mock_cfg.should_show_content.return_value = True
            mock_cfg.should_show_full_content.return_value = True
            mock_cfg.get_max_preview_length.return_value = 300
            mock_cfg.is_smart_toc_enabled.return_value = False
            mock_cfg.get_smart_toc_threshold.return_value = 2000
            mock_cfg.tools = {}

            from joplin_mcp.tools.notes import create_note

            fn = _get_tool_fn(create_note)
            result = await fn(title="Work Task", notebook_name="Work", body="task body")
            assert "SUCCESS" in result

    @pytest.mark.asyncio
    async def test_create_note_in_non_child_denied(self, mock_notebook_hierarchy):
        """create_note fails when target notebook is NOT a child of allowlisted parent."""
        ids = mock_notebook_hierarchy["ids"]
        notebooks = mock_notebook_hierarchy["notebooks"]
        client = _make_mock_client(notebooks)
        client_fn = lambda: client  # noqa: E731

        allowlist = ["Projects"]

        with (
            patch("joplin_mcp.tools.notes._module_config") as mock_cfg,
            patch("joplin_mcp.tools.notes.get_joplin_client", return_value=client),
            patch(
                "joplin_mcp.tools.notes.get_notebook_id_by_name",
                return_value=ids["Diary"],
            ),
            patch(
                "joplin_mcp.tools.notes.validate_notebook_access",
                side_effect=lambda nb_id, allowlist_entries=None, **kw: (
                    validate_notebook_access(
                        nb_id,
                        allowlist_entries=allowlist_entries,
                        client_fn=client_fn,
                    )
                ),
            ),
        ):
            mock_cfg.has_notebook_allowlist = True
            mock_cfg.notebook_allowlist = allowlist
            mock_cfg.should_show_content.return_value = True
            mock_cfg.should_show_full_content.return_value = True
            mock_cfg.get_max_preview_length.return_value = 300
            mock_cfg.is_smart_toc_enabled.return_value = False
            mock_cfg.get_smart_toc_threshold.return_value = 2000
            mock_cfg.tools = {}

            from joplin_mcp.tools.notes import create_note

            fn = _get_tool_fn(create_note)
            with pytest.raises(ValueError, match="Notebook not accessible"):
                await fn(title="Diary Entry", notebook_name="Diary", body="private")


# ---------------------------------------------------------------------------
# Test 3: Backward compatibility (no allowlist configured)
# All operations succeed when allowlist is not set
# ---------------------------------------------------------------------------


class TestBackwardCompatibilityIntegration:
    """Integration test: no allowlist configured, all tools work normally."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    @pytest.mark.asyncio
    async def test_get_note_works_without_allowlist(self):
        """get_note succeeds for any notebook when no allowlist is configured."""
        mock_note = MagicMock()
        mock_note.parent_id = "any_notebook_id_0000000000000000"
        mock_note.title = "Any Note"
        mock_note.body = "content"
        mock_note.id = "12345678901234567890123456789012"
        mock_note.created_time = 1609459200000
        mock_note.updated_time = 1609545600000
        mock_note.is_todo = 0
        mock_note.todo_completed = 0

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note

        with (
            patch("joplin_mcp.tools.notes._module_config") as mock_cfg,
            patch("joplin_mcp.tools.notes.get_joplin_client", return_value=mock_client),
        ):
            mock_cfg.has_notebook_allowlist = False
            mock_cfg.notebook_allowlist = None
            mock_cfg.should_show_content.return_value = True
            mock_cfg.should_show_full_content.return_value = True
            mock_cfg.get_max_preview_length.return_value = 300
            mock_cfg.is_smart_toc_enabled.return_value = False
            mock_cfg.get_smart_toc_threshold.return_value = 2000
            mock_cfg.tools = {}

            from joplin_mcp.tools.notes import get_note

            fn = _get_tool_fn(get_note)
            result = await fn(note_id="12345678901234567890123456789012")
            assert "Any Note" in result

    @pytest.mark.asyncio
    async def test_create_note_works_without_allowlist(self):
        """create_note succeeds for any notebook when no allowlist is configured."""
        mock_client = MagicMock()
        mock_client.add_note.return_value = "new_note_id"

        with (
            patch("joplin_mcp.tools.notes._module_config") as mock_cfg,
            patch("joplin_mcp.tools.notes.get_joplin_client", return_value=mock_client),
            patch(
                "joplin_mcp.tools.notes.get_notebook_id_by_name",
                return_value="any_nb_id",
            ),
        ):
            mock_cfg.has_notebook_allowlist = False
            mock_cfg.notebook_allowlist = None
            mock_cfg.should_show_content.return_value = True
            mock_cfg.should_show_full_content.return_value = True
            mock_cfg.get_max_preview_length.return_value = 300
            mock_cfg.is_smart_toc_enabled.return_value = False
            mock_cfg.get_smart_toc_threshold.return_value = 2000
            mock_cfg.tools = {}

            from joplin_mcp.tools.notes import create_note

            fn = _get_tool_fn(create_note)
            result = await fn(title="Free Note", notebook_name="Anywhere", body="hi")
            assert "SUCCESS" in result

    @pytest.mark.asyncio
    async def test_list_notebooks_returns_all_without_allowlist(self):
        """list_notebooks returns all notebooks when no allowlist is configured."""
        mock_notebooks = [
            MagicMock(id="nb1", title="Work"),
            MagicMock(id="nb2", title="Personal"),
            MagicMock(id="nb3", title="Secret"),
        ]
        mock_client = MagicMock()
        mock_client.get_all_notebooks.return_value = mock_notebooks

        with (
            patch("joplin_mcp.tools.notebooks._module_config") as mock_cfg,
            patch(
                "joplin_mcp.tools.notebooks.get_joplin_client",
                return_value=mock_client,
            ),
            patch("joplin_mcp.tools.notebooks.format_item_list") as mock_format,
        ):
            mock_cfg.has_notebook_allowlist = False
            mock_cfg.notebook_allowlist = None

            mock_format.return_value = "ALL_NOTEBOOKS_LISTED"

            from joplin_mcp.tools.notebooks import list_notebooks

            fn = _get_tool_fn(list_notebooks)
            result = await fn()

            assert result == "ALL_NOTEBOOKS_LISTED"
            # format_item_list should have received all 3 notebooks
            from joplin_mcp.fastmcp_server import ItemType

            mock_format.assert_called_once_with(mock_notebooks, ItemType.notebook)

    @pytest.mark.asyncio
    async def test_delete_note_works_without_allowlist(self):
        """delete_note succeeds for any notebook when no allowlist is configured."""
        mock_client = MagicMock()

        with (
            patch("joplin_mcp.tools.notes._module_config") as mock_cfg,
            patch("joplin_mcp.tools.notes.get_joplin_client", return_value=mock_client),
        ):
            mock_cfg.has_notebook_allowlist = False
            mock_cfg.notebook_allowlist = None
            mock_cfg.should_show_content.return_value = True
            mock_cfg.should_show_full_content.return_value = True
            mock_cfg.get_max_preview_length.return_value = 300
            mock_cfg.is_smart_toc_enabled.return_value = False
            mock_cfg.get_smart_toc_threshold.return_value = 2000
            mock_cfg.tools = {}

            from joplin_mcp.tools.notes import delete_note

            fn = _get_tool_fn(delete_note)
            result = await fn(note_id="12345678901234567890123456789012")
            assert "SUCCESS" in result

    def test_config_without_allowlist_property(self):
        """JoplinMCPConfig with no notebook_allowlist has has_notebook_allowlist=False."""
        config = JoplinMCPConfig(token="test_token")
        assert config.has_notebook_allowlist is False
        assert config.notebook_allowlist == JoplinMCPConfig.ALLOW_ALL


# ---------------------------------------------------------------------------
# Test 4: Mixed pattern types
# Allowlist with exact path + glob pattern + ID, verify all work together
# ---------------------------------------------------------------------------


class TestMixedPatternTypesIntegration:
    """Integration test: allowlist with IDs, paths, and globs all work together."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_exact_path_and_glob_combined(self, mock_notebook_hierarchy):
        """Allowlist with exact path 'AI' and glob 'Projects/*' both work."""
        ids = mock_notebook_hierarchy["ids"]
        notebooks = mock_notebook_hierarchy["notebooks"]
        client = _make_mock_client(notebooks)
        client_fn = lambda: client  # noqa: E731

        allowlist = ["AI", "Projects/*"]

        # Exact path match: AI
        assert is_notebook_accessible(
            ids["AI"], allowlist_entries=allowlist, client_fn=client_fn,
        ) is True

        invalidate_notebook_map_cache()
        # Glob match: Projects/Work
        assert is_notebook_accessible(
            ids["Work"], allowlist_entries=allowlist, client_fn=client_fn,
        ) is True

        invalidate_notebook_map_cache()
        # Glob match: Projects/Fun
        assert is_notebook_accessible(
            ids["Fun"], allowlist_entries=allowlist, client_fn=client_fn,
        ) is True

        invalidate_notebook_map_cache()
        # Non-matching: Personal
        assert is_notebook_accessible(
            ids["Personal"], allowlist_entries=allowlist, client_fn=client_fn,
        ) is False

        invalidate_notebook_map_cache()
        # Non-matching: Personal/Diary
        assert is_notebook_accessible(
            ids["Diary"], allowlist_entries=allowlist, client_fn=client_fn,
        ) is False

    def test_negation_with_mixed_patterns(self, mock_notebook_hierarchy):
        """Negation pattern excludes specific child from glob match."""
        ids = mock_notebook_hierarchy["ids"]
        notebooks = mock_notebook_hierarchy["notebooks"]
        client = _make_mock_client(notebooks)
        client_fn = lambda: client  # noqa: E731

        allowlist = ["Projects/*", "!Projects/Fun"]

        # Projects/Work should be accessible
        assert is_notebook_accessible(
            ids["Work"], allowlist_entries=allowlist, client_fn=client_fn,
        ) is True

        invalidate_notebook_map_cache()
        # Projects/Fun should be denied by negation
        assert is_notebook_accessible(
            ids["Fun"], allowlist_entries=allowlist, client_fn=client_fn,
        ) is False

    def test_id_based_allowlist_entry(self):
        """Allowlist with raw 32-char hex notebook ID works alongside path patterns."""
        # Use real 32-char hex IDs so _HEX_ID_RE matches for ID-based allowlisting
        personal_id = "aabbccddee11223344556677aabbccdd"
        ai_id = "11223344556677889900aabbccddeeff"
        projects_id = "ffeeddccbbaa99887766554433221100"

        notebooks = [
            SimpleNamespace(id=projects_id, title="Projects", parent_id=""),
            SimpleNamespace(id=personal_id, title="Personal", parent_id=""),
            SimpleNamespace(id=ai_id, title="AI", parent_id=""),
        ]
        client = _make_mock_client(notebooks)
        client_fn = lambda: client  # noqa: E731

        # Mix a raw hex ID with a path pattern
        allowlist = [personal_id, "AI"]

        # Personal accessible by hex ID
        assert is_notebook_accessible(
            personal_id, allowlist_entries=allowlist, client_fn=client_fn,
        ) is True

        invalidate_notebook_map_cache()
        # AI accessible by path
        assert is_notebook_accessible(
            ai_id, allowlist_entries=allowlist, client_fn=client_fn,
        ) is True

        invalidate_notebook_map_cache()
        # Projects not accessible (not in allowlist)
        assert is_notebook_accessible(
            projects_id, allowlist_entries=allowlist, client_fn=client_fn,
        ) is False

    @pytest.mark.asyncio
    async def test_find_notes_filters_with_mixed_allowlist(
        self, mock_notebook_hierarchy
    ):
        """find_notes returns only notes in notebooks matching mixed allowlist."""
        ids = mock_notebook_hierarchy["ids"]
        notebooks = mock_notebook_hierarchy["notebooks"]
        client = _make_mock_client(notebooks)
        client_fn = lambda: client  # noqa: E731

        note_in_work = MagicMock()
        note_in_work.parent_id = ids["Work"]
        note_in_work.id = "work_note_id_00000000000000000000"
        note_in_work.title = "Work Task"
        note_in_work.updated_time = 1609545600000
        note_in_work.is_todo = 0
        note_in_work.todo_completed = 0

        note_in_ai = MagicMock()
        note_in_ai.parent_id = ids["AI"]
        note_in_ai.id = "ai_note_id_0000000000000000000000"
        note_in_ai.title = "AI Research"
        note_in_ai.updated_time = 1609545600000
        note_in_ai.is_todo = 0
        note_in_ai.todo_completed = 0

        note_in_diary = MagicMock()
        note_in_diary.parent_id = ids["Diary"]
        note_in_diary.id = "diary_note_id_000000000000000000"
        note_in_diary.title = "Private Diary Entry"
        note_in_diary.updated_time = 1609459200000
        note_in_diary.is_todo = 0
        note_in_diary.todo_completed = 0

        client.get_all_notes.return_value = [note_in_work, note_in_ai, note_in_diary]

        allowlist = ["AI", "Projects/*"]

        with (
            patch("joplin_mcp.tools.notes._module_config") as mock_cfg,
            patch("joplin_mcp.tools.notes.get_joplin_client", return_value=client),
            patch(
                "joplin_mcp.tools.notes.is_notebook_accessible",
                side_effect=lambda parent_id, allowlist_entries=None, **kw: (
                    is_notebook_accessible(
                        parent_id,
                        allowlist_entries=allowlist_entries,
                        client_fn=client_fn,
                    )
                ),
            ),
        ):
            mock_cfg.has_notebook_allowlist = True
            mock_cfg.notebook_allowlist = allowlist
            mock_cfg.should_show_content.return_value = True
            mock_cfg.should_show_full_content.return_value = True
            mock_cfg.get_max_preview_length.return_value = 300
            mock_cfg.is_smart_toc_enabled.return_value = False
            mock_cfg.get_smart_toc_threshold.return_value = 2000
            mock_cfg.tools = {}

            from joplin_mcp.tools.notes import find_notes

            fn = _get_tool_fn(find_notes)
            result = await fn(query="*", limit=20)

            assert "Work Task" in result
            assert "AI Research" in result
            assert "Private Diary Entry" not in result


# ---------------------------------------------------------------------------
# Test 5: Startup validation integration (D3)
# Server starts with valid/invalid allowlist configurations
# ---------------------------------------------------------------------------


class TestStartupValidationIntegration:
    """Integration test: startup validation with various allowlist configs."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_startup_with_valid_allowlist(self, mock_notebook_hierarchy):
        """Server starts successfully with valid allowlist entries."""
        notebooks = mock_notebook_hierarchy["notebooks"]
        client = _make_mock_client(notebooks)

        config = JoplinMCPConfig(
            token="test_token",
            notebook_allowlist=["Projects", "AI"],
        )

        # Should not raise
        validate_allowlist_at_startup(config, client)

    def test_startup_with_invalid_entries(self, mock_notebook_hierarchy):
        """Server starts successfully even with unresolvable allowlist entries (D3)."""
        notebooks = mock_notebook_hierarchy["notebooks"]
        client = _make_mock_client(notebooks)

        config = JoplinMCPConfig(
            token="test_token",
            notebook_allowlist=["NonExistent/Path", "GhostNotebook"],
        )

        # Per D3: server always starts, never raises
        validate_allowlist_at_startup(config, client)

    def test_startup_with_no_allowlist(self):
        """Server starts successfully with no allowlist configured."""
        client = MagicMock()
        config = JoplinMCPConfig(token="test_token")

        # Should not raise
        validate_allowlist_at_startup(config, client)

    def test_startup_with_empty_allowlist(self, mock_notebook_hierarchy):
        """Server starts successfully with empty allowlist (D3: never crashes)."""
        notebooks = mock_notebook_hierarchy["notebooks"]
        client = _make_mock_client(notebooks)

        config = JoplinMCPConfig(
            token="test_token",
            notebook_allowlist=[],
        )

        # Should not raise, even though empty allowlist means no access
        validate_allowlist_at_startup(config, client)

    def test_startup_with_mixed_valid_invalid(self, mock_notebook_hierarchy):
        """Server starts with mix of valid and invalid entries, logging warnings."""
        notebooks = mock_notebook_hierarchy["notebooks"]
        client = _make_mock_client(notebooks)

        config = JoplinMCPConfig(
            token="test_token",
            notebook_allowlist=["Projects", "NonExistent", "AI"],
        )

        # Should not raise; valid entries still work
        validate_allowlist_at_startup(config, client)

        # Verify accessible notebooks still work after startup
        client_fn = lambda: client  # noqa: E731
        invalidate_notebook_map_cache()
        projects_id = [
            nb.id for nb in notebooks if nb.title == "Projects"
        ][0]

        assert is_notebook_accessible(
            projects_id,
            allowlist_entries=config.notebook_allowlist,
            client_fn=client_fn,
        ) is True

    def test_startup_warns_on_zero_accessible_notebooks(self):
        """When allowlist resolves to zero notebooks, warn but do not auto-create."""
        from unittest.mock import patch as _patch

        invalidate_notebook_map_cache()

        client = _make_mock_client([])

        config = JoplinMCPConfig(
            token="test_token",
            notebook_allowlist=["SomePattern"],
        )

        with _patch("joplin_mcp.notebook_utils.logger") as mock_logger:
            validate_allowlist_at_startup(config, client)
        mock_logger.warning.assert_any_call(
            "Allowlist is configured but resolves to zero accessible "
            "notebooks -- check your allowlist configuration"
        )
        client.add_notebook.assert_not_called()


# ---------------------------------------------------------------------------
# Test 6: Filter accessible notebooks integration
# filter_accessible_notebooks with real notebook_utils logic
# ---------------------------------------------------------------------------


class TestFilterAccessibleNotebooksIntegration:
    """Integration test: filter_accessible_notebooks with real hierarchy."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_filter_returns_only_accessible(self, mock_notebook_hierarchy):
        """filter_accessible_notebooks returns only allowlisted notebooks."""
        notebooks = mock_notebook_hierarchy["notebooks"]
        client = _make_mock_client(notebooks)
        client_fn = lambda: client  # noqa: E731

        allowlist = ["Projects", "AI"]

        result = filter_accessible_notebooks(
            notebooks, allowlist_entries=allowlist, client_fn=client_fn,
        )

        result_titles = {nb.title for nb in result}
        # Projects itself, its children (Work, Fun via hierarchical), and AI
        assert "Projects" in result_titles
        assert "Work" in result_titles
        assert "Fun" in result_titles
        assert "AI" in result_titles
        # Personal and Diary should be excluded
        assert "Personal" not in result_titles
        assert "Diary" not in result_titles

    def test_filter_with_allow_all_returns_all(self):
        """filter_accessible_notebooks returns all notebooks when allowlist is ALLOW_ALL (no restrictions)."""
        notebooks = [SimpleNamespace(id="nb1", title="Work")]
        client = _make_mock_client(notebooks)
        client_fn = lambda: client  # noqa: E731
        result = filter_accessible_notebooks(
            notebooks,
            allowlist_entries=list(JoplinMCPConfig.ALLOW_ALL),
            client_fn=client_fn,
        )
        assert len(result) == 1
        assert result[0].id == "nb1"

    def test_filter_with_glob_pattern(self, mock_notebook_hierarchy):
        """filter_accessible_notebooks works with glob patterns."""
        notebooks = mock_notebook_hierarchy["notebooks"]
        client = _make_mock_client(notebooks)
        client_fn = lambda: client  # noqa: E731

        allowlist = ["Projects/*"]

        result = filter_accessible_notebooks(
            notebooks, allowlist_entries=allowlist, client_fn=client_fn,
        )

        result_titles = {nb.title for nb in result}
        assert "Work" in result_titles
        assert "Fun" in result_titles
        # Projects itself is not matched by "Projects/*" (only children)
        # Personal and Diary should be excluded
        assert "Personal" not in result_titles
        assert "Diary" not in result_titles
