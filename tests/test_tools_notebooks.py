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

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.notebook_resolver")
    async def test_creates_with_emoji_icon(self, mock_resolver):
        """Should serialise emoji into Joplin's icon JSON shape."""
        import json
        from joplin_mcp.tools.notebooks import create_notebook

        mock_resolver.add_notebook.return_value = "nb_id"

        fn = _get_tool_fn(create_notebook)
        await fn(title="Tasks", emoji="🎯")

        call_kwargs = mock_resolver.add_notebook.call_args[1]
        assert call_kwargs["title"] == "Tasks"
        assert json.loads(call_kwargs["icon"]) == {
            "type": 1,
            "emoji": "🎯",
            "name": "",
        }

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.notebook_resolver")
    async def test_creates_with_zwj_emoji_icon(self, mock_resolver):
        """ZWJ emoji sequences (e.g. family, profession) round-trip cleanly."""
        import json
        from joplin_mcp.tools.notebooks import create_notebook

        mock_resolver.add_notebook.return_value = "nb_id"

        fn = _get_tool_fn(create_notebook)
        await fn(title="Family", emoji="👨‍👩‍👧")

        call_kwargs = mock_resolver.add_notebook.call_args[1]
        assert json.loads(call_kwargs["icon"])["emoji"] == "👨‍👩‍👧"

    @pytest.mark.asyncio
    async def test_rejects_word_as_emoji(self):
        """A non-emoji string should be rejected — guards against the agent
        stuffing a title-like value into the emoji parameter."""
        from joplin_mcp.tools.notebooks import create_notebook

        fn = _get_tool_fn(create_notebook)
        with pytest.raises(ValueError, match="emoji"):
            await fn(title="Bad", emoji="hello")

    @pytest.mark.asyncio
    async def test_rejects_over_long_emoji(self):
        """Length cap protects against multi-emoji or pasted prose."""
        from joplin_mcp.tools.notebooks import create_notebook

        fn = _get_tool_fn(create_notebook)
        with pytest.raises(ValueError, match="emoji"):
            await fn(title="Bad", emoji="this is a sentence, not an emoji")

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.notebook_resolver")
    async def test_accepts_long_zwj_sequence_with_skin_tones(self, mock_resolver):
        """Skin-tone ZWJ sequences (e.g. kiss-with-skin-tones) can reach ~10
        codepoints. They must clear the length cap or we'd reject legitimate
        emojis chosen by Joplin's picker."""
        import json
        from joplin_mcp.tools.notebooks import create_notebook

        mock_resolver.add_notebook.return_value = "nb_id"

        kiss = "👩🏽‍❤️‍💋‍👨🏿"  # 10 codepoints
        fn = _get_tool_fn(create_notebook)
        await fn(title="Couple", emoji=kiss)

        call_kwargs = mock_resolver.add_notebook.call_args[1]
        assert json.loads(call_kwargs["icon"])["emoji"] == kiss


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

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.notebook_resolver")
    async def test_updates_emoji_only(self, mock_resolver):
        """Should accept emoji-only updates without requiring a title."""
        import json
        from joplin_mcp.tools.notebooks import update_notebook

        fn = _get_tool_fn(update_notebook)
        await fn(
            notebook_id="12345678901234567890123456789012",
            emoji="🕰️",
        )

        call_args, call_kwargs = mock_resolver.modify_notebook.call_args
        assert call_args == ("12345678901234567890123456789012",)
        assert "title" not in call_kwargs
        assert json.loads(call_kwargs["icon"]) == {
            "type": 1,
            "emoji": "🕰️",
            "name": "",
        }

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.notebook_resolver")
    async def test_clears_emoji_with_empty_string(self, mock_resolver):
        """`emoji=""` should clear the icon by sending an empty string to Joplin."""
        from joplin_mcp.tools.notebooks import update_notebook

        fn = _get_tool_fn(update_notebook)
        await fn(
            notebook_id="12345678901234567890123456789012",
            emoji="",
        )

        _, call_kwargs = mock_resolver.modify_notebook.call_args
        assert call_kwargs["icon"] == ""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.notebook_resolver")
    async def test_updates_title_and_emoji_together(self, mock_resolver):
        """Both fields can be updated in a single call."""
        from joplin_mcp.tools.notebooks import update_notebook

        fn = _get_tool_fn(update_notebook)
        await fn(
            notebook_id="12345678901234567890123456789012",
            title="Renamed",
            emoji="📁",
        )

        _, call_kwargs = mock_resolver.modify_notebook.call_args
        assert call_kwargs["title"] == "Renamed"
        assert "icon" in call_kwargs

    @pytest.mark.asyncio
    async def test_rejects_update_with_no_fields(self):
        """Calling update_notebook with nothing to change should be an error."""
        from joplin_mcp.tools.notebooks import update_notebook

        fn = _get_tool_fn(update_notebook)
        with pytest.raises(ValueError, match="At least one field"):
            await fn(notebook_id="12345678901234567890123456789012")

    @pytest.mark.asyncio
    async def test_rejects_empty_title(self):
        """An empty `title` would silently rename the notebook to "" — reject
        it at the Pydantic boundary instead. Regression guard."""
        from joplin_mcp.tools.notebooks import update_notebook

        with pytest.raises(ValidationError, match="at least 1 character"):
            await update_notebook.run(
                {
                    "notebook_id": "12345678901234567890123456789012",
                    "title": "",
                }
            )


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


# === Tests for _format_notebook_icon (list_notebooks output parsing) ===


class TestFormatNotebookIcon:
    """Tests for the icon-field renderer used by format_item_list."""

    def test_renders_emoji_icon(self):
        from joplin_mcp.fastmcp_server import _format_notebook_icon

        line = _format_notebook_icon('{"type":1,"emoji":"🎯","name":""}')
        assert line == "  emoji: 🎯"

    def test_renders_zwj_emoji_icon(self):
        from joplin_mcp.fastmcp_server import _format_notebook_icon

        line = _format_notebook_icon('{"type":1,"emoji":"👨‍👩‍👧","name":""}')
        assert line == "  emoji: 👨‍👩‍👧"

    def test_renders_legacy_typeless_emoji_icon(self):
        """Older Joplin entries in the wild store emoji icons without an
        explicit `type` field. Dispatching on the `emoji` key (not `type==1`)
        keeps them rendering correctly."""
        from joplin_mcp.fastmcp_server import _format_notebook_icon

        line = _format_notebook_icon('{"emoji":"🎩","name":"top hat"}')
        assert line == "  emoji: 🎩"

    def test_flags_image_icon(self):
        """Non-emoji icon types should be surfaced as 'image' so the agent
        knows an icon exists without trying to render it."""
        from joplin_mcp.fastmcp_server import _format_notebook_icon

        line = _format_notebook_icon('{"type":2,"name":"folder","dataUrl":"data:image/png;base64,..."}')
        assert line == "  icon: image"

    def test_skips_empty_icon(self):
        from joplin_mcp.fastmcp_server import _format_notebook_icon

        assert _format_notebook_icon("") is None
        assert _format_notebook_icon(None) is None

    def test_skips_unparseable_icon(self):
        """Corrupt or unexpected JSON should be silently skipped rather than
        breaking the listing."""
        from joplin_mcp.fastmcp_server import _format_notebook_icon

        assert _format_notebook_icon("not json at all") is None
        assert _format_notebook_icon("[1,2,3]") is None  # JSON but not a dict

    def test_skips_emoji_type_without_emoji_field(self):
        """A type=1 icon with no emoji glyph is malformed — skip rather than
        render an empty line."""
        from joplin_mcp.fastmcp_server import _format_notebook_icon

        assert _format_notebook_icon('{"type":1,"name":""}') is None
