"""Notebook tools for Joplin MCP."""
import json
from typing import Annotated, Optional

from pydantic import Field

from joplin_mcp.config import get_config
from joplin_mcp.fastmcp_server import (
    ItemType,
    JoplinIdType,
    RequiredStringType,
    create_tool,
    format_creation_success,
    format_delete_success,
    format_item_list,
    format_update_success,
    get_joplin_client,
)
from joplin_mcp.notebook_utils import get_notebook_id_by_name, notebook_resolver


# Joplin stores folder icons as a JSON string with type=1 for emoji.
# Length cap leaves room for the longest standard ZWJ emoji sequences
# (kiss-with-skin-tones can reach ~10 codepoints; cap leaves headroom)
# without admitting prose.
_EMOJI_MAX_LEN = 16
_EMOJI_ERROR = (
    "emoji must be a short emoji glyph; got an empty/whitespace or "
    "letter/digit-containing string, or one over "
    f"{_EMOJI_MAX_LEN} characters"
)


def _build_icon_payload(emoji: str) -> str:
    """Convert an `emoji` parameter to Joplin's icon-field wire format.

    Empty string is passed through unchanged (sentinel for "clear icon").
    Other strings are validated and serialised as a type=1 emoji icon.
    """
    if emoji == "":
        return ""

    if (
        not emoji.strip()
        or len(emoji) > _EMOJI_MAX_LEN
        or any(c.isascii() and c.isalnum() for c in emoji)
    ):
        raise ValueError(_EMOJI_ERROR)

    return json.dumps(
        {"type": 1, "emoji": emoji, "name": ""},
        ensure_ascii=False,
    )


# === NOTEBOOK TOOLS ===


@create_tool("list_notebooks", "List notebooks")
async def list_notebooks() -> str:
    """List all notebooks/folders in your Joplin instance.

    Retrieves and displays all notebooks (folders) in your Joplin application.

    Returns:
        str: Formatted list of all notebooks including title, unique ID, parent notebook (if sub-notebook), and creation date.
    """
    client = get_joplin_client()
    fields_list = "id,title,created_time,updated_time,parent_id,icon"
    notebooks = client.get_all_notebooks(fields=fields_list)
    if get_config().has_notebook_allowlist:
        notebooks = notebook_resolver.filter_accessible(
            notebooks, allowlist_entries=get_config().notebook_allowlist
        )
    return format_item_list(notebooks, ItemType.notebook)


@create_tool("create_notebook", "Create notebook")
async def create_notebook(
    title: Annotated[RequiredStringType, Field(description="Notebook title")],
    parent_name: Annotated[
        Optional[str],
        Field(
            description=(
                "Parent notebook name or path (e.g., 'Work' or 'Projects/Work'). "
                "Omit for a top-level notebook."
            )
        ),
    ] = None,
    emoji: Annotated[
        Optional[str],
        Field(description="Single emoji glyph to use as the notebook's icon (optional)"),
    ] = None,
) -> str:
    """Create a new notebook (folder) in Joplin to organize your notes.

    Creates a new notebook that can be used to organize and contain notes. You can create
    top-level notebooks or sub-notebooks within existing notebooks, optionally with an
    emoji icon shown in Joplin's sidebar.

    Notebook can be specified by name or path:
    - "Work" - matches notebook named "Work" (must be unique)
    - "Projects/Work" - matches "Work" notebook inside "Projects"

    Returns:
        str: Success message containing the created notebook's title and unique ID.

    Examples:
        - create_notebook("Work Projects") - Create a top-level notebook
        - create_notebook("2024 Projects", "Work") - Create a sub-notebook under "Work"
        - create_notebook("Tasks", "Projects/Work") - Create a sub-notebook by path
        - create_notebook("Tasks", emoji="🎯") - Create a notebook with an emoji icon
    """

    resolved_parent_id: Optional[str] = None
    if parent_name is not None:
        resolved_parent_id = get_notebook_id_by_name(parent_name)

    if get_config().has_notebook_allowlist:
        if resolved_parent_id:
            notebook_resolver.validate_access(
                resolved_parent_id,
                allowlist_entries=get_config().notebook_allowlist,
            )
        else:
            raise ValueError("Notebook not accessible")

    notebook_kwargs = {"title": title}
    if resolved_parent_id:
        notebook_kwargs["parent_id"] = resolved_parent_id
    if emoji is not None:
        notebook_kwargs["icon"] = _build_icon_payload(emoji)

    notebook = notebook_resolver.add_notebook(**notebook_kwargs)
    return format_creation_success(ItemType.notebook, title, str(notebook))


@create_tool("update_notebook", "Update notebook")
async def update_notebook(
    notebook_id: Annotated[JoplinIdType, Field(description="Notebook ID to update")],
    title: Annotated[
        Optional[str],
        Field(description="New notebook title (optional)", min_length=1),
    ] = None,
    emoji: Annotated[
        Optional[str],
        Field(
            description=(
                "New emoji icon for the notebook (optional). "
                "Pass an empty string to clear an existing icon."
            )
        ),
    ] = None,
) -> str:
    """Update an existing notebook's title and/or emoji icon.

    Pass `emoji=""` to clear an existing icon. At least one of `title` or `emoji`
    must be provided.

    Returns:
        str: Success message confirming the notebook was updated.

    Examples:
        - update_notebook("0123...", title="Archive") - Rename a notebook
        - update_notebook("0123...", emoji="🎯") - Set or replace the emoji icon
        - update_notebook("0123...", emoji="") - Clear the emoji icon
    """
    update_kwargs = {}
    if title is not None:
        update_kwargs["title"] = title
    if emoji is not None:
        update_kwargs["icon"] = _build_icon_payload(emoji)

    if not update_kwargs:
        raise ValueError("At least one field must be provided for update")

    if get_config().has_notebook_allowlist:
        notebook_resolver.validate_access(
            notebook_id, allowlist_entries=get_config().notebook_allowlist
        )

    notebook_resolver.modify_notebook(notebook_id, **update_kwargs)
    return format_update_success(ItemType.notebook, notebook_id)


@create_tool("delete_notebook", "Delete notebook")
async def delete_notebook(
    notebook_id: Annotated[JoplinIdType, Field(description="Notebook ID to delete")],
) -> str:
    """Delete a notebook from Joplin (moves to trash).

    Soft-deletes a notebook and its contained notes by moving them to
    Joplin's trash. Trashed items can be found with find_notes(trash=True)
    and restored with restore_from_trash(). This action is reversible (unlike
    delete_tag, which is permanent).

    Returns:
        str: Success message confirming the notebook was moved to trash.

    Raises:
        ValueError: if the notebook ID does not exist.
    """
    client = get_joplin_client()

    if get_config().has_notebook_allowlist:
        notebook_resolver.validate_access(
            notebook_id, allowlist_entries=get_config().notebook_allowlist
        )

    # Joplin's API silently 200s on DELETE for a missing notebook, so the
    # tool would otherwise report SUCCESS for a no-op. GET first to surface
    # the 404 as a sanitised ValueError via with_client_error_handling.
    client.get_notebook(notebook_id, fields="id")

    notebook_resolver.delete_notebook(notebook_id)
    return format_delete_success(ItemType.notebook, notebook_id)
