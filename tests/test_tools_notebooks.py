"""Tests for tools/notebooks.py - Notebook tool functions."""

from unittest.mock import MagicMock, patch

import pytest


def _get_tool_fn(tool):
    """Get the underlying function from a tool (handles both wrapped and unwrapped)."""
    if hasattr(tool, 'fn'):
        return tool.fn
    return tool


# === Tests for list_notebooks tool ===


class TestListNotebooksTool:
    """Tests for list_notebooks tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.format_item_list")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_lists_all_notebooks(self, mock_get_client, mock_format):
        """Should list all notebooks."""
        from joplin_mcp.tools.notebooks import list_notebooks
        from joplin_mcp.fastmcp_server import ItemType

        mock_notebooks = [
            MagicMock(id="nb1", title="Work", parent_id=None),
            MagicMock(id="nb2", title="Personal", parent_id=None),
            MagicMock(id="nb3", title="Projects", parent_id="nb1"),
        ]

        mock_client = MagicMock()
        mock_client.get_all_notebooks.return_value = mock_notebooks
        mock_get_client.return_value = mock_client

        mock_format.return_value = "FORMATTED_NOTEBOOKS"

        fn = _get_tool_fn(list_notebooks)
        result = await fn()

        mock_client.get_all_notebooks.assert_called_once()
        assert "id,title,created_time,updated_time,parent_id" in mock_client.get_all_notebooks.call_args[1]["fields"]
        mock_format.assert_called_once_with(mock_notebooks, ItemType.notebook)
        assert result == "FORMATTED_NOTEBOOKS"


# === Tests for create_notebook tool ===


class TestCreateNotebookTool:
    """Tests for create_notebook tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_creates_notebook_successfully(self, mock_get_client, mock_invalidate):
        """Should create a new notebook."""
        from joplin_mcp.tools.notebooks import create_notebook

        mock_client = MagicMock()
        mock_client.add_notebook.return_value = "new_notebook_id_12345"
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(create_notebook)
        result = await fn(title="My New Notebook")

        mock_client.add_notebook.assert_called_once_with(title="My New Notebook")
        assert "CREATE_NOTEBOOK" in result
        assert "SUCCESS" in result
        assert "My New Notebook" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_creates_sub_notebook(self, mock_get_client, mock_invalidate):
        """Should create a sub-notebook with parent_id."""
        from joplin_mcp.tools.notebooks import create_notebook

        mock_client = MagicMock()
        mock_client.add_notebook.return_value = "sub_notebook_id_67890"
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(create_notebook)
        result = await fn(
            title="Sub Notebook",
            parent_id="parent_id_12345"
        )

        mock_client.add_notebook.assert_called_once()
        call_kwargs = mock_client.add_notebook.call_args[1]
        assert call_kwargs["title"] == "Sub Notebook"
        assert call_kwargs["parent_id"] == "parent_id_12345"
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_invalidates_cache_after_create(self, mock_get_client, mock_invalidate):
        """Should invalidate notebook cache after creating."""
        from joplin_mcp.tools.notebooks import create_notebook

        mock_client = MagicMock()
        mock_client.add_notebook.return_value = "nb_id"
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(create_notebook)
        await fn(title="Test")

        mock_invalidate.assert_called_once()

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_strips_whitespace_from_parent_id(self, mock_get_client, mock_invalidate):
        """Should strip whitespace from parent_id."""
        from joplin_mcp.tools.notebooks import create_notebook

        mock_client = MagicMock()
        mock_client.add_notebook.return_value = "nb_id"
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(create_notebook)
        await fn(title="Test", parent_id="  parent_id  ")

        call_kwargs = mock_client.add_notebook.call_args[1]
        assert call_kwargs["parent_id"] == "parent_id"


# === Tests for update_notebook tool ===


class TestUpdateNotebookTool:
    """Tests for update_notebook tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_updates_notebook_title(self, mock_get_client, mock_invalidate):
        """Should update notebook title."""
        from joplin_mcp.tools.notebooks import update_notebook

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(update_notebook)
        result = await fn(
            notebook_id="12345678901234567890123456789012",
            title="Renamed Notebook"
        )

        mock_client.modify_notebook.assert_called_once_with(
            "12345678901234567890123456789012",
            title="Renamed Notebook"
        )
        assert "UPDATE_NOTEBOOK" in result
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_invalidates_cache_after_update(self, mock_get_client, mock_invalidate):
        """Should invalidate notebook cache after updating."""
        from joplin_mcp.tools.notebooks import update_notebook

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(update_notebook)
        await fn(
            notebook_id="12345678901234567890123456789012",
            title="New Title"
        )

        mock_invalidate.assert_called_once()


# === Tests for delete_notebook tool ===


class TestDeleteNotebookTool:
    """Tests for delete_notebook tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_deletes_notebook(self, mock_get_client, mock_invalidate):
        """Should delete a notebook."""
        from joplin_mcp.tools.notebooks import delete_notebook

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(delete_notebook)
        result = await fn(notebook_id="12345678901234567890123456789012")

        mock_client.delete_notebook.assert_called_once_with(
            "12345678901234567890123456789012"
        )
        assert "DELETE_NOTEBOOK" in result
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_invalidates_cache_after_delete(self, mock_get_client, mock_invalidate):
        """Should invalidate notebook cache after deleting."""
        from joplin_mcp.tools.notebooks import delete_notebook

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(delete_notebook)
        await fn(notebook_id="12345678901234567890123456789012")

        mock_invalidate.assert_called_once()


# === Integration tests for cache invalidation ===


class TestNotebookCacheInvalidation:
    """Tests to verify all mutating operations invalidate the cache."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_create_invalidates_cache(self, mock_get_client, mock_invalidate):
        """create_notebook should invalidate cache."""
        from joplin_mcp.tools.notebooks import create_notebook

        mock_client = MagicMock()
        mock_client.add_notebook.return_value = "id"
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(create_notebook)
        await fn(title="Test")
        mock_invalidate.assert_called()

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_update_invalidates_cache(self, mock_get_client, mock_invalidate):
        """update_notebook should invalidate cache."""
        from joplin_mcp.tools.notebooks import update_notebook

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(update_notebook)
        await fn(notebook_id="12345678901234567890123456789012", title="Test")
        mock_invalidate.assert_called()

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_delete_invalidates_cache(self, mock_get_client, mock_invalidate):
        """delete_notebook should invalidate cache."""
        from joplin_mcp.tools.notebooks import delete_notebook

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(delete_notebook)
        await fn(notebook_id="12345678901234567890123456789012")
        mock_invalidate.assert_called()
