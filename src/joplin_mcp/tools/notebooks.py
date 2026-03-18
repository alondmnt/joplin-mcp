"""Notebook tools for Joplin MCP."""
from typing import Annotated, Optional

from pydantic import Field

from joplin_mcp.fastmcp_server import (
    ItemType,
    JoplinIdType,
    RequiredStringType,
    _compute_notebook_path,
    create_tool,
    format_creation_success,
    format_delete_success,
    format_item_list,
    format_update_success,
    get_joplin_client,
    get_notebook_id_by_name,
    get_notebook_map_cached,
    invalidate_notebook_map_cache,
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
    fields_list = "id,title,created_time,updated_time,parent_id"
    notebooks = client.get_all_notebooks(fields=fields_list)
    return format_item_list(notebooks, ItemType.notebook)


@create_tool("create_notebook", "Create notebook")
async def create_notebook(
    title: Annotated[RequiredStringType, Field(description="Notebook title")],
    parent_id: Annotated[
        Optional[str], Field(description="Parent notebook ID (optional)")
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

    client = get_joplin_client()
    notebook_kwargs = {"title": title}
    if parent_id:
        notebook_kwargs["parent_id"] = parent_id.strip()

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
    client = get_joplin_client()
    client.modify_notebook(notebook_id, title=title)
    # Invalidate cache in case the notebook moved/renamed
    invalidate_notebook_map_cache()
    return format_update_success(ItemType.notebook, notebook_id)


@create_tool("delete_notebook", "Delete notebook")
async def delete_notebook(
    notebook_id: Annotated[JoplinIdType, Field(description="Notebook ID to delete")],
) -> str:
    """Delete a notebook from Joplin.

    Permanently removes a notebook from Joplin. This action cannot be undone.

    Returns:
        str: Success message confirming the notebook was deleted.

    Warning: This action is permanent and cannot be undone. All notes in the notebook will also be deleted.
    """
    client = get_joplin_client()
    client.delete_notebook(notebook_id)
    # Invalidate cache since structure changed
    invalidate_notebook_map_cache()
    return format_delete_success(ItemType.notebook, notebook_id)


@create_tool("get_folder_id", "Get folder ID")
async def get_folder_id(
    name: Annotated[
        RequiredStringType,
        Field(
            description=(
                "Notebook name or hierarchical path to look up. "
                "Use a plain name for an exact title match (e.g. 'Work'), "
                "or a '/'-separated path for nested notebooks "
                "(e.g. 'Professional & Knowledge/Claude Code')."
            )
        ),
    ],
) -> str:
    """Look up a Joplin notebook's ID by name or hierarchical path.

    Resolves a notebook name or '/'-separated path to its unique Joplin ID and
    returns the ID together with the notebook's title and full path for
    confirmation.

    Supports:
    - Exact title match: ``get_folder_id("Work")``
    - Hierarchical path match: ``get_folder_id("Projects/Work/Tasks")``

    Returns:
        str: Formatted block containing the resolved notebook ID, title, and
        full path, or an error message if the notebook was not found.

    Examples:
        - get_folder_id("Work") - Find a top-level notebook by title
        - get_folder_id("Professional & Knowledge/Claude Code") - Find by path
    """
    notebook_id = get_notebook_id_by_name(name)
    nb_map = get_notebook_map_cached()
    full_path = _compute_notebook_path(notebook_id, nb_map)
    title = (nb_map.get(notebook_id) or {}).get("title") or name

    return (
        f"Notebook found:\n"
        f"  ID:    {notebook_id}\n"
        f"  Title: {title}\n"
        f"  Path:  {full_path}"
    )
