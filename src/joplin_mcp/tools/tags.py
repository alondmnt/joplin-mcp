"""Tag tools for Joplin MCP."""
from typing import Annotated

from pydantic import Field

from joplin_mcp.fastmcp_server import (
    COMMON_NOTE_FIELDS,
    ItemType,
    JoplinIdType,
    RequiredStringType,
    create_tool,
    format_creation_success,
    format_delete_success,
    format_item_list,
    format_no_results_message,
    format_relation_success,
    format_tag_list_with_counts,
    format_update_success,
    get_joplin_client,
    get_tag_id_by_name,
    process_search_results,
)


# === TAG HELPER FUNCTIONS ===


async def _tag_note_impl(note_id: str, tag_name: str) -> str:
    """Shared implementation for adding a tag to a note using note ID and tag name."""
    client = get_joplin_client()

    # Verify note exists by getting it
    try:
        note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
        note_title = getattr(note, "title", "Unknown Note")
    except Exception:
        raise ValueError(
            f"Note with ID '{note_id}' not found. Use find_notes to find available notes."
        )

    # Use helper function to get tag ID
    tag_id = get_tag_id_by_name(tag_name)

    client.add_tag_to_note(tag_id, note_id)
    return format_relation_success(
        "tagged note",
        ItemType.note,
        f"{note_title} (ID: {note_id})",
        ItemType.tag,
        tag_name,
    )


async def _untag_note_impl(note_id: str, tag_name: str) -> str:
    """Shared implementation for removing a tag from a note using note ID and tag name."""

    client = get_joplin_client()

    # Verify note exists by getting it
    try:
        note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
        note_title = getattr(note, "title", "Unknown Note")
    except Exception:
        raise ValueError(
            f"Note with ID '{note_id}' not found. Use find_notes to find available notes."
        )

    # Use helper function to get tag ID
    tag_id = get_tag_id_by_name(tag_name)

    client.remove_tag_from_note(tag_id, note_id)
    return format_relation_success(
        "removed tag from note",
        ItemType.note,
        f"{note_title} (ID: {note_id})",
        ItemType.tag,
        tag_name,
    )


# === TAG TOOLS ===


@create_tool("list_tags", "List tags")
async def list_tags() -> str:
    """List all tags in your Joplin instance with note counts.

    Retrieves and displays all tags that exist in your Joplin application. Tags are labels
    that can be applied to notes for categorization and organization.

    Returns:
        str: Formatted list of all tags including title, unique ID, number of notes tagged with it, and creation date.
    """
    client = get_joplin_client()
    fields_list = "id,title,created_time,updated_time"
    tags = client.get_all_tags(fields=fields_list)
    return format_tag_list_with_counts(tags, client)


@create_tool("create_tag", "Create tag")
async def create_tag(
    title: Annotated[RequiredStringType, Field(description="Tag title")],
) -> str:
    """Create a new tag.

    Creates a new tag that can be applied to notes for categorization and organization.

    Returns:
        str: Success message with the created tag's title and unique ID.

    Examples:
        - create_tag("work") - Create a new tag named "work"
        - create_tag("important") - Create a new tag named "important"
    """
    client = get_joplin_client()
    tag = client.add_tag(title=title)
    return format_creation_success(ItemType.tag, title, str(tag))


@create_tool("update_tag", "Update tag")
async def update_tag(
    tag_id: Annotated[JoplinIdType, Field(description="Tag ID to update")],
    title: Annotated[RequiredStringType, Field(description="New tag title")],
) -> str:
    """Update an existing tag.

    Updates the title of an existing tag. Currently only the title can be updated.

    Returns:
        str: Success message confirming the tag was updated.
    """
    client = get_joplin_client()
    client.modify_tag(tag_id, title=title)
    return format_update_success(ItemType.tag, tag_id)


@create_tool("delete_tag", "Delete tag")
async def delete_tag(
    tag_id: Annotated[JoplinIdType, Field(description="Tag ID to delete")],
) -> str:
    """Delete a tag from Joplin.

    Permanently removes a tag from Joplin. This action cannot be undone.
    The tag will be removed from all notes that currently have it.

    Returns:
        str: Success message confirming the tag was deleted.

    Warning: This action is permanent and cannot be undone. The tag will be removed from all notes.
    """
    client = get_joplin_client()
    client.delete_tag(tag_id)
    return format_delete_success(ItemType.tag, tag_id)


@create_tool("get_tags_by_note", "Get tags by note")
async def get_tags_by_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to get tags from")],
) -> str:
    """Get all tags for a specific note.

    Retrieves all tags that are currently applied to a specific note.

    Returns:
        str: Formatted list of tags applied to the note with title, ID, and creation date.
    """

    client = get_joplin_client()
    fields_list = "id,title,created_time,updated_time"
    tags_result = client.get_tags(note_id=note_id, fields=fields_list)
    tags = process_search_results(tags_result)

    if not tags:
        return format_no_results_message("tag", f"for note: {note_id}")

    return format_item_list(tags, ItemType.tag)


# === TAG-NOTE RELATIONSHIP OPERATIONS ===


@create_tool("tag_note", "Tag note")
async def tag_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to add tag to")],
    tag_name: Annotated[RequiredStringType, Field(description="Tag name to add")],
) -> str:
    """Add a tag to a note for categorization and organization.

    Applies an existing tag to a specific note using the note's unique ID and the tag's name.
    Uses note ID for precise targeting and tag name for intuitive selection.

    Returns:
        str: Success message confirming the tag was added to the note.

    Examples:
        - tag_note("a1b2c3d4e5f6...", "Important") - Add 'Important' tag to specific note
        - tag_note("note_id_123", "Work") - Add 'Work' tag to the note

    Note: The note must exist (by ID) and the tag must exist (by name). A note can have multiple tags.
    """
    return await _tag_note_impl(note_id, tag_name)


@create_tool("untag_note", "Untag note")
async def untag_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to remove tag from")],
    tag_name: Annotated[RequiredStringType, Field(description="Tag name to remove")],
) -> str:
    """Remove a tag from a note.

    Removes an existing tag from a specific note using the note's unique ID and the tag's name.

    Returns:
        str: Success message confirming the tag was removed from the note.

    Examples:
        - untag_note("a1b2c3d4e5f6...", "Important") - Remove 'Important' tag from specific note
        - untag_note("note_id_123", "Work") - Remove 'Work' tag from the note

    Note: Both the note (by ID) and tag (by name) must exist in Joplin.
    """
    return await _untag_note_impl(note_id, tag_name)
