"""Tests for formatting.py - Pure functions for MCP tool response formatting."""

import pytest

from joplin_mcp.formatting import (
    ItemType,
    build_pagination_header,
    build_pagination_summary,
    format_creation_success,
    format_delete_success,
    format_find_in_note_summary,
    format_no_results_message,
    format_note_metadata_lines,
    format_relation_success,
    format_update_success,
    get_item_emoji,
)


# === Tests for ItemType and get_item_emoji ===


class TestItemTypeAndEmoji:
    """Tests for ItemType enum and get_item_emoji function."""

    def test_item_type_values(self):
        """ItemType should have correct string values."""
        assert ItemType.note.value == "note"
        assert ItemType.notebook.value == "notebook"
        assert ItemType.tag.value == "tag"

    def test_get_item_emoji_note(self):
        """Note type should return note emoji."""
        assert get_item_emoji(ItemType.note) == "📝"

    def test_get_item_emoji_notebook(self):
        """Notebook type should return folder emoji."""
        assert get_item_emoji(ItemType.notebook) == "📁"

    def test_get_item_emoji_tag(self):
        """Tag type should return tag emoji."""
        assert get_item_emoji(ItemType.tag) == "🏷️"

    def test_get_item_emoji_unknown(self):
        """Unknown type should return default emoji."""
        # Using a mock/invalid value to test fallback
        result = get_item_emoji(None)
        assert result == "📄"


# === Tests for format_creation_success ===


class TestFormatCreationSuccess:
    """Tests for format_creation_success function."""

    def test_note_creation_success(self):
        """Should format note creation success correctly."""
        result = format_creation_success(
            ItemType.note, "My New Note", "abc123def456789012345678901234"
        )
        assert "OPERATION: CREATE_NOTE" in result
        assert "STATUS: SUCCESS" in result
        assert "ITEM_TYPE: note" in result
        assert "ITEM_ID: abc123def456789012345678901234" in result
        assert "TITLE: My New Note" in result
        assert "note created successfully" in result

    def test_notebook_creation_success(self):
        """Should format notebook creation success correctly."""
        result = format_creation_success(
            ItemType.notebook, "Work Projects", "notebook123"
        )
        assert "OPERATION: CREATE_NOTEBOOK" in result
        assert "ITEM_TYPE: notebook" in result
        assert "TITLE: Work Projects" in result
        assert "notebook created successfully" in result

    def test_tag_creation_success(self):
        """Should format tag creation success correctly."""
        result = format_creation_success(ItemType.tag, "important", "tag456")
        assert "OPERATION: CREATE_TAG" in result
        assert "ITEM_TYPE: tag" in result
        assert "TITLE: important" in result
        assert "tag created successfully" in result


# === Tests for format_update_success ===


class TestFormatUpdateSuccess:
    """Tests for format_update_success function."""

    def test_note_update_success(self):
        """Should format note update success correctly."""
        result = format_update_success(ItemType.note, "note123456")
        assert "OPERATION: UPDATE_NOTE" in result
        assert "STATUS: SUCCESS" in result
        assert "ITEM_TYPE: note" in result
        assert "ITEM_ID: note123456" in result
        assert "note updated successfully" in result

    def test_notebook_update_success(self):
        """Should format notebook update success correctly."""
        result = format_update_success(ItemType.notebook, "nb789")
        assert "OPERATION: UPDATE_NOTEBOOK" in result
        assert "ITEM_TYPE: notebook" in result
        assert "notebook updated successfully" in result

    def test_tag_update_success(self):
        """Should format tag update success correctly."""
        result = format_update_success(ItemType.tag, "tag001")
        assert "OPERATION: UPDATE_TAG" in result
        assert "ITEM_TYPE: tag" in result
        assert "tag updated successfully" in result


# === Tests for format_delete_success ===


class TestFormatDeleteSuccess:
    """Tests for format_delete_success function."""

    def test_note_delete_success(self):
        """Should format note delete success correctly."""
        result = format_delete_success(ItemType.note, "deleted_note_id")
        assert "OPERATION: DELETE_NOTE" in result
        assert "STATUS: SUCCESS" in result
        assert "ITEM_TYPE: note" in result
        assert "ITEM_ID: deleted_note_id" in result
        assert "note deleted successfully" in result

    def test_notebook_delete_success(self):
        """Should format notebook delete success correctly."""
        result = format_delete_success(ItemType.notebook, "nb_to_delete")
        assert "OPERATION: DELETE_NOTEBOOK" in result
        assert "ITEM_TYPE: notebook" in result
        assert "notebook deleted successfully" in result

    def test_tag_delete_success(self):
        """Should format tag delete success correctly."""
        result = format_delete_success(ItemType.tag, "tag_gone")
        assert "OPERATION: DELETE_TAG" in result
        assert "ITEM_TYPE: tag" in result
        assert "tag deleted successfully" in result


# === Tests for format_relation_success ===


class TestFormatRelationSuccess:
    """Tests for format_relation_success function."""

    def test_tagged_note_success(self):
        """Should format tag-note relationship success correctly."""
        result = format_relation_success(
            "tagged note",
            ItemType.note,
            "note123",
            ItemType.tag,
            "important",
        )
        assert "OPERATION: TAGGED_NOTE" in result
        assert "STATUS: SUCCESS" in result
        assert "ITEM1_TYPE: note" in result
        assert "ITEM1_ID: note123" in result
        assert "ITEM2_TYPE: tag" in result
        assert "ITEM2_ID: important" in result
        assert "tagged note completed successfully" in result

    def test_removed_tag_success(self):
        """Should format remove tag operation success correctly."""
        result = format_relation_success(
            "removed tag from note",
            ItemType.note,
            "note456",
            ItemType.tag,
            "old-tag",
        )
        assert "OPERATION: REMOVED_TAG_FROM_NOTE" in result
        assert "MESSAGE: removed tag from note completed successfully" in result

    def test_operation_with_spaces_normalized(self):
        """Operation names with spaces should be normalized to underscores."""
        result = format_relation_success(
            "linked notes together",
            ItemType.note,
            "n1",
            ItemType.note,
            "n2",
        )
        assert "OPERATION: LINKED_NOTES_TOGETHER" in result


# === Tests for format_no_results_message ===


class TestFormatNoResultsMessage:
    """Tests for format_no_results_message function."""

    def test_no_results_basic(self):
        """Should format no results message correctly."""
        result = format_no_results_message("note")
        assert "ITEM_TYPE: note" in result
        assert "TOTAL_ITEMS: 0" in result
        assert "No notes found" in result

    def test_no_results_with_context(self):
        """Should include context in message."""
        result = format_no_results_message("note", 'matching query "test"')
        assert "CONTEXT: matching query" in result
        assert '"test"' in result

    def test_no_results_for_tag(self):
        """Should work for tag type."""
        result = format_no_results_message("tag", "for note: xyz123")
        assert "ITEM_TYPE: tag" in result
        assert "No tags found" in result
        assert "for note: xyz123" in result


# === Tests for build_pagination_header ===


class TestBuildPaginationHeader:
    """Tests for build_pagination_header function."""

    def test_first_page(self):
        """Should format first page header correctly."""
        header = build_pagination_header("test query", total_count=50, limit=10, offset=0)
        assert "SEARCH_QUERY: test query" in header
        assert "TOTAL_RESULTS: 50" in header
        assert "SHOWING_RESULTS: 1-10" in header
        assert "CURRENT_PAGE: 1" in header
        assert "TOTAL_PAGES: 5" in header
        assert "LIMIT: 10" in header
        assert "OFFSET: 0" in header
        # Should include next page hint
        assert any("NEXT_PAGE:" in line for line in header)
        assert any("offset=10" in line for line in header)

    def test_middle_page(self):
        """Should format middle page header correctly."""
        header = build_pagination_header("search", total_count=100, limit=20, offset=40)
        assert "SHOWING_RESULTS: 41-60" in header
        assert "CURRENT_PAGE: 3" in header
        assert "TOTAL_PAGES: 5" in header
        assert any("offset=60" in line for line in header)

    def test_last_page(self):
        """Should format last page without next page hint."""
        header = build_pagination_header("query", total_count=25, limit=10, offset=20)
        assert "SHOWING_RESULTS: 21-25" in header
        assert "CURRENT_PAGE: 3" in header
        assert "TOTAL_PAGES: 3" in header
        # Should NOT include next page hint
        assert not any("NEXT_PAGE:" in line for line in header)

    def test_single_page(self):
        """Should handle single page results correctly."""
        header = build_pagination_header("small", total_count=5, limit=10, offset=0)
        assert "SHOWING_RESULTS: 1-5" in header
        assert "CURRENT_PAGE: 1" in header
        assert "TOTAL_PAGES: 1" in header
        assert not any("NEXT_PAGE:" in line for line in header)

    def test_empty_results(self):
        """Should handle empty results correctly."""
        header = build_pagination_header("empty", total_count=0, limit=10, offset=0)
        assert "SHOWING_RESULTS: 0-0" in header
        assert "TOTAL_RESULTS: 0" in header

    def test_offset_beyond_results(self):
        """Should handle offset beyond total results."""
        header = build_pagination_header("far", total_count=10, limit=20, offset=100)
        # When offset > total_count, count=0, start_result=0, end_result=offset+count=100
        # This is the actual behavior - shows 0-100 range even though no results
        assert "SHOWING_RESULTS: 0-100" in header


# === Tests for build_pagination_summary ===


class TestBuildPaginationSummary:
    """Tests for build_pagination_summary function."""

    def test_multi_page_first(self):
        """Should build summary for first page of multi-page results."""
        summary = build_pagination_summary(total_count=50, limit=10, offset=0)
        assert "PAGINATION_SUMMARY:" in summary
        assert any("showing_page: 1 of 5" in line for line in summary)
        assert any("showing_results: 1-10 of 50" in line for line in summary)
        assert any("results_per_page: 10" in line for line in summary)
        assert any("next_page_offset: 10" in line for line in summary)
        # No prev_page on first page
        assert not any("prev_page_offset" in line for line in summary)

    def test_multi_page_middle(self):
        """Should build summary for middle page with both prev and next."""
        summary = build_pagination_summary(total_count=100, limit=20, offset=40)
        assert any("showing_page: 3 of 5" in line for line in summary)
        assert any("next_page_offset: 60" in line for line in summary)
        assert any("prev_page_offset: 20" in line for line in summary)

    def test_multi_page_last(self):
        """Should build summary for last page without next."""
        summary = build_pagination_summary(total_count=25, limit=10, offset=20)
        assert any("showing_page: 3 of 3" in line for line in summary)
        assert not any("next_page_offset" in line for line in summary)
        assert any("prev_page_offset: 10" in line for line in summary)

    def test_single_page_returns_empty(self):
        """Should return empty list for single page results."""
        summary = build_pagination_summary(total_count=5, limit=10, offset=0)
        assert summary == []


# === Tests for format_find_in_note_summary ===


class TestFormatFindInNoteSummary:
    """Tests for format_find_in_note_summary function."""

    def test_basic_summary(self):
        """Should format summary with matches correctly."""
        result = format_find_in_note_summary(
            limit=20, offset=0, total_count=15, showing_count=15
        )
        assert "SUMMARY:" in result
        assert "showing=15" in result
        assert "range=1-15" in result
        assert "total=15" in result
        assert "page=1/1" in result
        assert "offset=0" in result
        assert "limit=20" in result

    def test_paginated_summary(self):
        """Should format paginated results correctly."""
        result = format_find_in_note_summary(
            limit=10, offset=10, total_count=35, showing_count=10
        )
        assert "showing=10" in result
        assert "range=11-20" in result
        assert "total=35" in result
        assert "page=2/4" in result

    def test_no_matches_summary(self):
        """Should handle no matches correctly."""
        result = format_find_in_note_summary(
            limit=20, offset=0, total_count=0, showing_count=0
        )
        assert "showing=0" in result
        assert "range=0-0" in result
        assert "total=0" in result
        assert "page=1/1" in result

    def test_partial_last_page(self):
        """Should handle partial last page correctly."""
        result = format_find_in_note_summary(
            limit=10, offset=20, total_count=25, showing_count=5
        )
        assert "showing=5" in result
        assert "range=21-25" in result
        assert "page=3/3" in result

    def test_offset_beyond_results(self):
        """Should handle offset beyond total results (empty page)."""
        result = format_find_in_note_summary(
            limit=10, offset=100, total_count=50, showing_count=0
        )
        assert "showing=0" in result
        assert "range=0-0" in result
        assert "total=50" in result


# === Tests for format_note_metadata_lines ===


class TestFormatNoteMetadataLines:
    """Tests for format_note_metadata_lines function."""

    def test_basic_metadata_upper_style(self):
        """Should format metadata with uppercase labels by default."""
        metadata = {
            "note_id": "abc123",
            "title": "Test Note",
            "notebook_path": "Work / Projects",
        }
        lines = format_note_metadata_lines(metadata)
        assert "NOTE_ID: abc123" in lines
        assert "TITLE: Test Note" in lines
        assert "NOTEBOOK_PATH: Work / Projects" in lines

    def test_basic_metadata_lower_style(self):
        """Should format metadata with lowercase labels when specified."""
        metadata = {
            "note_id": "def456",
            "title": "Another Note",
        }
        lines = format_note_metadata_lines(metadata, style="lower")
        assert "note_id: def456" in lines
        assert "title: Another Note" in lines

    def test_metadata_with_indent(self):
        """Should apply indent to all lines."""
        metadata = {
            "note_id": "xyz789",
            "title": "Indented",
        }
        lines = format_note_metadata_lines(metadata, indent="  ")
        for line in lines:
            assert line.startswith("  ")

    def test_boolean_values_formatted(self):
        """Should format boolean values as true/false."""
        metadata = {
            "note_id": "bool123",
            "is_todo": True,
            "todo_completed": False,
        }
        lines = format_note_metadata_lines(metadata)
        assert "IS_TODO: true" in lines
        assert "TODO_COMPLETED: false" in lines

    def test_timestamps_included(self):
        """Should include created and updated timestamps."""
        metadata = {
            "note_id": "time123",
            "created": "2024-01-15 10:30:00",
            "updated": "2024-01-16 14:20:00",
        }
        lines = format_note_metadata_lines(metadata)
        assert "CREATED: 2024-01-15 10:30:00" in lines
        assert "UPDATED: 2024-01-16 14:20:00" in lines

    def test_content_stats_included(self):
        """Should include content stats when provided."""
        metadata = {
            "note_id": "stats123",
            "content_stats": {
                "characters": 1500,
                "words": 250,
                "lines": 45,
            },
        }
        lines = format_note_metadata_lines(metadata)
        assert "CONTENT_SIZE_CHARS: 1500" in lines
        assert "CONTENT_SIZE_WORDS: 250" in lines
        assert "CONTENT_SIZE_LINES: 45" in lines

    def test_content_stats_lower_style(self):
        """Should format content stats with lowercase labels."""
        metadata = {
            "note_id": "lower123",
            "content_stats": {
                "characters": 500,
                "words": 80,
                "lines": 20,
            },
        }
        lines = format_note_metadata_lines(metadata, style="lower")
        assert "content_size_chars: 500" in lines
        assert "content_size_words: 80" in lines
        assert "content_size_lines: 20" in lines

    def test_key_order_preserved(self):
        """Should output keys in defined order."""
        metadata = {
            "title": "Test",
            "note_id": "order123",
            "updated": "2024-01-16",
            "created": "2024-01-15",
            "notebook_path": "Work",
            "notebook_id": "nb123",
        }
        lines = format_note_metadata_lines(metadata)
        # Find indices
        note_id_idx = next(i for i, l in enumerate(lines) if "NOTE_ID" in l)
        title_idx = next(i for i, l in enumerate(lines) if "TITLE" in l)
        created_idx = next(i for i, l in enumerate(lines) if "CREATED" in l)
        updated_idx = next(i for i, l in enumerate(lines) if "UPDATED" in l)
        notebook_id_idx = next(i for i, l in enumerate(lines) if "NOTEBOOK_ID" in l)
        notebook_path_idx = next(i for i, l in enumerate(lines) if "NOTEBOOK_PATH" in l)

        # Verify order: note_id, title, created, updated, notebook_id, notebook_path
        assert note_id_idx < title_idx
        assert title_idx < created_idx
        assert created_idx < updated_idx
        assert updated_idx < notebook_id_idx
        assert notebook_id_idx < notebook_path_idx

    def test_missing_keys_skipped(self):
        """Should skip keys not present in metadata."""
        metadata = {
            "note_id": "sparse123",
            "title": "Sparse Note",
        }
        lines = format_note_metadata_lines(metadata)
        assert len(lines) == 2
        assert not any("CREATED" in line for line in lines)
        assert not any("UPDATED" in line for line in lines)
        assert not any("NOTEBOOK" in line for line in lines)
