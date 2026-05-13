"""E2E tests for the notebook allowlist feature against a live Joplin instance.

These tests create a real notebook hierarchy and verify every tool's allowlist
enforcement with actual Joplin API calls. Module configuration is patched for
test isolation, but the Joplin API itself is never mocked.
"""

import asyncio
import re
import time
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


async def _wait_for_search(tool, *, expected: str, timeout: float = 15.0, **kwargs) -> str:
    """Poll an FTS-backed search tool until ``expected`` appears in its output.

    Joplin's FTS index lags note/tag mutations by several seconds, so tools
    that go through ``client.search_all`` (find_notes, find_notes_with_tag,
    and get_links' backlink resolver) can return empty immediately after a
    create or tag. Without this wait, negative assertions like
    ``assert "X" not in result`` would pass trivially on an empty result and
    silently hide a broken allowlist filter.
    """
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        last = await _call(tool, **kwargs)
        if expected in last:
            return last
        await asyncio.sleep(0.5)
    raise AssertionError(
        f"Timed out after {timeout}s waiting for {expected!r} in search output. "
        f"Last output: {last!r}"
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

    Structure (all titles prefixed with ``E2ETest_`` so they cannot collide
    with notebooks the developer already has in their Joplin instance):

        E2ETest_Projects/
            E2ETest_Work/
            E2ETest_Secret/
        E2ETest_Personal/
            E2ETest_Diary/
        E2ETest_AI/

    Returns dict of {name: id}.  Uses e2e_client directly (not tool functions)
    to avoid allowlist/cache interference.  Created once per module, cleaned up
    at the end to minimize churn on the Joplin container.
    """
    from joplin_mcp.notebook_utils import invalidate_notebook_map_cache

    invalidate_notebook_map_cache()

    ids = {}
    created_ids = []  # track creation order for cleanup

    # Top-level
    for name in ("E2ETest_Projects", "E2ETest_Personal", "E2ETest_AI"):
        nb_id = e2e_client.add_notebook(title=name)
        ids[name] = nb_id
        created_ids.append(nb_id)

    # Children
    for name, parent in [
        ("E2ETest_Work", "E2ETest_Projects"),
        ("E2ETest_Secret", "E2ETest_Projects"),
        ("E2ETest_Diary", "E2ETest_Personal"),
    ]:
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
        for name in ("E2ETest_Projects", "E2ETest_Work", "E2ETest_Secret", "E2ETest_Personal", "E2ETest_Diary", "E2ETest_AI"):
            assert name in listing

    @pytest.mark.asyncio
    async def test_note_crud_unrestricted(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, get_note, delete_note

        r = await _call(create_note, title="Free Note", notebook_name="E2ETest_Projects/E2ETest_Secret", body="x")
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

        with _allowlist_config(["E2ETest_AI", "E2ETest_Projects"]):
            listing = await _call(list_notebooks)
            assert "E2ETest_AI" in listing
            assert "E2ETest_Projects" in listing
            assert "E2ETest_Personal" not in listing
            assert "E2ETest_Diary" not in listing

    @pytest.mark.asyncio
    async def test_hierarchical_access_shows_children(self, hierarchy):
        """Allowlisting 'Projects' should also show its children."""
        from joplin_mcp.tools.notebooks import list_notebooks

        with _allowlist_config(["E2ETest_Projects"]):
            listing = await _call(list_notebooks)
            assert "E2ETest_Projects" in listing
            assert "E2ETest_Work" in listing
            assert "E2ETest_Secret" in listing
            # Other top-level notebooks excluded
            assert "E2ETest_Personal" not in listing
            assert "E2ETest_AI" not in listing

    @pytest.mark.asyncio
    async def test_empty_allowlist_denies_all_notebooks(self, hierarchy):
        """Empty list [] means deny all notebooks, not unrestricted access."""
        from joplin_mcp.tools.notebooks import list_notebooks

        with _allowlist_config([]):
            listing = await _call(list_notebooks)
            # Empty allowlist = deny all = no notebooks visible
            for name in ("E2ETest_Projects", "E2ETest_Work", "E2ETest_Secret", "E2ETest_Personal", "E2ETest_Diary", "E2ETest_AI"):
                assert name not in listing


# ===================================================================
# 3. CREATE NOTE — write validation
# ===================================================================

class TestCreateNoteAllowlist:

    @pytest.mark.asyncio
    async def test_create_in_allowed_notebook(self, hierarchy, e2e_client):
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["E2ETest_AI"]):
            r = await _call(create_note, title="Allowed", notebook_name="E2ETest_AI", body="ok")
            assert "Allowed" in r
            nid = _extract_id(r)
            assert e2e_client.get_note(nid, fields="id,parent_id").parent_id == hierarchy["E2ETest_AI"]

    @pytest.mark.asyncio
    async def test_create_in_blocked_notebook_raises(self, hierarchy):
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["E2ETest_AI"]):
            with pytest.raises(Exception):
                await _call(create_note, title="Nope", notebook_name="E2ETest_Personal", body="no")

    @pytest.mark.asyncio
    async def test_create_in_child_of_allowed_parent(self, hierarchy, e2e_client):
        """Allowlisting 'Projects' should allow creating notes in 'Work'."""
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["E2ETest_Projects"]):
            r = await _call(create_note, title="Child OK", notebook_name="E2ETest_Work", body="ok")
            assert "Child OK" in r
            nid = _extract_id(r)
            assert e2e_client.get_note(nid, fields="id,parent_id").parent_id == hierarchy["E2ETest_Work"]

    @pytest.mark.asyncio
    async def test_create_in_child_of_blocked_parent(self, hierarchy):
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["E2ETest_AI"]):
            with pytest.raises(Exception):
                await _call(create_note, title="No", notebook_name="E2ETest_Diary", body="no")


# ===================================================================
# 4. GET NOTE — read validation
# ===================================================================

class TestGetNoteAllowlist:

    @pytest.mark.asyncio
    async def test_get_allowed_note(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, get_note

        # Create note without allowlist
        r = await _call(create_note, title="Readable", notebook_name="E2ETest_AI", body="content")
        nid = _extract_id(r)

        with _allowlist_config(["E2ETest_AI"]):
            result = await _call(get_note, note_id=nid)
            assert "Readable" in result
            assert "content" in result

    @pytest.mark.asyncio
    async def test_get_blocked_note_raises(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, get_note

        r = await _call(create_note, title="Hidden", notebook_name="E2ETest_Personal", body="secret")
        nid = _extract_id(r)

        with _allowlist_config(["E2ETest_AI"]):
            with pytest.raises(Exception):
                await _call(get_note, note_id=nid)


# ===================================================================
# 5. UPDATE NOTE — write validation
# ===================================================================

class TestUpdateNoteAllowlist:

    @pytest.mark.asyncio
    async def test_update_allowed_note(self, hierarchy, e2e_client):
        from joplin_mcp.tools.notes import create_note, get_note, update_note

        r = await _call(create_note, title="Editable", notebook_name="E2ETest_AI", body="v1")
        nid = _extract_id(r)

        with _allowlist_config(["E2ETest_AI"]):
            await _call(update_note, note_id=nid, title="Edited", body="v2")
            result = await _call(get_note, note_id=nid)
            assert "Edited" in result
            assert e2e_client.get_note(nid, fields="id,parent_id").parent_id == hierarchy["E2ETest_AI"]

    @pytest.mark.asyncio
    async def test_update_blocked_note_raises(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, update_note

        r = await _call(create_note, title="Locked", notebook_name="E2ETest_Personal", body="v1")
        nid = _extract_id(r)

        with _allowlist_config(["E2ETest_AI"]):
            with pytest.raises(Exception):
                await _call(update_note, note_id=nid, title="Nope")


# ===================================================================
# 6. EDIT NOTE — precision edit validation
# ===================================================================

class TestEditNoteAllowlist:

    @pytest.mark.asyncio
    async def test_edit_allowed_note(self, hierarchy, e2e_client):
        from joplin_mcp.tools.notes import create_note, edit_note, get_note

        r = await _call(create_note, title="EditMe", notebook_name="E2ETest_AI", body="hello world")
        nid = _extract_id(r)

        with _allowlist_config(["E2ETest_AI"]):
            await _call(edit_note, note_id=nid, old_string="hello", new_string="goodbye")
            result = await _call(get_note, note_id=nid)
            assert "goodbye world" in result
            assert e2e_client.get_note(nid, fields="id,parent_id").parent_id == hierarchy["E2ETest_AI"]

    @pytest.mark.asyncio
    async def test_edit_blocked_note_raises(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, edit_note

        r = await _call(create_note, title="NoEdit", notebook_name="E2ETest_Personal", body="text")
        nid = _extract_id(r)

        with _allowlist_config(["E2ETest_AI"]):
            with pytest.raises(Exception):
                await _call(edit_note, note_id=nid, old_string="text", new_string="nope")


# ===================================================================
# 7. DELETE NOTE — destructive validation
# ===================================================================

class TestDeleteNoteAllowlist:

    @pytest.mark.asyncio
    async def test_delete_allowed_note(self, hierarchy, e2e_client):
        from joplin_mcp.tools.notes import create_note, delete_note

        r = await _call(create_note, title="Deletable", notebook_name="E2ETest_AI", body="bye")
        nid = _extract_id(r)

        with _allowlist_config(["E2ETest_AI"]):
            result = await _call(delete_note, note_id=nid)
            assert "delete" in result.lower() or "success" in result.lower()

    @pytest.mark.asyncio
    async def test_delete_blocked_note_raises(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, delete_note

        r = await _call(create_note, title="Protected", notebook_name="E2ETest_Personal", body="x")
        nid = _extract_id(r)

        with _allowlist_config(["E2ETest_AI"]):
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
        await _call(create_note, title="VisibleSearchNote", notebook_name="E2ETest_AI", body="x")
        await _call(create_note, title="HiddenSearchNote", notebook_name="E2ETest_Personal", body="x")

        with _allowlist_config(["E2ETest_AI"]):
            result = await _call(find_notes, query="*")
            assert "VisibleSearchNote" in result
            assert "HiddenSearchNote" not in result

    @pytest.mark.asyncio
    async def test_list_all_returns_nothing_when_all_blocked(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, find_notes

        await _call(create_note, title="GhostSearchNote", notebook_name="E2ETest_Personal", body="x")

        with _allowlist_config(["E2ETest_AI"]):
            result = await _call(find_notes, query="*")
            assert "GhostSearchNote" not in result


# ===================================================================
# 9. FIND NOTES IN NOTEBOOK — notebook-level validation
# ===================================================================

class TestFindNotesInNotebookAllowlist:

    @pytest.mark.asyncio
    async def test_find_in_allowed_notebook(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, find_notes_in_notebook

        await _call(create_note, title="InAI", notebook_name="E2ETest_AI", body="something")

        with _allowlist_config(["E2ETest_AI"]):
            result = await _call(find_notes_in_notebook, notebook_name="E2ETest_AI")
            assert "InAI" in result

    @pytest.mark.asyncio
    async def test_find_in_blocked_notebook_raises(self, hierarchy):
        from joplin_mcp.tools.notes import find_notes_in_notebook

        with _allowlist_config(["E2ETest_AI"]):
            with pytest.raises(Exception):
                await _call(find_notes_in_notebook, notebook_name="E2ETest_Personal")


# ===================================================================
# 10. CREATE NOTEBOOK — with allowlist
# ===================================================================

class TestCreateNotebookAllowlist:

    @pytest.mark.asyncio
    async def test_create_sub_notebook_in_allowed_parent(self, hierarchy, e2e_client):
        from joplin_mcp.tools.notebooks import create_notebook

        with _allowlist_config(["E2ETest_Projects"]):
            r = await _call(create_notebook, title="New Sub", parent_id=hierarchy["E2ETest_Projects"])
            assert "New Sub" in r
            nb_id = _extract_id(r)
            assert e2e_client.get_notebook(nb_id, fields="id,parent_id").parent_id == hierarchy["E2ETest_Projects"]

    @pytest.mark.asyncio
    async def test_create_sub_notebook_in_blocked_parent_raises(self, hierarchy):
        from joplin_mcp.tools.notebooks import create_notebook

        with _allowlist_config(["E2ETest_AI"]):
            with pytest.raises(Exception):
                await _call(create_notebook, title="Nope", parent_id=hierarchy["E2ETest_Personal"])

    @pytest.mark.asyncio
    async def test_create_top_level_notebook_blocked(self, hierarchy):
        """With allowlist active, creating top-level notebooks is blocked."""
        from joplin_mcp.tools.notebooks import create_notebook

        with _allowlist_config(["E2ETest_AI"]):
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

        r = await _call(create_note, title="Deep Note", notebook_name="E2ETest_Work", body="deep")
        nid = _extract_id(r)

        with _allowlist_config(["E2ETest_Projects"]):
            result = await _call(get_note, note_id=nid)
            assert "Deep Note" in result

    @pytest.mark.asyncio
    async def test_parent_allowlist_grants_child_note_write(self, hierarchy, e2e_client):
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["E2ETest_Projects"]):
            r = await _call(create_note, title="Work Note", notebook_name="E2ETest_Work", body="ok")
            assert "Work Note" in r
            nid = _extract_id(r)
            assert e2e_client.get_note(nid, fields="id,parent_id").parent_id == hierarchy["E2ETest_Work"]

    @pytest.mark.asyncio
    async def test_child_allowlist_does_not_grant_parent(self, hierarchy):
        """Allowlisting 'Work' should NOT grant access to sibling 'Secret'."""
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["E2ETest_Projects/E2ETest_Work"]):
            with pytest.raises(Exception):
                await _call(create_note, title="No", notebook_name="E2ETest_Secret", body="no")


# ===================================================================
# 12. NEGATION PATTERNS
# ===================================================================

class TestNegationPatterns:

    @pytest.mark.asyncio
    async def test_negation_excludes_child(self, hierarchy, e2e_client):
        """'Projects' + '!Projects/Secret' should block Secret but allow Work."""
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["E2ETest_Projects", "!E2ETest_Projects/E2ETest_Secret"]):
            r = await _call(create_note, title="OK", notebook_name="E2ETest_Work", body="ok")
            assert "OK" in r
            nid = _extract_id(r)
            assert e2e_client.get_note(nid, fields="id,parent_id").parent_id == hierarchy["E2ETest_Work"]

            with pytest.raises(Exception):
                await _call(create_note, title="No", notebook_name="E2ETest_Secret", body="no")

    @pytest.mark.asyncio
    async def test_negation_in_listing(self, hierarchy):
        from joplin_mcp.tools.notebooks import list_notebooks

        with _allowlist_config(["E2ETest_Projects", "!E2ETest_Projects/E2ETest_Secret"]):
            listing = await _call(list_notebooks)
            assert "E2ETest_Work" in listing
            assert "E2ETest_Secret" not in listing


# ===================================================================
# 13. GLOB PATTERNS
# ===================================================================

class TestGlobPatterns:

    @pytest.mark.asyncio
    async def test_wildcard_matches_children(self, hierarchy):
        """'Projects/*' should match direct children Work and Secret."""
        from joplin_mcp.tools.notebooks import list_notebooks

        with _allowlist_config(["E2ETest_Projects/*"]):
            listing = await _call(list_notebooks)
            assert "E2ETest_Work" in listing
            assert "E2ETest_Secret" in listing

    @pytest.mark.asyncio
    async def test_wildcard_with_negation(self, hierarchy):
        from joplin_mcp.tools.notebooks import list_notebooks

        with _allowlist_config(["E2ETest_Projects/*", "!E2ETest_Projects/E2ETest_Secret"]):
            listing = await _call(list_notebooks)
            assert "E2ETest_Work" in listing
            assert "E2ETest_Secret" not in listing


# ===================================================================
# 14. ERROR MESSAGE PRIVACY (D7)
# ===================================================================

class TestErrorMessagePrivacy:

    @pytest.mark.asyncio
    async def test_error_does_not_leak_notebook_details(self, hierarchy):
        """Blocked access should raise a generic error without notebook info."""
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["E2ETest_AI"]):
            with pytest.raises(Exception) as exc_info:
                await _call(create_note, title="X", notebook_name="E2ETest_Personal", body="x")

            error_msg = str(exc_info.value).lower()
            # Should contain generic denial
            assert "not accessible" in error_msg
            # Should NOT contain the blocked notebook name or ID
            assert hierarchy["E2ETest_Personal"].lower() not in error_msg


# ===================================================================
# 15. TAGS + ALLOWLIST interaction
# ===================================================================

class TestTagsWithAllowlist:

    @pytest.mark.asyncio
    async def test_tag_note_in_allowed_notebook(self, hierarchy, e2e_client):
        from joplin_mcp.tools.notes import create_note
        from joplin_mcp.tools.tags import create_tag, get_tags_by_note, tag_note

        r = await _call(create_note, title="TagTarget", notebook_name="E2ETest_AI", body="x")
        nid = _extract_id(r)
        assert e2e_client.get_note(nid, fields="id,parent_id").parent_id == hierarchy["E2ETest_AI"]
        await _call(create_tag, title="e2e-al-tag")

        with _allowlist_config(["E2ETest_AI"]):
            await _call(tag_note, note_id=nid, tag_name="e2e-al-tag")
            tags = await _call(get_tags_by_note, note_id=nid)
            assert "e2e-al-tag" in tags

    @pytest.mark.asyncio
    async def test_tag_note_in_blocked_notebook_raises(self, hierarchy):
        """Tagging a note in a blocked notebook should be denied."""
        from joplin_mcp.tools.notes import create_note
        from joplin_mcp.tools.tags import create_tag, tag_note

        r = await _call(create_note, title="BlockedTagTarget", notebook_name="E2ETest_Personal", body="x")
        nid = _extract_id(r)
        await _call(create_tag, title="e2e-al-blocked-tag")

        with _allowlist_config(["E2ETest_AI"]):
            with pytest.raises(Exception):
                await _call(tag_note, note_id=nid, tag_name="e2e-al-blocked-tag")

    @pytest.mark.asyncio
    async def test_untag_note_in_allowed_notebook(self, hierarchy, e2e_client):
        from joplin_mcp.tools.notes import create_note
        from joplin_mcp.tools.tags import create_tag, tag_note, untag_note

        r = await _call(create_note, title="UntagTarget", notebook_name="E2ETest_AI", body="x")
        nid = _extract_id(r)
        assert e2e_client.get_note(nid, fields="id,parent_id").parent_id == hierarchy["E2ETest_AI"]
        await _call(create_tag, title="e2e-al-untag")
        await _call(tag_note, note_id=nid, tag_name="e2e-al-untag")

        with _allowlist_config(["E2ETest_AI"]):
            result = await _call(untag_note, note_id=nid, tag_name="e2e-al-untag")
            assert "success" in result.lower()

    @pytest.mark.asyncio
    async def test_untag_note_in_blocked_notebook_raises(self, hierarchy):
        """Untagging a note in a blocked notebook should be denied."""
        from joplin_mcp.tools.notes import create_note
        from joplin_mcp.tools.tags import create_tag, tag_note, untag_note

        r = await _call(create_note, title="BlockedUntagTarget", notebook_name="E2ETest_Personal", body="x")
        nid = _extract_id(r)
        await _call(create_tag, title="e2e-al-untag-blocked")
        await _call(tag_note, note_id=nid, tag_name="e2e-al-untag-blocked")

        with _allowlist_config(["E2ETest_AI"]):
            with pytest.raises(Exception):
                await _call(untag_note, note_id=nid, tag_name="e2e-al-untag-blocked")

    @pytest.mark.asyncio
    async def test_get_tags_by_note_in_blocked_notebook_raises(self, hierarchy):
        """Getting tags for a note in a blocked notebook should be denied."""
        from joplin_mcp.tools.notes import create_note
        from joplin_mcp.tools.tags import get_tags_by_note

        r = await _call(create_note, title="BlockedTagQuery", notebook_name="E2ETest_Personal", body="x")
        nid = _extract_id(r)

        with _allowlist_config(["E2ETest_AI"]):
            with pytest.raises(Exception):
                await _call(get_tags_by_note, note_id=nid)


# ===================================================================
# 16. MIXED PATTERNS (exact + glob + negation)
# ===================================================================

class TestMixedPatterns:

    @pytest.mark.asyncio
    async def test_exact_plus_glob_plus_negation(self, hierarchy, e2e_client):
        """Combine 'AI' (exact) + 'Projects/*' (glob) + '!Projects/Secret' (negate)."""
        from joplin_mcp.tools.notebooks import list_notebooks
        from joplin_mcp.tools.notes import create_note

        with _allowlist_config(["E2ETest_AI", "E2ETest_Projects/*", "!E2ETest_Projects/E2ETest_Secret"]):
            listing = await _call(list_notebooks)
            assert "E2ETest_AI" in listing
            assert "E2ETest_Work" in listing
            assert "E2ETest_Secret" not in listing
            assert "E2ETest_Personal" not in listing

            # Can create in allowed notebooks
            r = await _call(create_note, title="MixedOK", notebook_name="E2ETest_AI", body="ok")
            assert "MixedOK" in r
            nid = _extract_id(r)
            assert e2e_client.get_note(nid, fields="id,parent_id").parent_id == hierarchy["E2ETest_AI"]

            r2 = await _call(create_note, title="MixedOK2", notebook_name="E2ETest_Work", body="ok")
            assert "MixedOK2" in r2
            nid2 = _extract_id(r2)
            assert e2e_client.get_note(nid2, fields="id,parent_id").parent_id == hierarchy["E2ETest_Work"]

            # Blocked notebooks
            with pytest.raises(Exception):
                await _call(create_note, title="No", notebook_name="E2ETest_Secret", body="no")
            with pytest.raises(Exception):
                await _call(create_note, title="No", notebook_name="E2ETest_Personal", body="no")


# ===================================================================
# 17. FIND NOTES WITH TAG — search result filtering
# ===================================================================

class TestFindNotesWithTagAllowlist:
    """find_notes_with_tag must filter out notes in inaccessible notebooks."""

    @pytest.mark.asyncio
    async def test_returns_only_notes_in_allowed_notebooks(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, find_notes_with_tag
        from joplin_mcp.tools.tags import create_tag, tag_note

        r_allow = await _call(create_note, title="TaggedAllow", notebook_name="E2ETest_AI", body="x")
        r_block = await _call(create_note, title="TaggedBlock", notebook_name="E2ETest_Personal", body="x")
        nid_allow = _extract_id(r_allow)
        nid_block = _extract_id(r_block)
        await _call(create_tag, title="e2e-fnwt")
        await _call(tag_note, note_id=nid_allow, tag_name="e2e-fnwt")
        await _call(tag_note, note_id=nid_block, tag_name="e2e-fnwt")

        # Wait for Joplin's FTS index to catch up so the blocked note would
        # appear without filtering — otherwise the negative assertion would
        # pass trivially on an empty result.
        await _wait_for_search(find_notes_with_tag, expected="TaggedAllow", tag_name="e2e-fnwt")
        await _wait_for_search(find_notes_with_tag, expected="TaggedBlock", tag_name="e2e-fnwt")

        with _allowlist_config(["E2ETest_AI"]):
            result = await _call(find_notes_with_tag, tag_name="e2e-fnwt")
            assert "TaggedAllow" in result
            assert "TaggedBlock" not in result

    @pytest.mark.asyncio
    async def test_returns_nothing_when_all_tagged_notes_blocked(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, find_notes_with_tag
        from joplin_mcp.tools.tags import create_tag, tag_note

        r = await _call(create_note, title="TaggedHidden", notebook_name="E2ETest_Personal", body="x")
        nid = _extract_id(r)
        await _call(create_tag, title="e2e-fnwt-hidden")
        await _call(tag_note, note_id=nid, tag_name="e2e-fnwt-hidden")

        # Wait for indexing so the assertion isn't a trivial empty-result pass.
        await _wait_for_search(find_notes_with_tag, expected="TaggedHidden", tag_name="e2e-fnwt-hidden")

        with _allowlist_config(["E2ETest_AI"]):
            result = await _call(find_notes_with_tag, tag_name="e2e-fnwt-hidden")
            assert "TaggedHidden" not in result


# ===================================================================
# 18. FIND IN NOTE — single-note regex search
# ===================================================================

class TestFindInNoteAllowlist:
    """find_in_note must enforce allowlist on the target note's notebook."""

    @pytest.mark.asyncio
    async def test_find_in_allowed_note(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, find_in_note

        r = await _call(create_note, title="FINAllowed", notebook_name="E2ETest_AI", body="hello target world")
        nid = _extract_id(r)

        with _allowlist_config(["E2ETest_AI"]):
            result = await _call(find_in_note, note_id=nid, pattern="target")
            assert "target" in result

    @pytest.mark.asyncio
    async def test_find_in_blocked_note_raises(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, find_in_note

        r = await _call(create_note, title="FINBlocked", notebook_name="E2ETest_Personal", body="secret target value")
        nid = _extract_id(r)

        with _allowlist_config(["E2ETest_AI"]):
            with pytest.raises(Exception):
                await _call(find_in_note, note_id=nid, pattern="target")


# ===================================================================
# 19. GET ALL NOTES — full-listing filtering
# ===================================================================

class TestGetAllNotesAllowlist:
    """get_all_notes must filter out notes in inaccessible notebooks."""

    @pytest.mark.asyncio
    async def test_returns_only_notes_in_allowed_notebooks(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, get_all_notes

        await _call(create_note, title="GANVisible", notebook_name="E2ETest_AI", body="x")
        await _call(create_note, title="GANHidden", notebook_name="E2ETest_Personal", body="x")

        with _allowlist_config(["E2ETest_AI"]):
            result = await _call(get_all_notes, limit=100)
            assert "GANVisible" in result
            assert "GANHidden" not in result

    @pytest.mark.asyncio
    async def test_returns_nothing_when_all_blocked(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, get_all_notes

        await _call(create_note, title="GANOnlyHidden", notebook_name="E2ETest_Personal", body="x")

        with _allowlist_config(["E2ETest_AI"]):
            result = await _call(get_all_notes, limit=100)
            assert "GANOnlyHidden" not in result


# ===================================================================
# 20. GET LINKS — outgoing-link + backlink filtering
# ===================================================================

class TestGetLinksAllowlist:
    """get_links must deny the source note when blocked, and filter both
    outgoing-link targets and backlinks that live in inaccessible notebooks."""

    @pytest.mark.asyncio
    async def test_get_links_from_allowed_source(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, get_links

        target_r = await _call(create_note, title="GLTarget", notebook_name="E2ETest_AI", body="dst")
        target_id = _extract_id(target_r)
        source_r = await _call(
            create_note,
            title="GLSource",
            notebook_name="E2ETest_AI",
            body=f"see [t](:/{target_id})",
        )
        source_id = _extract_id(source_r)

        with _allowlist_config(["E2ETest_AI"]):
            result = await _call(get_links, note_id=source_id)
            assert "GLTarget" in result

    @pytest.mark.asyncio
    async def test_get_links_from_blocked_source_raises(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, get_links

        r = await _call(create_note, title="GLBlockedSource", notebook_name="E2ETest_Personal", body="x")
        nid = _extract_id(r)

        with _allowlist_config(["E2ETest_AI"]):
            with pytest.raises(Exception):
                await _call(get_links, note_id=nid)

    @pytest.mark.asyncio
    async def test_get_links_filters_blocked_outgoing_target(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, get_links

        hidden_r = await _call(create_note, title="GLHiddenTarget", notebook_name="E2ETest_Personal", body="x")
        hidden_id = _extract_id(hidden_r)
        source_r = await _call(
            create_note,
            title="GLMixedSource",
            notebook_name="E2ETest_AI",
            body=f"link [h](:/{hidden_id})",
        )
        source_id = _extract_id(source_r)

        with _allowlist_config(["E2ETest_AI"]):
            result = await _call(get_links, note_id=source_id)
            assert "GLHiddenTarget" not in result

    @pytest.mark.asyncio
    async def test_get_links_filters_blocked_backlinks(self, hierarchy):
        from joplin_mcp.tools.notes import create_note, find_notes, get_links

        target_r = await _call(create_note, title="GLBacklinkTarget", notebook_name="E2ETest_AI", body="x")
        target_id = _extract_id(target_r)
        await _call(
            create_note,
            title="GLHiddenBacklinker",
            notebook_name="E2ETest_Personal",
            body=f"refers [t](:/{target_id})",
        )

        # Backlinks are resolved via search_all, which is gated by Joplin's
        # FTS index. Wait until the backlink would surface without filtering
        # so the negative assertion isn't a trivial empty-result pass.
        await _wait_for_search(find_notes, expected="GLHiddenBacklinker", query=f":/{target_id}")

        with _allowlist_config(["E2ETest_AI"]):
            result = await _call(get_links, note_id=target_id)
            assert "GLHiddenBacklinker" not in result
