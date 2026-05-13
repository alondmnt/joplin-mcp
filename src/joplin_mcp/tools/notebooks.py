"""Notebook tools for Joplin MCP."""
from typing import Annotated, Optional

from pydantic import Field

from joplin_mcp.fastmcp_server import (
    ItemType,
    JoplinIdType,
    RequiredStringType,
    _module_config,
    create_tool,
    format_creation_success,
    format_delete_success,
    format_item_list,
    format_update_success,
    get_joplin_client,
    invalidate_notebook_map_cache,
    validate_joplin_id,
)
from joplin_mcp.notebook_utils import (
    filter_accessible_notebooks,
    validate_notebook_access,
)


PARENT_ID_ERROR = "parent_id must be null or a valid notebook ID"


def _normalize_parent_id(parent_id: Optional[str]) -> Optional[str]:
    """Validate optional notebook parent IDs for top-level/sub-notebook creation."""
    if parent_id is None:
        return None

    normalized = parent_id.strip()
    if not normalized:
        raise ValueError(PARENT_ID_ERROR)

    try:
        return validate_joplin_id(normalized)
    except ValueError as exc:
        raise ValueError(PARENT_ID_ERROR) from exc


# === NOTEBOOK TOOLS ===


@create_tool("list_notebooks", "List notebooks")
async def list_notebooks() -> str:
    """List all notebooks/folders in your Joplin instance.

    Retrieves and displays all notebooks (folders) in your Joplin application.

    Returns:
        str: Formatted list of all notebooks including title, unique ID, parent notebook (if sub-notebook), and creation date.
    """
    client = get_joplin_client()
    fields_list = "id,title,created_time,updated_time,parent_id"
    notebooks = client.get_all_notebooks(fields=fields_list)
    if _module_config.has_notebook_allowlist:
        notebooks = filter_accessible_notebooks(
            notebooks, allowlist_entries=_module_config.notebook_allowlist
        )
    return format_item_list(notebooks, ItemType.notebook)


@create_tool("create_notebook", "Create notebook")
async def create_notebook(
    title: Annotated[RequiredStringType, Field(description="Notebook title")],
    parent_id: Annotated[
        Optional[JoplinIdType], Field(description="Parent notebook ID (optional)")
    ] = None,
) -> str:
    """Create a new notebook (folder) in Joplin to organize your notes.

    Creates a new notebook that can be used to organize and contain notes. You can create
    top-level notebooks or sub-notebooks within existing notebooks.

    Returns:
        str: Success message containing the created notebook's title and unique ID.

    Examples:
        - create_notebook("Work Projects") - Create a top-level notebook
        - create_notebook("2024 Projects", "work_notebook_id") - Create a sub-notebook
    """

    normalized_parent_id = _normalize_parent_id(parent_id)

    if _module_config.has_notebook_allowlist:
        if normalized_parent_id:
            validate_notebook_access(
                normalized_parent_id,
                allowlist_entries=_module_config.notebook_allowlist,
            )
        else:
            raise ValueError("Notebook not accessible")

    client = get_joplin_client()
    notebook_kwargs = {"title": title}
    if normalized_parent_id:
        notebook_kwargs["parent_id"] = normalized_parent_id

    notebook = client.add_notebook(**notebook_kwargs)
    # Invalidate notebook path cache to reflect new structure immediately
    invalidate_notebook_map_cache()
    return format_creation_success(ItemType.notebook, title, str(notebook))


@create_tool("update_notebook", "Update notebook")
async def update_notebook(
    notebook_id: Annotated[JoplinIdType, Field(description="Notebook ID to update")],
    title: Annotated[RequiredStringType, Field(description="New notebook title")],
) -> str:
    """Update an existing notebook.

    Updates the title of an existing notebook. Currently only the title can be updated.

    Returns:
        str: Success message confirming the notebook was updated.
    """
    if _module_config.has_notebook_allowlist:
        validate_notebook_access(
            notebook_id, allowlist_entries=_module_config.notebook_allowlist
        )

    client = get_joplin_client()
    client.modify_notebook(notebook_id, title=title)
    # Invalidate cache in case the notebook moved/renamed
    invalidate_notebook_map_cache()
    return format_update_success(ItemType.notebook, notebook_id)


@create_tool("delete_notebook", "Delete notebook")
async def delete_notebook(
    notebook_id: Annotated[JoplinIdType, Field(description="Notebook ID to delete")],
) -> str:
    """Delete a notebook from Joplin (moves to trash).

    Soft-deletes a notebook and its contained notes by moving them to
    Joplin's trash.  Trashed items can be found with find_notes(trash=True)
    and restored with restore_from_trash().

    Returns:
        str: Success message confirming the notebook was moved to trash.
    """
    if _module_config.has_notebook_allowlist:
        validate_notebook_access(
            notebook_id, allowlist_entries=_module_config.notebook_allowlist
        )

    client = get_joplin_client()
    client.delete_notebook(notebook_id)
    # Invalidate cache since structure changed
    invalidate_notebook_map_cache()
    return format_delete_success(ItemType.notebook, notebook_id)
