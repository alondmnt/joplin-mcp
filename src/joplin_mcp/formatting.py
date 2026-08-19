"""Formatting utilities for MCP tool responses.

Pure formatting functions optimized for LLM comprehension.
Functions that need notebook path utilities or config remain in fastmcp_server.py.
"""

from enum import Enum
from typing import Any, Dict, List, Optional


class ItemType(str, Enum):
    """Item types for formatting."""
    note = "note"
    notebook = "notebook"
    tag = "tag"


def get_item_emoji(item_type: ItemType) -> str:
    """Get emoji for item type."""
    emoji_map = {ItemType.note: "📝", ItemType.notebook: "📁", ItemType.tag: "🏷️"}
    return emoji_map.get(item_type, "📄")


def format_creation_success(item_type: ItemType, title: str, item_id: str) -> str:
    """Format a standardized success message for creation operations optimized for LLM comprehension."""
    return f"""OPERATION: CREATE_{item_type.value.upper()}
STATUS: SUCCESS
ITEM_TYPE: {item_type.value}
ITEM_ID: {item_id}
TITLE: {title}
MESSAGE: {item_type.value} created successfully in Joplin"""


def format_update_success(
    item_type: ItemType, item_id: str, title: Optional[str] = None
) -> str:
    """Format a standardized success message for update operations optimized for LLM comprehension.

    ``title`` is optional because an update does not always carry one: only the
    caller that actually changed the title knows it without a further fetch. The
    ``TITLE:`` line is omitted when no title is available, so the caller never has
    to invent a placeholder.
    """
    title_line = f"\nTITLE: {title}" if title else ""
    return f"""OPERATION: UPDATE_{item_type.value.upper()}
STATUS: SUCCESS
ITEM_TYPE: {item_type.value}
ITEM_ID: {item_id}{title_line}
MESSAGE: {item_type.value} updated successfully in Joplin"""


def format_delete_success(item_type: ItemType, item_id: str) -> str:
    """Format a standardized success message for delete operations optimized for LLM comprehension."""
    if item_type is ItemType.note:
        message = (
            "note moved to trash."
            " Use find_notes(\"*\", trash=True) to list trashed notes,"
            f" restore_from_trash(item_id=\"{item_id}\", item_type=\"note\") to restore"
        )
    elif item_type is ItemType.notebook:
        # No listing path for trashed notebooks yet — keep the ID prominent
        message = (
            "notebook moved to trash."
            f" Restore with restore_from_trash(item_id=\"{item_id}\", item_type=\"notebook\")."
            " Notes inside the notebook are also trashed; restore the notebook first."
        )
    else:
        message = f"{item_type.value} deleted successfully from Joplin"
    return f"""OPERATION: DELETE_{item_type.value.upper()}
STATUS: SUCCESS
ITEM_TYPE: {item_type.value}
ITEM_ID: {item_id}
MESSAGE: {message}"""


def format_restore_success(item_type: ItemType, item_id: str) -> str:
    """Format a standardized success message for restore-from-trash operations."""
    return f"""OPERATION: RESTORE_{item_type.value.upper()}
STATUS: SUCCESS
ITEM_TYPE: {item_type.value}
ITEM_ID: {item_id}
MESSAGE: {item_type.value} restored successfully from trash in Joplin"""


def format_relation_success(
    operation: str,
    item1_type: ItemType,
    item1_id: str,
    item2_type: ItemType,
    item2_id: str,
) -> str:
    """Format a standardized success message for relationship operations optimized for LLM comprehension."""
    return f"""OPERATION: {operation.upper().replace(' ', '_')}
STATUS: SUCCESS
ITEM1_TYPE: {item1_type.value}
ITEM1_ID: {item1_id}
ITEM2_TYPE: {item2_type.value}
ITEM2_ID: {item2_id}
MESSAGE: {operation} completed successfully"""


def format_no_results_message(item_type: str, context: str = "") -> str:
    """Format a standardized no results message optimized for LLM comprehension."""
    return f"ITEM_TYPE: {item_type}\nTOTAL_ITEMS: 0\nCONTEXT: {context}\nSTATUS: No {item_type}s found"


def build_pagination_header(
    query: str,
    total_count: int,
    limit: int,
    offset: int,
    *,
    order_by: Optional[str] = None,
    order_dir: Optional[str] = None,
    include_hints: bool = False,
) -> List[str]:
    """Build pagination header with search and pagination info.

    ``include_hints`` adds the worked-example NEXT_PAGE line. It is a parameter
    rather than a config lookup so this module stays free of config imports;
    callers read the setting.
    """
    count = min(limit, total_count - offset) if total_count > offset else 0
    start_result = offset + 1 if count > 0 else 0
    end_result = offset + count

    # One statement of the window. page number and page count are derivable
    # from offset/limit/total, and were previously given twice: once here and
    # again in a PAGINATION_SUMMARY footer.
    span = f"{start_result}-{end_result}" if count else "0"
    header = [
        f"SEARCH_QUERY: {query}",
        f"RESULTS: {span} of {total_count} (offset={offset}, limit={limit})",
    ]

    if order_by is not None:
        sort_desc = f"{order_by} {order_dir}" if order_dir else order_by
        header.append(f"SORT_ORDER: {sort_desc}")

    header.append("")

    # Add next page guidance
    if include_hints and total_count > end_result:
        next_offset = offset + limit
        header.extend(
            [f"NEXT_PAGE: Use offset={next_offset} to get the next {limit} results", ""]
        )

    return header


def format_find_in_note_summary(
    limit: int,
    offset: int,
    total_count: int,
    showing_count: int,
) -> str:
    """Compose a compact summary line for find_in_note output without repeating metadata."""
    if total_count > 0:
        total_pages = (total_count + limit - 1) // limit
        current_page = (offset // limit) + 1
        if showing_count > 0:
            start_result = offset + 1
            end_result = offset + showing_count
            showing_range = f"{start_result}-{end_result}"
        else:
            showing_range = "0-0"
    else:
        total_pages = 1
        current_page = 1
        showing_range = "0-0"

    return (
        "SUMMARY: "
        f"showing={showing_count} range={showing_range} "
        f"total={total_count} page={current_page}/{total_pages} "
        f"offset={offset} limit={limit}"
    )


def format_note_metadata_lines(
    metadata: Dict[str, Any],
    *,
    style: str = "upper",
    indent: str = "",
) -> List[str]:
    """Format collected note metadata into lines with a given style."""

    key_order = [
        "note_id",
        "title",
        "created",
        "updated",
        "deleted",
        "notebook_id",
        "notebook_path",
        "is_todo",
        "todo_completed",
    ]

    label_map = {
        "upper": {
            "note_id": "NOTE_ID",
            "title": "TITLE",
            "created": "CREATED",
            "updated": "UPDATED",
            "deleted": "DELETED",
            "notebook_id": "NOTEBOOK_ID",
            "notebook_path": "NOTEBOOK_PATH",
            "is_todo": "IS_TODO",
            "todo_completed": "TODO_COMPLETED",
        },
        "lower": {
            "note_id": "note_id",
            "title": "title",
            "created": "created",
            "updated": "updated",
            "deleted": "deleted",
            "notebook_id": "notebook_id",
            "notebook_path": "notebook_path",
            "is_todo": "is_todo",
            "todo_completed": "todo_completed",
        },
    }

    stats_label = {"upper": "CONTENT_SIZE", "lower": "content_size"}

    lines: List[str] = []
    labels = label_map[style]

    for key in key_order:
        if key not in metadata:
            continue
        value = metadata[key]
        if isinstance(value, bool):
            value_str = "true" if value else "false"
        else:
            value_str = value
        lines.append(f"{indent}{labels[key]}: {value_str}")

    # One line rather than three: every search result carries these, so the
    # repeated labels cost more than the numbers they introduce.
    stats = metadata.get("content_stats")
    if stats:
        units = [("characters", "chars"), ("words", "words"), ("lines", "lines")]
        parts = [
            f"{stats[stat_key]} {unit}" for stat_key, unit in units if stat_key in stats
        ]
        if parts:
            lines.append(f"{indent}{stats_label[style]}: {', '.join(parts)}")

    return lines
