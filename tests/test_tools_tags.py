"""Tests for tools/tags.py - Tag tool helpers and tool functions."""

from unittest.mock import MagicMock, patch

import pytest


def _get_tool_fn(tool):
    """Get the underlying function from a tool (handles both wrapped and unwrapped)."""
    if hasattr(tool, 'fn'):
        return tool.fn
    return tool


# === Tests for _tag_note_impl helper ===


class TestTagNoteImpl:
    """Tests for _tag_note_impl helper function."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_tag_id_by_name")
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_tags_note_successfully(self, mock_get_client, mock_get_tag_id):
        """Should tag a note successfully."""
        from joplin_mcp.tools.tags import _tag_note_impl

        mock_note = MagicMock()
        mock_note.title = "Test Note"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client
        mock_get_tag_id.return_value = "tag_id_123"

        result = await _tag_note_impl("note_id_456", "important")

        mock_client.get_note.assert_called_once()
        mock_get_tag_id.assert_called_once_with("important")
        mock_client.add_tag_to_note.assert_called_once_with("tag_id_123", "note_id_456")
        assert "tagged note" in result.lower()
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_raises_error_when_note_not_found(self, mock_get_client):
        """Should raise error when note doesn't exist."""
        from joplin_mcp.tools.tags import _tag_note_impl

        mock_client = MagicMock()
        mock_client.get_note.side_effect = Exception("Note not found")
        mock_get_client.return_value = mock_client

        with pytest.raises(ValueError) as exc_info:
            await _tag_note_impl("nonexistent_note", "tag")
        assert "not found" in str(exc_info.value)
        assert "find_notes" in str(exc_info.value)


# === Tests for _untag_note_impl helper ===


class TestUntagNoteImpl:
    """Tests for _untag_note_impl helper function."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_tag_id_by_name")
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_untags_note_successfully(self, mock_get_client, mock_get_tag_id):
        """Should remove tag from note successfully."""
        from joplin_mcp.tools.tags import _untag_note_impl

        mock_note = MagicMock()
        mock_note.title = "Test Note"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client
        mock_get_tag_id.return_value = "tag_id_789"

        result = await _untag_note_impl("note_id_111", "old-tag")

        mock_client.remove_tag_from_note.assert_called_once_with("tag_id_789", "note_id_111")
        assert "removed tag" in result.lower()
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_raises_error_when_note_not_found(self, mock_get_client):
        """Should raise error when note doesn't exist."""
        from joplin_mcp.tools.tags import _untag_note_impl

        mock_client = MagicMock()
        mock_client.get_note.side_effect = Exception("Note not found")
        mock_get_client.return_value = mock_client

        with pytest.raises(ValueError) as exc_info:
            await _untag_note_impl("nonexistent", "tag")
        assert "not found" in str(exc_info.value)


# === Tests for list_tags tool ===


class TestListTagsTool:
    """Tests for list_tags tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.format_tag_list_with_counts")
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_lists_all_tags(self, mock_get_client, mock_format):
        """Should list all tags with counts."""
        from joplin_mcp.tools.tags import list_tags

        mock_tags = [
            MagicMock(id="tag1", title="work"),
            MagicMock(id="tag2", title="personal"),
        ]

        mock_client = MagicMock()
        mock_client.get_all_tags.return_value = mock_tags
        mock_get_client.return_value = mock_client

        mock_format.return_value = "FORMATTED_TAG_LIST"

        fn = _get_tool_fn(list_tags)
        result = await fn()

        mock_client.get_all_tags.assert_called_once()
        mock_format.assert_called_once_with(mock_tags, mock_client)
        assert result == "FORMATTED_TAG_LIST"


# === Tests for create_tag tool ===


class TestCreateTagTool:
    """Tests for create_tag tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_creates_tag_successfully(self, mock_get_client):
        """Should create a new tag."""
        from joplin_mcp.tools.tags import create_tag

        mock_client = MagicMock()
        mock_client.add_tag.return_value = "new_tag_id_123"
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(create_tag)
        result = await fn(title="important")

        mock_client.add_tag.assert_called_once_with(title="important")
        assert "CREATE_TAG" in result
        assert "SUCCESS" in result
        assert "important" in result


# === Tests for update_tag tool ===


class TestUpdateTagTool:
    """Tests for update_tag tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_updates_tag_title(self, mock_get_client):
        """Should update tag title."""
        from joplin_mcp.tools.tags import update_tag

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(update_tag)
        result = await fn(
            tag_id="12345678901234567890123456789012",
            title="renamed-tag"
        )

        mock_client.modify_tag.assert_called_once_with(
            "12345678901234567890123456789012",
            title="renamed-tag"
        )
        assert "UPDATE_TAG" in result
        assert "SUCCESS" in result


# === Tests for delete_tag tool ===


class TestDeleteTagTool:
    """Tests for delete_tag tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_deletes_tag(self, mock_get_client):
        """Should delete a tag."""
        from joplin_mcp.tools.tags import delete_tag

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(delete_tag)
        result = await fn(tag_id="12345678901234567890123456789012")

        mock_client.delete_tag.assert_called_once_with("12345678901234567890123456789012")
        assert "DELETE_TAG" in result
        assert "SUCCESS" in result


# === Tests for get_tags_by_note tool ===


class TestGetTagsByNoteTool:
    """Tests for get_tags_by_note tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.format_item_list")
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_gets_tags_for_note(self, mock_get_client, mock_format):
        """Should get all tags for a note."""
        from joplin_mcp.tools.tags import get_tags_by_note
        from joplin_mcp.fastmcp_server import ItemType

        mock_tags = [
            MagicMock(id="tag1", title="work"),
            MagicMock(id="tag2", title="important"),
        ]

        mock_client = MagicMock()
        mock_client.get_tags.return_value = mock_tags
        mock_get_client.return_value = mock_client

        mock_format.return_value = "FORMATTED_TAGS"

        fn = _get_tool_fn(get_tags_by_note)
        result = await fn(note_id="12345678901234567890123456789012")

        mock_client.get_tags.assert_called_once()
        call_kwargs = mock_client.get_tags.call_args[1]
        assert call_kwargs["note_id"] == "12345678901234567890123456789012"
        mock_format.assert_called_once()
        assert result == "FORMATTED_TAGS"

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.format_no_results_message")
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_returns_no_results_when_no_tags(self, mock_get_client, mock_format):
        """Should return no results message when note has no tags."""
        from joplin_mcp.tools.tags import get_tags_by_note

        mock_client = MagicMock()
        mock_client.get_tags.return_value = []
        mock_get_client.return_value = mock_client

        mock_format.return_value = "NO_TAGS_MESSAGE"

        fn = _get_tool_fn(get_tags_by_note)
        result = await fn(note_id="12345678901234567890123456789012")

        mock_format.assert_called_once_with("tag", "for note: 12345678901234567890123456789012")
        assert result == "NO_TAGS_MESSAGE"


# === Tests for tag_note tool ===


class TestTagNoteTool:
    """Tests for tag_note tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags._tag_note_impl")
    async def test_calls_implementation(self, mock_impl):
        """Should delegate to _tag_note_impl."""
        from joplin_mcp.tools.tags import tag_note

        mock_impl.return_value = "TAG_RESULT"

        fn = _get_tool_fn(tag_note)
        result = await fn(
            note_id="12345678901234567890123456789012",
            tag_name="important"
        )

        mock_impl.assert_called_once_with(
            "12345678901234567890123456789012",
            "important"
        )
        assert result == "TAG_RESULT"


# === Tests for untag_note tool ===


class TestUntagNoteTool:
    """Tests for untag_note tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags._untag_note_impl")
    async def test_calls_implementation(self, mock_impl):
        """Should delegate to _untag_note_impl."""
        from joplin_mcp.tools.tags import untag_note

        mock_impl.return_value = "UNTAG_RESULT"

        fn = _get_tool_fn(untag_note)
        result = await fn(
            note_id="12345678901234567890123456789012",
            tag_name="old-tag"
        )

        mock_impl.assert_called_once_with(
            "12345678901234567890123456789012",
            "old-tag"
        )
        assert result == "UNTAG_RESULT"
