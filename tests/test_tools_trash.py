"""Tests for tools/trash.py - Trash management tool functions."""

from unittest.mock import MagicMock, patch

import pytest


def _get_tool_fn(tool):
    """Get the underlying function from a tool (handles both wrapped and unwrapped)."""
    if hasattr(tool, 'fn'):
        return tool.fn
    return tool


# === Tests for restore_from_trash tool ===


class TestRestoreFromTrashTool:
    """Tests for restore_from_trash tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.trash._clear_note_cache")
    @patch("joplin_mcp.tools.trash.get_joplin_client")
    async def test_restores_note(self, mock_get_client, mock_clear_cache):
        """Should restore a note by setting deleted_time to 0."""
        from joplin_mcp.tools.trash import restore_from_trash

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(restore_from_trash)
        result = await fn(
            item_id="12345678901234567890123456789012",
            item_type="note",
        )

        mock_client.modify_note.assert_called_once_with(
            "12345678901234567890123456789012", deleted_time=0
        )
        mock_clear_cache.assert_called_once()
        assert "RESTORE_NOTE" in result
        assert "SUCCESS" in result
        assert "12345678901234567890123456789012" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.trash.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.trash.get_joplin_client")
    async def test_restores_notebook(self, mock_get_client, mock_invalidate_cache):
        """Should restore a notebook by setting deleted_time to 0."""
        from joplin_mcp.tools.trash import restore_from_trash

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(restore_from_trash)
        result = await fn(
            item_id="12345678901234567890123456789012",
            item_type="notebook",
        )

        mock_client.modify_notebook.assert_called_once_with(
            "12345678901234567890123456789012", deleted_time=0
        )
        mock_invalidate_cache.assert_called_once()
        assert "RESTORE_NOTEBOOK" in result
        assert "SUCCESS" in result
        assert "12345678901234567890123456789012" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.trash.get_joplin_client")
    async def test_rejects_invalid_item_type(self, mock_get_client):
        """Should raise ValueError for invalid item_type."""
        from joplin_mcp.tools.trash import restore_from_trash

        mock_get_client.return_value = MagicMock()

        fn = _get_tool_fn(restore_from_trash)
        with pytest.raises(ValueError, match="item_type must be"):
            await fn(
                item_id="12345678901234567890123456789012",
                item_type="tag",
            )

    @pytest.mark.asyncio
    async def test_rejects_invalid_item_id(self):
        """Should reject item_id that is not a valid 32-char hex string."""
        from joplin_mcp.tools.trash import restore_from_trash

        fn = _get_tool_fn(restore_from_trash)
        with pytest.raises((ValueError, Exception)):
            await fn(item_id="not-a-valid-id", item_type="note")

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.trash._clear_note_cache")
    @patch("joplin_mcp.tools.trash.get_joplin_client")
    async def test_output_format_has_uppercase_keys(self, mock_get_client, mock_clear_cache):
        """Output should use uppercase keys matching project conventions."""
        from joplin_mcp.tools.trash import restore_from_trash

        mock_get_client.return_value = MagicMock()

        fn = _get_tool_fn(restore_from_trash)
        result = await fn(
            item_id="12345678901234567890123456789012",
            item_type="note",
        )

        lines = result.strip().split("\n")
        keys = [line.split(":")[0].strip() for line in lines]
        assert keys == ["OPERATION", "STATUS", "ITEM_TYPE", "ITEM_ID", "MESSAGE"]
