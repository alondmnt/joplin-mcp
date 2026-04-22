"""Tag tools for Joplin MCP."""
from typing import Annotated, Dict, List, Tuple, Union

from pydantic import Field

from joplin_mcp.fastmcp_server import (
    COMMON_NOTE_FIELDS,
    ItemType,
    JoplinIdType,
    RequiredStringType,
    _redact_token,
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


# === TAG-NOTE BULK HELPERS ===


def _resolve_tag_ids(client, tag_names: List[str]) -> Dict[str, str]:
    """Resolve multiple tag names to IDs with a single get_all_tags fetch.

    Returns a dict keyed by the *input* names (preserving case) mapping to tag IDs.
    Raises ValueError if any name is missing or ambiguous (multiple Joplin tags
    with the same case-insensitive title), matching get_tag_id_by_name parity.
    """
    all_tags = client.get_all_tags(fields="id,title")
    by_lower: Dict[str, List[str]] = {}
    for t in all_tags:
        tid = getattr(t, "id", None)
        if not tid:
            continue
        by_lower.setdefault(getattr(t, "title", "").lower(), []).append(tid)

    resolved: Dict[str, str] = {}
    missing: List[str] = []
    ambiguous: List[str] = []
    for name in tag_names:
        matches = by_lower.get(name.lower(), [])
        if not matches:
            missing.append(name)
        elif len(matches) > 1:
            ambiguous.append(name)
        else:
            resolved[name] = matches[0]

    if missing or ambiguous:
        parts: List[str] = []
        if missing:
            quoted = ", ".join(f"'{m}'" for m in missing)
            parts.append(f"Tag(s) not found: {quoted}.")
        if ambiguous:
            quoted = ", ".join(f"'{a}'" for a in ambiguous)
            parts.append(f"Ambiguous tag name(s): {quoted}.")
        available = [getattr(t, "title", "Untitled") for t in all_tags]
        parts.append(f"Available tags: {', '.join(available)}.")
        if missing:
            parts.append("Use create_tag to create a new tag.")
        raise ValueError(" ".join(parts))
    return resolved


def _sanitize_report_field(value: str) -> str:
    """Normalise whitespace and replace double quotes for the one-line report format."""
    return " ".join(value.split()).replace('"', "'")


def _format_tag_op_report(
    operation: str,
    results: List[Tuple[str, str, bool, str]],
) -> str:
    """Format an aggregated TAG_NOTE / UNTAG_NOTE report for bulk ops."""
    total = len(results)
    succeeded = sum(1 for _, _, ok, _ in results if ok)
    failed = total - succeeded
    status = "SUCCESS" if failed == 0 else "PARTIAL"

    lines = [
        f"OPERATION: {operation}",
        f"STATUS: {status}",
        f"TOTAL_OPS: {total}",
        f"SUCCEEDED: {succeeded}",
        f"FAILED: {failed}",
        f"MESSAGE: {succeeded} of {total} operations succeeded",
    ]
    if failed:
        lines.append("FAILURES:")
        for note_id, tag_name, ok, err in results:
            if not ok:
                clean_tag = _sanitize_report_field(tag_name)
                clean_err = _sanitize_report_field(err)
                lines.append(
                    f'  - note_id={note_id} tag_name="{clean_tag}" error="{clean_err}"'
                )
    return "\n".join(lines)


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
    note_id: Annotated[
        Union[JoplinIdType, List[JoplinIdType]],
        Field(description="Note ID, or list of note IDs"),
    ],
    tag_name: Annotated[
        Union[RequiredStringType, List[RequiredStringType]],
        Field(description="Tag name, or list of tag names"),
    ],
) -> str:
    """Add one or more tags to one or more notes.

    Both args accept a single string or a list. When either is a list, the cartesian
    product is applied (every tag on every note) in one call — preferred over looping.

    Output shape:
    - Scalar note_id + scalar tag_name: single-op success line (unchanged).
    - Any list input: aggregated TAG_NOTE report with TOTAL_OPS / SUCCEEDED / FAILED.

    Tags must exist beforehand — use create_tag to add new ones. Missing tags are
    reported up front and nothing is applied. Per-op failures (e.g. invalid note ID)
    are captured in the aggregated report; other ops still run.

    Examples:
        - tag_note("abc...", "Work") - Tag one note with one tag
        - tag_note(["abc...", "def..."], "Work") - Tag two notes with one tag
        - tag_note("abc...", ["Work", "Urgent"]) - Add two tags to one note
        - tag_note(["abc...", "def..."], ["Work", "Urgent"]) - 2x2 = 4 ops
    """
    scalar_inputs = isinstance(note_id, str) and isinstance(tag_name, str)
    note_ids = [note_id] if isinstance(note_id, str) else list(note_id)
    tag_names = [tag_name] if isinstance(tag_name, str) else list(tag_name)
    if not note_ids:
        raise ValueError("note_id list must not be empty")
    if not tag_names:
        raise ValueError("tag_name list must not be empty")

    client = get_joplin_client()

    if scalar_inputs:
        # Preserve existing single-op output format for backwards compatibility.
        try:
            note = client.get_note(note_ids[0], fields=COMMON_NOTE_FIELDS)
            note_title = getattr(note, "title", "Unknown Note")
        except Exception:
            raise ValueError(
                f"Note with ID '{note_ids[0]}' not found. "
                "Use find_notes to find available notes."
            )
        tag_id = get_tag_id_by_name(tag_names[0])
        client.add_tag_to_note(tag_id, note_ids[0])
        return format_relation_success(
            "tagged note",
            ItemType.note,
            f"{note_title} (ID: {note_ids[0]})",
            ItemType.tag,
            tag_names[0],
        )

    # Bulk path: resolve all tags up front, then loop the cartesian product.
    tag_map = _resolve_tag_ids(client, tag_names)

    results: List[Tuple[str, str, bool, str]] = []
    for nid in note_ids:
        for tname in tag_names:
            try:
                client.add_tag_to_note(tag_map[tname], nid)
                results.append((nid, tname, True, ""))
            except Exception as e:
                results.append((nid, tname, False, _redact_token(str(e))))

    return _format_tag_op_report("TAG_NOTE", results)


@create_tool("untag_note", "Untag note")
async def untag_note(
    note_id: Annotated[
        Union[JoplinIdType, List[JoplinIdType]],
        Field(description="Note ID, or list of note IDs"),
    ],
    tag_name: Annotated[
        Union[RequiredStringType, List[RequiredStringType]],
        Field(description="Tag name, or list of tag names"),
    ],
) -> str:
    """Remove one or more tags from one or more notes.

    Both args accept a single string or a list. When either is a list, the cartesian
    product is applied (remove every tag from every note) in one call.

    Output shape:
    - Scalar note_id + scalar tag_name: single-op success line (unchanged).
    - Any list input: aggregated UNTAG_NOTE report with TOTAL_OPS / SUCCEEDED / FAILED.

    Tags must exist (by name). Missing tags are reported up front and nothing is
    removed. Per-op failures are captured in the aggregated report; other ops still
    run.

    Examples:
        - untag_note("abc...", "Work") - Remove one tag from one note
        - untag_note(["abc...", "def..."], "Work") - Remove one tag from two notes
        - untag_note("abc...", ["Work", "Urgent"]) - Remove two tags from one note
        - untag_note(["abc...", "def..."], ["Work", "Urgent"]) - 2x2 = 4 ops
    """
    scalar_inputs = isinstance(note_id, str) and isinstance(tag_name, str)
    note_ids = [note_id] if isinstance(note_id, str) else list(note_id)
    tag_names = [tag_name] if isinstance(tag_name, str) else list(tag_name)
    if not note_ids:
        raise ValueError("note_id list must not be empty")
    if not tag_names:
        raise ValueError("tag_name list must not be empty")

    client = get_joplin_client()

    if scalar_inputs:
        # Preserve existing single-op output format for backwards compatibility.
        try:
            note = client.get_note(note_ids[0], fields=COMMON_NOTE_FIELDS)
            note_title = getattr(note, "title", "Unknown Note")
        except Exception:
            raise ValueError(
                f"Note with ID '{note_ids[0]}' not found. "
                "Use find_notes to find available notes."
            )
        tag_id = get_tag_id_by_name(tag_names[0])
        client.delete(f"/tags/{tag_id}/notes/{note_ids[0]}")
        return format_relation_success(
            "removed tag from note",
            ItemType.note,
            f"{note_title} (ID: {note_ids[0]})",
            ItemType.tag,
            tag_names[0],
        )

    # Bulk path: resolve all tags up front, then loop the cartesian product.
    tag_map = _resolve_tag_ids(client, tag_names)

    results: List[Tuple[str, str, bool, str]] = []
    for nid in note_ids:
        for tname in tag_names:
            try:
                client.delete(f"/tags/{tag_map[tname]}/notes/{nid}")
                results.append((nid, tname, True, ""))
            except Exception as e:
                results.append((nid, tname, False, _redact_token(str(e))))

    return _format_tag_op_report("UNTAG_NOTE", results)
