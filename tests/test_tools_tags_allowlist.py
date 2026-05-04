"""Tests for tag tool allowlist enforcement."""

from unittest.mock import MagicMock, patch

import pytest


def _get_tool_fn(tool):
    """Get the underlying function from a tool (handles both wrapped and unwrapped)."""
    if hasattr(tool, "fn"):
        return tool.fn
    return tool


# === Fixtures ===


@pytest.fixture
def mock_allowlist_config():
    """Enable allowlist in _module_config for tag tools."""
    with patch("joplin_mcp.tools.tags._module_config") as mock_cfg:
        mock_cfg.has_notebook_allowlist = True
        mock_cfg.notebook_allowlist = ["AI", "Projects/*"]
        mock_cfg.tools = {}
        yield mock_cfg


@pytest.fixture
def mock_no_allowlist_config():
    """Explicitly disable allowlist in _module_config for backward compat tests."""
    with patch("joplin_mcp.tools.tags._module_config") as mock_cfg:
        mock_cfg.has_notebook_allowlist = False
        mock_cfg.notebook_allowlist = None
        mock_cfg.tools = {}
        yield mock_cfg


# === Tests for tag_note with allowlist ===


class TestTagNoteAllowlist:
    """Tests for tag_note allowlist validation."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.validate_notebook_access")
    @patch("joplin_mcp.tools.tags.get_tag_id_by_name")
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_tag_note_allowlisted(
        self,
        mock_get_client,
        mock_get_tag_id,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should succeed when note is in an allowlisted notebook."""
        from joplin_mcp.tools.tags import tag_note

        mock_note = MagicMock()
        mock_note.parent_id = "allowlisted_nb_id"
        mock_note.title = "Test Note"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client
        mock_get_tag_id.return_value = "tag_id_123"

        fn = _get_tool_fn(tag_note)
        result = await fn(
            note_id="12345678901234567890123456789012", tag_name="Important"
        )

        mock_validate.assert_called_once_with(
            "allowlisted_nb_id",
            allowlist_entries=mock_allowlist_config.notebook_allowlist,
        )
        mock_client.add_tag_to_note.assert_called_once()
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.validate_notebook_access")
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_tag_note_non_allowlisted(
        self,
        mock_get_client,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should raise error when note is in a non-allowlisted notebook."""
        from joplin_mcp.tools.tags import tag_note

        mock_note = MagicMock()
        mock_note.parent_id = "blocked_nb_id"
        mock_note.title = "Secret Note"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(tag_note)
        with pytest.raises(ValueError, match="Notebook not accessible"):
            await fn(
                note_id="12345678901234567890123456789012", tag_name="Important"
            )

        mock_client.add_tag_to_note.assert_not_called()

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_tag_id_by_name")
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_tag_note_no_allowlist(
        self,
        mock_get_client,
        mock_get_tag_id,
        mock_no_allowlist_config,
    ):
        """Should succeed without allowlist checks when allowlist is disabled."""
        from joplin_mcp.tools.tags import tag_note

        mock_note = MagicMock()
        mock_note.parent_id = "any_nb_id"
        mock_note.title = "Test Note"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client
        mock_get_tag_id.return_value = "tag_id_123"

        fn = _get_tool_fn(tag_note)
        result = await fn(
            note_id="12345678901234567890123456789012", tag_name="Work"
        )

        mock_client.add_tag_to_note.assert_called_once()
        assert "SUCCESS" in result


# === Tests for untag_note with allowlist ===


class TestUntagNoteAllowlist:
    """Tests for untag_note allowlist validation."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.validate_notebook_access")
    @patch("joplin_mcp.tools.tags.get_tag_id_by_name")
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_untag_note_allowlisted(
        self,
        mock_get_client,
        mock_get_tag_id,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should succeed when note is in an allowlisted notebook."""
        from joplin_mcp.tools.tags import untag_note

        mock_note = MagicMock()
        mock_note.parent_id = "allowlisted_nb_id"
        mock_note.title = "Test Note"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client
        mock_get_tag_id.return_value = "tag_id_123"

        fn = _get_tool_fn(untag_note)
        result = await fn(
            note_id="12345678901234567890123456789012", tag_name="Important"
        )

        mock_validate.assert_called_once_with(
            "allowlisted_nb_id",
            allowlist_entries=mock_allowlist_config.notebook_allowlist,
        )
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.validate_notebook_access")
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_untag_note_non_allowlisted(
        self,
        mock_get_client,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should raise error when note is in a non-allowlisted notebook."""
        from joplin_mcp.tools.tags import untag_note

        mock_note = MagicMock()
        mock_note.parent_id = "blocked_nb_id"
        mock_note.title = "Secret Note"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(untag_note)
        with pytest.raises(ValueError, match="Notebook not accessible"):
            await fn(
                note_id="12345678901234567890123456789012", tag_name="Important"
            )

        mock_client.delete.assert_not_called()

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_tag_id_by_name")
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_untag_note_no_allowlist(
        self,
        mock_get_client,
        mock_get_tag_id,
        mock_no_allowlist_config,
    ):
        """Should succeed without allowlist checks when allowlist is disabled."""
        from joplin_mcp.tools.tags import untag_note

        mock_note = MagicMock()
        mock_note.parent_id = "any_nb_id"
        mock_note.title = "Test Note"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client
        mock_get_tag_id.return_value = "tag_id_123"

        fn = _get_tool_fn(untag_note)
        result = await fn(
            note_id="12345678901234567890123456789012", tag_name="Work"
        )

        assert "SUCCESS" in result


# === Tests for get_tags_by_note with allowlist ===


class TestGetTagsByNoteAllowlist:
    """Tests for get_tags_by_note allowlist validation."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.validate_notebook_access")
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_get_tags_by_note_allowlisted(
        self,
        mock_get_client,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should succeed when note is in an allowlisted notebook."""
        from joplin_mcp.tools.tags import get_tags_by_note

        mock_note = MagicMock()
        mock_note.parent_id = "allowlisted_nb_id"

        mock_tag = MagicMock()
        mock_tag.title = "Work"
        mock_tag.id = "tag_id_1"
        mock_tag.created_time = 1609459200000
        mock_tag.updated_time = 1609545600000

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_client.get_tags.return_value = [mock_tag]
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(get_tags_by_note)
        result = await fn(note_id="12345678901234567890123456789012")

        mock_validate.assert_called_once_with(
            "allowlisted_nb_id",
            allowlist_entries=mock_allowlist_config.notebook_allowlist,
        )
        assert result is not None

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.validate_notebook_access")
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_get_tags_by_note_non_allowlisted(
        self,
        mock_get_client,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should raise error when note is in a non-allowlisted notebook."""
        from joplin_mcp.tools.tags import get_tags_by_note

        mock_note = MagicMock()
        mock_note.parent_id = "blocked_nb_id"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(get_tags_by_note)
        with pytest.raises(ValueError, match="Notebook not accessible"):
            await fn(note_id="12345678901234567890123456789012")

        mock_client.get_tags.assert_not_called()

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags.get_joplin_client")
    async def test_get_tags_by_note_no_allowlist(
        self,
        mock_get_client,
        mock_no_allowlist_config,
    ):
        """Should succeed without allowlist checks when allowlist is disabled."""
        from joplin_mcp.tools.tags import get_tags_by_note

        mock_tag = MagicMock()
        mock_tag.title = "Work"
        mock_tag.id = "tag_id_1"
        mock_tag.created_time = 1609459200000
        mock_tag.updated_time = 1609545600000

        mock_client = MagicMock()
        mock_client.get_tags.return_value = [mock_tag]
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(get_tags_by_note)
        result = await fn(note_id="12345678901234567890123456789012")

        mock_client.get_note.assert_not_called()
        assert result is not None
