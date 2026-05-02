"""Tests for notebook tool allowlist enforcement."""

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
    """Enable allowlist in _module_config for notebook tools."""
    with patch("joplin_mcp.tools.notebooks._module_config") as mock_cfg:
        mock_cfg.has_notebook_allowlist = True
        mock_cfg.notebook_allowlist = ["AI", "Projects/*"]
        yield mock_cfg


@pytest.fixture
def mock_no_allowlist_config():
    """Explicitly disable allowlist in _module_config for backward compat tests."""
    with patch("joplin_mcp.tools.notebooks._module_config") as mock_cfg:
        mock_cfg.has_notebook_allowlist = False
        mock_cfg.notebook_allowlist = None
        yield mock_cfg


# === Tests for list_notebooks with allowlist ===


class TestListNotebooksAllowlist:
    """Tests for list_notebooks allowlist filtering."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.format_item_list")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_list_notebooks_no_allowlist(
        self, mock_get_client, mock_format, mock_no_allowlist_config
    ):
        """All notebooks returned when no allowlist configured."""
        from joplin_mcp.tools.notebooks import list_notebooks

        mock_notebooks = [
            MagicMock(id="nb1", title="Work"),
            MagicMock(id="nb2", title="Personal"),
        ]
        mock_client = MagicMock()
        mock_client.get_all_notebooks.return_value = mock_notebooks
        mock_get_client.return_value = mock_client
        mock_format.return_value = "ALL_NOTEBOOKS"

        fn = _get_tool_fn(list_notebooks)
        result = await fn()

        # filter_accessible_notebooks should NOT be called
        from joplin_mcp.fastmcp_server import ItemType

        mock_format.assert_called_once_with(mock_notebooks, ItemType.notebook)
        assert result == "ALL_NOTEBOOKS"

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.filter_accessible_notebooks")
    @patch("joplin_mcp.tools.notebooks.format_item_list")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_list_notebooks_with_allowlist(
        self,
        mock_get_client,
        mock_format,
        mock_filter,
        mock_allowlist_config,
    ):
        """Only matching notebooks returned when allowlist configured."""
        from joplin_mcp.tools.notebooks import list_notebooks

        all_notebooks = [
            MagicMock(id="nb1", title="AI"),
            MagicMock(id="nb2", title="Personal"),
            MagicMock(id="nb3", title="Projects"),
        ]
        filtered = [all_notebooks[0], all_notebooks[2]]

        mock_client = MagicMock()
        mock_client.get_all_notebooks.return_value = all_notebooks
        mock_get_client.return_value = mock_client
        mock_filter.return_value = filtered
        mock_format.return_value = "FILTERED_NOTEBOOKS"

        fn = _get_tool_fn(list_notebooks)
        result = await fn()

        mock_filter.assert_called_once_with(
            all_notebooks,
            allowlist_entries=mock_allowlist_config.notebook_allowlist,
        )
        from joplin_mcp.fastmcp_server import ItemType

        mock_format.assert_called_once_with(filtered, ItemType.notebook)
        assert result == "FILTERED_NOTEBOOKS"

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.format_item_list")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_list_notebooks_empty_allowlist(
        self, mock_get_client, mock_format
    ):
        """All notebooks returned when allowlist is empty list (same as none)."""
        # Empty allowlist = has_notebook_allowlist is False in config
        with patch("joplin_mcp.tools.notebooks._module_config") as mock_cfg:
            mock_cfg.has_notebook_allowlist = False
            mock_cfg.notebook_allowlist = []

            from joplin_mcp.tools.notebooks import list_notebooks

            mock_notebooks = [MagicMock(id="nb1", title="Work")]
            mock_client = MagicMock()
            mock_client.get_all_notebooks.return_value = mock_notebooks
            mock_get_client.return_value = mock_client
            mock_format.return_value = "ALL"

            fn = _get_tool_fn(list_notebooks)
            result = await fn()

            from joplin_mcp.fastmcp_server import ItemType

            mock_format.assert_called_once_with(mock_notebooks, ItemType.notebook)
            assert result == "ALL"


# === Tests for create_notebook with allowlist ===


class TestCreateNotebookAllowlist:
    """Tests for create_notebook allowlist validation."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.validate_notebook_access")
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_create_notebook_allowlisted_parent(
        self,
        mock_get_client,
        mock_invalidate,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should succeed when parent notebook is allowlisted."""
        from joplin_mcp.tools.notebooks import create_notebook

        mock_client = MagicMock()
        mock_client.add_notebook.return_value = "new_nb_id"
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(create_notebook)
        result = await fn(title="Sub Notebook", parent_id="allowlisted_parent_id")

        mock_validate.assert_called_once_with(
            "allowlisted_parent_id",
            allowlist_entries=mock_allowlist_config.notebook_allowlist,
        )
        mock_client.add_notebook.assert_called_once()
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.validate_notebook_access")
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_create_notebook_non_allowlisted_parent(
        self,
        mock_get_client,
        mock_invalidate,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should raise error when parent notebook is not allowlisted."""
        from joplin_mcp.tools.notebooks import create_notebook

        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(create_notebook)
        with pytest.raises(ValueError, match="Notebook not accessible"):
            await fn(title="Bad Notebook", parent_id="blocked_parent_id")

        # Verify error message is generic (D7) -- no notebook details leaked
        mock_validate.assert_called_once()
        mock_client = mock_get_client.return_value
        mock_client.add_notebook.assert_not_called()

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_create_notebook_no_parent_no_allowlist(
        self,
        mock_get_client,
        mock_invalidate,
        mock_no_allowlist_config,
    ):
        """Top-level notebook creation succeeds when no allowlist configured."""
        from joplin_mcp.tools.notebooks import create_notebook

        mock_client = MagicMock()
        mock_client.add_notebook.return_value = "top_nb_id"
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(create_notebook)
        result = await fn(title="Top Level")

        mock_client.add_notebook.assert_called_once_with(title="Top Level")
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    async def test_create_notebook_no_parent_with_allowlist_blocked(
        self,
        mock_allowlist_config,
    ):
        """Top-level notebook creation blocked when allowlist is active (no bypass)."""
        from joplin_mcp.tools.notebooks import create_notebook

        fn = _get_tool_fn(create_notebook)
        with pytest.raises(ValueError, match="Notebook not accessible"):
            await fn(title="Rogue Top Level")


# === Tests for update_notebook with allowlist ===


class TestUpdateNotebookAllowlist:
    """Tests for update_notebook allowlist validation."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.validate_notebook_access")
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_update_notebook_allowlisted(
        self,
        mock_get_client,
        mock_invalidate,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should succeed when notebook is allowlisted."""
        from joplin_mcp.tools.notebooks import update_notebook

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(update_notebook)
        result = await fn(
            notebook_id="12345678901234567890123456789012",
            title="Renamed",
        )

        mock_validate.assert_called_once_with(
            "12345678901234567890123456789012",
            allowlist_entries=mock_allowlist_config.notebook_allowlist,
        )
        mock_client.modify_notebook.assert_called_once()
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.validate_notebook_access")
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_update_notebook_non_allowlisted(
        self,
        mock_get_client,
        mock_invalidate,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should raise error when notebook is not allowlisted."""
        from joplin_mcp.tools.notebooks import update_notebook

        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(update_notebook)
        with pytest.raises(ValueError, match="Notebook not accessible"):
            await fn(
                notebook_id="blocked_nb_id_0000000000000000",
                title="Should Fail",
            )

        mock_client = mock_get_client.return_value
        mock_client.modify_notebook.assert_not_called()


# === Tests for delete_notebook with allowlist ===


class TestDeleteNotebookAllowlist:
    """Tests for delete_notebook allowlist validation."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.validate_notebook_access")
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_delete_notebook_allowlisted(
        self,
        mock_get_client,
        mock_invalidate,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should succeed when notebook is allowlisted."""
        from joplin_mcp.tools.notebooks import delete_notebook

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(delete_notebook)
        result = await fn(notebook_id="12345678901234567890123456789012")

        mock_validate.assert_called_once_with(
            "12345678901234567890123456789012",
            allowlist_entries=mock_allowlist_config.notebook_allowlist,
        )
        mock_client.delete_notebook.assert_called_once()
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.validate_notebook_access")
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_delete_notebook_non_allowlisted(
        self,
        mock_get_client,
        mock_invalidate,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should raise error when notebook is not allowlisted."""
        from joplin_mcp.tools.notebooks import delete_notebook

        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(delete_notebook)
        with pytest.raises(ValueError, match="Notebook not accessible"):
            await fn(notebook_id="blocked_nb_id_0000000000000000")

        mock_client = mock_get_client.return_value
        mock_client.delete_notebook.assert_not_called()


# === Backward compatibility tests ===


class TestNotebookAllowlistBackwardCompat:
    """Verify all notebook tools work normally when no allowlist is configured."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.format_item_list")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_list_notebooks_works_without_allowlist(
        self, mock_get_client, mock_format, mock_no_allowlist_config
    ):
        """list_notebooks returns all notebooks when no allowlist."""
        from joplin_mcp.tools.notebooks import list_notebooks

        mock_notebooks = [MagicMock(id="nb1"), MagicMock(id="nb2")]
        mock_client = MagicMock()
        mock_client.get_all_notebooks.return_value = mock_notebooks
        mock_get_client.return_value = mock_client
        mock_format.return_value = "OK"

        fn = _get_tool_fn(list_notebooks)
        result = await fn()
        assert result == "OK"

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_create_notebook_works_without_allowlist(
        self, mock_get_client, mock_invalidate, mock_no_allowlist_config
    ):
        """create_notebook succeeds without allowlist."""
        from joplin_mcp.tools.notebooks import create_notebook

        mock_client = MagicMock()
        mock_client.add_notebook.return_value = "id"
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(create_notebook)
        result = await fn(title="Test")
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_update_notebook_works_without_allowlist(
        self, mock_get_client, mock_invalidate, mock_no_allowlist_config
    ):
        """update_notebook succeeds without allowlist."""
        from joplin_mcp.tools.notebooks import update_notebook

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(update_notebook)
        result = await fn(
            notebook_id="12345678901234567890123456789012", title="New"
        )
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.invalidate_notebook_map_cache")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_delete_notebook_works_without_allowlist(
        self, mock_get_client, mock_invalidate, mock_no_allowlist_config
    ):
        """delete_notebook succeeds without allowlist."""
        from joplin_mcp.tools.notebooks import delete_notebook

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(delete_notebook)
        result = await fn(notebook_id="12345678901234567890123456789012")
        assert "SUCCESS" in result


# === Error message tests (D7) ===


class TestNotebookAllowlistErrorMessages:
    """Verify error messages are generic and do not leak notebook details."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notebooks.validate_notebook_access")
    @patch("joplin_mcp.tools.notebooks.get_joplin_client")
    async def test_error_does_not_contain_notebook_id(
        self, mock_get_client, mock_validate, mock_allowlist_config
    ):
        """Error message should not contain the notebook ID."""
        from joplin_mcp.tools.notebooks import update_notebook

        blocked_id = "secret_notebook_id_00000000000000"
        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(update_notebook)
        with pytest.raises(ValueError) as exc_info:
            await fn(notebook_id=blocked_id, title="X")

        error_msg = str(exc_info.value)
        assert blocked_id not in error_msg
        assert "secret" not in error_msg.lower()
        assert "Notebook not accessible" in error_msg

    @pytest.mark.asyncio
    async def test_create_top_level_error_is_generic(self, mock_allowlist_config):
        """Top-level creation error should be generic."""
        from joplin_mcp.tools.notebooks import create_notebook

        fn = _get_tool_fn(create_notebook)
        with pytest.raises(ValueError) as exc_info:
            await fn(title="My Secret Notebook")

        error_msg = str(exc_info.value)
        assert "My Secret Notebook" not in error_msg
        assert "Notebook not accessible" in error_msg
