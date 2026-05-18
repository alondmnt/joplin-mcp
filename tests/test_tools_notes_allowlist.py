"""Tests for note tool allowlist enforcement."""

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
    """Enable an allowlist on the live config for the test body."""
    from joplin_mcp.config import get_config, set_config

    snapshot = get_config()
    set_config(snapshot.copy(notebook_allowlist=["AI", "Projects/*"]))
    try:
        yield get_config()
    finally:
        set_config(snapshot)


@pytest.fixture
def mock_no_allowlist_config():
    """Explicit no-allowlist fixture for backward-compat tests.

    The autouse _no_notebook_allowlist already gives this state; this
    fixture exists so tests can request it by name for readability.
    """
    from joplin_mcp.config import get_config

    yield get_config()


# === Tests for create_note with allowlist ===


class TestCreateNoteAllowlist:
    """Tests for create_note allowlist validation."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_create_note_allowlisted_notebook(
        self,
        mock_get_client,
        mock_get_nb_id,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should succeed when target notebook is allowlisted."""
        from joplin_mcp.tools.notes import create_note

        mock_get_nb_id.return_value = "allowlisted_nb_id"
        mock_client = MagicMock()
        mock_client.add_note.return_value = "new_note_id"
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(create_note)
        result = await fn(title="Test Note", notebook_name="AI", body="content")

        mock_validate.assert_called_once_with(
            "allowlisted_nb_id",
            allowlist_entries=mock_allowlist_config.notebook_allowlist,
        )
        mock_client.add_note.assert_called_once()
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_create_note_non_allowlisted_notebook(
        self,
        mock_get_client,
        mock_get_nb_id,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should raise error when target notebook is not allowlisted."""
        from joplin_mcp.tools.notes import create_note

        mock_get_nb_id.return_value = "blocked_nb_id"
        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(create_note)
        with pytest.raises(ValueError, match="Notebook not accessible"):
            await fn(title="Bad Note", notebook_name="Secret", body="content")

        mock_client = mock_get_client.return_value
        mock_client.add_note.assert_not_called()

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_create_note_empty_allowlist_denies(
        self,
        mock_get_client,
        mock_get_nb_id,
        mock_validate,
        override_config,
    ):
        """notebook_allowlist=[] means deny-all: create_note must raise (closes #46)."""
        from joplin_mcp.tools.notes import create_note

        mock_get_nb_id.return_value = "any_nb_id"
        mock_validate.side_effect = ValueError("Notebook not accessible")

        with override_config(notebook_allowlist=[]):
            fn = _get_tool_fn(create_note)
            with pytest.raises(ValueError, match="Notebook not accessible"):
                await fn(title="Test", notebook_name="Anywhere", body="content")

        # Validation was called with the empty allowlist.
        mock_validate.assert_called_once_with("any_nb_id", allowlist_entries=[])
        mock_client = mock_get_client.return_value
        mock_client.add_note.assert_not_called()


# === Tests for get_note with allowlist ===


class TestGetNoteAllowlist:
    """Tests for get_note allowlist validation."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_get_note_allowlisted(
        self,
        mock_get_client,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should succeed when note is in an allowlisted notebook."""
        from joplin_mcp.tools.notes import get_note

        mock_note = MagicMock()
        mock_note.parent_id = "allowlisted_nb_id"
        mock_note.title = "Test Note"
        mock_note.body = "content"
        mock_note.id = "12345678901234567890123456789012"
        mock_note.created_time = 1609459200000
        mock_note.updated_time = 1609545600000
        mock_note.is_todo = 0
        mock_note.todo_completed = 0

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(get_note)
        # Should not raise
        result = await fn(note_id="12345678901234567890123456789012")

        mock_validate.assert_called_once_with(
            "allowlisted_nb_id",
            allowlist_entries=mock_allowlist_config.notebook_allowlist,
        )
        assert result is not None

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_get_note_non_allowlisted(
        self,
        mock_get_client,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should raise error when note is in a non-allowlisted notebook."""
        from joplin_mcp.tools.notes import get_note

        mock_note = MagicMock()
        mock_note.parent_id = "blocked_nb_id"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(get_note)
        with pytest.raises(ValueError, match="Notebook not accessible"):
            await fn(note_id="12345678901234567890123456789012")

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_get_note_empty_allowlist_denies(
        self,
        mock_get_client,
        mock_validate,
        override_config,
    ):
        """notebook_allowlist=[] means deny-all: get_note must raise even for a notebook that exists (closes #46)."""
        from joplin_mcp.tools.notes import get_note

        mock_note = MagicMock()
        mock_note.parent_id = "any_nb_id"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        mock_validate.side_effect = ValueError("Notebook not accessible")

        with override_config(notebook_allowlist=[]):
            fn = _get_tool_fn(get_note)
            with pytest.raises(ValueError, match="Notebook not accessible"):
                await fn(note_id="12345678901234567890123456789012")

        mock_validate.assert_called_once_with("any_nb_id", allowlist_entries=[])


# === Tests for get_note_resources with allowlist ===


class TestGetNoteResourcesAllowlist:
    """Tests for get_note_resources allowlist validation."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_get_note_resources_allowlisted(
        self,
        mock_get_client,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should succeed and fetch resources when the parent notebook is allowlisted."""
        from joplin_mcp.tools.notes import get_note_resources

        mock_note = MagicMock()
        mock_note.parent_id = "allowlisted_nb_id"

        mock_page = MagicMock()
        mock_page.items = []
        mock_page.has_more = False

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_client.get_resources.return_value = mock_page
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(get_note_resources)
        result = await fn(note_id="12345678901234567890123456789012")

        mock_validate.assert_called_once_with(
            "allowlisted_nb_id",
            allowlist_entries=mock_allowlist_config.notebook_allowlist,
        )
        assert "TOTAL_RESOURCES: 0" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_get_note_resources_non_allowlisted(
        self,
        mock_get_client,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should raise (and not fetch resources) when parent notebook is not allowlisted."""
        from joplin_mcp.tools.notes import get_note_resources

        mock_note = MagicMock()
        mock_note.parent_id = "blocked_nb_id"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(get_note_resources)
        with pytest.raises(ValueError, match="Notebook not accessible"):
            await fn(note_id="12345678901234567890123456789012")

        mock_client.get_resources.assert_not_called()


# === Tests for update_note with allowlist ===


class TestUpdateNoteAllowlist:
    """Tests for update_note allowlist validation."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_update_note_allowlisted(
        self,
        mock_get_client,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should succeed when note is in an allowlisted notebook."""
        from joplin_mcp.tools.notes import update_note

        mock_note = MagicMock()
        mock_note.parent_id = "allowlisted_nb_id"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(update_note)
        result = await fn(
            note_id="12345678901234567890123456789012",
            title="Updated Title",
        )

        mock_validate.assert_called_once_with(
            "allowlisted_nb_id",
            allowlist_entries=mock_allowlist_config.notebook_allowlist,
        )
        mock_client.modify_note.assert_called_once()
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_update_note_non_allowlisted(
        self,
        mock_get_client,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should raise error when note is in a non-allowlisted notebook."""
        from joplin_mcp.tools.notes import update_note

        mock_note = MagicMock()
        mock_note.parent_id = "blocked_nb_id"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(update_note)
        with pytest.raises(ValueError, match="Notebook not accessible"):
            await fn(
                note_id="12345678901234567890123456789012",
                title="Should Fail",
            )

        mock_client.modify_note.assert_not_called()


# === Tests for edit_note with allowlist ===


class TestEditNoteAllowlist:
    """Tests for edit_note allowlist validation."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_edit_note_allowlisted(
        self,
        mock_get_client,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should succeed when note is in an allowlisted notebook."""
        from joplin_mcp.tools.notes import edit_note

        mock_note = MagicMock()
        mock_note.parent_id = "allowlisted_nb_id"
        mock_note.body = "old text here"
        mock_note.title = "Test"
        mock_note.id = "12345678901234567890123456789012"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(edit_note)
        result = await fn(
            note_id="12345678901234567890123456789012",
            old_string="old text",
            new_string="new text",
        )

        mock_validate.assert_called_once_with(
            "allowlisted_nb_id",
            allowlist_entries=mock_allowlist_config.notebook_allowlist,
        )
        assert "EDIT_NOTE" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_edit_note_non_allowlisted(
        self,
        mock_get_client,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should raise error when note is in a non-allowlisted notebook."""
        from joplin_mcp.tools.notes import edit_note

        mock_note = MagicMock()
        mock_note.parent_id = "blocked_nb_id"
        mock_note.body = "content"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(edit_note)
        with pytest.raises(ValueError, match="Notebook not accessible"):
            await fn(
                note_id="12345678901234567890123456789012",
                old_string="content",
                new_string="modified",
            )

        mock_client.modify_note.assert_not_called()


# === Tests for delete_note with allowlist ===


class TestDeleteNoteAllowlist:
    """Tests for delete_note allowlist validation."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_delete_note_allowlisted(
        self,
        mock_get_client,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should succeed when note is in an allowlisted notebook."""
        from joplin_mcp.tools.notes import delete_note

        mock_note = MagicMock()
        mock_note.parent_id = "allowlisted_nb_id"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(delete_note)
        result = await fn(note_id="12345678901234567890123456789012")

        mock_validate.assert_called_once_with(
            "allowlisted_nb_id",
            allowlist_entries=mock_allowlist_config.notebook_allowlist,
        )
        mock_client.delete_note.assert_called_once()
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_delete_note_non_allowlisted(
        self,
        mock_get_client,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should raise error when note is in a non-allowlisted notebook."""
        from joplin_mcp.tools.notes import delete_note

        mock_note = MagicMock()
        mock_note.parent_id = "blocked_nb_id"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(delete_note)
        with pytest.raises(ValueError, match="Notebook not accessible"):
            await fn(note_id="12345678901234567890123456789012")

        mock_client.delete_note.assert_not_called()


# === Tests for find_notes with allowlist ===


class TestFindNotesAllowlist:
    """Tests for find_notes allowlist filtering."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.is_notebook_accessible")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_find_notes_filters_results(
        self,
        mock_get_client,
        mock_is_accessible,
        mock_allowlist_config,
    ):
        """Only notes in allowlisted notebooks should be returned."""
        from joplin_mcp.tools.notes import find_notes

        note_ok = MagicMock()
        note_ok.parent_id = "allowlisted_nb_id"
        note_ok.id = "note_ok_id_000000000000000000000"
        note_ok.title = "Good Note"
        note_ok.updated_time = 1609545600000
        note_ok.is_todo = 0
        note_ok.todo_completed = 0

        note_blocked = MagicMock()
        note_blocked.parent_id = "blocked_nb_id"
        note_blocked.id = "note_blocked_id_0000000000000000"
        note_blocked.title = "Secret Note"
        note_blocked.updated_time = 1609459200000
        note_blocked.is_todo = 0
        note_blocked.todo_completed = 0

        mock_client = MagicMock()
        mock_client.get_all_notes.return_value = [note_ok, note_blocked]
        mock_get_client.return_value = mock_client

        def accessible_side_effect(parent_id, allowlist_entries=None):
            return parent_id == "allowlisted_nb_id"

        mock_is_accessible.side_effect = accessible_side_effect

        fn = _get_tool_fn(find_notes)
        result = await fn(query="*", limit=20)

        # is_notebook_accessible should have been called for filtering
        assert mock_is_accessible.call_count >= 1
        # Result should contain the good note but not the blocked one
        assert "Good Note" in result
        assert "Secret Note" not in result


# === Tests for find_notes_with_tag with allowlist ===


class TestFindNotesWithTagAllowlist:
    """Tests for find_notes_with_tag allowlist filtering."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.is_notebook_accessible")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_find_notes_with_tag_filters_results(
        self,
        mock_get_client,
        mock_is_accessible,
        mock_allowlist_config,
    ):
        """Only notes in allowlisted notebooks returned for tag search."""
        from joplin_mcp.tools.notes import find_notes_with_tag

        note_ok = MagicMock()
        note_ok.parent_id = "allowlisted_nb_id"
        note_ok.id = "note_ok_id_000000000000000000000"
        note_ok.title = "Tagged Good Note"
        note_ok.updated_time = 1609545600000
        note_ok.is_todo = 0
        note_ok.todo_completed = 0

        note_blocked = MagicMock()
        note_blocked.parent_id = "blocked_nb_id"
        note_blocked.id = "note_blocked_id_0000000000000000"
        note_blocked.title = "Tagged Secret Note"
        note_blocked.updated_time = 1609459200000
        note_blocked.is_todo = 0
        note_blocked.todo_completed = 0

        mock_client = MagicMock()
        mock_client.search_all.return_value = [note_ok, note_blocked]
        mock_get_client.return_value = mock_client

        def accessible_side_effect(parent_id, allowlist_entries=None):
            return parent_id == "allowlisted_nb_id"

        mock_is_accessible.side_effect = accessible_side_effect

        fn = _get_tool_fn(find_notes_with_tag)
        result = await fn(tag_name="work")

        assert mock_is_accessible.call_count >= 1
        assert "Tagged Good Note" in result
        assert "Tagged Secret Note" not in result


# === Tests for find_notes_in_notebook with allowlist ===


class TestFindNotesInNotebookAllowlist:
    """Tests for find_notes_in_notebook allowlist validation."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_find_notes_in_notebook_allowlisted(
        self,
        mock_get_client,
        mock_get_nb_id,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should succeed when target notebook is allowlisted."""
        from joplin_mcp.tools.notes import find_notes_in_notebook

        mock_get_nb_id.return_value = "allowlisted_nb_id"

        note = MagicMock()
        note.parent_id = "allowlisted_nb_id"
        note.id = "note_id_00000000000000000000000"
        note.title = "Note in Allowlisted"
        note.updated_time = 1609545600000
        note.is_todo = 0
        note.todo_completed = 0

        mock_client = MagicMock()
        mock_client.get_all_notes.return_value = [note]
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(find_notes_in_notebook)
        result = await fn(notebook_name="AI")

        mock_validate.assert_called_once_with(
            "allowlisted_nb_id",
            allowlist_entries=mock_allowlist_config.notebook_allowlist,
        )
        assert "Note in Allowlisted" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_find_notes_in_notebook_non_allowlisted(
        self,
        mock_get_client,
        mock_get_nb_id,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should raise error when target notebook is not allowlisted."""
        from joplin_mcp.tools.notes import find_notes_in_notebook

        mock_get_nb_id.return_value = "blocked_nb_id"
        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(find_notes_in_notebook)
        with pytest.raises(ValueError, match="Notebook not accessible"):
            await fn(notebook_name="Secret")


# === Tests for get_all_notes with allowlist ===


class TestGetAllNotesAllowlist:
    """Tests for get_all_notes allowlist filtering."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.is_notebook_accessible")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_get_all_notes_filters_results(
        self,
        mock_get_client,
        mock_is_accessible,
        mock_allowlist_config,
    ):
        """Only notes in allowlisted notebooks should be returned."""
        from joplin_mcp.tools.notes import get_all_notes

        note_ok = MagicMock()
        note_ok.parent_id = "allowlisted_nb_id"
        note_ok.id = "note_ok_id_000000000000000000000"
        note_ok.title = "Allowed Note"
        note_ok.updated_time = 1609545600000
        note_ok.is_todo = 0
        note_ok.todo_completed = 0

        note_blocked = MagicMock()
        note_blocked.parent_id = "blocked_nb_id"
        note_blocked.id = "note_blocked_id_0000000000000000"
        note_blocked.title = "Hidden Note"
        note_blocked.updated_time = 1609459200000
        note_blocked.is_todo = 0
        note_blocked.todo_completed = 0

        mock_client = MagicMock()
        mock_client.get_all_notes.return_value = [note_ok, note_blocked]
        mock_get_client.return_value = mock_client

        def accessible_side_effect(parent_id, allowlist_entries=None):
            return parent_id == "allowlisted_nb_id"

        mock_is_accessible.side_effect = accessible_side_effect

        fn = _get_tool_fn(get_all_notes)
        result = await fn()

        assert mock_is_accessible.call_count >= 1
        assert "Allowed Note" in result
        assert "Hidden Note" not in result


# === Backward compatibility tests ===


class TestNoteAllowlistBackwardCompat:
    """Verify all note tools work normally when no allowlist is configured."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_create_note_works_without_allowlist(
        self,
        mock_get_client,
        mock_get_nb_id,
        mock_no_allowlist_config,
    ):
        """create_note succeeds without allowlist."""
        from joplin_mcp.tools.notes import create_note

        mock_get_nb_id.return_value = "nb_id"
        mock_client = MagicMock()
        mock_client.add_note.return_value = "note_id"
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(create_note)
        result = await fn(title="Test", notebook_name="Work", body="content")
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_get_note_works_without_allowlist(
        self,
        mock_get_client,
        mock_no_allowlist_config,
    ):
        """get_note succeeds without allowlist."""
        from joplin_mcp.tools.notes import get_note

        mock_note = MagicMock()
        mock_note.parent_id = "nb_id"
        mock_note.title = "Test Note"
        mock_note.body = "content"
        mock_note.id = "12345678901234567890123456789012"
        mock_note.created_time = 1609459200000
        mock_note.updated_time = 1609545600000
        mock_note.is_todo = 0
        mock_note.todo_completed = 0

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(get_note)
        result = await fn(note_id="12345678901234567890123456789012")
        assert result is not None

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_delete_note_works_without_allowlist(
        self,
        mock_get_client,
        mock_no_allowlist_config,
    ):
        """delete_note succeeds without allowlist."""
        from joplin_mcp.tools.notes import delete_note

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fn = _get_tool_fn(delete_note)
        result = await fn(note_id="12345678901234567890123456789012")
        assert "SUCCESS" in result


# === Error message tests (D7) ===


class TestNoteAllowlistErrorMessages:
    """Verify error messages are generic and do not leak notebook details."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_get_note_error_does_not_contain_notebook_id(
        self,
        mock_get_client,
        mock_validate,
        mock_allowlist_config,
    ):
        """Error message should not contain the notebook ID or name."""
        from joplin_mcp.tools.notes import get_note

        blocked_nb_id = "secret_private_nb_id_0000000000"
        mock_note = MagicMock()
        mock_note.parent_id = blocked_nb_id

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(get_note)
        with pytest.raises(ValueError) as exc_info:
            await fn(note_id="12345678901234567890123456789012")

        error_msg = str(exc_info.value)
        assert blocked_nb_id not in error_msg
        assert "secret" not in error_msg.lower()
        assert "private" not in error_msg.lower()
        assert "Notebook not accessible" in error_msg

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_create_note_error_does_not_contain_notebook_name(
        self,
        mock_get_client,
        mock_get_nb_id,
        mock_validate,
        mock_allowlist_config,
    ):
        """Error message should not contain the target notebook name."""
        from joplin_mcp.tools.notes import create_note

        mock_get_nb_id.return_value = "some_nb_id"
        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(create_note)
        with pytest.raises(ValueError) as exc_info:
            await fn(
                title="Test",
                notebook_name="My Private Diary",
                body="content",
            )

        error_msg = str(exc_info.value)
        assert "My Private Diary" not in error_msg
        assert "Notebook not accessible" in error_msg

    @pytest.mark.asyncio
    @patch("joplin_mcp.notebook_utils.get_notebook_map_cached")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_create_note_flat_unknown_name_does_not_leak_titles(
        self,
        mock_get_client,
        mock_get_map,
        override_config,
    ):
        """create_note(notebook_name='X-not-real') under allowlist must not enumerate denied notebooks."""
        from joplin_mcp.tools.notes import create_note

        mock_get_map.return_value = {
            "work_id": {"title": "Work", "parent_id": None},
            "secret_id": {"title": "Secrets", "parent_id": None},
            "diary_id": {"title": "Diary", "parent_id": None},
            "tax_id": {"title": "Tax", "parent_id": None},
        }

        fn = _get_tool_fn(create_note)
        with override_config(notebook_allowlist=["Work"]):
            with pytest.raises(ValueError) as exc_info:
                await fn(
                    title="Test",
                    notebook_name="anything-not-real",
                    body="content",
                )

        msg = str(exc_info.value)
        for denied in ("Secrets", "Diary", "Tax"):
            assert denied not in msg
        assert "Available notebooks" not in msg

    @pytest.mark.asyncio
    @patch("joplin_mcp.notebook_utils.get_notebook_map_cached")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_create_note_unknown_name_under_empty_allowlist_does_not_leak_titles(
        self,
        mock_get_client,
        mock_get_map,
        override_config,
    ):
        """Empty allowlist must NOT leak titles through resolution suggestions (closes #47).

        Companion to the non-empty case above. Previously, get_accessible_map
        short-circuited on any falsy allowlist and returned the full map, so
        ``resolve_by_name("Diary", [])`` would surface every notebook title
        in its "did you mean" suggestions before the validate-after-resolve
        step refused the access.
        """
        from joplin_mcp.tools.notes import create_note

        mock_get_map.return_value = {
            "work_id": {"title": "Work", "parent_id": None},
            "secret_id": {"title": "Secrets", "parent_id": None},
            "diary_id": {"title": "Diary", "parent_id": None},
            "tax_id": {"title": "Tax", "parent_id": None},
        }

        fn = _get_tool_fn(create_note)
        with override_config(notebook_allowlist=[]):
            with pytest.raises(ValueError) as exc_info:
                await fn(
                    title="Test",
                    notebook_name="Diray",  # typo, near-matches "Diary"
                    body="content",
                )

        msg = str(exc_info.value)
        for denied in ("Work", "Secrets", "Diary", "Tax"):
            assert denied not in msg
        assert "Did you mean" not in msg
        assert "Available notebooks" not in msg


# === Tests for get_links with allowlist ===


class TestGetLinksAllowlist:
    """Tests for get_links allowlist validation and filtering."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.is_notebook_accessible")
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_get_links_blocked_source_note(
        self,
        mock_get_client,
        mock_validate,
        mock_is_accessible,
        mock_allowlist_config,
    ):
        """Should raise error when source note is in a non-allowlisted notebook."""
        from joplin_mcp.tools.notes import get_links

        mock_note = MagicMock()
        mock_note.parent_id = "blocked_nb_id"
        mock_note.title = "Secret Note"
        mock_note.body = "some content"
        mock_note.id = "12345678901234567890123456789012"
        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(get_links)
        with pytest.raises(ValueError, match="Notebook not accessible"):
            await fn(note_id="12345678901234567890123456789012")

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.process_search_results")
    @patch("joplin_mcp.tools.notes.is_notebook_accessible")
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_get_links_filters_inaccessible_linked_notes(
        self,
        mock_get_client,
        mock_validate,
        mock_is_accessible,
        mock_search_results,
        mock_allowlist_config,
    ):
        """Should filter out outgoing links to notes in non-accessible notebooks."""
        from joplin_mcp.tools.notes import get_links

        target_note_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        blocked_note_id = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

        mock_note = MagicMock()
        mock_note.parent_id = "allowed_nb_id"
        mock_note.title = "Source Note"
        mock_note.body = (
            f"Link to [allowed](:/{target_note_id}) and [blocked](:/{blocked_note_id})"
        )
        mock_note.id = "12345678901234567890123456789012"

        target_note = MagicMock()
        target_note.id = target_note_id
        target_note.title = "Allowed Target"
        target_note.parent_id = "allowed_nb_id"

        blocked_note = MagicMock()
        blocked_note.id = blocked_note_id
        blocked_note.title = "Blocked Target"
        blocked_note.parent_id = "blocked_nb_id"

        mock_client = MagicMock()
        mock_client.get_note.side_effect = lambda nid, **kw: {
            "12345678901234567890123456789012": mock_note,
            target_note_id: target_note,
            blocked_note_id: blocked_note,
        }[nid]
        mock_client.search_all.return_value = []
        mock_get_client.return_value = mock_client
        mock_search_results.return_value = []

        # Source note passes validation; is_notebook_accessible controls link filtering
        mock_validate.return_value = None
        mock_is_accessible.side_effect = lambda nb_id, **kw: nb_id != "blocked_nb_id"

        fn = _get_tool_fn(get_links)
        result = await fn(note_id="12345678901234567890123456789012")

        # The allowed link should appear, the blocked one should not
        assert "Allowed Target" in result
        assert "Blocked Target" not in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.process_search_results")
    @patch("joplin_mcp.tools.notes.is_notebook_accessible")
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_get_links_filters_inaccessible_backlinks(
        self,
        mock_get_client,
        mock_validate,
        mock_is_accessible,
        mock_search_results,
        mock_allowlist_config,
    ):
        """Should filter out backlinks from notes in non-accessible notebooks."""
        from joplin_mcp.tools.notes import get_links

        note_id = "12345678901234567890123456789012"

        mock_note = MagicMock()
        mock_note.parent_id = "allowed_nb_id"
        mock_note.title = "My Note"
        mock_note.body = "no links here"
        mock_note.id = note_id

        # Backlink from an accessible notebook
        allowed_backlink = MagicMock()
        allowed_backlink.id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        allowed_backlink.title = "Allowed Backlink"
        allowed_backlink.parent_id = "allowed_nb_id"
        allowed_backlink.body = f"See [ref](:/{note_id})"

        # Backlink from a blocked notebook
        blocked_backlink = MagicMock()
        blocked_backlink.id = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        blocked_backlink.title = "Blocked Backlink"
        blocked_backlink.parent_id = "blocked_nb_id"
        blocked_backlink.body = f"See [ref](:/{note_id})"

        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_client.search_all.return_value = []
        mock_get_client.return_value = mock_client
        mock_search_results.return_value = [allowed_backlink, blocked_backlink]

        mock_validate.return_value = None
        mock_is_accessible.side_effect = lambda nb_id, **kw: nb_id != "blocked_nb_id"

        fn = _get_tool_fn(get_links)
        result = await fn(note_id=note_id)

        assert "Allowed Backlink" in result
        assert "Blocked Backlink" not in result


# === Tests for find_in_note with allowlist ===


class TestFindInNoteAllowlist:
    """Tests for find_in_note allowlist validation."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_find_in_note_blocked_notebook(
        self,
        mock_get_client,
        mock_validate,
        mock_allowlist_config,
    ):
        """Should raise error when note is in a non-allowlisted notebook."""
        from joplin_mcp.tools.notes import find_in_note

        mock_note = MagicMock()
        mock_note.parent_id = "blocked_nb_id"
        mock_note.title = "Secret Note"
        mock_note.body = "secret content"
        mock_note.id = "12345678901234567890123456789012"
        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        mock_validate.side_effect = ValueError("Notebook not accessible")

        fn = _get_tool_fn(find_in_note)
        with pytest.raises(ValueError, match="Notebook not accessible"):
            await fn(
                note_id="12345678901234567890123456789012",
                pattern="secret",
            )

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.get_notebook_map_cached")
    @patch("joplin_mcp.tools.notes.validate_notebook_access")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_find_in_note_allowed_notebook(
        self,
        mock_get_client,
        mock_validate,
        mock_nb_map,
        mock_allowlist_config,
    ):
        """Should succeed when note is in an allowlisted notebook."""
        from joplin_mcp.tools.notes import find_in_note

        mock_note = MagicMock()
        mock_note.parent_id = "allowed_nb_id"
        mock_note.title = "Public Note"
        mock_note.body = "hello world"
        mock_note.id = "12345678901234567890123456789012"
        mock_note.created_time = 1609459200000
        mock_note.updated_time = 1609545600000
        mock_note.is_todo = 0
        mock_client = MagicMock()
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client
        mock_nb_map.return_value = {}

        mock_validate.return_value = None

        fn = _get_tool_fn(find_in_note)
        result = await fn(
            note_id="12345678901234567890123456789012",
            pattern="hello",
        )

        mock_validate.assert_called_once_with(
            "allowed_nb_id",
            allowlist_entries=mock_allowlist_config.notebook_allowlist,
        )
        assert "hello" in result
