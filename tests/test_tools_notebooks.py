"""Tests for tools/notebooks.py - Notebook tool functions.

Mutation tools route through ``notebook_resolver`` so cache invalidation is
guaranteed by the resolver itself. Tests therefore patch the resolver
instance imported into ``tools.notebooks`` and assert on its mutation
methods rather than the raw client.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError


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
    @patch("joplin_mcp.tools.notebooks.notebook_resolver")
    async def test_creates_notebook_successfully(self, mock_resolver):
        """Should create a new notebook through the resolver."""
        from joplin_mcp.tools.notebooks import create_notebook

        mock_resolver.add_notebook.return_value = "new_notebook_id_12345"

        fn = _get_tool_fn(create_notebook)
        result = await fn(title="My New Notebook")

        mock_resolver.add_notebook.assert_called_once_with(title="My New Notebook")
        assert "CREATE_NOTEBOOK" in result
        assert "SUCCESS" in result
        assert "My New Notebook" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.notebook_resolver")
    async def test_creates_sub_notebook(self, mock_resolver):
        """Should create a sub-notebook with parent_id."""
        from joplin_mcp.tools.notebooks import create_notebook

        mock_resolver.add_notebook.return_value = "sub_notebook_id_67890"

        fn = _get_tool_fn(create_notebook)
        result = await fn(
            title="Sub Notebook",
            parent_id="12345678901234567890123456789012"
        )

        mock_resolver.add_notebook.assert_called_once()
        call_kwargs = mock_resolver.add_notebook.call_args[1]
        assert call_kwargs["title"] == "Sub Notebook"
        assert call_kwargs["parent_id"] == "12345678901234567890123456789012"
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.notebook_resolver")
    async def test_create_routes_through_resolver(self, mock_resolver):
        """create_notebook should route the write through the resolver so the
        resolver's mutation path can invalidate caches atomically."""
        from joplin_mcp.tools.notebooks import create_notebook

        mock_resolver.add_notebook.return_value = "nb_id"

        fn = _get_tool_fn(create_notebook)
        await fn(title="Test")

        mock_resolver.add_notebook.assert_called_once()

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.notebook_resolver")
    async def test_strips_whitespace_from_parent_id(self, mock_resolver):
        """Should strip whitespace from parent_id."""
        from joplin_mcp.tools.notebooks import create_notebook

        mock_resolver.add_notebook.return_value = "nb_id"

        await create_notebook.run(
            {"title": "Test", "parent_id": " 12345678901234567890123456789012 "}
        )

        call_kwargs = mock_resolver.add_notebook.call_args[1]
        assert call_kwargs["parent_id"] == "12345678901234567890123456789012"

    @pytest.mark.asyncio
    async def test_rejects_string_null_parent_id(self):
        """Should reject the literal string 'null' as parent_id."""
        from joplin_mcp.tools.notebooks import create_notebook

        with pytest.raises(ValidationError, match="at least 32 characters"):
            await create_notebook.run({"title": "Bad Notebook", "parent_id": "null"})

    @pytest.mark.asyncio
    async def test_rejects_blank_parent_id(self):
        """Should reject blank parent_id values instead of treating them as valid."""
        from joplin_mcp.tools.notebooks import create_notebook

        with pytest.raises(ValidationError, match="at least 32 characters"):
            await create_notebook.run({"title": "Bad Notebook", "parent_id": "   "})

    @pytest.mark.asyncio
    async def test_rejects_non_hex_parent_id(self):
        """Should reject 32-char parent IDs that are not valid hex."""
        from joplin_mcp.tools.notebooks import create_notebook

        with pytest.raises(
            ValidationError,
            match="parent_id must be omitted for a top-level notebook",
        ):
            await create_notebook.run(
                {
                    "title": "Bad Notebook",
                    "parent_id": "g2345678901234567890123456789012",
                }
            )

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.notebook_resolver")
    async def test_accepts_explicit_null_parent_id(self, mock_resolver):
        """Should allow explicit null parent_id values via the MCP tool path."""
        from joplin_mcp.tools.notebooks import create_notebook

        mock_resolver.add_notebook.return_value = "nb_id"

        await create_notebook.run({"title": "Top Level Notebook", "parent_id": None})

        mock_resolver.add_notebook.assert_called_once_with(title="Top Level Notebook")


# === Tests for update_notebook tool ===


class TestUpdateNotebookTool:
    """Tests for update_notebook tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.notebook_resolver")
    async def test_updates_notebook_title(self, mock_resolver):
        """Should update notebook title through the resolver."""
        from joplin_mcp.tools.notebooks import update_notebook

        fn = _get_tool_fn(update_notebook)
        result = await fn(
            notebook_id="12345678901234567890123456789012",
            title="Renamed Notebook"
        )

        mock_resolver.modify_notebook.assert_called_once_with(
            "12345678901234567890123456789012",
            title="Renamed Notebook"
        )
        assert "UPDATE_NOTEBOOK" in result
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.notebook_resolver")
    async def test_update_routes_through_resolver(self, mock_resolver):
        """update_notebook should route the write through the resolver so its
        mutation path can invalidate caches atomically."""
        from joplin_mcp.tools.notebooks import update_notebook

        fn = _get_tool_fn(update_notebook)
        await fn(
            notebook_id="12345678901234567890123456789012",
            title="New Title"
        )

        mock_resolver.modify_notebook.assert_called_once()


# === Tests for delete_notebook tool ===


class TestDeleteNotebookTool:
    """Tests for delete_notebook tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.notebook_resolver")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_deletes_notebook(self, mock_get_client, mock_resolver):
        """Should delete a notebook through the resolver."""
        from joplin_mcp.tools.notebooks import delete_notebook

        mock_client = MagicMock()
        mock_client.get_notebook.return_value = MagicMock(id="12345678901234567890123456789012")
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(delete_notebook)
        result = await fn(notebook_id="12345678901234567890123456789012")

        mock_resolver.delete_notebook.assert_called_once_with(
            "12345678901234567890123456789012"
        )
        assert "DELETE_NOTEBOOK" in result
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.notebook_resolver")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_delete_routes_through_resolver(self, mock_get_client, mock_resolver):
        """delete_notebook should route the write through the resolver so its
        mutation path can invalidate caches atomically."""
        from joplin_mcp.tools.notebooks import delete_notebook

        mock_client = MagicMock()
        mock_client.get_notebook.return_value = MagicMock(id="12345678901234567890123456789012")
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(delete_notebook)
        await fn(notebook_id="12345678901234567890123456789012")

        mock_resolver.delete_notebook.assert_called_once()

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.notebook_resolver")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_raises_when_notebook_missing(self, mock_get_client, mock_resolver):
        """Joplin's DELETE is idempotent — silently 200s on a missing notebook.
        delete_notebook must GET first and surface the 404 so a caller doesn't
        see SUCCESS for a no-op. Regression for the smoke-test finding."""
        from joplin_mcp.tools.notebooks import delete_notebook

        mock_client = MagicMock()
        mock_client.get_notebook.side_effect = RuntimeError(
            "404 Client Error: Not Found for url: http://localhost:41184/folders/00000000000000000000000000000000?token=***"
        )
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(delete_notebook)
        with pytest.raises(ValueError, match="404"):
            await fn(notebook_id="00000000000000000000000000000000")

        mock_resolver.delete_notebook.assert_not_called()
