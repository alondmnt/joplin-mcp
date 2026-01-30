"""Tests for tools/notes.py - Note tool helpers and tool functions."""

import time
from unittest.mock import MagicMock, patch

import pytest


# === Tests for note body cache ===


class TestNoteCache:
    """Tests for the single-note cache used in sequential reading."""

    def test_cache_and_retrieve(self):
        """Should cache and retrieve note."""
        from joplin_mcp.tools.notes import _set_cached_note, _get_cached_note, _clear_note_cache

        _clear_note_cache()
        mock_note = MagicMock()
        mock_note.body = "Test content"

        _set_cached_note("note123", mock_note)
        result = _get_cached_note("note123")

        assert result is mock_note

    def test_cache_miss_returns_none(self):
        """Should return None for cache miss."""
        from joplin_mcp.tools.notes import _get_cached_note, _clear_note_cache

        _clear_note_cache()
        assert _get_cached_note("nonexistent") is None

    def test_caching_new_note_replaces_old(self):
        """Should replace old cached note when caching a new one."""
        from joplin_mcp.tools.notes import _set_cached_note, _get_cached_note, _clear_note_cache

        _clear_note_cache()
        note1, note2 = MagicMock(), MagicMock()

        _set_cached_note("note1", note1)
        _set_cached_note("note2", note2)

        assert _get_cached_note("note1") is None
        assert _get_cached_note("note2") is note2

    def test_clear_cache(self):
        """Should clear the cached note."""
        from joplin_mcp.tools.notes import _set_cached_note, _get_cached_note, _clear_note_cache

        _clear_note_cache()
        _set_cached_note("note1", MagicMock())

        _clear_note_cache()
        assert _get_cached_note("note1") is None


# === Tests for _create_note_object ===


class TestCreateNoteObject:
    """Tests for _create_note_object helper function."""

    def test_copies_original_note_attributes(self):
        """Should copy standard attributes from original note."""
        from joplin_mcp.tools.notes import _create_note_object

        original = MagicMock()
        original.id = "note123"
        original.title = "Test Note"
        original.created_time = 1609459200000
        original.updated_time = 1609545600000
        original.parent_id = "nb456"
        original.is_todo = 1
        original.todo_completed = 0
        original.body = "Original body"

        result = _create_note_object(original)

        assert result.id == "note123"
        assert result.title == "Test Note"
        assert result.created_time == 1609459200000
        assert result.updated_time == 1609545600000
        assert result.parent_id == "nb456"
        assert result.is_todo == 1
        assert result.todo_completed == 0
        assert result.body == "Original body"

    def test_overrides_body_when_provided(self):
        """Should use body_override when provided."""
        from joplin_mcp.tools.notes import _create_note_object

        original = MagicMock()
        original.body = "Original body content"
        original.id = "note123"
        original.title = "Test"

        result = _create_note_object(original, body_override="New body content")

        assert result.body == "New body content"

    def test_handles_missing_attributes(self):
        """Should handle notes with missing attributes gracefully."""
        from joplin_mcp.tools.notes import _create_note_object

        # Create a mock that returns None for missing attributes
        original = MagicMock()
        original.configure_mock(
            id="note123",
            title="Test",
            body="Body",
        )
        # Remove attributes that should use getattr default
        del original.created_time
        del original.updated_time
        del original.parent_id
        del original.is_todo
        del original.todo_completed

        result = _create_note_object(original)

        assert result.id == "note123"
        assert result.body == "Body"


# === Tests for _handle_section_extraction ===


class TestHandleSectionExtraction:
    """Tests for _handle_section_extraction helper function."""

    def test_returns_none_when_no_section(self):
        """Should return None when section is not provided."""
        from joplin_mcp.tools.notes import _handle_section_extraction

        note = MagicMock()
        note.body = "# Heading\nContent"

        result = _handle_section_extraction(note, None, "note123", True)

        assert result is None

    def test_returns_none_when_include_body_false(self):
        """Should return None when include_body is False."""
        from joplin_mcp.tools.notes import _handle_section_extraction

        note = MagicMock()
        note.body = "# Heading\nContent"

        result = _handle_section_extraction(note, "Heading", "note123", False)

        assert result is None

    def test_returns_none_when_no_body(self):
        """Should return None when note has no body."""
        from joplin_mcp.tools.notes import _handle_section_extraction

        note = MagicMock()
        note.body = ""

        result = _handle_section_extraction(note, "Heading", "note123", True)

        assert result is None

    @patch("joplin_mcp.tools.notes.format_note_details")
    def test_extracts_valid_section(self, mock_format):
        """Should extract section content when found."""
        from joplin_mcp.tools.notes import _handle_section_extraction

        note = MagicMock()
        note.body = "# Introduction\nThis is the intro.\n# Conclusion\nThis is the end."
        note.title = "Test Note"

        mock_format.return_value = "FORMATTED_OUTPUT"

        result = _handle_section_extraction(note, "Introduction", "note123", True)

        assert result is not None
        assert "EXTRACTED_SECTION: Introduction" in result
        assert "SECTION_QUERY: Introduction" in result
        assert "FORMATTED_OUTPUT" in result

    def test_shows_available_sections_when_not_found(self):
        """Should show available sections when section not found."""
        from joplin_mcp.tools.notes import _handle_section_extraction

        note = MagicMock()
        note.body = "# Section A\nContent A\n# Section B\nContent B"
        note.title = "Test Note"

        result = _handle_section_extraction(note, "NonExistent", "note123", True)

        assert result is not None
        assert "SECTION_NOT_FOUND: NonExistent" in result
        assert "NOTE_ID: note123" in result
        assert "AVAILABLE_SECTIONS:" in result
        assert "Section A" in result
        assert "Section B" in result
        assert "Section 'NonExistent' not found" in result


# === Tests for _handle_line_extraction ===


class TestHandleLineExtraction:
    """Tests for _handle_line_extraction helper function."""

    def test_returns_none_when_include_body_false(self):
        """Should return None when include_body is False."""
        from joplin_mcp.tools.notes import _handle_line_extraction

        note = MagicMock()
        note.body = "Line 1\nLine 2\nLine 3"

        result = _handle_line_extraction(note, 1, None, "note123", False)

        assert result is None

    def test_returns_none_when_no_body(self):
        """Should return None when note has no body."""
        from joplin_mcp.tools.notes import _handle_line_extraction

        note = MagicMock()
        note.body = ""

        result = _handle_line_extraction(note, 1, None, "note123", True)

        assert result is None

    def test_validates_start_line_too_low(self):
        """Should return error when start_line is less than 1."""
        from joplin_mcp.tools.notes import _handle_line_extraction

        note = MagicMock()
        note.body = "Line 1\nLine 2\nLine 3"
        note.title = "Test"

        result = _handle_line_extraction(note, 0, None, "note123", True)

        assert "LINE_EXTRACTION_ERROR" in result
        assert "Invalid start_line" in result
        assert "must be between 1" in result

    def test_validates_start_line_too_high(self):
        """Should return error when start_line exceeds total lines."""
        from joplin_mcp.tools.notes import _handle_line_extraction

        note = MagicMock()
        note.body = "Line 1\nLine 2\nLine 3"
        note.title = "Test"

        result = _handle_line_extraction(note, 10, None, "note123", True)

        assert "LINE_EXTRACTION_ERROR" in result
        assert "Invalid start_line" in result
        assert "must be between 1 and 3" in result

    def test_validates_line_count_negative(self):
        """Should return error when line_count is less than 1."""
        from joplin_mcp.tools.notes import _handle_line_extraction

        note = MagicMock()
        note.body = "Line 1\nLine 2\nLine 3"
        note.title = "Test"

        result = _handle_line_extraction(note, 1, 0, "note123", True)

        assert "LINE_EXTRACTION_ERROR" in result
        assert "Invalid line_count" in result
        assert "must be >= 1" in result

    @patch("joplin_mcp.tools.notes.format_note_details")
    def test_extracts_lines_with_default_count(self, mock_format):
        """Should extract 50 lines by default when line_count not specified."""
        from joplin_mcp.tools.notes import _handle_line_extraction

        # Create note with 100 lines
        lines = [f"Line {i}" for i in range(1, 101)]
        note = MagicMock()
        note.body = "\n".join(lines)
        note.title = "Test"

        mock_format.return_value = "FORMATTED_OUTPUT"

        result = _handle_line_extraction(note, 1, None, "note123", True)

        assert result is not None
        assert "EXTRACTED_LINES: 1-50" in result
        assert "50 lines" in result
        assert "TOTAL_LINES: 100" in result
        assert "EXTRACTION_TYPE: sequential_reading" in result
        assert 'NEXT_CHUNK: get_note("note123", start_line=51)' in result

    @patch("joplin_mcp.tools.notes.format_note_details")
    def test_extracts_specified_line_count(self, mock_format):
        """Should extract specified number of lines."""
        from joplin_mcp.tools.notes import _handle_line_extraction

        lines = [f"Line {i}" for i in range(1, 21)]
        note = MagicMock()
        note.body = "\n".join(lines)
        note.title = "Test"

        mock_format.return_value = "FORMATTED_OUTPUT"

        result = _handle_line_extraction(note, 5, 3, "note123", True)

        assert result is not None
        assert "EXTRACTED_LINES: 5-7" in result
        assert "3 lines" in result

    @patch("joplin_mcp.tools.notes.format_note_details")
    def test_shows_end_of_note_status(self, mock_format):
        """Should show end of note status when reaching end."""
        from joplin_mcp.tools.notes import _handle_line_extraction

        lines = ["Line 1", "Line 2", "Line 3"]
        note = MagicMock()
        note.body = "\n".join(lines)
        note.title = "Test"

        mock_format.return_value = "FORMATTED_OUTPUT"

        result = _handle_line_extraction(note, 1, 10, "note123", True)

        assert result is not None
        assert "STATUS: End of note reached" in result
        assert "NEXT_CHUNK" not in result


# === Tests for _handle_toc_display ===


class TestHandleTocDisplay:
    """Tests for _handle_toc_display helper function."""

    @patch("joplin_mcp.tools.notes.format_note_details")
    def test_returns_toc_with_metadata(self, mock_format):
        """Should return TOC with metadata when headings exist."""
        from joplin_mcp.tools.notes import _handle_toc_display

        note = MagicMock()
        note.body = "# Heading 1\nContent\n## Heading 2\nMore content"
        note.title = "Test Note"
        note.id = "note123"

        mock_format.return_value = "METADATA_OUTPUT"

        result = _handle_toc_display(note, "note123", "explicit")

        assert result is not None
        assert "METADATA_OUTPUT" in result
        assert "TABLE_OF_CONTENTS:" in result
        assert "Heading 1" in result
        assert "Heading 2" in result
        assert "DISPLAY_MODE: explicit" in result
        assert "NEXT_STEPS:" in result

    def test_returns_none_when_no_headings(self):
        """Should return None when body has no headings."""
        from joplin_mcp.tools.notes import _handle_toc_display

        note = MagicMock()
        note.body = "Just regular text without any headings."
        note.title = "Test"

        result = _handle_toc_display(note, "note123", "explicit")

        assert result is None

    def test_returns_none_when_no_body(self):
        """Should return None when note has no body."""
        from joplin_mcp.tools.notes import _handle_toc_display

        note = MagicMock()
        note.body = ""

        result = _handle_toc_display(note, "note123", "explicit", "")

        assert result is None


# === Tests for _handle_smart_toc_behavior ===


class TestHandleSmartTocBehavior:
    """Tests for _handle_smart_toc_behavior helper function."""

    def test_returns_none_when_disabled(self):
        """Should return None when smart TOC is disabled."""
        from joplin_mcp.tools.notes import _handle_smart_toc_behavior

        config = MagicMock()
        config.is_smart_toc_enabled.return_value = False

        note = MagicMock()
        note.body = "# Heading\n" + "Content " * 500

        result = _handle_smart_toc_behavior(note, "note123", config)

        assert result is None

    def test_returns_none_when_no_body(self):
        """Should return None when note has no body."""
        from joplin_mcp.tools.notes import _handle_smart_toc_behavior

        config = MagicMock()
        config.is_smart_toc_enabled.return_value = True

        note = MagicMock()
        note.body = ""

        result = _handle_smart_toc_behavior(note, "note123", config)

        assert result is None

    def test_returns_none_when_short_note(self):
        """Should return None when note is shorter than threshold."""
        from joplin_mcp.tools.notes import _handle_smart_toc_behavior

        config = MagicMock()
        config.is_smart_toc_enabled.return_value = True
        config.get_smart_toc_threshold.return_value = 2000

        note = MagicMock()
        note.body = "Short note content"

        result = _handle_smart_toc_behavior(note, "note123", config)

        assert result is None

    @patch("joplin_mcp.tools.notes._handle_toc_display")
    def test_returns_toc_for_long_note_with_headings(self, mock_toc_display):
        """Should return TOC for long note with headings."""
        from joplin_mcp.tools.notes import _handle_smart_toc_behavior

        config = MagicMock()
        config.is_smart_toc_enabled.return_value = True
        config.get_smart_toc_threshold.return_value = 100

        note = MagicMock()
        note.body = "# Heading\n" + "Content " * 100

        mock_toc_display.return_value = "TOC_DISPLAY_OUTPUT"

        result = _handle_smart_toc_behavior(note, "note123", config)

        assert result == "TOC_DISPLAY_OUTPUT"

    @patch("joplin_mcp.tools.notes._handle_toc_display")
    @patch("joplin_mcp.tools.notes.format_note_details")
    def test_truncates_long_note_without_headings(self, mock_format, mock_toc_display):
        """Should truncate long note when no headings exist."""
        from joplin_mcp.tools.notes import _handle_smart_toc_behavior

        config = MagicMock()
        config.is_smart_toc_enabled.return_value = True
        config.get_smart_toc_threshold.return_value = 100

        note = MagicMock()
        note.body = "Just regular text " * 100  # Long content, no headings

        mock_toc_display.return_value = None  # No headings
        mock_format.return_value = "TRUNCATED_OUTPUT"

        result = _handle_smart_toc_behavior(note, "note123", config)

        assert result is not None
        assert "CONTENT_TRUNCATED" in result
        assert "no headings for navigation" in result
        assert "force_full=True" in result


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
