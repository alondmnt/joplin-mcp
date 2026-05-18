"""E2E tests exercising real MCP tool functions against a live Joplin instance."""

import asyncio
import re
import time
import uuid

import pytest

pytestmark = pytest.mark.e2e


async def _call(tool, **kwargs):
    """Call a FunctionTool or raw async function."""
    fn = getattr(tool, "fn", tool)
    return await fn(**kwargs)


async def _wait_for_search(tool, *, expected: str, timeout: float = 15.0, **kwargs) -> str:
    """Poll an FTS-backed search tool until ``expected`` appears in its output.

    Joplin's FTS index lags note/tag mutations by several seconds, so tools
    that go through ``client.search_all`` (find_notes, find_notes_with_tag)
    can return empty immediately after a create. Without this wait, a
    substring assertion like ``"Title" in result`` can pass on the
    no-results template, which echoes the query back in its CONTEXT line.
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


# ---------------------------------------------------------------------------
# Ping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_ping():
    """Verify Joplin connection via the ping tool."""
    from joplin_mcp.fastmcp_server import ping_joplin

    result = await _call(ping_joplin)
    assert "SUCCESS" in result
    assert "ESTABLISHED" in result


# ---------------------------------------------------------------------------
# Notebooks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_list_notebooks():
    """list_notebooks returns without error."""
    from joplin_mcp.tools.notebooks import list_notebooks

    result = await _call(list_notebooks)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_e2e_create_notebook(e2e_client):
    """Create a notebook, verify listing, then round-trip an emoji icon
    through create / update / clear."""
    from joplin_mcp.tools.notebooks import (
        create_notebook,
        list_notebooks,
        update_notebook,
    )

    # Create with an emoji icon up-front.
    result = await _call(
        create_notebook, title="E2E Test Notebook", emoji="🎯"
    )
    assert "E2E Test Notebook" in result

    match = re.search(r"ITEM_ID:\s*(\S+)", result)
    assert match, f"Couldn't find ITEM_ID in create output: {result!r}"
    nb_id = match.group(1)

    # Listing should surface the emoji we just set.
    listing = await _call(list_notebooks)
    assert "E2E Test Notebook" in listing
    assert "emoji: 🎯" in listing

    # Replace the emoji with a different glyph, then verify the change shows up.
    await _call(update_notebook, notebook_id=nb_id, emoji="🕰️")
    listing = await _call(list_notebooks)
    assert "emoji: 🕰️" in listing
    assert "emoji: 🎯" not in listing

    # Clearing via empty string should remove the line for this notebook.
    await _call(update_notebook, notebook_id=nb_id, emoji="")
    listing = await _call(list_notebooks)
    nb_section = listing[listing.index("E2E Test Notebook"):]
    next_item = nb_section.find("ITEM_")
    nb_block = nb_section if next_item == -1 else nb_section[:next_item]
    assert "emoji:" not in nb_block


@pytest.mark.asyncio
async def test_e2e_create_notebook_under_sandbox_parent(e2e_client):
    """create_notebook(parent_name=...) resolves the parent and threads the
    resolved id to Joplin.

    Uses a uniquely-named sandbox notebook built fresh per test so the
    assertion doesn't rely on any pre-existing structure in the live DB.
    The autouse e2e_cleanup fixture reaps both the sandbox and the child.
    """
    from joplin_mcp.tools.notebooks import create_notebook

    sandbox_title = f"__e2e_sandbox_{uuid.uuid4().hex[:8]}__"
    sandbox_id = e2e_client.add_notebook(title=sandbox_title)

    result = await _call(create_notebook, title="Child", parent_name=sandbox_title)
    child_id = _extract_id(result)

    child = e2e_client.get_notebook(child_id, fields="id,parent_id")
    assert child.parent_id == sandbox_id


@pytest.mark.asyncio
async def test_e2e_create_top_level_notebook_with_no_parent(e2e_client):
    """Omitting parent_name creates a top-level notebook (parent_id == "")."""
    from joplin_mcp.tools.notebooks import create_notebook

    title = f"__e2e_top_{uuid.uuid4().hex[:8]}__"
    result = await _call(create_notebook, title=title)
    new_id = _extract_id(result)

    nb = e2e_client.get_notebook(new_id, fields="id,parent_id")
    assert nb.parent_id == ""


@pytest.mark.asyncio
async def test_e2e_create_notebook_missing_parent_raises(e2e_client):
    """parent_name that doesn't resolve surfaces the resolver error and
    creates nothing."""
    from joplin_mcp.tools.notebooks import create_notebook

    missing = f"__e2e_missing_{uuid.uuid4().hex[:8]}__"

    before = {nb.id for nb in e2e_client.get_all_notebooks()}
    with pytest.raises(ValueError, match="not found"):
        await _call(create_notebook, title="Orphan", parent_name=missing)
    after = {nb.id for nb in e2e_client.get_all_notebooks()}

    assert before == after


# ---------------------------------------------------------------------------
# Notes — CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_create_and_get_note(e2e_client):
    """Create a note, retrieve it, and verify content."""
    from joplin_mcp.tools.notebooks import create_notebook
    from joplin_mcp.tools.notes import create_note, get_note

    await _call(create_notebook, title="E2E Notes NB")

    create_result = await _call(
        create_note,
        title="E2E Hello",
        notebook_name="E2E Notes NB",
        body="Hello from E2E tests!",
    )
    assert "E2E Hello" in create_result

    note_id = _extract_id(create_result)
    assert note_id is not None, f"Could not extract note ID from: {create_result}"

    get_result = await _call(get_note, note_id=note_id)
    assert "E2E Hello" in get_result
    assert "Hello from E2E tests!" in get_result


@pytest.mark.asyncio
async def test_e2e_update_note(e2e_client):
    """Modify a note's title and body, then verify."""
    from joplin_mcp.tools.notebooks import create_notebook
    from joplin_mcp.tools.notes import create_note, get_note, update_note

    await _call(create_notebook, title="E2E Update NB")
    create_result = await _call(
        create_note,
        title="Original Title",
        notebook_name="E2E Update NB",
        body="Original body",
    )
    note_id = _extract_id(create_result)

    await _call(update_note, note_id=note_id, title="Updated Title", body="Updated body")

    get_result = await _call(get_note, note_id=note_id)
    assert "Updated Title" in get_result
    assert "Updated body" in get_result


@pytest.mark.asyncio
async def test_e2e_delete_note(e2e_client):
    """Delete a note and verify it's in trash (soft-deleted)."""
    from joplin_mcp.tools.notebooks import create_notebook
    from joplin_mcp.tools.notes import create_note, delete_note

    await _call(create_notebook, title="E2E Delete NB")
    create_result = await _call(
        create_note,
        title="To Delete",
        notebook_name="E2E Delete NB",
        body="bye",
    )
    note_id = _extract_id(create_result)

    del_result = await _call(delete_note, note_id=note_id)
    assert "delete" in del_result.lower() or "success" in del_result.lower()

    # Joplin soft-deletes to trash — the note is still fetchable but has
    # deleted_time set. Asserting raise here would only catch hard-delete
    # behaviour the API doesn't have.
    note = e2e_client.get_note(note_id, fields="id,deleted_time")
    assert note.deleted_time is not None


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_find_notes(e2e_client):
    """Create a note and search for it via find_notes."""
    from joplin_mcp.tools.notebooks import create_notebook
    from joplin_mcp.tools.notes import create_note, find_notes

    await _call(create_notebook, title="E2E Search NB")
    create_result = await _call(
        create_note,
        title="Unique Searchable Note Alpha",
        notebook_name="E2E Search NB",
        body="cantaloupe watermelon",
    )
    note_id = _extract_id(create_result)

    # Poll on the note id, not the title. Joplin's FTS index lags creation
    # by several seconds, and the no-results template echoes the query
    # back in its CONTEXT line — so a title substring would pass on an
    # empty result. The note id only appears when a real row is returned.
    await _wait_for_search(
        find_notes, expected=note_id, query="Unique Searchable Note Alpha"
    )


# ---------------------------------------------------------------------------
# Tags workflow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_tags_workflow(e2e_client):
    """Create tag, tag a note, verify via get_tags_by_note, untag."""
    from joplin_mcp.tools.notebooks import create_notebook
    from joplin_mcp.tools.notes import create_note
    from joplin_mcp.tools.tags import (
        create_tag,
        get_tags_by_note,
        tag_note,
        untag_note,
    )

    await _call(create_notebook, title="E2E Tags NB")
    create_result = await _call(
        create_note,
        title="E2E Tagged Note",
        notebook_name="E2E Tags NB",
        body="tag me",
    )
    note_id = _extract_id(create_result)

    # Create and apply tag
    tag_result = await _call(create_tag, title="e2e-test-tag")
    assert "e2e-test-tag" in tag_result

    await _call(tag_note, note_id=note_id, tag_name="e2e-test-tag")

    # Verify tag is applied
    tags = await _call(get_tags_by_note, note_id=note_id)
    assert "e2e-test-tag" in tags

    # Untag and verify
    await _call(untag_note, note_id=note_id, tag_name="e2e-test-tag")
    tags_after = await _call(get_tags_by_note, note_id=note_id)
    assert "e2e-test-tag" not in tags_after


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_id(tool_output: str) -> str:
    """Extract a 32-character hex Joplin ID from tool output."""
    match = re.search(r"\b([a-f0-9]{32})\b", tool_output)
    if match:
        return match.group(1)
    match = re.search(r"ID:\s*(\S+)", tool_output)
    if match:
        return match.group(1)
    raise AssertionError(
        f"Could not extract Joplin ID from tool output: {tool_output!r}"
    )
