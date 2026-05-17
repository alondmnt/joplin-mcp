"""Tests for tools/notes.py - Note tool helpers and tool functions."""

from unittest.mock import MagicMock, patch

import pytest


# === Tests for format_no_results_with_pagination ===


class TestFormatNoResultsWithPagination:
    """Tests for format_no_results_with_pagination helper function."""

    def test_basic_no_results(self):
        """Should format basic no results message."""
        from joplin_mcp.tools.notes import format_no_results_with_pagination

        result = format_no_results_with_pagination("note", "matching 'test'", 0, 20)

        assert "ITEM_TYPE: note" in result
        assert "No notes found" in result
        assert "matching 'test'" in result

    def test_includes_page_info_when_offset_nonzero(self):
        """Should include page info when offset is nonzero."""
        from joplin_mcp.tools.notes import format_no_results_with_pagination

        result = format_no_results_with_pagination("note", "in notebook", 20, 10)

        assert "Page 3" in result
        assert "offset 20" in result


# === Tests for tool functions with mocked client ===


class TestGetNoteToolValidation:
    """Tests for get_note tool input validation."""

    @pytest.mark.asyncio
    async def test_rejects_both_section_and_start_line(self):
        """Should reject both section and start_line being specified."""
        from joplin_mcp.tools.notes import get_note

        with pytest.raises(ValueError) as exc_info:
            await get_note.fn("12345678901234567890123456789012", section="1", start_line=10)
        assert "Cannot specify both start_line and section" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validates_start_line_minimum(self):
        """Should reject start_line less than 1."""
        from joplin_mcp.tools.notes import get_note

        with pytest.raises(ValueError) as exc_info:
            await get_note.fn("12345678901234567890123456789012", start_line=0)
        assert "start_line must be >= 1" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validates_line_count_minimum(self):
        """Should reject line_count less than 1."""
        from joplin_mcp.tools.notes import get_note

        with pytest.raises(ValueError) as exc_info:
            await get_note.fn("12345678901234567890123456789012", start_line=1, line_count=0)
        assert "line_count must be >= 1" in str(exc_info.value)


class TestCreateNoteTool:
    """Tests for create_note tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_creates_basic_note(self, mock_get_client, mock_get_notebook_id):
        """Should create a basic note successfully."""
        from joplin_mcp.tools.notes import create_note

        mock_client = MagicMock()
        mock_client.add_note.return_value = "new_note_id_123456789012345678"
        mock_get_client.return_value = mock_client
        mock_get_notebook_id.return_value = "notebook_id_789"

        result = await create_note.fn(
            title="Test Note",
            notebook_name="Work",
            body="Note content",
        )

        mock_get_notebook_id.assert_called_once_with("Work")
        mock_client.add_note.assert_called_once()
        call_kwargs = mock_client.add_note.call_args[1]
        assert call_kwargs["title"] == "Test Note"
        assert call_kwargs["body"] == "Note content"
        assert call_kwargs["parent_id"] == "notebook_id_789"
        assert "CREATE_NOTE" in result
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_creates_todo_with_due_date(self, mock_get_client, mock_get_notebook_id):
        """Should create a todo with due date."""
        from joplin_mcp.tools.notes import create_note

        mock_client = MagicMock()
        mock_client.add_note.return_value = "todo_id_123456789012345678901"
        mock_get_client.return_value = mock_client
        mock_get_notebook_id.return_value = "nb123"

        result = await create_note.fn(
            title="Todo Item",
            notebook_name="Tasks",
            body="",
            is_todo=True,
            todo_due=1735660800000,  # Timestamp in ms
        )

        call_kwargs = mock_client.add_note.call_args[1]
        assert call_kwargs["is_todo"] == 1
        assert call_kwargs["todo_due"] == 1735660800000
        assert "SUCCESS" in result


class TestUpdateNoteTool:
    """Tests for update_note tool."""

    @pytest.mark.asyncio
    async def test_requires_at_least_one_field(self):
        """Should reject update with no fields."""
        from joplin_mcp.tools.notes import update_note

        with pytest.raises(ValueError) as exc_info:
            await update_note.fn("12345678901234567890123456789012")
        assert "At least one field must be provided" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rejects_empty_title(self):
        """An empty `title` would silently rename the note to "" — reject it
        at the Pydantic boundary."""
        from pydantic import ValidationError
        from joplin_mcp.tools.notes import update_note

        with pytest.raises(ValidationError, match="at least 1 character"):
            await update_note.run(
                {
                    "note_id": "12345678901234567890123456789012",
                    "title": "",
                }
            )

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_updates_title(self, mock_get_client):
        """Should update note title."""
        from joplin_mcp.tools.notes import update_note

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = await update_note.fn(
            "12345678901234567890123456789012",
            title="New Title",
        )

        mock_client.modify_note.assert_called_once()
        call_args = mock_client.modify_note.call_args
        assert call_args[0][0] == "12345678901234567890123456789012"
        assert call_args[1]["title"] == "New Title"
        assert "UPDATE_NOTE" in result
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_moves_note_to_notebook(self, mock_get_client, mock_resolve_nb):
        """Should move note when notebook_name is provided."""
        from joplin_mcp.tools.notes import update_note

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_resolve_nb.return_value = "target-notebook-id"

        result = await update_note.fn(
            "12345678901234567890123456789012",
            notebook_name="Archive",
        )

        mock_resolve_nb.assert_called_once_with("Archive")
        mock_client.modify_note.assert_called_once()
        call_args = mock_client.modify_note.call_args
        assert call_args[0][0] == "12345678901234567890123456789012"
        assert call_args[1]["parent_id"] == "target-notebook-id"
        assert "title" not in call_args[1]
        assert "UPDATE_NOTE" in result
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_updates_title_and_moves_together(
        self, mock_get_client, mock_resolve_nb
    ):
        """Should combine notebook move with other field updates in one call."""
        from joplin_mcp.tools.notes import update_note

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_resolve_nb.return_value = "target-notebook-id"

        await update_note.fn(
            "12345678901234567890123456789012",
            title="Renamed",
            notebook_name="Projects/Work",
        )

        mock_resolve_nb.assert_called_once_with("Projects/Work")
        call_args = mock_client.modify_note.call_args
        assert call_args[1]["title"] == "Renamed"
        assert call_args[1]["parent_id"] == "target-notebook-id"

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_invalid_notebook_name_raises(
        self, mock_get_client, mock_resolve_nb
    ):
        """Should propagate ValueError from get_notebook_id_by_name and not call modify_note."""
        from joplin_mcp.tools.notes import update_note

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_resolve_nb.side_effect = ValueError(
            "Notebook 'NoSuch' not found. Available notebooks: Work, Personal."
        )

        with pytest.raises(ValueError, match="not found"):
            await update_note.fn(
                "12345678901234567890123456789012",
                notebook_name="NoSuch",
            )

        mock_client.modify_note.assert_not_called()


def _get_tool_fn(tool):
    """Get the underlying function from a tool (handles both wrapped and unwrapped)."""
    if hasattr(tool, 'fn'):
        return tool.fn
    return tool


class TestDeleteNoteTool:
    """Tests for delete_note tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_deletes_note(self, mock_get_client):
        """Should delete note successfully."""
        from joplin_mcp.tools.notes import delete_note

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(delete_note)
        result = await fn("12345678901234567890123456789012")

        mock_client.delete_note.assert_called_once_with("12345678901234567890123456789012")
        assert "DELETE_NOTE" in result
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_raises_when_note_missing(self, mock_get_client):
        """Joplin's DELETE is idempotent — silently 200s on a missing note.
        delete_note must GET first and surface the 404 so a caller doesn't
        see SUCCESS for a no-op. Regression for the smoke-test finding."""
        from joplin_mcp.tools.notes import delete_note

        mock_client = MagicMock()
        mock_client.get_note.side_effect = RuntimeError(
            "404 Client Error: Not Found for url: http://localhost:41184/notes/00000000000000000000000000000000?token=***"
        )
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(delete_note)
        with pytest.raises(ValueError, match="404"):
            await fn("00000000000000000000000000000000")

        mock_client.delete_note.assert_not_called()


class TestFindNotesTool:
    """Tests for find_notes tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.format_search_results_with_pagination")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_finds_notes_by_query(self, mock_get_client, mock_format):
        """Should search notes by query."""
        from joplin_mcp.tools.notes import find_notes

        mock_note = MagicMock()
        mock_note.id = "note123"
        mock_note.title = "Test Note"
        mock_note.updated_time = 1609545600000

        mock_client = MagicMock()
        mock_client.search_all.return_value = [mock_note]
        mock_get_client.return_value = mock_client

        mock_format.return_value = "FORMATTED_RESULTS"

        result = await find_notes.fn("test query")

        mock_client.search_all.assert_called_once()
        assert "test query" in mock_client.search_all.call_args[1]["query"]
        assert result == "FORMATTED_RESULTS"

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.format_search_results_with_pagination")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_lists_all_notes_with_wildcard(self, mock_get_client, mock_format):
        """Should list all notes when query is '*'."""
        from joplin_mcp.tools.notes import find_notes

        mock_note = MagicMock()
        mock_note.id = "note123"
        mock_note.title = "Test Note"
        mock_note.updated_time = 1609545600000

        mock_client = MagicMock()
        mock_client.get_all_notes.return_value = [mock_note]
        mock_get_client.return_value = mock_client

        mock_format.return_value = "ALL_NOTES"

        result = await find_notes.fn("*")

        mock_client.get_all_notes.assert_called_once()
        assert result == "ALL_NOTES"


class TestFindNotesTrashGuards:
    """Tests for find_notes trash=True validation guards.

    Joplin's search API and filter queries ignore include_deleted entirely,
    so trash=True is only supported for query='*' with no task/completed filters.
    These tests pin the ValueError behaviour.
    """

    @pytest.mark.asyncio
    async def test_trash_with_text_query_raises(self):
        """Should raise ValueError when trash=True is combined with a text query."""
        from joplin_mcp.tools.notes import find_notes

        with pytest.raises(ValueError, match="trash=True only works with"):
            await find_notes.fn("meeting", trash=True)

    @pytest.mark.asyncio
    async def test_trash_with_task_filter_raises(self):
        """Should raise ValueError when trash=True is combined with task filter."""
        from joplin_mcp.tools.notes import find_notes

        with pytest.raises(ValueError, match="trash=True cannot be combined"):
            await find_notes.fn("*", trash=True, task=True)

    @pytest.mark.asyncio
    async def test_trash_with_completed_filter_raises(self):
        """Should raise ValueError when trash=True is combined with completed filter."""
        from joplin_mcp.tools.notes import find_notes

        with pytest.raises(ValueError, match="trash=True cannot be combined"):
            await find_notes.fn("*", trash=True, completed=False)

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.format_search_results_with_pagination")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_trash_wildcard_passes_include_deleted(
        self, mock_get_client, mock_format
    ):
        """Should forward include_deleted=1 to get_all_notes on the supported path."""
        from joplin_mcp.tools.notes import find_notes

        trashed = MagicMock()
        trashed.id = "t1"
        trashed.title = "Trashed"
        trashed.deleted_time = 1700000000000
        trashed.updated_time = 1609545600000

        mock_client = MagicMock()
        mock_client.get_all_notes.return_value = [trashed]
        mock_get_client.return_value = mock_client
        mock_format.return_value = "TRASHED_RESULTS"

        result = await find_notes.fn("*", trash=True)

        mock_client.get_all_notes.assert_called_once()
        assert mock_client.get_all_notes.call_args[1].get("include_deleted") == 1
        assert result == "TRASHED_RESULTS"


class TestFindNoteWithTagTool:
    """Tests for find_notes_with_tag tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.format_search_results_with_pagination")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_finds_notes_by_tag(self, mock_get_client, mock_format):
        """Should search notes by tag name."""
        from joplin_mcp.tools.notes import find_notes_with_tag

        mock_note = MagicMock()
        mock_note.id = "tagged_note"
        mock_note.title = "Tagged Note"

        mock_client = MagicMock()
        mock_client.search_all.return_value = [mock_note]
        mock_get_client.return_value = mock_client

        mock_format.return_value = "TAGGED_RESULTS"

        result = await find_notes_with_tag.fn("important")

        mock_client.search_all.assert_called_once()
        assert 'tag:"important"' in mock_client.search_all.call_args[1]["query"]
        assert result == "TAGGED_RESULTS"


class TestFindNotesInNotebookTool:
    """Tests for find_notes_in_notebook tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.format_search_results_with_pagination")
    @patch("joplin_mcp.tools.notes.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_finds_notes_in_notebook(self, mock_get_client, mock_get_notebook_id, mock_format):
        """Should find notes in specified notebook."""
        from joplin_mcp.tools.notes import find_notes_in_notebook

        mock_note = MagicMock()
        mock_note.id = "nb_note"
        mock_note.title = "Notebook Note"
        mock_note.updated_time = 1609545600000
        mock_note.is_todo = 0
        mock_note.todo_completed = 0

        mock_client = MagicMock()
        mock_client.get_all_notes.return_value = [mock_note]
        mock_get_client.return_value = mock_client
        mock_get_notebook_id.return_value = "notebook_id_123"

        mock_format.return_value = "NOTEBOOK_RESULTS"

        result = await find_notes_in_notebook.fn("Work")

        mock_get_notebook_id.assert_called_once_with("Work")
        mock_client.get_all_notes.assert_called_once()
        assert mock_client.get_all_notes.call_args[1]["notebook_id"] == "notebook_id_123"
        assert result == "NOTEBOOK_RESULTS"


class TestGetAllNotesTool:
    """Tests for get_all_notes tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.format_search_results_with_pagination")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_gets_all_notes_with_limit(self, mock_get_client, mock_format):
        """Should get all notes with limit."""
        from joplin_mcp.tools.notes import get_all_notes

        # Create 5 mock notes
        mock_notes = []
        for i in range(5):
            note = MagicMock()
            note.id = f"note{i}"
            note.title = f"Note {i}"
            note.updated_time = 1609545600000 + i * 1000
            mock_notes.append(note)

        mock_client = MagicMock()
        mock_client.get_all_notes.return_value = mock_notes
        mock_get_client.return_value = mock_client

        mock_format.return_value = "ALL_NOTES_RESULT"

        fn = _get_tool_fn(get_all_notes)
        result = await fn(limit=3)

        mock_client.get_all_notes.assert_called_once()
        assert result == "ALL_NOTES_RESULT"


class TestGetLinksTool:
    """Tests for get_links tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_extracts_outgoing_links(self, mock_get_client):
        """Should extract outgoing links from note content."""
        from joplin_mcp.tools.notes import get_links

        main_note = MagicMock()
        main_note.id = "12345678901234567890123456789012"
        main_note.title = "Main Note"
        main_note.body = "Check out [linked note](:/abc123def456789012345678901234) for details."

        target_note = MagicMock()
        target_note.id = "abc123def456789012345678901234"
        target_note.title = "Linked Note"

        mock_client = MagicMock()
        mock_client.get_note.side_effect = lambda note_id, **kwargs: main_note if note_id == "12345678901234567890123456789012" else target_note
        mock_client.search_all.return_value = []
        mock_get_client.return_value = mock_client

        result = await get_links.fn("12345678901234567890123456789012")

        assert "SOURCE_NOTE: Main Note" in result
        assert "TOTAL_OUTGOING_LINKS: 1" in result
        assert "target_note_id: abc123def456789012345678901234" in result
        assert "target_note_title: Linked Note" in result
        assert "link_status: VALID" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_detects_broken_links(self, mock_get_client):
        """Should detect broken links."""
        from joplin_mcp.tools.notes import get_links

        main_note = MagicMock()
        main_note.id = "12345678901234567890123456789012"
        main_note.title = "Note with Broken Link"
        main_note.body = "Link to [missing note](:/nonexistent12345678901234567)."

        mock_client = MagicMock()

        def get_note_side_effect(note_id, **kwargs):
            if note_id == "12345678901234567890123456789012":
                return main_note
            raise Exception("Note not found")

        mock_client.get_note.side_effect = get_note_side_effect
        mock_client.search_all.return_value = []
        mock_get_client.return_value = mock_client

        result = await get_links.fn("12345678901234567890123456789012")

        assert "TOTAL_OUTGOING_LINKS: 1" in result
        assert "link_status: BROKEN" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_extracts_section_slugs(self, mock_get_client):
        """Should extract section slugs from links."""
        from joplin_mcp.tools.notes import get_links

        main_note = MagicMock()
        main_note.id = "12345678901234567890123456789012"
        main_note.title = "Note with Section Link"
        main_note.body = "See [section link](:/target78901234567890123456789012#my-section) for info."

        target_note = MagicMock()
        target_note.id = "target78901234567890123456789012"
        target_note.title = "Target Note"

        mock_client = MagicMock()
        mock_client.get_note.side_effect = lambda note_id, **kwargs: main_note if note_id == "12345678901234567890123456789012" else target_note
        mock_client.search_all.return_value = []
        mock_get_client.return_value = mock_client

        result = await get_links.fn("12345678901234567890123456789012")

        assert "section_slug: my-section" in result


class TestFindInNoteTool:
    """Tests for find_in_note tool."""

    @pytest.mark.asyncio
    async def test_rejects_invalid_regex(self):
        """Should reject invalid regex pattern."""
        from joplin_mcp.tools.notes import find_in_note

        with pytest.raises(ValueError) as exc_info:
            await find_in_note.fn(
                "12345678901234567890123456789012",
                pattern="[invalid regex"
            )
        assert "Invalid regular expression" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_notebook_map_cached")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_finds_matches_in_note(self, mock_get_client, mock_get_notebook_map):
        """Should find regex matches in note content."""
        from joplin_mcp.tools.notes import find_in_note

        note = MagicMock()
        note.id = "12345678901234567890123456789012"
        note.title = "Note with Patterns"
        note.body = "Line 1\nfoo bar\nLine 3\nfoo baz\nLine 5"
        note.parent_id = "nb123"

        mock_client = MagicMock()
        mock_client.get_note.return_value = note
        mock_get_client.return_value = mock_client
        mock_get_notebook_map.return_value = {}

        result = await find_in_note.fn(
            "12345678901234567890123456789012",
            pattern="foo"
        )

        assert "NOTE_ID:" in result
        assert "PATTERN: foo" in result
        assert "TOTAL_MATCHES: 2" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_notebook_map_cached")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_reports_no_matches(self, mock_get_client, mock_get_notebook_map):
        """Should report when no matches found."""
        from joplin_mcp.tools.notes import find_in_note

        note = MagicMock()
        note.id = "12345678901234567890123456789012"
        note.title = "Note without Patterns"
        note.body = "This note has no matches"
        note.parent_id = "nb123"

        mock_client = MagicMock()
        mock_client.get_note.return_value = note
        mock_get_client.return_value = mock_client
        mock_get_notebook_map.return_value = {}

        result = await find_in_note.fn(
            "12345678901234567890123456789012",
            pattern="xyz123"
        )

        assert "TOTAL_MATCHES: 0" in result
        assert "No matches found" in result


# === Tests for edit_note tool ===


class TestEditNoteTool:
    """Tests for edit_note tool."""

    def _make_note(self, body="Hello world, hello again."):
        """Create a mock note with the given body."""
        note = MagicMock()
        note.id = "12345678901234567890123456789012"
        note.title = "Test Note"
        note.body = body
        note.parent_id = "abcdef12345678901234567890123456"
        note.created_time = 1609459200000
        note.updated_time = 1609545600000
        note.is_todo = 0
        note.todo_completed = 0
        return note

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_replace_unique_match(self, mock_get_client):
        """Should replace a unique substring in the note body."""
        from joplin_mcp.tools.notes import edit_note

        note = self._make_note("Fix the color in this line.")
        mock_client = MagicMock()
        mock_client.get_note.return_value = note
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(edit_note)
        result = await fn(
            "12345678901234567890123456789012",
            new_string="colour",
            old_string="color",
        )

        mock_client.modify_note.assert_called_once()
        call_kwargs = mock_client.modify_note.call_args[1]
        assert call_kwargs["body"] == "Fix the colour in this line."
        assert "Replaced 1 occurrence" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_replace_all_occurrences(self, mock_get_client):
        """Should replace all occurrences when replace_all=True."""
        from joplin_mcp.tools.notes import edit_note

        note = self._make_note("color here and color there")
        mock_client = MagicMock()
        mock_client.get_note.return_value = note
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(edit_note)
        result = await fn(
            "12345678901234567890123456789012",
            new_string="colour",
            old_string="color",
            replace_all=True,
        )

        call_kwargs = mock_client.modify_note.call_args[1]
        assert call_kwargs["body"] == "colour here and colour there"
        assert "Replaced 2 occurrence" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_delete_text(self, mock_get_client):
        """Should delete text when new_string is empty."""
        from joplin_mcp.tools.notes import edit_note

        note = self._make_note("Remove this part please.")
        mock_client = MagicMock()
        mock_client.get_note.return_value = note
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(edit_note)
        result = await fn(
            "12345678901234567890123456789012",
            new_string="",
            old_string="this part ",
        )

        call_kwargs = mock_client.modify_note.call_args[1]
        assert call_kwargs["body"] == "Remove please."
        assert "Deleted 1 occurrence" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_append_to_note(self, mock_get_client):
        """Should append text to end of note body."""
        from joplin_mcp.tools.notes import edit_note

        note = self._make_note("Existing content.")
        mock_client = MagicMock()
        mock_client.get_note.return_value = note
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(edit_note)
        result = await fn(
            "12345678901234567890123456789012",
            new_string="\nNew line at end.",
            position="end",
        )

        call_kwargs = mock_client.modify_note.call_args[1]
        assert call_kwargs["body"] == "Existing content.\nNew line at end."
        assert "Appended" in result
        assert "17 characters" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_prepend_to_note(self, mock_get_client):
        """Should prepend text to beginning of note body."""
        from joplin_mcp.tools.notes import edit_note

        note = self._make_note("Existing content.")
        mock_client = MagicMock()
        mock_client.get_note.return_value = note
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(edit_note)
        result = await fn(
            "12345678901234567890123456789012",
            new_string="Header\n",
            position="beginning",
        )

        call_kwargs = mock_client.modify_note.call_args[1]
        assert call_kwargs["body"] == "Header\nExisting content."
        assert "Prepended" in result
        assert "7 characters" in result

    @pytest.mark.asyncio
    async def test_error_old_string_not_found(self):
        """Should raise ValueError when old_string is not found in note body."""
        from joplin_mcp.tools.notes import edit_note

        note = self._make_note("Some content here.")

        with patch("joplin_mcp.tools.notes.get_joplin_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_note.return_value = note
            mock_get_client.return_value = mock_client

            fn = _get_tool_fn(edit_note)
            with pytest.raises(ValueError) as exc_info:
                await fn(
                    "12345678901234567890123456789012",
                    new_string="replacement",
                    old_string="nonexistent text",
                )
            assert "old_string not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_ambiguous_match(self):
        """Should raise ValueError when old_string matches >1 time without replace_all."""
        from joplin_mcp.tools.notes import edit_note

        note = self._make_note("foo bar foo baz foo")

        with patch("joplin_mcp.tools.notes.get_joplin_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_note.return_value = note
            mock_get_client.return_value = mock_client

            fn = _get_tool_fn(edit_note)
            with pytest.raises(ValueError) as exc_info:
                await fn(
                    "12345678901234567890123456789012",
                    new_string="qux",
                    old_string="foo",
                )
            assert "matches 3 times" in str(exc_info.value)
            assert "replace_all=True" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_old_string_and_position_both_set(self):
        """Should raise ValueError when both old_string and position are set."""
        from joplin_mcp.tools.notes import edit_note

        fn = _get_tool_fn(edit_note)
        with pytest.raises(ValueError) as exc_info:
            await fn(
                "12345678901234567890123456789012",
                new_string="text",
                old_string="old",
                position="end",
            )
        assert "Cannot specify both" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_no_old_string_and_no_position(self):
        """Should raise ValueError when neither old_string nor position is set."""
        from joplin_mcp.tools.notes import edit_note

        fn = _get_tool_fn(edit_note)
        with pytest.raises(ValueError) as exc_info:
            await fn(
                "12345678901234567890123456789012",
                new_string="text",
            )
        assert "Must specify either" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_old_string_equals_new_string(self):
        """Should raise ValueError when old_string equals new_string."""
        from joplin_mcp.tools.notes import edit_note

        fn = _get_tool_fn(edit_note)
        with pytest.raises(ValueError) as exc_info:
            await fn(
                "12345678901234567890123456789012",
                new_string="same",
                old_string="same",
            )
        assert "identical" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_invalid_position(self):
        """Should raise ValueError for invalid position value."""
        from joplin_mcp.tools.notes import edit_note

        fn = _get_tool_fn(edit_note)
        with pytest.raises(ValueError) as exc_info:
            await fn(
                "12345678901234567890123456789012",
                new_string="text",
                position="middle",
            )
        assert "must be 'beginning' or 'end'" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("joplin_mcp.note_view.clear_note_cache")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_cache_invalidation(self, mock_get_client, mock_clear_cache):
        """Should clear note cache after editing."""
        from joplin_mcp.tools.notes import edit_note

        note = self._make_note("Unique text here.")
        mock_client = MagicMock()
        mock_client.get_note.return_value = note
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(edit_note)
        await fn(
            "12345678901234567890123456789012",
            new_string="Modified text here.",
            old_string="Unique text here.",
        )

        mock_clear_cache.assert_called_once()


# === Tests for sorting support ===


class TestFlexibleEnumConverter:
    """Tests for flexible_enum_converter."""

    def test_returns_none_for_none(self):
        from joplin_mcp.fastmcp_server import SortBy, flexible_enum_converter
        assert flexible_enum_converter(None, SortBy, "order_by") is None

    def test_passes_through_enum_value(self):
        from joplin_mcp.fastmcp_server import SortBy, flexible_enum_converter
        result = flexible_enum_converter(SortBy.title, SortBy, "order_by")
        assert result is SortBy.title

    def test_converts_string_to_enum(self):
        from joplin_mcp.fastmcp_server import SortBy, flexible_enum_converter
        result = flexible_enum_converter("title", SortBy, "order_by")
        assert result == SortBy.title

    def test_case_insensitive_string(self):
        from joplin_mcp.fastmcp_server import SortOrder, flexible_enum_converter
        result = flexible_enum_converter("ASC", SortOrder, "order_dir")
        assert result == SortOrder.asc

    def test_strips_whitespace(self):
        from joplin_mcp.fastmcp_server import SortBy, flexible_enum_converter
        result = flexible_enum_converter(" updated_time ", SortBy, "order_by")
        assert result == SortBy.updated_time

    def test_raises_for_invalid_string(self):
        from joplin_mcp.fastmcp_server import SortBy, flexible_enum_converter
        with pytest.raises(ValueError, match="Invalid order_by"):
            flexible_enum_converter("invalid", SortBy, "order_by")

    def test_raises_for_invalid_type(self):
        from joplin_mcp.fastmcp_server import SortBy, flexible_enum_converter
        with pytest.raises(ValueError, match="Invalid order_by type"):
            flexible_enum_converter(123, SortBy, "order_by")


class TestResolveSortParams:
    """Tests for resolve_sort_params."""

    def test_defaults_to_updated_time_desc(self):
        from joplin_mcp.fastmcp_server import resolve_sort_params
        result = resolve_sort_params(None, None)
        assert result == {"order_by": "updated_time", "order_dir": "DESC"}

    def test_title_defaults_to_asc(self):
        from joplin_mcp.fastmcp_server import SortBy, resolve_sort_params
        result = resolve_sort_params(SortBy.title, None)
        assert result == {"order_by": "title", "order_dir": "ASC"}

    def test_created_time_defaults_to_desc(self):
        from joplin_mcp.fastmcp_server import SortBy, resolve_sort_params
        result = resolve_sort_params(SortBy.created_time, None)
        assert result == {"order_by": "created_time", "order_dir": "DESC"}

    def test_explicit_direction_overrides_default(self):
        from joplin_mcp.fastmcp_server import SortBy, SortOrder, resolve_sort_params
        result = resolve_sort_params(SortBy.title, SortOrder.desc)
        assert result == {"order_by": "title", "order_dir": "DESC"}

    def test_custom_default_order_by(self):
        from joplin_mcp.fastmcp_server import SortBy, resolve_sort_params
        result = resolve_sort_params(None, None, default_order_by=SortBy.created_time)
        assert result == {"order_by": "created_time", "order_dir": "DESC"}


class TestFindNotesSorting:
    """Tests for sorting in find_notes."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.format_search_results_with_pagination")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_wildcard_passes_sort_kwargs_to_get_all_notes(self, mock_get_client, mock_format):
        """Wildcard query should pass sort kwargs to get_all_notes."""
        from joplin_mcp.tools.notes import find_notes

        mock_note = MagicMock()
        mock_note.id = "note123"
        mock_note.title = "Test"
        mock_note.updated_time = 1000

        mock_client = MagicMock()
        mock_client.get_all_notes.return_value = [mock_note]
        mock_get_client.return_value = mock_client
        mock_format.return_value = "RESULTS"

        await find_notes.fn("*", order_by="title")

        call_kwargs = mock_client.get_all_notes.call_args[1]
        assert call_kwargs["order_by"] == "title"
        assert call_kwargs["order_dir"] == "ASC"

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.format_search_results_with_pagination")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_text_query_preserves_relevance_by_default(self, mock_get_client, mock_format):
        """Text query without explicit sort should not pass sort kwargs (preserve relevance)."""
        from joplin_mcp.tools.notes import find_notes

        mock_note = MagicMock()
        mock_note.id = "note123"
        mock_note.title = "Test"
        mock_note.updated_time = 1000

        mock_client = MagicMock()
        mock_client.search_all.return_value = [mock_note]
        mock_get_client.return_value = mock_client
        mock_format.return_value = "RESULTS"

        await find_notes.fn("meeting")

        call_kwargs = mock_client.search_all.call_args[1]
        assert "order_by" not in call_kwargs
        assert "order_dir" not in call_kwargs

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.format_search_results_with_pagination")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_text_query_with_explicit_sort(self, mock_get_client, mock_format):
        """Text query with explicit sort should pass sort kwargs."""
        from joplin_mcp.tools.notes import find_notes

        mock_note = MagicMock()
        mock_note.id = "note123"
        mock_note.title = "Test"
        mock_note.updated_time = 1000

        mock_client = MagicMock()
        mock_client.search_all.return_value = [mock_note]
        mock_get_client.return_value = mock_client
        mock_format.return_value = "RESULTS"

        await find_notes.fn("meeting", order_by="created_time", order_dir="asc")

        call_kwargs = mock_client.search_all.call_args[1]
        assert call_kwargs["order_by"] == "created_time"
        assert call_kwargs["order_dir"] == "ASC"


class TestFindNotesWithTagSorting:
    """Tests for sorting in find_notes_with_tag."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.format_search_results_with_pagination")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_passes_sort_kwargs_to_search(self, mock_get_client, mock_format):
        """Should pass sort kwargs to search_all."""
        from joplin_mcp.tools.notes import find_notes_with_tag

        mock_note = MagicMock()
        mock_note.id = "note123"
        mock_note.title = "Tagged"

        mock_client = MagicMock()
        mock_client.search_all.return_value = [mock_note]
        mock_get_client.return_value = mock_client
        mock_format.return_value = "RESULTS"

        await find_notes_with_tag.fn("work", order_by="title", order_dir="desc")

        call_kwargs = mock_client.search_all.call_args[1]
        assert call_kwargs["order_by"] == "title"
        assert call_kwargs["order_dir"] == "DESC"


class TestFindNotesInNotebookSorting:
    """Tests for sorting in find_notes_in_notebook."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.format_search_results_with_pagination")
    @patch("joplin_mcp.tools.notes.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_passes_sort_kwargs_to_get_all_notes(self, mock_get_client, mock_get_nb, mock_format):
        """Should pass sort kwargs to get_all_notes."""
        from joplin_mcp.tools.notes import find_notes_in_notebook

        mock_note = MagicMock()
        mock_note.id = "note123"
        mock_note.title = "NB Note"
        mock_note.updated_time = 1000
        mock_note.is_todo = 0
        mock_note.todo_completed = 0

        mock_client = MagicMock()
        mock_client.get_all_notes.return_value = [mock_note]
        mock_get_client.return_value = mock_client
        mock_get_nb.return_value = "nb_id"
        mock_format.return_value = "RESULTS"

        await find_notes_in_notebook.fn("Work", order_by="created_time", order_dir="asc")

        call_kwargs = mock_client.get_all_notes.call_args[1]
        assert call_kwargs["order_by"] == "created_time"
        assert call_kwargs["order_dir"] == "ASC"


class TestGetAllNotesSorting:
    """Tests for sorting in get_all_notes."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.format_search_results_with_pagination")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_passes_sort_kwargs(self, mock_get_client, mock_format):
        """Should pass sort kwargs to get_all_notes."""
        from joplin_mcp.tools.notes import get_all_notes

        mock_note = MagicMock()
        mock_note.id = "note123"
        mock_note.title = "Note"
        mock_note.updated_time = 1000

        mock_client = MagicMock()
        mock_client.get_all_notes.return_value = [mock_note]
        mock_get_client.return_value = mock_client
        mock_format.return_value = "RESULTS"

        fn = _get_tool_fn(get_all_notes)
        await fn(order_by="title")

        call_kwargs = mock_client.get_all_notes.call_args[1]
        assert call_kwargs["order_by"] == "title"
        assert call_kwargs["order_dir"] == "ASC"
