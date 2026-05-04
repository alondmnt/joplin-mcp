"""E2E tests exercising real MCP tool functions against a live Joplin instance."""

import re

import pytest

pytestmark = pytest.mark.e2e


async def _call(tool, **kwargs):
    """Call a FunctionTool or raw async function."""
    fn = getattr(tool, "fn", tool)
    return await fn(**kwargs)


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
    """Create a notebook and verify it appears in the list."""
    from joplin_mcp.tools.notebooks import create_notebook, list_notebooks

    result = await _call(create_notebook, title="E2E Test Notebook")
    assert "E2E Test Notebook" in result

    listing = await _call(list_notebooks)
    assert "E2E Test Notebook" in listing


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
    """Delete a note and verify it's gone."""
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

    # Attempting to get should fail
    with pytest.raises(Exception):
        e2e_client.get_note(note_id)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_find_notes(e2e_client):
    """Create notes and search for them."""
    from joplin_mcp.tools.notebooks import create_notebook
    from joplin_mcp.tools.notes import create_note, find_notes

    await _call(create_notebook, title="E2E Search NB")
    await _call(
        create_note,
        title="Unique Searchable Note Alpha",
        notebook_name="E2E Search NB",
        body="cantaloupe watermelon",
    )

    result = await _call(find_notes, query="Unique Searchable Note Alpha")
    assert "Unique Searchable Note Alpha" in result


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
# Allowlist enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_allowlist_enforcement(e2e_client):
    """Create notebooks, configure allowlist, verify access control."""
    from unittest.mock import patch

    from joplin_mcp.config import JoplinMCPConfig
    from joplin_mcp.tools.notebooks import create_notebook, list_notebooks
    from joplin_mcp.tools.notes import create_note

    await _call(create_notebook, title="E2E Allowed NB")
    await _call(create_notebook, title="E2E Blocked NB")

    restricted_config = JoplinMCPConfig(
        token=e2e_client._token if hasattr(e2e_client, '_token') else "e2e_test_token",
        notebook_allowlist=["E2E Allowed NB"],
    )

    with patch("joplin_mcp.tools.notes._module_config", restricted_config), \
         patch("joplin_mcp.tools.notebooks._module_config", restricted_config):

        result = await _call(
            create_note,
            title="Allowed Note",
            notebook_name="E2E Allowed NB",
            body="should work",
        )
        assert "Allowed Note" in result

        with pytest.raises(Exception):
            await _call(
                create_note,
                title="Blocked Note",
                notebook_name="E2E Blocked NB",
                body="should fail",
            )

        listing = await _call(list_notebooks)
        assert "E2E Allowed NB" in listing
        assert "E2E Blocked NB" not in listing


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
