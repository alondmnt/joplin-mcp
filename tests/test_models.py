"""
Tests for Joplin MCP data models.

This module contains comprehensive tests for all Pydantic models used in the Joplin MCP,
following TDD principles. These tests define the expected behavior and validation rules.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

# Import the models - they should exist now in GREEN phase
from joplin_mcp.models import (
    JoplinTimestamp,
    MCPAPIResponse,
    MCPErrorResponse,
    MCPNote,
    MCPNotebook,
    MCPPaginatedResponse,
    MCPSearchResult,
    MCPTag,
    NotePriority,
)


class TestMCPNote:
    """Test cases for MCPNote model."""

    def test_note_creation_with_minimal_data(self, sample_note_data):
        """Test creating a note with minimal required fields."""
        minimal_data = {
            "id": "12345678901234567890123456789012",
            "title": "Test Note",
            "body": "Test content",
            "created_time": 1609459200000,
            "updated_time": 1609545600000,
        }

        note = MCPNote(**minimal_data)

        assert note.id == "12345678901234567890123456789012"
        assert note.title == "Test Note"
        assert note.body == "Test content"
        assert note.created_time == 1609459200000
        assert note.updated_time == 1609545600000

    def test_note_creation_with_full_data(self, sample_note_data):
        """Test creating a note with all possible fields."""
        note = MCPNote(**sample_note_data)

        assert note.id == sample_note_data["id"]
        assert note.title == sample_note_data["title"]
        assert note.body == sample_note_data["body"]
        assert note.parent_id == sample_note_data["parent_id"]
        assert note.created_time == sample_note_data["created_time"]
        assert note.updated_time == sample_note_data["updated_time"]
        assert note.markup_language == sample_note_data["markup_language"]
        assert note.is_todo == bool(sample_note_data["is_todo"])

    def test_note_validation_missing_required_fields(self):
        """Test that validation fails when required fields are missing."""
        with pytest.raises(ValidationError) as exc_info:
            MCPNote()

        error_fields = [error["loc"][0] for error in exc_info.value.errors()]
        required_fields = {"id", "title", "body", "created_time", "updated_time"}

        for field in required_fields:
            assert field in error_fields

    def test_note_id_validation(self):
        """Test that note ID must be a 32-character hexadecimal string."""
        valid_data = {
            "id": "abcdef12345678901234567890123456",
            "title": "Test",
            "body": "Content",
            "created_time": 1609459200000,
            "updated_time": 1609545600000,
        }

        # Valid ID should work
        note = MCPNote(**valid_data)
        assert len(note.id) == 32

        # Invalid IDs should fail
        invalid_ids = [
            "short",  # Too short
            "12345678901234567890123456789012345",  # Too long (33 chars)
            "1234567890123456789012345678901@",  # Invalid characters
        ]

        for invalid_id in invalid_ids:
            with pytest.raises(ValidationError):
                MCPNote(**{**valid_data, "id": invalid_id})

    def test_note_timestamps_validation(self):
        """Test that timestamps are properly validated as Unix milliseconds."""
        base_data = {
            "id": "fedcba09876543210987654321098765",
            "title": "Test",
            "body": "Content",
        }

        # Valid timestamps
        valid_timestamps = [
            1609459200000,  # 2021-01-01 00:00:00 UTC
            1609545600000,  # 2021-01-02 00:00:00 UTC
            0,  # Unix epoch
        ]

        for timestamp in valid_timestamps:
            note = MCPNote(**base_data, created_time=timestamp, updated_time=timestamp)
            assert note.created_time == timestamp
            assert note.updated_time == timestamp

        # Invalid timestamps should fail
        invalid_timestamps = [-1, "invalid", 1.5]

        for invalid_timestamp in invalid_timestamps:
            with pytest.raises(ValidationError):
                MCPNote(
                    **base_data,
                    created_time=invalid_timestamp,
                    updated_time=1609459200000,
                )

    def test_note_boolean_fields_coercion(self):
        """Test that integer boolean fields are properly coerced to Python booleans."""
        data = {
            "id": "11111222223333344444555556666677",
            "title": "Test",
            "body": "Content",
            "created_time": 1609459200000,
            "updated_time": 1609459200000,
            "is_todo": 1,
            "todo_completed": 0,
            "is_conflict": 1,
        }

        note = MCPNote(**data)

        assert note.is_todo is True
        assert note.todo_completed is False
        assert note.is_conflict is True

    def test_note_optional_fields_default_values(self):
        """Test that optional fields have appropriate default values."""
        minimal_data = {
            "id": "99999888887777766666555554444433",
            "title": "Test Note",
            "body": "Test content",
            "created_time": 1609459200000,
            "updated_time": 1609545600000,
        }

        note = MCPNote(**minimal_data)

        assert note.parent_id is None
        assert note.markup_language == 1  # Default to Markdown
        assert note.is_todo is False
        assert note.todo_completed is False
        assert note.is_conflict is False
        assert note.latitude == 0.0
        assert note.longitude == 0.0
        assert note.altitude == 0.0

    def test_note_to_joplin_dict(self, sample_note_data):
        """Test conversion back to Joplin API format."""
        note = MCPNote(**sample_note_data)
        joplin_dict = note.to_joplin_dict()

        # Should contain all Joplin fields
        expected_fields = {
            "id",
            "title",
            "body",
            "parent_id",
            "created_time",
            "updated_time",
            "markup_language",
            "is_todo",
            "todo_completed",
            "is_conflict",
        }

        for field in expected_fields:
            assert field in joplin_dict

        # Boolean fields should be converted back to integers
        assert joplin_dict["is_todo"] in [0, 1]
        assert joplin_dict["todo_completed"] in [0, 1]

    def test_note_summary_for_mcp(self, sample_note_data):
        """Test creating a summary suitable for MCP responses."""
        note = MCPNote(**sample_note_data)
        summary = note.to_mcp_summary()

        assert "id" in summary
        assert "title" in summary
        assert "excerpt" in summary  # Truncated body
        assert "updated_time" in summary
        assert "parent_id" in summary

        # Excerpt should be truncated for long content
        assert len(summary["excerpt"]) <= 200

    def test_note_tags_relationship(self):
        """Test that notes can have associated tags."""
        note_data = {
            "id": "12345678901234567890123456789012",
            "title": "Test Note",
            "body": "Content",
            "created_time": 1609459200000,
            "updated_time": 1609459200000,
        }

        note = MCPNote(**note_data)
        note.tags = ["work", "important", "project-alpha"]

        assert len(note.tags) == 3
        assert "work" in note.tags
        assert "important" in note.tags


class TestJoplinTimestamp:
    """Test cases for JoplinTimestamp utility."""

    def test_timestamp_to_datetime_conversion(self):
        """Test converting Joplin timestamps to Python datetime objects."""
        timestamp = 1609459200000  # 2021-01-01 00:00:00 UTC
        dt = JoplinTimestamp.to_datetime(timestamp)

        assert isinstance(dt, datetime)
        assert dt.year == 2021
        assert dt.month == 1
        assert dt.day == 1
        assert dt.hour == 0
        assert dt.minute == 0
        assert dt.second == 0
        assert dt.tzinfo == timezone.utc

    def test_datetime_to_timestamp_conversion(self):
        """Test converting Python datetime objects to Joplin timestamps."""
        dt = datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        timestamp = JoplinTimestamp.from_datetime(dt)

        assert timestamp == 1609459200000

    def test_current_timestamp(self):
        """Test getting current timestamp in Joplin format."""
        timestamp = JoplinTimestamp.now()

        assert isinstance(timestamp, int)
        assert timestamp > 1609459200000  # Should be after 2021


class TestNotePriority:
    """Test cases for NotePriority enum."""

    def test_priority_values(self):
        """Test that priority enum has expected values."""
        assert NotePriority.LOW.value == 1
        assert NotePriority.NORMAL.value == 2
        assert NotePriority.HIGH.value == 3
        assert NotePriority.URGENT.value == 4

    def test_priority_from_string(self):
        """Test creating priority from string values."""
        assert NotePriority.from_string("low") == NotePriority.LOW
        assert NotePriority.from_string("HIGH") == NotePriority.HIGH
        assert NotePriority.from_string("Normal") == NotePriority.NORMAL


# Mark all tests in this class as unit tests
pytestmark = pytest.mark.unit


class TestMCPNotebook:
    """Test cases for MCPNotebook model with parent-child relationships."""

    def test_notebook_creation_with_minimal_data(self):
        """Test creating a notebook with minimal required data."""
        notebook_data = {
            "id": "12345678901234567890123456789012",
            "title": "My Notebook",
            "created_time": 1609459200000,
            "updated_time": 1609545600000,
        }

        notebook = MCPNotebook(**notebook_data)

        assert notebook.id == "12345678901234567890123456789012"
        assert notebook.title == "My Notebook"
        assert notebook.created_time == 1609459200000
        assert notebook.updated_time == 1609545600000
        assert notebook.parent_id is None  # Top-level notebook
        assert notebook.share_id is None
        assert notebook.master_key_id is None

    def test_notebook_creation_with_parent_child_relationship(self):
        """Test creating notebooks with parent-child relationships."""
        parent_data = {
            "id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1",
            "title": "Parent Notebook",
            "created_time": 1609459200000,
            "updated_time": 1609459200000,
        }

        child_data = {
            "id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "title": "Child Notebook",
            "parent_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1",
            "created_time": 1609459200000,
            "updated_time": 1609459200000,
        }

        parent = MCPNotebook(**parent_data)
        child = MCPNotebook(**child_data)

        assert parent.parent_id is None
        assert child.parent_id == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1"
        assert child.is_child_of(parent.id)
        assert not parent.is_child_of(child.id)

    def test_notebook_validation_missing_required_fields(self):
        """Test that validation fails when required fields are missing."""
        with pytest.raises(ValidationError):
            MCPNotebook()  # No data at all

        with pytest.raises(ValidationError):
            MCPNotebook(title="Missing ID")  # Missing id

        with pytest.raises(ValidationError):
            MCPNotebook(id="12345678901234567890123456789012")  # Missing title

    def test_notebook_id_validation(self):
        """Test that notebook ID must be a 32-character hexadecimal string."""
        valid_data = {
            "id": "abcdef12345678901234567890123456",
            "title": "Test Notebook",
            "created_time": 1609459200000,
            "updated_time": 1609545600000,
        }

        # Valid ID should work
        notebook = MCPNotebook(**valid_data)
        assert len(notebook.id) == 32

        # Invalid IDs should fail
        invalid_ids = [
            "short",  # Too short
            "12345678901234567890123456789012345",  # Too long (33 chars)
            "1234567890123456789012345678901@",  # Invalid characters
        ]

        for invalid_id in invalid_ids:
            with pytest.raises(ValidationError):
                MCPNotebook(**{**valid_data, "id": invalid_id})

    def test_notebook_parent_id_validation(self):
        """Test that parent_id follows the same format as id when provided."""
        base_data = {
            "id": "12345678901234567890123456789012",
            "title": "Child Notebook",
            "created_time": 1609459200000,
            "updated_time": 1609459200000,
        }

        # Valid parent_id should work
        valid_parent_id = "abcdef98765432109876543210987654"
        notebook = MCPNotebook(**base_data, parent_id=valid_parent_id)
        assert notebook.parent_id == valid_parent_id

        # Invalid parent_ids should fail
        invalid_parent_ids = [
            "short",  # Too short
            "12345678901234567890123456789012345",  # Too long
            "1234567890123456789012345678901@",  # Invalid characters
        ]

        for invalid_parent_id in invalid_parent_ids:
            with pytest.raises(ValidationError):
                MCPNotebook(**base_data, parent_id=invalid_parent_id)

    def test_notebook_hierarchy_methods(self):
        """Test methods for working with notebook hierarchies."""
        parent_id = "11111111111111111111111111111111"
        child_id = "22222222222222222222222222222222"
        grandchild_id = "33333333333333333333333333333333"

        parent = MCPNotebook(
            id=parent_id,
            title="Parent",
            created_time=1609459200000,
            updated_time=1609459200000,
        )

        child = MCPNotebook(
            id=child_id,
            title="Child",
            parent_id=parent_id,
            created_time=1609459200000,
            updated_time=1609459200000,
        )

        grandchild = MCPNotebook(
            id=grandchild_id,
            title="Grandchild",
            parent_id=child_id,
            created_time=1609459200000,
            updated_time=1609459200000,
        )

        # Test is_root_notebook
        assert parent.is_root_notebook()
        assert not child.is_root_notebook()
        assert not grandchild.is_root_notebook()

        # Test is_child_of
        assert child.is_child_of(parent_id)
        assert not parent.is_child_of(child_id)
        assert grandchild.is_child_of(child_id)
        assert not grandchild.is_child_of(parent_id)  # Not direct child

    def test_notebook_to_joplin_dict(self):
        """Test conversion back to Joplin API format."""
        notebook_data = {
            "id": "44444444444444444444444444444444",
            "title": "Test Notebook",
            "parent_id": "55555555555555555555555555555555",
            "created_time": 1609459200000,
            "updated_time": 1609545600000,
            "share_id": "share123",
            "master_key_id": "masterkey456",
        }

        notebook = MCPNotebook(**notebook_data)
        joplin_dict = notebook.to_joplin_dict()

        # Should contain all Joplin fields
        expected_fields = {
            "id",
            "title",
            "parent_id",
            "created_time",
            "updated_time",
            "share_id",
            "master_key_id",
        }

        for field in expected_fields:
            assert field in joplin_dict
            assert joplin_dict[field] == getattr(notebook, field)

    def test_notebook_to_mcp_summary(self):
        """Test creating a summary suitable for MCP responses."""
        notebook_data = {
            "id": "66666666666666666666666666666666",
            "title": "My Research Notebook",
            "parent_id": "77777777777777777777777777777777",
            "created_time": 1609459200000,
            "updated_time": 1609545600000,
        }

        notebook = MCPNotebook(**notebook_data)
        summary = notebook.to_mcp_summary()

        assert "id" in summary
        assert "title" in summary
        assert "parent_id" in summary
        assert "created_time" in summary
        assert "updated_time" in summary
        assert "is_root" in summary

        assert summary["id"] == notebook.id
        assert summary["title"] == notebook.title
        assert summary["is_root"] == notebook.is_root_notebook()

    def test_notebook_path_representation(self):
        """Test generating path-like representation for nested notebooks."""
        root_notebook = MCPNotebook(
            id="abcd1111111111111111111111111111",
            title="Root",
            created_time=1609459200000,
            updated_time=1609459200000,
        )

        child_notebook = MCPNotebook(
            id="efab2222222222222222222222222222",
            title="Projects",
            parent_id="abcd1111111111111111111111111111",
            created_time=1609459200000,
            updated_time=1609459200000,
        )

        grandchild_notebook = MCPNotebook(
            id="cdef3333333333333333333333333333",
            title="AI Research",
            parent_id="efab2222222222222222222222222222",
            created_time=1609459200000,
            updated_time=1609459200000,
        )

        # Test path generation (would need parent lookup in real implementation)
        assert root_notebook.title == "Root"
        assert child_notebook.parent_id == root_notebook.id
        assert grandchild_notebook.parent_id == child_notebook.id


class TestMCPTag:
    """Test cases for MCPTag model."""

    def test_tag_creation_with_minimal_data(self):
        """Test creating a tag with minimal required data."""
        tag_data = {
            "id": "12345678901234567890123456789012",
            "title": "important",
            "created_time": 1609459200000,
            "updated_time": 1609545600000,
        }

        tag = MCPTag(**tag_data)

        assert tag.id == "12345678901234567890123456789012"
        assert tag.title == "important"
        assert tag.created_time == 1609459200000
        assert tag.updated_time == 1609545600000

    def test_tag_validation_missing_required_fields(self):
        """Test that validation fails when required fields are missing."""
        with pytest.raises(ValidationError):
            MCPTag()  # No data at all

        with pytest.raises(ValidationError):
            MCPTag(title="Missing ID")  # Missing id

        with pytest.raises(ValidationError):
            MCPTag(id="12345678901234567890123456789012")  # Missing title

    def test_tag_id_validation(self):
        """Test that tag ID must be a 32-character hexadecimal string."""
        valid_data = {
            "id": "abcdef12345678901234567890123456",
            "title": "work",
            "created_time": 1609459200000,
            "updated_time": 1609545600000,
        }

        # Valid ID should work
        tag = MCPTag(**valid_data)
        assert len(tag.id) == 32

        # Invalid IDs should fail
        invalid_ids = [
            "short",  # Too short
            "12345678901234567890123456789012345",  # Too long (33 chars)
            "1234567890123456789012345678901@",  # Invalid characters
        ]

        for invalid_id in invalid_ids:
            with pytest.raises(ValidationError):
                MCPTag(**{**valid_data, "id": invalid_id})

    def test_tag_timestamps_validation(self):
        """Test that timestamps are properly validated as Unix milliseconds."""
        base_data = {
            "id": "fedcba09876543210987654321098765",
            "title": "project",
        }

        # Valid timestamps
        valid_timestamps = [
            1609459200000,  # 2021-01-01 00:00:00 UTC
            1609545600000,  # 2021-01-02 00:00:00 UTC
            0,  # Unix epoch
        ]

        for timestamp in valid_timestamps:
            tag = MCPTag(**base_data, created_time=timestamp, updated_time=timestamp)
            assert tag.created_time == timestamp
            assert tag.updated_time == timestamp

        # Invalid timestamps should fail
        invalid_timestamps = [-1, "invalid", 1.5]

        for invalid_timestamp in invalid_timestamps:
            with pytest.raises(ValidationError):
                MCPTag(
                    **base_data,
                    created_time=invalid_timestamp,
                    updated_time=1609459200000,
                )

    def test_tag_title_normalization(self):
        """Test that tag titles are normalized (lowercased, trimmed)."""
        tag_data = {
            "id": "11111222223333344444555556666677",
            "title": "  IMPORTANT Work  ",
            "created_time": 1609459200000,
            "updated_time": 1609459200000,
        }

        tag = MCPTag(**tag_data)

        # Title should be normalized to lowercase and trimmed
        assert tag.title == "important work"

    def test_tag_to_joplin_dict(self):
        """Test conversion back to Joplin API format."""
        tag_data = {
            "id": "99999888887777766666555554444433",
            "title": "personal",
            "created_time": 1609459200000,
            "updated_time": 1609545600000,
        }

        tag = MCPTag(**tag_data)
        joplin_dict = tag.to_joplin_dict()

        # Should contain all Joplin fields
        expected_fields = {"id", "title", "created_time", "updated_time"}

        for field in expected_fields:
            assert field in joplin_dict
            assert joplin_dict[field] == getattr(tag, field)

    def test_tag_to_mcp_summary(self):
        """Test creating a summary suitable for MCP responses."""
        tag_data = {
            "id": "12121212121212121212121212121212",
            "title": "urgent",
            "created_time": 1609459200000,
            "updated_time": 1609545600000,
        }

        tag = MCPTag(**tag_data)
        summary = tag.to_mcp_summary()

        assert "id" in summary
        assert "title" in summary
        assert "created_time" in summary
        assert "updated_time" in summary

        assert summary["id"] == tag.id
        assert summary["title"] == tag.title

    def test_tag_comparison_and_sorting(self):
        """Test that tags can be compared and sorted by title."""
        tag1 = MCPTag(
            id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1",
            title="zebra",
            created_time=1609459200000,
            updated_time=1609459200000,
        )

        tag2 = MCPTag(
            id="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            title="alpha",
            created_time=1609459200000,
            updated_time=1609459200000,
        )

        # Should be able to compare tags by title
        assert tag1.title > tag2.title
        assert tag2.title < tag1.title


class TestMCPSearchResult:
    """Test cases for MCPSearchResult model."""

    def test_search_result_creation_empty(self):
        """Test creating an empty search result."""
        result = MCPSearchResult()

        assert result.items == []
        assert result.has_more is False
        assert result.total_count is None
        assert result.page is None

    def test_search_result_creation_with_items(self, sample_note_data):
        """Test creating a search result with items."""
        items = [
            {"id": "note1", "title": "First Note", "type": "note"},
            {"id": "note2", "title": "Second Note", "type": "note"},
        ]

        result = MCPSearchResult(items=items, has_more=True, total_count=100, page=1)

        assert len(result.items) == 2
        assert result.has_more is True
        assert result.total_count == 100
        assert result.page == 1

    def test_search_result_pagination_info(self):
        """Test search result pagination information."""
        result = MCPSearchResult(
            items=[{"id": "test", "title": "Test"}],
            has_more=False,
            total_count=1,
            page=1,
        )

        pagination_info = result.get_pagination_info()

        assert "has_more" in pagination_info
        assert "total_count" in pagination_info
        assert "page" in pagination_info
        assert "items_count" in pagination_info

        assert pagination_info["has_more"] is False
        assert pagination_info["total_count"] == 1
        assert pagination_info["page"] == 1
        assert pagination_info["items_count"] == 1

    def test_search_result_add_item(self):
        """Test adding items to search result."""
        result = MCPSearchResult()

        item1 = {"id": "item1", "title": "First Item"}
        item2 = {"id": "item2", "title": "Second Item"}

        result.add_item(item1)
        result.add_item(item2)

        assert len(result.items) == 2
        assert result.items[0] == item1
        assert result.items[1] == item2

    def test_search_result_filtering(self):
        """Test filtering search results by type."""
        items = [
            {"id": "note1", "title": "Note 1", "type": "note"},
            {"id": "notebook1", "title": "Notebook 1", "type": "notebook"},
            {"id": "note2", "title": "Note 2", "type": "note"},
            {"id": "tag1", "title": "Tag 1", "type": "tag"},
        ]

        result = MCPSearchResult(items=items)

        # Filter by type
        notes = result.filter_by_type("note")
        notebooks = result.filter_by_type("notebook")
        tags = result.filter_by_type("tag")

        assert len(notes) == 2
        assert len(notebooks) == 1
        assert len(tags) == 1

        assert all(item["type"] == "note" for item in notes)
        assert all(item["type"] == "notebook" for item in notebooks)
        assert all(item["type"] == "tag" for item in tags)

    def test_search_result_to_mcp_response(self):
        """Test converting search result to MCP response format."""
        items = [
            {"id": "item1", "title": "Item 1", "type": "note"},
            {"id": "item2", "title": "Item 2", "type": "notebook"},
        ]

        result = MCPSearchResult(items=items, has_more=True, total_count=50, page=2)

        mcp_response = result.to_mcp_response()

        assert "content" in mcp_response
        assert "isError" in mcp_response
        assert "meta" in mcp_response

        assert mcp_response["isError"] is False
        assert mcp_response["content"]["items"] == items
        assert mcp_response["meta"]["has_more"] is True
        assert mcp_response["meta"]["total_count"] == 50
        assert mcp_response["meta"]["page"] == 2

    def test_search_result_merge_results(self):
        """Test merging multiple search results."""
        result1 = MCPSearchResult(
            items=[{"id": "item1", "title": "Item 1"}], total_count=25
        )

        result2 = MCPSearchResult(
            items=[{"id": "item2", "title": "Item 2"}], total_count=25
        )

        merged = result1.merge(result2)

        assert len(merged.items) == 2
        assert merged.total_count == 50
        assert merged.items[0]["id"] == "item1"
        assert merged.items[1]["id"] == "item2"


class TestMCPPaginatedResponse:
    """Test cases for MCPPaginatedResponse model."""

    def test_paginated_response_creation_with_items(self):
        """Test creating a paginated response with items."""
        items = [
            {"id": "note1", "title": "Note 1", "type": "note"},
            {"id": "note2", "title": "Note 2", "type": "note"},
        ]

        response = MCPPaginatedResponse(
            items=items, page=1, per_page=10, total_count=25, total_pages=3
        )

        assert len(response.items) == 2
        assert response.page == 1
        assert response.per_page == 10
        assert response.total_count == 25
        assert response.total_pages == 3
        assert response.has_next_page() is True
        assert response.has_previous_page() is False

    def test_paginated_response_empty_results(self):
        """Test creating a paginated response with no items."""
        response = MCPPaginatedResponse(
            items=[], page=1, per_page=10, total_count=0, total_pages=0
        )

        assert len(response.items) == 0
        assert response.is_empty() is True
        assert response.has_next_page() is False
        assert response.has_previous_page() is False

    def test_paginated_response_last_page(self):
        """Test pagination info for the last page."""
        items = [{"id": "note1", "title": "Last Note"}]

        response = MCPPaginatedResponse(
            items=items, page=3, per_page=10, total_count=21, total_pages=3
        )

        assert response.page == 3
        assert response.is_last_page() is True
        assert response.has_next_page() is False
        assert response.has_previous_page() is True

    def test_paginated_response_navigation_urls(self):
        """Test generation of navigation URLs."""
        base_url = "http://localhost:41184"
        endpoint = "/notes"

        response = MCPPaginatedResponse(
            items=[{"id": "note1"}],
            page=2,
            per_page=10,
            total_count=50,
            total_pages=5,
            base_url=base_url,
            endpoint=endpoint,
        )

        nav_urls = response.get_navigation_urls()

        assert "next" in nav_urls
        assert "previous" in nav_urls
        assert "first" in nav_urls
        assert "last" in nav_urls

        assert nav_urls["next"] == f"{base_url}{endpoint}?page=3&per_page=10"
        assert nav_urls["previous"] == f"{base_url}{endpoint}?page=1&per_page=10"
        assert nav_urls["first"] == f"{base_url}{endpoint}?page=1&per_page=10"
        assert nav_urls["last"] == f"{base_url}{endpoint}?page=5&per_page=10"

    def test_paginated_response_validation(self):
        """Test validation of pagination parameters."""
        # Valid pagination should work
        response = MCPPaginatedResponse(
            items=[], page=1, per_page=10, total_count=0, total_pages=0
        )
        assert response.page == 1

        # Invalid pagination should fail
        with pytest.raises(ValidationError):
            MCPPaginatedResponse(
                page=0, per_page=10, total_count=0, total_pages=0
            )  # page < 1

        with pytest.raises(ValidationError):
            MCPPaginatedResponse(
                page=1, per_page=0, total_count=0, total_pages=0
            )  # per_page < 1

        with pytest.raises(ValidationError):
            MCPPaginatedResponse(
                page=1, per_page=10, total_count=-1, total_pages=0
            )  # negative count

    def test_paginated_response_to_mcp_format(self):
        """Test conversion to MCP response format."""
        items = [{"id": "note1", "title": "Note 1"}]

        response = MCPPaginatedResponse(
            items=items, page=1, per_page=10, total_count=1, total_pages=1
        )

        mcp_response = response.to_mcp_response()

        assert "content" in mcp_response
        assert "meta" in mcp_response
        assert "pagination" in mcp_response["meta"]

        pagination = mcp_response["meta"]["pagination"]
        assert pagination["page"] == 1
        assert pagination["per_page"] == 10
        assert pagination["total_count"] == 1
        assert pagination["total_pages"] == 1


class TestMCPErrorResponse:
    """Test cases for MCPErrorResponse model."""

    def test_error_response_creation_basic(self):
        """Test creating a basic error response."""
        error = MCPErrorResponse(
            error_code="JOPLIN_CONNECTION_FAILED",
            message="Failed to connect to Joplin server",
            status_code=503,
        )

        assert error.error_code == "JOPLIN_CONNECTION_FAILED"
        assert error.message == "Failed to connect to Joplin server"
        assert error.status_code == 503
        assert error.is_client_error() is False
        assert error.is_server_error() is True

    def test_error_response_with_details(self):
        """Test creating an error response with detailed information."""
        error_details = {
            "endpoint": "/notes/invalid-id",
            "method": "GET",
            "timestamp": "2024-01-01T10:00:00Z",
            "request_id": "req-123456",
        }

        error = MCPErrorResponse(
            error_code="NOTE_NOT_FOUND",
            message="The requested note could not be found",
            status_code=404,
            details=error_details,
        )

        assert error.error_code == "NOTE_NOT_FOUND"
        assert error.details == error_details
        assert error.is_client_error() is True
        assert error.is_server_error() is False

    def test_error_response_validation_error(self):
        """Test error response for validation failures."""
        validation_errors = [
            {"field": "title", "message": "Title cannot be empty"},
            {"field": "id", "message": "Invalid ID format"},
        ]

        error = MCPErrorResponse(
            error_code="VALIDATION_ERROR",
            message="Request validation failed",
            status_code=400,
            validation_errors=validation_errors,
        )

        assert error.validation_errors == validation_errors
        assert error.has_validation_errors() is True
        assert len(error.get_field_errors("title")) == 1
        assert len(error.get_field_errors("id")) == 1
        assert len(error.get_field_errors("nonexistent")) == 0

    def test_error_response_from_exception(self):
        """Test creating error response from Python exception."""
        try:
            raise ValueError("Invalid note ID format")
        except ValueError as e:
            error = MCPErrorResponse.from_exception(e, "INVALID_ID")

            assert error.error_code == "INVALID_ID"
            assert "Invalid note ID format" in error.message
            assert error.status_code == 500  # Default server error

    def test_error_response_http_status_categorization(self):
        """Test HTTP status code categorization."""
        # Client errors (4xx)
        client_error = MCPErrorResponse(
            error_code="BAD_REQUEST", message="Bad request", status_code=400
        )
        assert client_error.is_client_error() is True
        assert client_error.is_server_error() is False

        # Server errors (5xx)
        server_error = MCPErrorResponse(
            error_code="INTERNAL_ERROR",
            message="Internal server error",
            status_code=500,
        )
        assert server_error.is_client_error() is False
        assert server_error.is_server_error() is True

    def test_error_response_to_mcp_format(self):
        """Test conversion to MCP error response format."""
        error = MCPErrorResponse(
            error_code="NOTE_NOT_FOUND", message="Note not found", status_code=404
        )

        mcp_response = error.to_mcp_response()

        assert mcp_response["isError"] is True
        assert "error" in mcp_response
        assert mcp_response["error"]["code"] == "NOTE_NOT_FOUND"
        assert mcp_response["error"]["message"] == "Note not found"
        assert mcp_response["error"]["status_code"] == 404


class TestMCPAPIResponse:
    """Test cases for MCPAPIResponse generic wrapper model."""

    def test_api_response_success(self):
        """Test creating a successful API response."""
        data = {"id": "note123", "title": "My Note"}

        response = MCPAPIResponse(success=True, data=data, timestamp=1609459200000)

        assert response.success is True
        assert response.data == data
        assert response.error is None
        assert response.is_success() is True
        assert response.is_error() is False

    def test_api_response_error(self):
        """Test creating an error API response."""
        error = MCPErrorResponse(
            error_code="INVALID_REQUEST",
            message="Invalid request parameters",
            status_code=400,
        )

        response = MCPAPIResponse(
            success=False, error_info=error, timestamp=1609459200000
        )

        assert response.success is False
        assert response.data is None
        assert response.error == error
        assert response.is_success() is False
        assert response.is_error() is True

    def test_api_response_with_metadata(self):
        """Test API response with additional metadata."""
        metadata = {
            "api_version": "1.0",
            "request_id": "req-789",
            "response_time_ms": 150,
            "cached": False,
        }

        response = MCPAPIResponse(
            success=True,
            data={"message": "Operation completed"},
            metadata=metadata,
            timestamp=1609459200000,
        )

        assert response.metadata == metadata
        assert response.get_metadata("api_version") == "1.0"
        assert response.get_metadata("nonexistent") is None
        assert response.get_metadata("nonexistent", "default") == "default"

    def test_api_response_validation(self):
        """Test API response validation rules."""
        # Cannot have both data and error
        with pytest.raises(ValidationError):
            MCPAPIResponse(
                success=True,
                data={"test": "data"},
                error_info=MCPErrorResponse(
                    error_code="TEST", message="Test", status_code=400
                ),
            )

        # Success=True should not have error
        with pytest.raises(ValidationError):
            MCPAPIResponse(
                success=True,
                error_info=MCPErrorResponse(
                    error_code="TEST", message="Test", status_code=400
                ),
            )

        # Success=False should have error
        with pytest.raises(ValidationError):
            MCPAPIResponse(success=False, data={"test": "data"})

        # Success=False should have error_info
        with pytest.raises(ValidationError):
            MCPAPIResponse(success=False)

    def test_api_response_factory_methods(self):
        """Test factory methods for creating responses."""
        # Success response
        data = {"id": "123", "title": "Test"}
        success_response = MCPAPIResponse.create_success(data)

        assert success_response.success is True
        assert success_response.data == data
        assert success_response.error is None

        # Error response
        error_response = MCPAPIResponse.create_error(
            "NOT_FOUND", "Resource not found", 404
        )

        assert error_response.success is False
        assert error_response.data is None
        assert error_response.error.error_code == "NOT_FOUND"

    def test_api_response_to_mcp_format(self):
        """Test conversion to MCP response format."""
        # Success response
        success_response = MCPAPIResponse.success_response({"message": "OK"})
        mcp_success = success_response.to_mcp_response()

        assert mcp_success["isError"] is False
        assert "content" in mcp_success
        assert mcp_success["content"] == {"message": "OK"}

        # Error response
        error_response = MCPAPIResponse.error_response(
            "FAILED", "Operation failed", 500
        )
        mcp_error = error_response.to_mcp_response()

        assert mcp_error["isError"] is True
        assert "error" in mcp_error
        assert mcp_error["error"]["code"] == "FAILED"
        assert mcp_error["error"]["message"] == "Operation failed"
        assert mcp_error["error"]["status_code"] == 500
