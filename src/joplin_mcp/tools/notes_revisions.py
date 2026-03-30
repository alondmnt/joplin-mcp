"""Revision history tools for Joplin MCP -- browse, restore, and snapshot note revisions."""

import json
import logging
from typing import Annotated, Optional

from pydantic import Field

from joplin_mcp.content_utils import format_timestamp
from joplin_mcp.fastmcp_server import (
    JoplinIdType,
    create_tool,
    format_creation_success,
    get_joplin_client,
    get_notebook_id_by_name,
    validate_joplin_id,
)
from joplin_mcp.formatting import ItemType
from joplin_mcp.revision_utils import (
    _apply_diff,
    _reconstruct_revision_content,
    save_note_revision,
)

logger = logging.getLogger(__name__)


# === REVISION HISTORY TOOLS ===


@create_tool("get_note_history", "Get note revision history")
async def get_note_history(
    note_id: Annotated[
        JoplinIdType, Field(description="Note ID to get revision history for")
    ],
) -> str:
    """List all saved revisions for a specific note.

    Shows the revision history with timestamps, enabling recovery of previous
    versions via restore_note_revision or Joplin Desktop's "Note History" UI.
    Revisions are created automatically by Joplin Desktop (every 10 minutes)
    and by MCP's auto-backup before title/body overwrites.

    Returns:
        str: List of revisions with timestamps, titles, and chain information.
    """
    note_id = validate_joplin_id(note_id)
    client = get_joplin_client()

    # Get all revisions and filter to this note
    all_revs = client.get_all_revisions(
        fields="id,item_id,item_type,item_updated_time,parent_id,"
        "created_time,title_diff,metadata_diff"
    )
    note_revs = [r for r in all_revs if getattr(r, "item_id", "") == note_id]

    if not note_revs:
        return (
            f"NOTE_ID: {note_id}\n"
            f"REVISIONS: 0\n"
            f"STATUS: No revision history found for this note"
        )

    # Sort by created_time, most recent first
    note_revs.sort(key=lambda r: getattr(r, "created_time", 0), reverse=True)

    # Try to get current note title for context
    try:
        note = client.get_note(note_id, fields="id,title")
        current_title = getattr(note, "title", "Unknown")
    except Exception:
        current_title = "Unknown (note may be deleted)"

    lines = [
        f"NOTE_ID: {note_id}",
        f"CURRENT_TITLE: {current_title}",
        f"REVISIONS: {len(note_revs)}",
        "",
    ]

    for i, rev in enumerate(note_revs, 1):
        rev_time = format_timestamp(getattr(rev, "created_time", None))
        parent_id = getattr(rev, "parent_id", "") or ""

        # Extract title from title_diff by applying patch to empty string
        rev_title = None
        title_diff = getattr(rev, "title_diff", "") or ""
        if title_diff and title_diff != "[]":
            try:
                patched = _apply_diff(title_diff, "")
                if patched:
                    rev_title = patched
            except Exception:
                pass

        # Fall back to metadata_diff for title
        if not rev_title:
            metadata_diff = getattr(rev, "metadata_diff", "") or ""
            if metadata_diff:
                try:
                    md = json.loads(metadata_diff)
                    rev_title = md.get("new", {}).get("title", None)
                except Exception:
                    pass

        lines.append(f"REVISION_{i}:")
        lines.append(f"  revision_id: {rev.id}")
        lines.append(f"  created: {rev_time}")
        if rev_title:
            lines.append(f"  title: {rev_title}")
        lines.append(
            f"  has_parent: {'yes' if parent_id else 'no (first revision)'}"
        )
        if parent_id:
            lines.append(f"  parent_id: {parent_id}")

    return "\n".join(lines)


@create_tool("restore_note_revision", "Restore a note from revision history")
async def restore_note_revision(
    revision_id: Annotated[
        str,
        Field(
            description="Revision ID to restore (from get_note_history)"
        ),
    ],
    target_notebook: Annotated[
        Optional[str],
        Field(
            description=(
                "Notebook name for restored note (default: original notebook, "
                "or 'Restored Notes' if unavailable)"
            )
        ),
    ] = None,
) -> str:
    """Restore a previous version of a note from its revision history.

    Reconstructs the note content from revision diffs and creates a NEW note
    with the restored content (same behaviour as Joplin Desktop's restore).
    Does not overwrite the current version of the note.

    Use get_note_history first to find the revision_id to restore.

    Returns:
        str: Success message with the restored note's ID and location.
    """
    client = get_joplin_client()

    # Reconstruct content from revision chain
    try:
        content = _reconstruct_revision_content(client, revision_id)
    except Exception as e:
        raise ValueError(f"Failed to reconstruct revision: {e}")

    title = content["title"] or "Untitled (restored)"
    body = content["body"] or ""
    metadata = content["metadata"]

    # Determine target notebook
    target_notebook_id = None
    if target_notebook:
        target_notebook_id = get_notebook_id_by_name(target_notebook)
    elif metadata.get("parent_id"):
        # Try original notebook
        try:
            import datetime as dt_module

            nb = client.get_notebook(
                metadata["parent_id"], fields="id,title,deleted_time"
            )
            deleted = getattr(nb, "deleted_time", None)
            if deleted and deleted != dt_module.datetime(1970, 1, 1, 0, 0):
                target_notebook_id = None  # Original notebook is trashed
            else:
                target_notebook_id = metadata["parent_id"]
        except Exception:
            target_notebook_id = None

    # Fall back to "Restored Notes" notebook (create if needed)
    if not target_notebook_id:
        try:
            target_notebook_id = get_notebook_id_by_name("Restored Notes")
        except ValueError:
            nb = client.add_notebook(title="Restored Notes")
            target_notebook_id = str(nb)

    # Create the restored note
    note_id = str(
        client.add_note(title=title, body=body, parent_id=target_notebook_id)
    )

    # Get target notebook name for display
    try:
        nb = client.get_notebook(target_notebook_id, fields="id,title")
        nb_name = getattr(nb, "title", target_notebook_id)
    except Exception:
        nb_name = target_notebook_id

    return (
        f"OPERATION: RESTORE_NOTE_REVISION\n"
        f"STATUS: SUCCESS\n"
        f"RESTORED_NOTE_ID: {note_id}\n"
        f"TITLE: {title}\n"
        f"NOTEBOOK: {nb_name}\n"
        f"SOURCE_REVISION: {revision_id}\n"
        f'MESSAGE: Note restored from revision history as a new note in "{nb_name}"'
    )


@create_tool("manually_backup_note", "Create manual revision backup")
async def manually_backup_note(
    note_id: Annotated[
        JoplinIdType, Field(description="Note ID to backup")
    ],
) -> str:
    """Create a manual revision snapshot of a note's current content.

    Saves the note's current title and body as a Joplin revision, enabling
    recovery via get_note_history + restore_note_revision or Joplin Desktop's
    "Note History" UI. Use before risky manual edits or bulk operations.

    Note: Revisions are also created automatically before title/body overwrites
    by update_note and search_and_bulk_update_execute.

    Returns:
        str: Success message with the revision ID.
    """
    note_id = validate_joplin_id(note_id)
    client = get_joplin_client()

    rev_id = save_note_revision(client, note_id)
    if rev_id:
        return (
            f"OPERATION: MANUALLY_BACKUP_NOTE\n"
            f"STATUS: SUCCESS\n"
            f"NOTE_ID: {note_id}\n"
            f"REVISION_ID: {rev_id}\n"
            f"MESSAGE: Revision snapshot created. Recoverable via "
            f"get_note_history + restore_note_revision or "
            f"Joplin Desktop's Note History."
        )
    else:
        return (
            f"OPERATION: MANUALLY_BACKUP_NOTE\n"
            f"STATUS: FAILED\n"
            f"NOTE_ID: {note_id}\n"
            f"MESSAGE: Failed to create revision snapshot. "
            f"Check server logs for details."
        )
