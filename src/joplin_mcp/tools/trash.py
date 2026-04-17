"""Trash management tools for Joplin MCP — restore soft-deleted items."""

import logging
from typing import Annotated

from pydantic import Field

from joplin_mcp.fastmcp_server import (
    ItemType,
    JoplinIdType,
    create_tool,
    format_restore_success,
    get_joplin_client,
    validate_joplin_id,
)
from joplin_mcp.notebook_utils import invalidate_notebook_map_cache
from joplin_mcp.tools.notes import _clear_note_cache

logger = logging.getLogger(__name__)


@create_tool("restore_from_trash", "Restore item from trash")
async def restore_from_trash(
    item_id: Annotated[
        JoplinIdType,
        Field(description="Note or notebook ID to restore"),
    ],
    item_type: Annotated[
        str,
        Field(description="Item type: 'note' or 'notebook'"),
    ] = "note",
) -> str:
    """Restore a note or notebook from Joplin's trash.

    Restores a previously deleted item by setting its deleted_time back to 0.
    The item reappears in its original notebook.  If the original notebook was
    also trashed, restore it first or the note may not be visible.

    Returns:
        str: Success message confirming the item was restored.
    """
    item_id = validate_joplin_id(item_id)
    client = get_joplin_client()

    if item_type == "note":
        client.modify_note(item_id, deleted_time=0)
        _clear_note_cache()
        return format_restore_success(ItemType.note, item_id)
    elif item_type == "notebook":
        client.modify_notebook(item_id, deleted_time=0)
        invalidate_notebook_map_cache()
        return format_restore_success(ItemType.notebook, item_id)
    else:
        raise ValueError(
            f"item_type must be 'note' or 'notebook', got '{item_type}'"
        )
