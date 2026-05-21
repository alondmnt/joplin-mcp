"""Trash management tools for Joplin MCP — restore soft-deleted items."""

import logging
from typing import Annotated

from pydantic import Field

from joplin_mcp import note_view
from joplin_mcp.fastmcp_server import (
    ItemType,
    JoplinIdType,
    create_tool,
    format_restore_success,
    get_joplin_client,
    validate_joplin_id,
)
from joplin_mcp.notebook_utils import notebook_resolver

logger = logging.getLogger(__name__)


@create_tool("restore_from_trash", "Restore item from trash")
async def restore_from_trash(
    item_id: Annotated[
        JoplinIdType,
        Field(description="Note or notebook ID to restore"),
    ],
    item_type: Annotated[
        str,
        Field(description="Item type: 'note' or 'notebook'. Restoring a notebook does not restore the items inside it."),
    ] = "note",
) -> str:
    """Restore a note or notebook from Joplin's trash.

    Restores a previously deleted item by setting its deleted_time back to 0.
    The item reappears in its original notebook.

    Scope of restore (important):
    - Only the single item identified by item_id is restored. When restoring
      a notebook, its sub-notebooks and the notes inside stay trashed and
      must each be restored individually. Joplin sets deleted_time on every
      descendant when a notebook is trashed, and this tool clears it on one
      item per call.
    - If the original parent notebook is also trashed, restore the parent
      first or the restored item may not be visible.

    To find descendants to restore after restoring a notebook, use
    find_notes(query="*", trash=True) and filter to the relevant subtree.

    Returns:
        str: Success message confirming the item was restored.
    """
    item_id = validate_joplin_id(item_id)

    if item_type == "note":
        client = get_joplin_client()
        note_view.modify_note(client, item_id, deleted_time=0)
        return format_restore_success(ItemType.note, item_id)
    elif item_type == "notebook":
        notebook_resolver.modify_notebook(item_id, deleted_time=0)
        return format_restore_success(ItemType.notebook, item_id)
    else:
        raise ValueError(
            f"item_type must be 'note' or 'notebook', got '{item_type}'"
        )
