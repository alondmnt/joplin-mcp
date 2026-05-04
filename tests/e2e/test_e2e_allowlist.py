"""E2E tests for the notebook allowlist feature against a live Joplin instance.

These tests create a real notebook hierarchy and verify every tool's allowlist
enforcement with actual Joplin API calls. Module configuration is patched for
test isolation, but the Joplin API itself is never mocked.
"""

import re
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from joplin_mcp.config import JoplinMCPConfig

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _call(tool, **kwargs):
    """Call a FunctionTool or raw async function."""
    fn = getattr(tool, "fn", tool)
    return await fn(**kwargs)


def _extract_id(tool_output: str) -> str:
    """Extract a 32-char hex Joplin ID from tool output."""
    m = re.search(r"\b([a-f0-9]{32})\b", tool_output)
    if m:
        return m.group(1)
    m = re.search(r"ID:\s*(\S+)", tool_output)
    if m:
        return m.group(1)
    raise AssertionError(
        f"Could not extract Joplin ID from tool output: {tool_output!r}"
    )


@contextmanager
def _allowlist_config(allowlist, token="e2e_test_token"):
    """Patch _module_config everywhere with the given allowlist."""
    from joplin_mcp.notebook_utils import invalidate_notebook_map_cache

    cfg = JoplinMCPConfig(token=token, notebook_allowlist=allowlist)
    targets = [
        "joplin_mcp.tools.notes._module_config",
        "joplin_mcp.tools.notebooks._module_config",
        "joplin_mcp.tools.tags._module_config",
    ]
    patches = [patch(t, cfg) for t in targets]
    invalidate_notebook_map_cache()
    for p in patches:
        p.start()
    try:
        yield cfg
    finally:
        for p in patches:
            p.stop()
        invalidate_notebook_map_cache()


# ---------------------------------------------------------------------------
# Shared fixture: build a real notebook hierarchy once per test
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def hierarchy(e2e_client):
    """Create a notebook hierarchy once for all allowlist tests.

    Structure:
        Projects/
            Work/
            Secret/
        Personal/
            Diary/
        AI/

    Returns dict of {name: id}.  Uses e2e_client directly (not tool functions)
    to avoid allowlist/cache interference.  Created once per module, cleaned up
    at the end to minimize churn on the Joplin container.
    """
    from joplin_mcp.notebook_utils import invalidate_notebook_map_cache

    invalidate_notebook_map_cache()

    ids = {}
    created_ids = []  # track creation order for cleanup

    # Top-level
    for name in ("Projects", "Personal", "AI"):
        nb_id = e2e_client.add_notebook(title=name)
        ids[name] = nb_id
        created_ids.append(nb_id)

    # Children
    for name, parent in [("Work", "Projects"), ("Secret", "Projects"), ("Diary", "Personal")]:
        nb_id = e2e_client.add_notebook(title=name, parent_id=ids[parent])
        ids[name] = nb_id
        created_ids.append(nb_id)

    invalidate_notebook_map_cache()

    yield ids

    # Module-level teardown: delete all notes in these notebooks, then notebooks
    invalidate_notebook_map_cache()
    try:
        for note in e2e_client.get_all_notes():
            if getattr(note, "parent_id", None) in ids.values():
                try:
                    e2e_client.delete_note(note.id)
                except Exception:
                    pass

        # Delete children first, then parents (reverse creation order)
        for nb_id in reversed(created_ids):
            try:
                e2e_client.delete_notebook(nb_id)
            except Exception:
                pass
    except Exception:
        pass

    invalidate_notebook_map_cache()


# ===================================================================
# 1. NO ALLOWLIST (backward compatibility)
# ===================================================================

class TestNoAllowlist:
    """When no allowlist is configured, everything should be accessible."""

    @pytest.mark.asyncio
    async def test_all_notebooks_listed(self, hierarchy):
        from joplin_mcp.tools.notebooks import list_notebooks

        listing = await _call(list_notebooks)
        for name in ("Projects", "Work", "Secret", "Personal", "Diary", "AI"):
            assert name in listing

    @pytest.mark.asyncio
    async def test_note_crud_unrestricted(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, get_note, delete_note

        r = await _call(create_note, title="Free Note", notebook_name="Projects/Secret", body="x")
        nid = _extract_id(r)
        get_r = await _call(get_note, note_id=nid)
        assert "Free Note" in get_r
        await _call(delete_note, note_id=nid)


# ===================================================================
# 2. LIST NOTEBOOKS — filtering
# ===================================================================

class TestListNotebooksAllowlist:

    @pytest.mark.asyncio
    async def test_only_allowed_notebooks_shown(self, hierarchy):
        from joplin_mcp.tools.notebooks import list_notebooks

        with _allowlist_config(["AI", "Projects"]):
            listing = await _call(list_notebooks)
            assert "AI" in listing
            assert "Projects" in listing
            assert "Personal" not in listing
            assert "Diary" not in listing

    @pytest.mark.asyncio
    async def test_hierarchical_access_shows_children(self, hierarchy):
        """Allowlisting 'Projects' should also show its children."""
        from joplin_mcp.tools.notebooks import list_notebooks

        with _allowlist_config(["Projects"]):
            listing = await _call(list_notebooks)
            assert "Projects" in listing
            assert "Work" in listing
            assert "Secret" in listing
            # Other top-level notebooks excluded
            assert "Personal" not in listing
            assert "AI" not in listing

    @pytest.mark.asyncio
    async def test_empty_allowlist_denies_all_notebooks(self, hierarchy):
        """Empty list [] means deny all notebooks, not unrestricted access."""
        from joplin_mcp.tools.notebooks import list_notebooks

        with _allowlist_config([]):
            listing = await _call(list_notebooks)
            # Empty allowlist = deny all = no notebooks visible
            for name in ("Projects", "Work", "Secret", "Personal", "Diary", "AI"):
                assert name not in listing


# ===================================================================
# 3. CREATE NOTE — write validation
# ===================================================================

class TestCreateNoteAllowlist:

    @pytest.mark.asyncio
    async def test_create_in_allowed_notebook(self, hierarchy):
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["AI"]):
            r = await _call(create_note, title="Allowed", notebook_name="AI", body="ok")
            assert "Allowed" in r

    @pytest.mark.asyncio
    async def test_create_in_blocked_notebook_raises(self, hierarchy):
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["AI"]):
            with pytest.raises(Exception):
                await _call(create_note, title="Nope", notebook_name="Personal", body="no")

    @pytest.mark.asyncio
    async def test_create_in_child_of_allowed_parent(self, hierarchy):
        """Allowlisting 'Projects' should allow creating notes in 'Work'."""
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["Projects"]):
            r = await _call(create_note, title="Child OK", notebook_name="Work", body="ok")
            assert "Child OK" in r

    @pytest.mark.asyncio
    async def test_create_in_child_of_blocked_parent(self, hierarchy):
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["AI"]):
            with pytest.raises(Exception):
                await _call(create_note, title="No", notebook_name="Diary", body="no")


# ===================================================================
# 4. GET NOTE — read validation
# ===================================================================

class TestGetNoteAllowlist:

    @pytest.mark.asyncio
    async def test_get_allowed_note(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, get_note

        # Create note without allowlist
        r = await _call(create_note, title="Readable", notebook_name="AI", body="content")
        nid = _extract_id(r)

        with _allowlist_config(["AI"]):
            result = await _call(get_note, note_id=nid)
            assert "Readable" in result
            assert "content" in result

    @pytest.mark.asyncio
    async def test_get_blocked_note_raises(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, get_note

        r = await _call(create_note, title="Hidden", notebook_name="Personal", body="secret")
        nid = _extract_id(r)

        with _allowlist_config(["AI"]):
            with pytest.raises(Exception):
                await _call(get_note, note_id=nid)


# ===================================================================
# 5. UPDATE NOTE — write validation
# ===================================================================

class TestUpdateNoteAllowlist:

    @pytest.mark.asyncio
    async def test_update_allowed_note(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, get_note, update_note

        r = await _call(create_note, title="Editable", notebook_name="AI", body="v1")
        nid = _extract_id(r)

        with _allowlist_config(["AI"]):
            await _call(update_note, note_id=nid, title="Edited", body="v2")
            result = await _call(get_note, note_id=nid)
            assert "Edited" in result

    @pytest.mark.asyncio
    async def test_update_blocked_note_raises(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, update_note

        r = await _call(create_note, title="Locked", notebook_name="Personal", body="v1")
        nid = _extract_id(r)

        with _allowlist_config(["AI"]):
            with pytest.raises(Exception):
                await _call(update_note, note_id=nid, title="Nope")


# ===================================================================
# 6. EDIT NOTE — precision edit validation
# ===================================================================

class TestEditNoteAllowlist:

    @pytest.mark.asyncio
    async def test_edit_allowed_note(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, edit_note, get_note

        r = await _call(create_note, title="EditMe", notebook_name="AI", body="hello world")
        nid = _extract_id(r)

        with _allowlist_config(["AI"]):
            await _call(edit_note, note_id=nid, old_string="hello", new_string="goodbye")
            result = await _call(get_note, note_id=nid)
            assert "goodbye world" in result

    @pytest.mark.asyncio
    async def test_edit_blocked_note_raises(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, edit_note

        r = await _call(create_note, title="NoEdit", notebook_name="Personal", body="text")
        nid = _extract_id(r)

        with _allowlist_config(["AI"]):
            with pytest.raises(Exception):
                await _call(edit_note, note_id=nid, old_string="text", new_string="nope")


# ===================================================================
# 7. DELETE NOTE — destructive validation
# ===================================================================

class TestDeleteNoteAllowlist:

    @pytest.mark.asyncio
    async def test_delete_allowed_note(self, hierarchy, e2e_client):
        from joplin_mcp.tools.notes import create_note, delete_note

        r = await _call(create_note, title="Deletable", notebook_name="AI", body="bye")
        nid = _extract_id(r)

        with _allowlist_config(["AI"]):
            result = await _call(delete_note, note_id=nid)
            assert "delete" in result.lower() or "success" in result.lower()

    @pytest.mark.asyncio
    async def test_delete_blocked_note_raises(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, delete_note

        r = await _call(create_note, title="Protected", notebook_name="Personal", body="x")
        nid = _extract_id(r)

        with _allowlist_config(["AI"]):
            with pytest.raises(Exception):
                await _call(delete_note, note_id=nid)


# ===================================================================
# 8. FIND NOTES — search result filtering
# ===================================================================

class TestFindNotesAllowlist:

    @pytest.mark.asyncio
    async def test_list_all_only_returns_allowed_notes(self, hierarchy):
        """find_notes('*') with allowlist should only return notes in allowed notebooks."""
        from joplin_mcp.tools.notes import create_note, find_notes

        # Create notes in allowed and blocked notebooks
        await _call(create_note, title="VisibleSearchNote", notebook_name="AI", body="x")
        await _call(create_note, title="HiddenSearchNote", notebook_name="Personal", body="x")

        with _allowlist_config(["AI"]):
            result = await _call(find_notes, query="*")
            assert "VisibleSearchNote" in result
            assert "HiddenSearchNote" not in result

    @pytest.mark.asyncio
    async def test_list_all_returns_nothing_when_all_blocked(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, find_notes

        await _call(create_note, title="GhostSearchNote", notebook_name="Personal", body="x")

        with _allowlist_config(["AI"]):
            result = await _call(find_notes, query="*")
            assert "GhostSearchNote" not in result


# ===================================================================
# 9. FIND NOTES IN NOTEBOOK — notebook-level validation
# ===================================================================

class TestFindNotesInNotebookAllowlist:

    @pytest.mark.asyncio
    async def test_find_in_allowed_notebook(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, find_notes_in_notebook

        await _call(create_note, title="InAI", notebook_name="AI", body="something")

        with _allowlist_config(["AI"]):
            result = await _call(find_notes_in_notebook, notebook_name="AI")
            assert "InAI" in result

    @pytest.mark.asyncio
    async def test_find_in_blocked_notebook_raises(self, hierarchy):
        from joplin_mcp.tools.notes import find_notes_in_notebook

        with _allowlist_config(["AI"]):
            with pytest.raises(Exception):
                await _call(find_notes_in_notebook, notebook_name="Personal")


# ===================================================================
# 10. CREATE NOTEBOOK — with allowlist
# ===================================================================

class TestCreateNotebookAllowlist:

    @pytest.mark.asyncio
    async def test_create_sub_notebook_in_allowed_parent(self, hierarchy):
        from joplin_mcp.tools.notebooks import create_notebook

        with _allowlist_config(["Projects"]):
            r = await _call(create_notebook, title="New Sub", parent_id=hierarchy["Projects"])
            assert "New Sub" in r

    @pytest.mark.asyncio
    async def test_create_sub_notebook_in_blocked_parent_raises(self, hierarchy):
        from joplin_mcp.tools.notebooks import create_notebook

        with _allowlist_config(["AI"]):
            with pytest.raises(Exception):
                await _call(create_notebook, title="Nope", parent_id=hierarchy["Personal"])

    @pytest.mark.asyncio
    async def test_create_top_level_notebook_blocked(self, hierarchy):
        """With allowlist active, creating top-level notebooks is blocked."""
        from joplin_mcp.tools.notebooks import create_notebook

        with _allowlist_config(["AI"]):
            with pytest.raises(Exception):
                await _call(create_notebook, title="Top Level Nope")


# ===================================================================
# 11. HIERARCHICAL ACCESS — parent grants child
# ===================================================================

class TestHierarchicalAccess:

    @pytest.mark.asyncio
    async def test_parent_allowlist_grants_child_note_read(self, hierarchy):
        """Allowlisting 'Projects' should let us read notes in 'Work'."""
        from joplin_mcp.tools.notes import create_note, get_note

        r = await _call(create_note, title="Deep Note", notebook_name="Work", body="deep")
        nid = _extract_id(r)

        with _allowlist_config(["Projects"]):
            result = await _call(get_note, note_id=nid)
            assert "Deep Note" in result

    @pytest.mark.asyncio
    async def test_parent_allowlist_grants_child_note_write(self, hierarchy):
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["Projects"]):
            r = await _call(create_note, title="Work Note", notebook_name="Work", body="ok")
            assert "Work Note" in r

    @pytest.mark.asyncio
    async def test_child_allowlist_does_not_grant_parent(self, hierarchy):
        """Allowlisting 'Work' should NOT grant access to sibling 'Secret'."""
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["Projects/Work"]):
            with pytest.raises(Exception):
                await _call(create_note, title="No", notebook_name="Secret", body="no")


# ===================================================================
# 12. NEGATION PATTERNS
# ===================================================================

class TestNegationPatterns:

    @pytest.mark.asyncio
    async def test_negation_excludes_child(self, hierarchy):
        """'Projects' + '!Projects/Secret' should block Secret but allow Work."""
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["Projects", "!Projects/Secret"]):
            r = await _call(create_note, title="OK", notebook_name="Work", body="ok")
            assert "OK" in r

            with pytest.raises(Exception):
                await _call(create_note, title="No", notebook_name="Secret", body="no")

    @pytest.mark.asyncio
    async def test_negation_in_listing(self, hierarchy):
        from joplin_mcp.tools.notebooks import list_notebooks

        with _allowlist_config(["Projects", "!Projects/Secret"]):
            listing = await _call(list_notebooks)
            assert "Work" in listing
            assert "Secret" not in listing


# ===================================================================
# 13. GLOB PATTERNS
# ===================================================================

class TestGlobPatterns:

    @pytest.mark.asyncio
    async def test_wildcard_matches_children(self, hierarchy):
        """'Projects/*' should match direct children Work and Secret."""
        from joplin_mcp.tools.notebooks import list_notebooks

        with _allowlist_config(["Projects/*"]):
            listing = await _call(list_notebooks)
            assert "Work" in listing
            assert "Secret" in listing

    @pytest.mark.asyncio
    async def test_wildcard_with_negation(self, hierarchy):
        from joplin_mcp.tools.notebooks import list_notebooks

        with _allowlist_config(["Projects/*", "!Projects/Secret"]):
            listing = await _call(list_notebooks)
            assert "Work" in listing
            assert "Secret" not in listing


# ===================================================================
# 14. ERROR MESSAGE PRIVACY (D7)
# ===================================================================

class TestErrorMessagePrivacy:

    @pytest.mark.asyncio
    async def test_error_does_not_leak_notebook_details(self, hierarchy):
        """Blocked access should raise a generic error without notebook info."""
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["AI"]):
            with pytest.raises(Exception) as exc_info:
                await _call(create_note, title="X", notebook_name="Personal", body="x")

            error_msg = str(exc_info.value).lower()
            # Should contain generic denial
            assert "not accessible" in error_msg
            # Should NOT contain the blocked notebook name or ID
            assert hierarchy["Personal"].lower() not in error_msg


# ===================================================================
# 15. TAGS + ALLOWLIST interaction
# ===================================================================

class TestTagsWithAllowlist:

    @pytest.mark.asyncio
    async def test_tag_note_in_allowed_notebook(self, hierarchy):
        from joplin_mcp.tools.notes import create_note
        from joplin_mcp.tools.tags import create_tag, get_tags_by_note, tag_note

        r = await _call(create_note, title="TagTarget", notebook_name="AI", body="x")
        nid = _extract_id(r)
        await _call(create_tag, title="e2e-al-tag")

        with _allowlist_config(["AI"]):
            await _call(tag_note, note_id=nid, tag_name="e2e-al-tag")
            tags = await _call(get_tags_by_note, note_id=nid)
            assert "e2e-al-tag" in tags

    @pytest.mark.asyncio
    async def test_tag_note_in_blocked_notebook_raises(self, hierarchy):
        """Tagging a note in a blocked notebook should be denied."""
        from joplin_mcp.tools.notes import create_note
        from joplin_mcp.tools.tags import create_tag, tag_note

        r = await _call(create_note, title="BlockedTagTarget", notebook_name="Personal", body="x")
        nid = _extract_id(r)
        await _call(create_tag, title="e2e-al-blocked-tag")

        with _allowlist_config(["AI"]):
            with pytest.raises(Exception):
                await _call(tag_note, note_id=nid, tag_name="e2e-al-blocked-tag")

    @pytest.mark.asyncio
    async def test_untag_note_in_allowed_notebook(self, hierarchy):
        from joplin_mcp.tools.notes import create_note
        from joplin_mcp.tools.tags import create_tag, tag_note, untag_note

        r = await _call(create_note, title="UntagTarget", notebook_name="AI", body="x")
        nid = _extract_id(r)
        await _call(create_tag, title="e2e-al-untag")
        await _call(tag_note, note_id=nid, tag_name="e2e-al-untag")

        with _allowlist_config(["AI"]):
            result = await _call(untag_note, note_id=nid, tag_name="e2e-al-untag")
            assert "success" in result.lower()

    @pytest.mark.asyncio
    async def test_untag_note_in_blocked_notebook_raises(self, hierarchy):
        """Untagging a note in a blocked notebook should be denied."""
        from joplin_mcp.tools.notes import create_note
        from joplin_mcp.tools.tags import create_tag, tag_note, untag_note

        r = await _call(create_note, title="BlockedUntagTarget", notebook_name="Personal", body="x")
        nid = _extract_id(r)
        await _call(create_tag, title="e2e-al-untag-blocked")
        await _call(tag_note, note_id=nid, tag_name="e2e-al-untag-blocked")

        with _allowlist_config(["AI"]):
            with pytest.raises(Exception):
                await _call(untag_note, note_id=nid, tag_name="e2e-al-untag-blocked")

    @pytest.mark.asyncio
    async def test_get_tags_by_note_in_blocked_notebook_raises(self, hierarchy):
        """Getting tags for a note in a blocked notebook should be denied."""
        from joplin_mcp.tools.notes import create_note
        from joplin_mcp.tools.tags import get_tags_by_note

        r = await _call(create_note, title="BlockedTagQuery", notebook_name="Personal", body="x")
        nid = _extract_id(r)

        with _allowlist_config(["AI"]):
            with pytest.raises(Exception):
                await _call(get_tags_by_note, note_id=nid)


# ===================================================================
# 16. MIXED PATTERNS (exact + glob + negation)
# ===================================================================

class TestMixedPatterns:

    @pytest.mark.asyncio
    async def test_exact_plus_glob_plus_negation(self, hierarchy):
        """Combine 'AI' (exact) + 'Projects/*' (glob) + '!Projects/Secret' (negate)."""
        from joplin_mcp.tools.notebooks import list_notebooks
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["AI", "Projects/*", "!Projects/Secret"]):
            listing = await _call(list_notebooks)
            assert "AI" in listing
            assert "Work" in listing
            assert "Secret" not in listing
            assert "Personal" not in listing

            # Can create in allowed notebooks
            r = await _call(create_note, title="MixedOK", notebook_name="AI", body="ok")
            assert "MixedOK" in r

            r2 = await _call(create_note, title="MixedOK2", notebook_name="Work", body="ok")
            assert "MixedOK2" in r2

            # Blocked notebooks
            with pytest.raises(Exception):
                await _call(create_note, title="No", notebook_name="Secret", body="no")
            with pytest.raises(Exception):
                await _call(create_note, title="No", notebook_name="Personal", body="no")
