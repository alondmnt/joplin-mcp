"""Formatting utilities for MCP tool responses.

Pure formatting functions optimized for LLM comprehension.
Functions that need notebook path utilities or config remain in fastmcp_server.py.
"""

from enum import Enum
from typing import Any, Dict, List


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


def format_update_success(item_type: ItemType, item_id: str) -> str:
    """Format a standardized success message for update operations optimized for LLM comprehension."""
    return f"""OPERATION: UPDATE_{item_type.value.upper()}
STATUS: SUCCESS
ITEM_TYPE: {item_type.value}
ITEM_ID: {item_id}
MESSAGE: {item_type.value} updated successfully in Joplin"""


def format_delete_success(item_type: ItemType, item_id: str) -> str:
    """Format a standardized success message for delete operations optimized for LLM comprehension."""
    return f"""OPERATION: DELETE_{item_type.value.upper()}
STATUS: SUCCESS
ITEM_TYPE: {item_type.value}
ITEM_ID: {item_id}
MESSAGE: {item_type.value} deleted successfully from Joplin"""


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
    query: str, total_count: int, limit: int, offset: int
) -> List[str]:
    """Build pagination header with search and pagination info."""
    count = min(limit, total_count - offset) if total_count > offset else 0
    current_page = (offset // limit) + 1
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
    start_result = offset + 1 if count > 0 else 0
    end_result = offset + count

    header = [
        f"SEARCH_QUERY: {query}",
        f"TOTAL_RESULTS: {total_count}",
        f"SHOWING_RESULTS: {start_result}-{end_result}",
        f"CURRENT_PAGE: {current_page}",
        f"TOTAL_PAGES: {total_pages}",
        f"LIMIT: {limit}",
        f"OFFSET: {offset}",
        "",
    ]

    # Add next page guidance
    if total_count > end_result:
        next_offset = offset + limit
        header.extend(
            [f"NEXT_PAGE: Use offset={next_offset} to get the next {limit} results", ""]
        )

    return header


def build_pagination_summary(total_count: int, limit: int, offset: int) -> List[str]:
    """Build pagination summary footer."""
    count = min(limit, total_count - offset) if total_count > offset else 0
    current_page = (offset // limit) + 1
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
    start_result = offset + 1 if count > 0 else 0
    end_result = offset + count

    if total_pages <= 1:
        return []

    summary = [
        "PAGINATION_SUMMARY:",
        f"  showing_page: {current_page} of {total_pages}",
        f"  showing_results: {start_result}-{end_result} of {total_count}",
        f"  results_per_page: {limit}",
    ]

    if current_page < total_pages:
        summary.append(f"  next_page_offset: {offset + limit}")

    if current_page > 1:
        summary.append(f"  prev_page_offset: {max(0, offset - limit)}")

    return summary


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
            "notebook_id": "notebook_id",
            "notebook_path": "notebook_path",
            "is_todo": "is_todo",
            "todo_completed": "todo_completed",
        },
    }

    stats_label_map = {
        "upper": {
            "characters": "CONTENT_SIZE_CHARS",
            "words": "CONTENT_SIZE_WORDS",
            "lines": "CONTENT_SIZE_LINES",
        },
        "lower": {
            "characters": "content_size_chars",
            "words": "content_size_words",
            "lines": "content_size_lines",
        },
    }

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

    stats = metadata.get("content_stats")
    if stats:
        stats_labels = stats_label_map[style]
        for stat_key in ["characters", "words", "lines"]:
            if stat_key in stats:
                lines.append(
                    f"{indent}{stats_labels[stat_key]}: {stats[stat_key]}"
                )

    return lines
