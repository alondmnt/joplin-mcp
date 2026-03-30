"""Bulk tag operation tools for Joplin MCP."""

import logging
from typing import Annotated, List

from pydantic import Field

from joplin_mcp.fastmcp_server import (
    COMMON_NOTE_FIELDS,
    JoplinIdType,
    create_tool,
    get_joplin_client,
    get_tag_id_by_name,
    process_search_results,
    validate_joplin_id,
)
from joplin_mcp.formatting import ItemType
from joplin_mcp.tools.tags import _tag_note_impl, _untag_note_impl

logger = logging.getLogger(__name__)


# === BULK TAG TOOLS ===


@create_tool("strip_note_tags", "Remove all tags from note")
async def strip_note_tags(
    note_id: Annotated[
        JoplinIdType,
        Field(description="Note ID to remove all tags from"),
    ],
) -> str:
    """Remove all tags from a specific note.

    Removes all existing tags from a note, effectively clearing its tag
    associations. Useful for resetting a note's categorisation or cleaning
    up over-tagged notes.

    Returns:
        str: Success message with details of the tag removal operation.

    Examples:
        - strip_note_tags("a1b2c3d4e5f6...") - Remove all tags from specific note
        - strip_note_tags("note_id_123") - Clear all tags from the note

    Note: The note must exist (by ID). If the note has no tags, the operation
    succeeds with no changes.
    """
    note_id = validate_joplin_id(note_id)
    client = get_joplin_client()

    # Verify note exists and get info (following alondmnt's pattern)
    try:
        note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
        note_title = getattr(note, "title", "Unknown Note")
    except Exception:
        raise ValueError(
            f"Note with ID '{note_id}' not found. "
            f"Use find_notes to find available notes."
        )

    # Get all tags currently on this note
    try:
        fields_list = "id,title,created_time,updated_time"
        tags_result = client.get_tags(note_id=note_id, fields=fields_list)
        note_tags = process_search_results(tags_result)
    except Exception as e:
        raise RuntimeError(
            f"Failed to retrieve tags for note '{note_title}': {e}"
        )

    if not note_tags:
        return (
            f"OPERATION: STRIP_TAGS\n"
            f"STATUS: SUCCESS\n"
            f"NOTE_ID: {note_id}\n"
            f"NOTE_TITLE: {note_title}\n"
            f"TAGS_REMOVED: 0\n"
            f"MESSAGE: Note already has no tags"
        )

    # Remove each tag from the note
    successful_removals = []
    failed_removals = []

    for tag in note_tags:
        tag_id = getattr(tag, "id", "")
        tag_name = getattr(tag, "title", "Unknown Tag")
        try:
            client.delete(f"/tags/{tag_id}/notes/{note_id}")
            successful_removals.append(tag_name)
        except Exception as e:
            failed_removals.append(f"'{tag_name}': {e}")

    success_count = len(successful_removals)
    total_count = len(note_tags)

    if failed_removals:
        result_lines = [
            "OPERATION: STRIP_TAGS",
            "STATUS: PARTIAL_SUCCESS",
            f"NOTE_ID: {note_id}",
            f"NOTE_TITLE: {note_title}",
            f"TAGS_REMOVED: {success_count}/{total_count}",
            f"REMOVED: {', '.join(successful_removals)}",
            f"FAILED: {', '.join(failed_removals)}",
        ]
    else:
        result_lines = [
            "OPERATION: STRIP_TAGS",
            "STATUS: SUCCESS",
            f"NOTE_ID: {note_id}",
            f"NOTE_TITLE: {note_title}",
            f"TAGS_REMOVED: {success_count}",
            f"REMOVED: {', '.join(successful_removals)}",
        ]

    return "\n".join(result_lines)


@create_tool("bulk_tag_notes", "Bulk tag notes")
async def bulk_tag_notes(
    note_ids: Annotated[
        List[str],
        Field(description="List of note IDs to add tags to"),
    ],
    tag_names: Annotated[
        List[str],
        Field(description="List of tag names to add to each note"),
    ],
) -> str:
    """Apply multiple tags to multiple notes in a single bulk operation.

    Adds all specified tags to all specified notes (cartesian product). Each
    tag will be applied to each note, creating comprehensive tagging across
    multiple items.

    Returns:
        str: Detailed success message with operation statistics.

    Examples:
        - bulk_tag_notes(["note1", "note2"], ["Important", "Work"])
        - bulk_tag_notes(["abc123", "def456", "ghi789"], ["Project-Alpha"])

    Note: All notes must exist (by ID) and all tags must exist (by name).
    Creates note-tag relationships for all combinations.
    """
    if not note_ids:
        raise ValueError("At least one note ID must be provided")
    if not tag_names:
        raise ValueError("At least one tag name must be provided")

    # Validate all note IDs
    validated_note_ids = [validate_joplin_id(nid) for nid in note_ids]

    client = get_joplin_client()

    # Verify all notes exist and collect titles (following alondmnt's pattern)
    note_titles = {}
    for nid in validated_note_ids:
        try:
            note = client.get_note(nid, fields=COMMON_NOTE_FIELDS)
            note_titles[nid] = getattr(note, "title", "Unknown Note")
        except Exception:
            raise ValueError(
                f"Note with ID '{nid}' not found. "
                f"Use find_notes to find available notes."
            )

    # Apply all tags to all notes (cartesian product)
    successful_operations = []
    failed_operations = []
    total_operations = len(validated_note_ids) * len(tag_names)

    for nid in validated_note_ids:
        note_title = note_titles[nid]
        for tag_name in tag_names:
            try:
                tag_id = get_tag_id_by_name(tag_name)
                client.add_tag_to_note(tag_id, nid)
                successful_operations.append(
                    f"'{tag_name}' -> '{note_title}' ({nid[:8]}...)"
                )
            except Exception as e:
                failed_operations.append(
                    f"'{tag_name}' -> '{note_title}' ({nid[:8]}...): {e}"
                )

    success_count = len(successful_operations)
    failure_count = len(failed_operations)

    if failure_count == 0:
        status = "SUCCESS"
    elif success_count > 0:
        status = "PARTIAL_SUCCESS"
    else:
        status = "FAILED"

    result_parts = [
        "OPERATION: BULK_TAG_NOTES",
        f"STATUS: {status}",
        f"NOTES_PROCESSED: {len(validated_note_ids)}",
        f"TAGS_APPLIED: {len(tag_names)}",
        f"TOTAL_OPERATIONS: {total_operations}",
        f"SUCCESSFUL: {success_count}",
        f"FAILED: {failure_count}",
        "",
    ]

    if successful_operations:
        result_parts.append("SUCCESSFUL_TAGS:")
        for op in successful_operations:
            result_parts.append(f"  {op}")
        result_parts.append("")

    if failed_operations:
        result_parts.append("FAILED_TAGS:")
        for op in failed_operations:
            result_parts.append(f"  {op}")
        result_parts.append("")

    # Summary message
    if failure_count == 0:
        result_parts.append(
            f"MESSAGE: Successfully applied {len(tag_names)} tag(s) to "
            f"{len(validated_note_ids)} note(s) ({success_count} total operations)"
        )
    elif success_count > 0:
        result_parts.append(
            f"MESSAGE: Partially completed bulk tagging: "
            f"{success_count} successful, {failure_count} failed"
        )
    else:
        result_parts.append(
            f"MESSAGE: Bulk tagging failed: "
            f"all {total_operations} operations failed"
        )

    return "\n".join(result_parts)
