"""Unit tests for PR contributions: field helpers, search, and bulk operations.

Uses mocked Joplin client. To test versioned scripts side-by-side, uncomment
ALT_MODULE and the parameterized fixture below.
"""

import importlib
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


MODULE = "joplin_mcp.tools.field_helpers"
# ALT_MODULE = "joplin_mcp.tools.field_helpers_v1"  # uncomment for side-by-side

_MODULES = [MODULE]
# _MODULES = [MODULE, ALT_MODULE]  # uncomment for side-by-side


@pytest.fixture(params=_MODULES)
def helpers(request):
    """Import field_helpers. Parameterized for side-by-side version testing."""
    return importlib.import_module(request.param)


# ---------------------------------------------------------------------------
# Mock notes
# ---------------------------------------------------------------------------


def _make_note(**kwargs):
    defaults = {
        "id": "a" * 32,
        "title": "Test Note",
        "body": "Test body content",
        "created_time": 1700000000000,
        "updated_time": 1700000000000,
        "parent_id": "b" * 32,
        "is_todo": 0,
        "todo_completed": 0,
        "todo_due": 0,
        "author": "",
        "source_url": "",
        "latitude": 0.0,
        "longitude": 0.0,
        "altitude": 0.0,
        "markup_language": 1,
        "user_created_time": 0,
        "user_updated_time": 0,
        "deleted_time": 0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


MOCK_NOTES = [
    _make_note(id="a" * 32, title="Meeting Notes", is_todo=0, author="Alice"),
    _make_note(id="b" * 32, title="Todo Item", is_todo=1, todo_completed=0, author="Bob"),
    _make_note(id="c" * 32, title="Done Item", is_todo=1, todo_completed=1700000000000, author="Alice"),
    _make_note(id="d" * 32, title="Draft", is_todo=0, author=""),
]


# ===========================================================================
# convert_todo_completed — identical in both versions
# ===========================================================================


class TestConvertTodoCompleted:

    def test_none(self, helpers):
        value, warning = helpers.convert_todo_completed(None)
        assert value is None
        assert warning is None

    def test_true(self, helpers):
        before = int(time.time() * 1000)
        value, warning = helpers.convert_todo_completed(True)
        after = int(time.time() * 1000)
        assert before <= value <= after
        assert warning is None

    def test_false(self, helpers):
        value, _ = helpers.convert_todo_completed(False)
        assert value == 0

    @pytest.mark.parametrize("s", ["true", "True", "TRUE", "yes", "on"])
    def test_string_true(self, helpers, s):
        value, _ = helpers.convert_todo_completed(s)
        assert value > 0

    @pytest.mark.parametrize("s", ["false", "False", "no", "off"])
    def test_string_false(self, helpers, s):
        value, _ = helpers.convert_todo_completed(s)
        assert value == 0

    def test_iso_datetime(self, helpers):
        value, _ = helpers.convert_todo_completed("2025-06-15 10:30")
        assert value > 0

    def test_iso_date_only(self, helpers):
        value, _ = helpers.convert_todo_completed("2025-06-15")
        assert value > 0

    def test_epoch_ms_passthrough(self, helpers):
        value, _ = helpers.convert_todo_completed(1700000000000)
        assert value == 1700000000000

    def test_zero(self, helpers):
        value, _ = helpers.convert_todo_completed(0)
        assert value == 0

    def test_small_int_warns(self, helpers):
        value, warning = helpers.convert_todo_completed(42)
        assert value == 42
        assert warning is not None and "WARNING" in warning

    def test_invalid_string_raises(self, helpers):
        with pytest.raises(ValueError, match="Unrecognized"):
            helpers.convert_todo_completed("not-a-date")

    def test_invalid_type_raises(self, helpers):
        with pytest.raises(ValueError, match="Invalid"):
            helpers.convert_todo_completed([1, 2, 3])


# ===========================================================================
# JOPLIN_NOTE_FIELDS registry — identical in both versions
# ===========================================================================


class TestFieldRegistry:

    def test_has_common_fields(self, helpers):
        for field in ["title", "body", "is_todo", "todo_completed", "parent_id", "todo_due"]:
            assert field in helpers.JOPLIN_NOTE_FIELDS, f"Missing: {field}"

    def test_has_extra_fields(self, helpers):
        for field in ["author", "source_url", "latitude", "longitude", "altitude"]:
            assert field in helpers.JOPLIN_NOTE_FIELDS, f"Missing: {field}"

    def test_each_field_has_callable_converter(self, helpers):
        for name, info in helpers.JOPLIN_NOTE_FIELDS.items():
            assert "type_converter" in info, f"{name}: missing type_converter"
            assert callable(info["type_converter"]), f"{name}: not callable"

    def test_is_todo_converter(self, helpers):
        conv = helpers.JOPLIN_NOTE_FIELDS["is_todo"]["type_converter"]
        assert conv("true") is True
        assert conv("false") is False
        assert conv(None) is None

    def test_todo_completed_converter(self, helpers):
        conv = helpers.JOPLIN_NOTE_FIELDS["todo_completed"]["type_converter"]
        result = conv(True)
        assert result > 1_000_000_000_000  # epoch ms

    def test_title_converter_is_identity(self, helpers):
        conv = helpers.JOPLIN_NOTE_FIELDS["title"]["type_converter"]
        assert conv("hello") == "hello"


# ===========================================================================
# extract_note_ids_from_result — identical in both versions
# ===========================================================================


SAMPLE_FORMATTED_OUTPUT = """SEARCH_QUERY: test
TOTAL_RESULTS: 3

RESULT_1:
  note_id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  title: Note A

RESULT_2:
  note_id: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
  title: Note B

RESULT_3:
  note_id: cccccccccccccccccccccccccccccccc
  title: Note C
"""


class TestExtractNoteIds:

    def test_extracts_all(self, helpers):
        ids = helpers.extract_note_ids_from_result(SAMPLE_FORMATTED_OUTPUT, 10)
        assert ids == ["a" * 32, "b" * 32, "c" * 32]

    def test_respects_limit(self, helpers):
        ids = helpers.extract_note_ids_from_result(SAMPLE_FORMATTED_OUTPUT, 2)
        assert len(ids) == 2

    def test_empty_input(self, helpers):
        assert helpers.extract_note_ids_from_result("", 10) == []

    def test_no_matches(self, helpers):
        assert helpers.extract_note_ids_from_result("just text\nno ids here", 10) == []


# ===========================================================================
# Parameter parsing: v1 generate_field_pars vs v2 _parse_update_params
# Both should identify the same updates and filters from the same input.
# ===========================================================================


class TestParamParsing:
    """Tests that v1 and v2 produce equivalent update/filter separation."""

    def _parse(self, helpers, **kwargs):
        """Unified interface: returns (update_field_names, filter_field_names)."""
        if hasattr(helpers, "_parse_update_params"):
            # v2
            updates, filters = helpers._parse_update_params(**kwargs)
            return set(updates.keys()), set(filters.keys())
        else:
            # v1
            result = helpers.generate_field_pars(**kwargs)
            return set(result["update_fields"]), set(result["filter_fields"])

    def test_basic_separation(self, helpers):
        updates, filters = self._parse(
            helpers, title="New Title", is_todo=True, author_filter="Alice"
        )
        assert "title" in updates
        assert "is_todo" in updates
        assert "author" in filters

    def test_none_values_ignored(self, helpers):
        updates, filters = self._parse(helpers, title=None, body=None)
        assert updates == set()
        assert filters == set()

    def test_unknown_keys_ignored(self, helpers):
        updates, filters = self._parse(
            helpers, query="test", expected_count=5, title="X"
        )
        assert updates == {"title"}
        assert filters == set()

    def test_update_and_filter_on_same_field(self, helpers):
        updates, filters = self._parse(
            helpers, is_todo=True, is_todo_filter=False
        )
        assert "is_todo" in updates
        assert "is_todo" in filters

    def test_multiple_filters(self, helpers):
        _, filters = self._parse(
            helpers, author_filter="Alice", is_todo_filter=True
        )
        assert filters == {"author", "is_todo"}


# ===========================================================================
# v2-only: _search_notes with filtering
# ===========================================================================


class TestSearchNotes:
    """Tests for _search_notes: search + post-fetch filtering."""

    def _mock_client(self, notes=None):
        client = MagicMock()
        notes = notes or MOCK_NOTES
        client.search_all.return_value = notes
        client.get_all_notes.return_value = notes
        return client

    def _get_search(self):
        mod = importlib.import_module(MODULE)
        return mod._search_notes, mod.ALL_NOTE_FIELDS

    @patch(f"{MODULE}.process_search_results", side_effect=lambda x: x)
    def test_no_filters_returns_all(self, mock_proc):
        search, _ = self._get_search()
        matching, skipped = search(self._mock_client(), "test")
        assert len(matching) == 4
        assert skipped == 0

    @patch(f"{MODULE}.process_search_results", side_effect=lambda x: x)
    def test_wildcard_uses_get_all(self, mock_proc):
        search, _ = self._get_search()
        client = self._mock_client()
        search(client, "*")
        client.get_all_notes.assert_called_once()
        client.search_all.assert_not_called()

    @patch(f"{MODULE}.process_search_results", side_effect=lambda x: x)
    def test_text_query_uses_search_all(self, mock_proc):
        search, _ = self._get_search()
        client = self._mock_client()
        search(client, "meeting notes")
        client.search_all.assert_called_once()
        client.get_all_notes.assert_not_called()

    @patch(f"{MODULE}.process_search_results", side_effect=lambda x: x)
    def test_filter_by_author(self, mock_proc):
        search, _ = self._get_search()
        matching, skipped = search(self._mock_client(), "*", author="Alice")
        assert len(matching) == 2
        assert skipped == 2

    @patch(f"{MODULE}.process_search_results", side_effect=lambda x: x)
    def test_filter_by_is_todo(self, mock_proc):
        search, _ = self._get_search()
        matching, skipped = search(self._mock_client(), "*", is_todo=1)
        assert len(matching) == 2
        assert skipped == 2

    @patch(f"{MODULE}.process_search_results", side_effect=lambda x: x)
    def test_and_filters(self, mock_proc):
        search, _ = self._get_search()
        matching, skipped = search(self._mock_client(), "*", is_todo=1, author="Alice")
        assert len(matching) == 1  # Done Item only
        assert skipped == 3

    @patch(f"{MODULE}.process_search_results", side_effect=lambda x: x)
    def test_no_matches(self, mock_proc):
        search, _ = self._get_search()
        matching, skipped = search(self._mock_client(), "*", author="Charlie")
        assert len(matching) == 0
        assert skipped == 4

    @patch(f"{MODULE}.process_search_results", side_effect=lambda x: x)
    def test_query_passed_untouched(self, mock_proc):
        search, all_fields = self._get_search()
        client = self._mock_client()
        search(client, 'notebook:"Work" title:meeting')
        call_kwargs = client.search_all.call_args[1]
        assert call_kwargs["query"] == 'notebook:"Work" title:meeting'
        assert call_kwargs["fields"] == all_fields

    @patch(f"{MODULE}.process_search_results", side_effect=lambda x: x)
    def test_all_fields_requested(self, mock_proc):
        """Verify ALL_NOTE_FIELDS includes both common and extra fields."""
        search, all_fields = self._get_search()
        client = self._mock_client()
        search(client, "test")
        call_kwargs = client.search_all.call_args[1]
        for field in ["id", "title", "body", "author", "source_url", "latitude"]:
            assert field in call_kwargs["fields"], f"Missing field: {field}"

    def test_no_extract_query_fields(self):
        """Query goes to Joplin untouched — no field name parsing."""
        mod = importlib.import_module(MODULE)
        assert not hasattr(mod, "extract_query_fields")


# ===========================================================================
# backup_database
# ===========================================================================


class TestBackupDatabase:

    @patch("joplin_mcp.tools.backup_database.subprocess.run")
    @patch("joplin_mcp.tools.backup_database._get_joplin_db_path")
    def test_auto_backup(self, mock_path, mock_run):
        from pathlib import Path
        import tempfile
        from joplin_mcp.tools.backup_database import backup_joplin_database

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_path.return_value = Path(tmpdir) / "database.sqlite"
            (Path(tmpdir) / "database.sqlite").touch()
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            with patch("joplin_mcp.tools.backup_database._BACKUP_DIR", Path(tmpdir) / "backups"):
                result = backup_joplin_database(force=False)
            assert result is not None
            assert "auto_backup" in result

    @patch("joplin_mcp.tools.backup_database.subprocess.run")
    @patch("joplin_mcp.tools.backup_database._get_joplin_db_path")
    def test_manual_backup(self, mock_path, mock_run):
        from pathlib import Path
        import tempfile
        from joplin_mcp.tools.backup_database import backup_joplin_database

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_path.return_value = Path(tmpdir) / "database.sqlite"
            (Path(tmpdir) / "database.sqlite").touch()
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            with patch("joplin_mcp.tools.backup_database._BACKUP_DIR", Path(tmpdir) / "backups"):
                result = backup_joplin_database(force=True)
            assert result is not None
            assert "manual_backup" in result

    def test_missing_db(self):
        from joplin_mcp.tools.backup_database import backup_joplin_database
        with patch("joplin_mcp.tools.backup_database._get_joplin_db_path",
                    side_effect=FileNotFoundError):
            assert backup_joplin_database() is None


# ===========================================================================
# revision_utils
# ===========================================================================


class TestRevisionUtils:

    def test_apply_diff_legacy(self):
        from joplin_mcp.revision_utils import _apply_diff
        import diff_match_patch as dmp_module
        dmp = dmp_module.diff_match_patch()

        patches = dmp.patch_make("hello", "hello world")
        diff_text = dmp.patch_toText(patches)
        assert _apply_diff(diff_text, "hello") == "hello world"

    def test_apply_diff_from_empty(self):
        from joplin_mcp.revision_utils import _apply_diff
        import diff_match_patch as dmp_module
        dmp = dmp_module.diff_match_patch()

        patches = dmp.patch_make("", "new content")
        diff_text = dmp.patch_toText(patches)
        assert _apply_diff(diff_text, "") == "new content"

    def test_save_revision_success(self):
        from joplin_mcp.revision_utils import save_note_revision

        client = MagicMock()
        client.get_note.return_value = SimpleNamespace(
            id="a" * 32, title="Test", body="Content",
            parent_id="b" * 32, is_todo=0, todo_completed=0,
        )
        client.get_all_revisions.return_value = []
        client.add_revision.return_value = "rev123"

        assert save_note_revision(client, "a" * 32) == "rev123"
        client.add_revision.assert_called_once()

    def test_save_revision_failure(self):
        from joplin_mcp.revision_utils import save_note_revision

        client = MagicMock()
        client.get_note.side_effect = Exception("Not found")
        assert save_note_revision(client, "a" * 32) is None


# ===========================================================================
# GROUP 1: Single-note MCP tool tests
# (move_note, update_note, edit_note, manually_backup_note)
# ===========================================================================

NOTE_ID = "a" * 32
NOTEBOOK_ID = "b" * 32


class TestMoveNoteTool:
    """Tests for move_note MCP tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes_bulk.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes_bulk.get_joplin_client")
    async def test_move_by_notebook_name(self, mock_get_client, mock_get_nb):
        from joplin_mcp.tools.notes_bulk import move_note

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_get_nb.return_value = NOTEBOOK_ID

        result = await move_note.fn(NOTE_ID, target_notebook="Archive")

        mock_get_nb.assert_called_once_with("Archive")
        mock_client.modify_note.assert_called_once_with(NOTE_ID, parent_id=NOTEBOOK_ID)
        assert "UPDATE_NOTE" in result
        assert "SUCCESS" in result
        assert NOTEBOOK_ID in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes_bulk.get_joplin_client")
    async def test_move_by_notebook_id(self, mock_get_client):
        from joplin_mcp.tools.notes_bulk import move_note

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = await move_note.fn(NOTE_ID, target_notebook_id=NOTEBOOK_ID)

        mock_client.modify_note.assert_called_once_with(NOTE_ID, parent_id=NOTEBOOK_ID)
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    async def test_error_no_target(self):
        from joplin_mcp.tools.notes_bulk import move_note

        with pytest.raises(ValueError, match="Must specify"):
            await move_note.fn(NOTE_ID)

    @pytest.mark.asyncio
    async def test_error_both_targets(self):
        from joplin_mcp.tools.notes_bulk import move_note

        with pytest.raises(ValueError, match="Cannot specify both"):
            await move_note.fn(NOTE_ID, target_notebook="X", target_notebook_id=NOTEBOOK_ID)


class TestUpdateNoteAutoBackup:
    """Tests for our enhancements to update_note: auto-backup + convert_todo_completed."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.save_note_revision")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_auto_backup_on_body_change(self, mock_get_client, mock_save_rev):
        from joplin_mcp.tools.notes import update_note

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        await update_note.fn(NOTE_ID, body="New body content")

        mock_save_rev.assert_called_once_with(mock_client, NOTE_ID)
        mock_client.modify_note.assert_called_once()
        assert mock_client.modify_note.call_args[1]["body"] == "New body content"

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.save_note_revision")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_auto_backup_on_title_change(self, mock_get_client, mock_save_rev):
        from joplin_mcp.tools.notes import update_note

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        await update_note.fn(NOTE_ID, title="New Title")

        mock_save_rev.assert_called_once_with(mock_client, NOTE_ID)

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.save_note_revision")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_no_backup_on_metadata_only(self, mock_get_client, mock_save_rev):
        from joplin_mcp.tools.notes import update_note

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        await update_note.fn(NOTE_ID, is_todo=True)

        mock_save_rev.assert_not_called()
        assert mock_client.modify_note.call_args[1]["is_todo"] == 1

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.save_note_revision")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_backup_failure_doesnt_block_update(self, mock_get_client, mock_save_rev):
        from joplin_mcp.tools.notes import update_note

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_save_rev.side_effect = Exception("Revision failed")

        result = await update_note.fn(NOTE_ID, body="New content")

        # Update should still succeed despite backup failure
        mock_client.modify_note.assert_called_once()
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.save_note_revision")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_todo_completed_true_sets_epoch_ms(self, mock_get_client, mock_save_rev):
        from joplin_mcp.tools.notes import update_note

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        before = int(time.time() * 1000)
        await update_note.fn(NOTE_ID, todo_completed=True)
        after = int(time.time() * 1000)

        call_kwargs = mock_client.modify_note.call_args[1]
        assert before <= call_kwargs["todo_completed"] <= after
        # Auto-sets is_todo=1 when marking complete
        assert call_kwargs["is_todo"] == 1

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.save_note_revision")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_todo_completed_false_sets_zero(self, mock_get_client, mock_save_rev):
        from joplin_mcp.tools.notes import update_note

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        await update_note.fn(NOTE_ID, todo_completed=False)

        call_kwargs = mock_client.modify_note.call_args[1]
        assert call_kwargs["todo_completed"] == 0


class TestEditNoteAutoBackup:
    """Tests for our auto-backup enhancement to edit_note."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.save_note_revision")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_backup_before_replace(self, mock_get_client, mock_save_rev):
        from joplin_mcp.tools.notes import edit_note

        mock_client = MagicMock()
        mock_note = MagicMock()
        mock_note.body = "Hello world"
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        await edit_note.fn(NOTE_ID, new_string="Hello universe", old_string="Hello world")

        mock_save_rev.assert_called_once_with(mock_client, NOTE_ID)
        mock_client.modify_note.assert_called_once()
        assert mock_client.modify_note.call_args[1]["body"] == "Hello universe"

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.save_note_revision")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_backup_before_append(self, mock_get_client, mock_save_rev):
        from joplin_mcp.tools.notes import edit_note

        mock_client = MagicMock()
        mock_note = MagicMock()
        mock_note.body = "Original"
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        await edit_note.fn(NOTE_ID, new_string=" appended", position="end")

        mock_save_rev.assert_called_once()
        assert mock_client.modify_note.call_args[1]["body"] == "Original appended"

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes.save_note_revision")
    @patch("joplin_mcp.tools.notes.get_joplin_client")
    async def test_backup_failure_doesnt_block_edit(self, mock_get_client, mock_save_rev):
        from joplin_mcp.tools.notes import edit_note

        mock_client = MagicMock()
        mock_note = MagicMock()
        mock_note.body = "Hello world"
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client
        mock_save_rev.side_effect = Exception("Backup failed")

        result = await edit_note.fn(NOTE_ID, new_string="Hello universe", old_string="Hello world")

        mock_client.modify_note.assert_called_once()
        assert "Replaced" in result


class TestManuallyBackupNoteTool:
    """Tests for manually_backup_note MCP tool."""

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes_revisions.save_note_revision")
    @patch("joplin_mcp.tools.notes_revisions.get_joplin_client")
    async def test_success(self, mock_get_client, mock_save_rev):
        from joplin_mcp.tools.notes_revisions import manually_backup_note

        mock_get_client.return_value = MagicMock()
        mock_save_rev.return_value = "rev_" + "x" * 28

        result = await manually_backup_note.fn(NOTE_ID)

        assert "MANUALLY_BACKUP_NOTE" in result
        assert "SUCCESS" in result
        assert "rev_" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes_revisions.save_note_revision")
    @patch("joplin_mcp.tools.notes_revisions.get_joplin_client")
    async def test_failure(self, mock_get_client, mock_save_rev):
        from joplin_mcp.tools.notes_revisions import manually_backup_note

        mock_get_client.return_value = MagicMock()
        mock_save_rev.return_value = None

        result = await manually_backup_note.fn(NOTE_ID)

        assert "FAILED" in result


# ===========================================================================
# GROUP 2: Bulk MCP tool tests
# (bulk_move_notes, search_and_bulk_update_preview/execute,
#  bulk_tag_notes, strip_note_tags)
# ===========================================================================


class TestBulkMoveNotesTool:

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes_bulk.backup_joplin_database")
    @patch("joplin_mcp.tools.notes_bulk.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes_bulk.get_joplin_client")
    async def test_moves_all_notes(self, mock_get_client, mock_get_nb, mock_backup):
        from joplin_mcp.tools.notes_bulk import bulk_move_notes

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_get_nb.return_value = NOTEBOOK_ID

        ids = ["a" * 32, "b" * 32, "c" * 32]
        result = await bulk_move_notes.fn(ids, target_notebook="Archive")

        assert mock_client.modify_note.call_count == 3
        assert "moved_successfully: 3" in result
        assert "success" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes_bulk.backup_joplin_database")
    @patch("joplin_mcp.tools.notes_bulk.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes_bulk.get_joplin_client")
    async def test_backup_called_daily(self, mock_get_client, mock_get_nb, mock_backup):
        from joplin_mcp.tools.notes_bulk import bulk_move_notes

        mock_get_client.return_value = MagicMock()
        mock_get_nb.return_value = NOTEBOOK_ID

        await bulk_move_notes.fn(["a" * 32], target_notebook="X")

        mock_backup.assert_called_once_with(force=False)

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes_bulk.backup_joplin_database")
    @patch("joplin_mcp.tools.notes_bulk.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes_bulk.get_joplin_client")
    async def test_backup_force(self, mock_get_client, mock_get_nb, mock_backup):
        from joplin_mcp.tools.notes_bulk import bulk_move_notes

        mock_get_client.return_value = MagicMock()
        mock_get_nb.return_value = NOTEBOOK_ID

        await bulk_move_notes.fn(["a" * 32], target_notebook="X", backup="force")

        mock_backup.assert_called_once_with(force=True)

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes_bulk.backup_joplin_database")
    @patch("joplin_mcp.tools.notes_bulk.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes_bulk.get_joplin_client")
    async def test_backup_suppress(self, mock_get_client, mock_get_nb, mock_backup):
        from joplin_mcp.tools.notes_bulk import bulk_move_notes

        mock_get_client.return_value = MagicMock()
        mock_get_nb.return_value = NOTEBOOK_ID

        await bulk_move_notes.fn(["a" * 32], target_notebook="X", backup="suppress")

        mock_backup.assert_not_called()

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes_bulk.backup_joplin_database")
    @patch("joplin_mcp.tools.notes_bulk.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes_bulk.get_joplin_client")
    async def test_partial_failure(self, mock_get_client, mock_get_nb, mock_backup):
        from joplin_mcp.tools.notes_bulk import bulk_move_notes

        mock_client = MagicMock()
        mock_client.modify_note.side_effect = [None, Exception("Not found"), None]
        mock_get_client.return_value = mock_client
        mock_get_nb.return_value = NOTEBOOK_ID

        ids = ["a" * 32, "b" * 32, "c" * 32]
        result = await bulk_move_notes.fn(ids, target_notebook="Archive")

        assert "moved_successfully: 2" in result
        assert "partial_success" in result
        assert "failed_moves: 1" in result


class TestStripNoteTagsTool:

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags_bulk.process_search_results")
    @patch("joplin_mcp.tools.tags_bulk.get_joplin_client")
    async def test_strips_all_tags(self, mock_get_client, mock_process):
        from joplin_mcp.tools.tags_bulk import strip_note_tags

        mock_client = MagicMock()
        mock_note = SimpleNamespace(title="Test Note")
        mock_client.get_note.return_value = mock_note
        mock_get_client.return_value = mock_client

        tags = [
            SimpleNamespace(id="t" * 32, title="tag-a"),
            SimpleNamespace(id="u" * 32, title="tag-b"),
        ]
        mock_process.return_value = tags

        result = await strip_note_tags.fn(NOTE_ID)

        assert "STRIP_TAGS" in result
        assert "SUCCESS" in result
        assert "TAGS_REMOVED: 2" in result
        assert mock_client.delete.call_count == 2

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags_bulk.process_search_results")
    @patch("joplin_mcp.tools.tags_bulk.get_joplin_client")
    async def test_no_tags(self, mock_get_client, mock_process):
        from joplin_mcp.tools.tags_bulk import strip_note_tags

        mock_client = MagicMock()
        mock_client.get_note.return_value = SimpleNamespace(title="Test")
        mock_get_client.return_value = mock_client
        mock_process.return_value = []

        result = await strip_note_tags.fn(NOTE_ID)

        assert "TAGS_REMOVED: 0" in result
        assert "already has no tags" in result


class TestBulkTagNotesTool:

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.tags_bulk.get_tag_id_by_name")
    @patch("joplin_mcp.tools.tags_bulk.get_joplin_client")
    async def test_tags_all_notes(self, mock_get_client, mock_get_tag):
        from joplin_mcp.tools.tags_bulk import bulk_tag_notes

        mock_client = MagicMock()
        mock_client.get_note.return_value = SimpleNamespace(title="Note")
        mock_get_client.return_value = mock_client
        mock_get_tag.return_value = "t" * 32

        ids = ["a" * 32, "b" * 32]
        result = await bulk_tag_notes.fn(ids, ["work", "urgent"])

        assert "BULK_TAG_NOTES" in result
        assert "SUCCESS" in result
        assert "TOTAL_OPERATIONS: 4" in result
        assert mock_client.add_tag_to_note.call_count == 4

    @pytest.mark.asyncio
    async def test_error_empty_note_ids(self):
        from joplin_mcp.tools.tags_bulk import bulk_tag_notes

        with pytest.raises(ValueError, match="At least one note"):
            await bulk_tag_notes.fn([], ["tag"])

    @pytest.mark.asyncio
    async def test_error_empty_tag_names(self):
        from joplin_mcp.tools.tags_bulk import bulk_tag_notes

        with pytest.raises(ValueError, match="At least one tag"):
            await bulk_tag_notes.fn(["a" * 32], [])


# ===========================================================================
# GROUP 3: Trash, revision, and backup MCP tool tests
# (list_trash, restore_from_trash, get_note_history,
#  restore_note_revision, backup_database)
# ===========================================================================


class TestListTrashTool:

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.trash.format_timestamp", return_value="2026-03-27 20:19")
    @patch("joplin_mcp.tools.trash.get_joplin_client")
    async def test_lists_trashed_notes(self, mock_get_client, mock_fmt_ts):
        from joplin_mcp.tools.trash import list_trash
        import datetime as dt_module

        mock_client = MagicMock()
        trashed = SimpleNamespace(
            id="a" * 32, title="Deleted Note",
            deleted_time=dt_module.datetime(2026, 3, 27, 20, 19),
            parent_id="b" * 32, is_todo=0,
        )
        active = SimpleNamespace(
            id="c" * 32, title="Active Note",
            deleted_time=dt_module.datetime(1970, 1, 1, 0, 0),
            parent_id="b" * 32, is_todo=0,
        )
        mock_client.get_all_notes.return_value = [trashed, active]
        mock_client.get_all_notebooks.return_value = [
            SimpleNamespace(id="b" * 32, title="Testing"),
        ]
        mock_get_client.return_value = mock_client

        result = await list_trash.fn(item_type="note")

        assert "TRASH_ITEMS: 1" in result
        assert "Deleted Note" in result
        assert "Testing" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.trash.get_joplin_client")
    async def test_empty_trash(self, mock_get_client):
        from joplin_mcp.tools.trash import list_trash
        import datetime as dt_module

        mock_client = MagicMock()
        active = SimpleNamespace(
            id="a" * 32, title="Active",
            deleted_time=dt_module.datetime(1970, 1, 1, 0, 0),
            parent_id="b" * 32, is_todo=0,
        )
        mock_client.get_all_notes.return_value = [active]
        mock_client.get_all_notebooks.return_value = []
        mock_get_client.return_value = mock_client

        result = await list_trash.fn()

        assert "TRASH_ITEMS: 0" in result
        assert "empty" in result.lower()


class TestRestoreFromTrashTool:

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.trash.get_joplin_client")
    async def test_restore_note(self, mock_get_client):
        from joplin_mcp.tools.trash import restore_from_trash

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = await restore_from_trash.fn(NOTE_ID, item_type="note")

        mock_client.modify_note.assert_called_once_with(NOTE_ID, deleted_time=0)
        assert "RESTORE_FROM_TRASH" in result
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.trash.get_joplin_client")
    async def test_restore_notebook(self, mock_get_client):
        from joplin_mcp.tools.trash import restore_from_trash

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = await restore_from_trash.fn(NOTEBOOK_ID, item_type="notebook")

        mock_client.modify_notebook.assert_called_once_with(NOTEBOOK_ID, deleted_time=0)
        assert "notebook" in result.lower()

    @pytest.mark.asyncio
    async def test_invalid_type(self):
        from joplin_mcp.tools.trash import restore_from_trash

        with pytest.raises(ValueError, match="must be"):
            await restore_from_trash.fn(NOTE_ID, item_type="tag")


class TestGetNoteHistoryTool:

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes_revisions.format_timestamp", return_value="2026-03-27 15:30")
    @patch("joplin_mcp.tools.notes_revisions.get_joplin_client")
    async def test_shows_revisions(self, mock_get_client, mock_fmt_ts):
        from joplin_mcp.tools.notes_revisions import get_note_history

        rev1 = SimpleNamespace(
            id="r" * 32, item_id=NOTE_ID, item_type=1,
            item_updated_time=1700000000000,
            parent_id="", created_time=1700000000000,
            title_diff="", metadata_diff='{"new":{"title":"Test"},"deleted":[]}',
        )
        mock_client = MagicMock()
        mock_client.get_all_revisions.return_value = [rev1]
        mock_client.get_note.return_value = SimpleNamespace(id=NOTE_ID, title="Current Title")
        mock_get_client.return_value = mock_client

        result = await get_note_history.fn(NOTE_ID)

        assert "REVISIONS: 1" in result
        assert "r" * 32 in result
        assert "no (first revision)" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes_revisions.get_joplin_client")
    async def test_no_revisions(self, mock_get_client):
        from joplin_mcp.tools.notes_revisions import get_note_history

        mock_client = MagicMock()
        mock_client.get_all_revisions.return_value = []
        mock_get_client.return_value = mock_client

        result = await get_note_history.fn(NOTE_ID)

        assert "REVISIONS: 0" in result


class TestRestoreNoteRevisionTool:

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes_revisions.get_notebook_id_by_name")
    @patch("joplin_mcp.tools.notes_revisions._reconstruct_revision_content")
    @patch("joplin_mcp.tools.notes_revisions.get_joplin_client")
    async def test_restores_to_new_note(self, mock_get_client, mock_reconstruct, mock_get_nb):
        from joplin_mcp.tools.notes_revisions import restore_note_revision

        mock_client = MagicMock()
        mock_client.add_note.return_value = "new_" + "n" * 28
        mock_client.get_notebook.return_value = SimpleNamespace(
            id=NOTEBOOK_ID, title="Original NB", deleted_time=0,
        )
        mock_get_client.return_value = mock_client
        mock_reconstruct.return_value = {
            "title": "Restored Title",
            "body": "Restored body content",
            "metadata": {"parent_id": NOTEBOOK_ID},
        }

        result = await restore_note_revision.fn("r" * 32, target_notebook="Testing")

        assert "RESTORE_NOTE_REVISION" in result
        assert "SUCCESS" in result
        assert "Restored Title" in result
        mock_client.add_note.assert_called_once()

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.notes_revisions._reconstruct_revision_content")
    @patch("joplin_mcp.tools.notes_revisions.get_joplin_client")
    async def test_falls_back_to_restored_notes(self, mock_get_client, mock_reconstruct):
        from joplin_mcp.tools.notes_revisions import restore_note_revision

        mock_client = MagicMock()
        mock_client.add_note.return_value = "new_" + "n" * 28
        # Original notebook is trashed
        mock_client.get_notebook.return_value = SimpleNamespace(
            id=NOTEBOOK_ID, title="Trashed NB",
            deleted_time=1700000000000,  # non-zero = trashed
        )
        mock_get_client.return_value = mock_client
        mock_reconstruct.return_value = {
            "title": "Old Title",
            "body": "Old body",
            "metadata": {"parent_id": NOTEBOOK_ID},
        }

        result = await restore_note_revision.fn("r" * 32)

        assert "SUCCESS" in result
        # Should fall back since original notebook is trashed
        call_kwargs = mock_client.add_note.call_args[1]
        assert call_kwargs["title"] == "Old Title"


class TestBackupDatabaseTool:

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.backup_database.backup_joplin_database")
    @patch("joplin_mcp.tools.backup_database._get_joplin_db_path")
    async def test_success(self, mock_db_path, mock_backup):
        from pathlib import Path
        import tempfile
        from joplin_mcp.tools.backup_database import backup_database

        with tempfile.NamedTemporaryFile(suffix=".sqlite") as tmp:
            mock_db_path.return_value = Path(tmp.name)
            mock_backup.return_value = tmp.name
            # Write some bytes so stat().st_size works
            tmp.write(b"x" * 1024)
            tmp.flush()

            result = await backup_database.fn()

        assert "BACKUP_DATABASE" in result
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    @patch("joplin_mcp.tools.backup_database.backup_joplin_database")
    @patch("joplin_mcp.tools.backup_database._get_joplin_db_path")
    async def test_failure(self, mock_db_path, mock_backup):
        from pathlib import Path
        from joplin_mcp.tools.backup_database import backup_database

        mock_db_path.return_value = Path("/nonexistent/database.sqlite")
        mock_backup.return_value = None

        result = await backup_database.fn()

        assert "FAILED" in result
