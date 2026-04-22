"""Tests for tools/tags.py - Tag tool helpers and tool functions."""

from unittest.mock import MagicMock, patch

import pytest


def _get_tool_fn(tool):
    """Get the underlying function from a tool (handles both wrapped and unwrapped)."""
    if hasattr(tool, 'fn'):
        return tool.fn
    return tool


# === Helper for tag-note bulk tests ===


def _make_tag(tag_id: str, title: str):
    """Build a MagicMock that mimics a joppy Tag object with id/title."""
    t = MagicMock()
    t.id = tag_id
    t.title = title
    return t


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


NOTE_A = "a" * 32
NOTE_B = "b" * 32
NOTE_C = "c" * 32


class TestTagNoteTool:
    """Tests for tag_note tool (scalar and bulk paths)."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_tag_id_by_name")
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_scalar_preserves_single_op_format(
        self, mock_get_client, mock_get_tag_id
    ):
        """Scalar + scalar returns the existing single-op success line unchanged."""
        from joplin_mcp.tools.tags import tag_note

        mock_note = MagicMock()
        mock_note.title = "Test Note"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client
        mock_get_tag_id.return_value = "tag_id_123"

        fn = _get_tool_fn(tag_note)
        result = await fn(note_id=NOTE_A, tag_name="Work")

        mock_get_tag_id.assert_called_once_with("Work")
        mock_client.add_tag_to_note.assert_called_once_with("tag_id_123", NOTE_A)
        assert "tagged note" in result.lower()
        assert "SUCCESS" in result
        assert "TOTAL_OPS" not in result  # not the aggregated format

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_scalar_raises_when_note_not_found(self, mock_get_client):
        """Scalar path raises ValueError with find_notes hint when note missing."""
        from joplin_mcp.tools.tags import tag_note

        mock_client = MagicMock()
        mock_client.get_note.side_effect = Exception("Note not found")
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(tag_note)
        with pytest.raises(ValueError) as exc_info:
            await fn(note_id=NOTE_A, tag_name="Work")
        assert "not found" in str(exc_info.value)
        assert "find_notes" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_bulk_report_has_message_line(self, mock_get_client):
        """Aggregated report includes a MESSAGE line matching other tool formatters."""
        from joplin_mcp.tools.tags import tag_note

        mock_client = MagicMock()
        mock_client.get_all_tags.return_value = [_make_tag("t1", "Work")]

        def side_effect(tag_id, note_id):
            if note_id == NOTE_B:
                raise Exception("boom")

        mock_client.add_tag_to_note.side_effect = side_effect
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(tag_note)
        # Partial case
        partial = await fn(note_id=[NOTE_A, NOTE_B], tag_name="Work")
        assert "MESSAGE: 1 of 2 operations succeeded" in partial

        # All-success case
        mock_client.add_tag_to_note.side_effect = None
        all_ok = await fn(note_id=[NOTE_A, NOTE_C], tag_name="Work")
        assert "MESSAGE: 2 of 2 operations succeeded" in all_ok

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_list_notes_scalar_tag(self, mock_get_client):
        """List of notes + scalar tag applies the tag to each note once."""
        from joplin_mcp.tools.tags import tag_note

        mock_client = MagicMock()
        mock_client.get_all_tags.return_value = [_make_tag("tag1", "Work")]
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(tag_note)
        result = await fn(note_id=[NOTE_A, NOTE_B], tag_name="Work")

        assert mock_client.add_tag_to_note.call_count == 2
        mock_client.add_tag_to_note.assert_any_call("tag1", NOTE_A)
        mock_client.add_tag_to_note.assert_any_call("tag1", NOTE_B)
        assert "OPERATION: TAG_NOTE" in result
        assert "STATUS: SUCCESS" in result
        assert "TOTAL_OPS: 2" in result
        assert "SUCCEEDED: 2" in result
        assert "FAILED: 0" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_scalar_note_list_tags_single_tag_fetch(self, mock_get_client):
        """Scalar note + list tags resolves via ONE get_all_tags fetch."""
        from joplin_mcp.tools.tags import tag_note

        mock_client = MagicMock()
        mock_client.get_all_tags.return_value = [
            _make_tag("t1", "Work"),
            _make_tag("t2", "Urgent"),
        ]
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(tag_note)
        result = await fn(note_id=NOTE_A, tag_name=["Work", "Urgent"])

        mock_client.get_all_tags.assert_called_once()
        assert mock_client.add_tag_to_note.call_count == 2
        mock_client.add_tag_to_note.assert_any_call("t1", NOTE_A)
        mock_client.add_tag_to_note.assert_any_call("t2", NOTE_A)
        assert "TOTAL_OPS: 2" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_list_notes_list_tags_cartesian(self, mock_get_client):
        """List x list applies cartesian product: N*M add_tag_to_note calls."""
        from joplin_mcp.tools.tags import tag_note

        mock_client = MagicMock()
        mock_client.get_all_tags.return_value = [
            _make_tag("t1", "Work"),
            _make_tag("t2", "Urgent"),
        ]
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(tag_note)
        result = await fn(
            note_id=[NOTE_A, NOTE_B, NOTE_C],
            tag_name=["Work", "Urgent"],
        )

        assert mock_client.add_tag_to_note.call_count == 6
        assert "TOTAL_OPS: 6" in result
        assert "SUCCEEDED: 6" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_missing_tag_raises_before_any_mutation(self, mock_get_client):
        """Any missing tag in list raises ValueError and no mutation is attempted."""
        from joplin_mcp.tools.tags import tag_note

        mock_client = MagicMock()
        mock_client.get_all_tags.return_value = [_make_tag("t1", "Work")]
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(tag_note)
        with pytest.raises(ValueError) as exc_info:
            await fn(note_id=[NOTE_A, NOTE_B], tag_name=["Work", "DoesNotExist"])

        assert "not found" in str(exc_info.value)
        assert "'DoesNotExist'" in str(exc_info.value)
        assert "create_tag" in str(exc_info.value)
        mock_client.add_tag_to_note.assert_not_called()

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_partial_failure_captured_in_report(self, mock_get_client):
        """Per-op exceptions are captured; other ops still run; STATUS becomes PARTIAL."""
        from joplin_mcp.tools.tags import tag_note

        mock_client = MagicMock()
        mock_client.get_all_tags.return_value = [_make_tag("t1", "Work")]

        # Fail on the 2nd add_tag_to_note call, succeed on others.
        def side_effect(tag_id, note_id):
            if note_id == NOTE_B:
                raise Exception("simulated note-missing error")

        mock_client.add_tag_to_note.side_effect = side_effect
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(tag_note)
        result = await fn(note_id=[NOTE_A, NOTE_B, NOTE_C], tag_name="Work")

        assert mock_client.add_tag_to_note.call_count == 3
        assert "STATUS: PARTIAL" in result
        assert "TOTAL_OPS: 3" in result
        assert "SUCCEEDED: 2" in result
        assert "FAILED: 1" in result
        assert "FAILURES:" in result
        assert NOTE_B in result
        assert "simulated note-missing error" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_token_redacted_in_failure_messages(self, mock_get_client):
        """Auth tokens in per-op exception strings must be redacted in the report."""
        from joplin_mcp.tools.tags import tag_note

        mock_client = MagicMock()
        mock_client.get_all_tags.return_value = [_make_tag("t1", "Work")]
        mock_client.add_tag_to_note.side_effect = Exception(
            "404 Not Found: http://localhost:41184/notes/abc?fields=id&token=SECRET123"
        )
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(tag_note)
        result = await fn(note_id=[NOTE_A], tag_name="Work")

        assert "SECRET123" not in result
        assert "token=***" in result

    @pytest.mark.asyncio
    async def test_empty_note_list_raises(self):
        """Empty note_id list raises ValueError without touching the client."""
        from joplin_mcp.tools.tags import tag_note

        fn = _get_tool_fn(tag_note)
        with pytest.raises(ValueError, match="note_id list must not be empty"):
            await fn(note_id=[], tag_name=["Work"])

    @pytest.mark.asyncio
    async def test_empty_tag_list_raises(self):
        """Empty tag_name list raises ValueError without touching the client."""
        from joplin_mcp.tools.tags import tag_note

        fn = _get_tool_fn(tag_note)
        with pytest.raises(ValueError, match="tag_name list must not be empty"):
            await fn(note_id=[NOTE_A], tag_name=[])

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_tag_name_case_insensitive_resolution(self, mock_get_client):
        """Tag name lookup is case-insensitive, matching get_tag_id_by_name behaviour."""
        from joplin_mcp.tools.tags import tag_note

        mock_client = MagicMock()
        mock_client.get_all_tags.return_value = [_make_tag("t1", "Work")]
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(tag_note)
        await fn(note_id=[NOTE_A], tag_name=["WORK"])

        mock_client.add_tag_to_note.assert_called_once_with("t1", NOTE_A)

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_ambiguous_tag_title_raises(self, mock_get_client):
        """Duplicate Joplin tag titles raise ValueError in bulk, matching scalar-path parity."""
        from joplin_mcp.tools.tags import tag_note

        mock_client = MagicMock()
        mock_client.get_all_tags.return_value = [
            _make_tag("t1", "Work"),
            _make_tag("t2", "Work"),  # same title — ambiguous
        ]
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(tag_note)
        with pytest.raises(ValueError) as exc_info:
            await fn(note_id=[NOTE_A], tag_name=["Work"])

        assert "Ambiguous" in str(exc_info.value)
        assert "'Work'" in str(exc_info.value)
        mock_client.add_tag_to_note.assert_not_called()

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_failure_report_sanitises_quotes_and_newlines(self, mock_get_client):
        """Multi-line errors and embedded quotes must not break the one-line-per-failure format."""
        from joplin_mcp.tools.tags import tag_note

        mock_client = MagicMock()
        mock_client.get_all_tags.return_value = [_make_tag("t1", "Work")]
        mock_client.add_tag_to_note.side_effect = Exception(
            'line1\nline2 with "inner" quotes\nline3'
        )
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(tag_note)
        result = await fn(note_id=[NOTE_A], tag_name="Work")

        # Pull out just the failure line and verify it's a single line with balanced quotes.
        failure_lines = [
            line for line in result.splitlines() if line.lstrip().startswith("- note_id=")
        ]
        assert len(failure_lines) == 1
        fline = failure_lines[0]
        # No literal newlines inside the error field.
        assert "line1 line2" in fline
        # No unescaped inner double quotes leaked.
        # We expect 4 `"` total: 2 around tag_name and 2 around error.
        assert fline.count('"') == 4

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_tag_id_by_name")
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_scalar_path_propagates_missing_tag_error(
        self, mock_get_client, mock_get_tag_id
    ):
        """Scalar path surfaces get_tag_id_by_name's ValueError when the tag is missing."""
        from joplin_mcp.tools.tags import tag_note

        mock_note = MagicMock()
        mock_note.title = "Test Note"
        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client
        mock_get_tag_id.side_effect = ValueError(
            "Tag 'Ghost' not found. Available tags: Work. Use create_tag to create a new tag."
        )

        fn = _get_tool_fn(tag_note)
        with pytest.raises(ValueError) as exc_info:
            await fn(note_id=NOTE_A, tag_name="Ghost")

        assert "'Ghost'" in str(exc_info.value)
        assert "create_tag" in str(exc_info.value)
        mock_client.add_tag_to_note.assert_not_called()


# === Tests for untag_note tool ===


class TestUntagNoteTool:
    """Tests for untag_note tool (scalar and bulk paths)."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_tag_id_by_name")
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_scalar_preserves_single_op_format(
        self, mock_get_client, mock_get_tag_id
    ):
        """Scalar + scalar returns the existing single-op success line unchanged."""
        from joplin_mcp.tools.tags import untag_note

        mock_note = MagicMock()
        mock_note.title = "Test Note"
        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client
        mock_get_tag_id.return_value = "tag_id_789"

        fn = _get_tool_fn(untag_note)
        result = await fn(note_id=NOTE_A, tag_name="Work")

        mock_client.delete.assert_called_once_with(f"/tags/tag_id_789/notes/{NOTE_A}")
        assert "removed tag" in result.lower()
        assert "SUCCESS" in result
        assert "TOTAL_OPS" not in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_scalar_raises_when_note_not_found(self, mock_get_client):
        """Scalar path raises ValueError with find_notes hint when note missing."""
        from joplin_mcp.tools.tags import untag_note

        mock_client = MagicMock()
        mock_client.get_note.side_effect = Exception("Note not found")
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(untag_note)
        with pytest.raises(ValueError) as exc_info:
            await fn(note_id=NOTE_A, tag_name="Work")
        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_list_notes_list_tags_cartesian(self, mock_get_client):
        """List x list issues N*M delete calls against the correct paths."""
        from joplin_mcp.tools.tags import untag_note

        mock_client = MagicMock()
        mock_client.get_all_tags.return_value = [
            _make_tag("t1", "Work"),
            _make_tag("t2", "Urgent"),
        ]
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(untag_note)
        result = await fn(note_id=[NOTE_A, NOTE_B], tag_name=["Work", "Urgent"])

        assert mock_client.delete.call_count == 4
        mock_client.delete.assert_any_call(f"/tags/t1/notes/{NOTE_A}")
        mock_client.delete.assert_any_call(f"/tags/t2/notes/{NOTE_B}")
        assert "OPERATION: UNTAG_NOTE" in result
        assert "TOTAL_OPS: 4" in result
        assert "SUCCEEDED: 4" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_missing_tag_raises_before_any_mutation(self, mock_get_client):
        """Missing tag raises ValueError, no delete calls attempted."""
        from joplin_mcp.tools.tags import untag_note

        mock_client = MagicMock()
        mock_client.get_all_tags.return_value = [_make_tag("t1", "Work")]
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(untag_note)
        with pytest.raises(ValueError) as exc_info:
            await fn(note_id=[NOTE_A], tag_name=["Work", "Ghost"])

        assert "'Ghost'" in str(exc_info.value)
        mock_client.delete.assert_not_called()

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_partial_failure_captured_in_report(self, mock_get_client):
        """Per-op delete exceptions are captured in the aggregated report."""
        from joplin_mcp.tools.tags import untag_note

        mock_client = MagicMock()
        mock_client.get_all_tags.return_value = [_make_tag("t1", "Work")]

        def side_effect(path):
            if NOTE_B in path:
                raise Exception("tag not on note")

        mock_client.delete.side_effect = side_effect
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(untag_note)
        result = await fn(note_id=[NOTE_A, NOTE_B], tag_name="Work")

        assert "STATUS: PARTIAL" in result
        assert "SUCCEEDED: 1" in result
        assert "FAILED: 1" in result
        assert "tag not on note" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_token_redacted_in_failure_messages(self, mock_get_client):
        """Auth tokens in per-op delete exceptions must be redacted in the report."""
        from joplin_mcp.tools.tags import untag_note

        mock_client = MagicMock()
        mock_client.get_all_tags.return_value = [_make_tag("t1", "Work")]
        mock_client.delete.side_effect = Exception(
            "404 Not Found: http://localhost:41184/tags/t1/notes/abc?token=SECRET999"
        )
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(untag_note)
        result = await fn(note_id=[NOTE_A], tag_name="Work")

        assert "SECRET999" not in result
        assert "token=***" in result
