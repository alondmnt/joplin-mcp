"""Field registry and search helpers for bulk operation tools.

Provides:
- JOPLIN_NOTE_FIELDS: Registry mapping field names to type converters
- ALL_NOTE_FIELDS: Comma-separated string of all fields for API requests
- convert_todo_completed: Timestamp converter for todo_completed values
- _search_notes: Single entry point for searching + filtering notes
- _parse_update_params: Separates update values from filter conditions
- extract_note_ids_from_result: Parses note IDs from formatted output
"""

import datetime
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from joplin_mcp.fastmcp_server import (
    COMMON_NOTE_FIELDS,
    flexible_bool_converter,
    process_search_results,
    timestamp_converter,
)


# ---------------------------------------------------------------------------
# todo_completed converter
# ---------------------------------------------------------------------------


def convert_todo_completed(
    value: Union[bool, str, int, None],
) -> tuple[Optional[int], Optional[str]]:
    """Convert todo_completed input to Joplin API epoch-ms timestamp.

    Accepts:
        - True/False  (True -> current time in ms, False -> 0)
        - Epoch milliseconds (int)
        - ISO datetime string ('YYYY-MM-DD HH:MM' or 'YYYY-MM-DD')

    Returns:
        (api_value, warning_message) tuple.
    """
    if value is None:
        return (None, None)

    if isinstance(value, bool):
        return (int(time.time() * 1000) if value else 0, None)

    if isinstance(value, str):
        value_stripped = value.strip()
        value_lower = value_stripped.lower()
        if value_lower in ("true", "yes", "on"):
            return (int(time.time() * 1000), None)
        if value_lower in ("false", "no", "off"):
            return (0, None)
        try:
            dt = datetime.datetime.fromisoformat(value_stripped)
            return (int(dt.timestamp() * 1000), None)
        except ValueError:
            raise ValueError(
                f"Unrecognized todo_completed format: '{value}'. "
                "Accepts: True/False, epoch milliseconds, or ISO datetime "
                "'YYYY-MM-DD HH:MM' / 'YYYY-MM-DD'"
            )

    if isinstance(value, (int, float)):
        int_value = int(value)
        if int_value == 0:
            return (0, None)
        if int_value >= 1_000_000_000_000:
            return (int_value, None)
        return (
            int_value,
            f"WARNING: todo_completed={int_value} interpreted as "
            f"{int_value}ms since epoch (1970-01-01). Did you mean True?",
        )

    raise ValueError(
        f"Invalid todo_completed type: {type(value).__name__}. "
        "Accepts: True/False, epoch milliseconds, or ISO datetime "
        "'YYYY-MM-DD HH:MM' / 'YYYY-MM-DD'"
    )


# ---------------------------------------------------------------------------
# Field registry
# ---------------------------------------------------------------------------

JOPLIN_NOTE_FIELDS: Dict[str, Dict[str, Any]] = {
    "title": {
        "type_converter": lambda x: x,
        "description": "Note title",
    },
    "body": {
        "type_converter": lambda x: x,
        "description": "Note content",
    },
    "is_todo": {
        "type_converter": flexible_bool_converter,
        "description": "Todo status",
    },
    "todo_completed": {
        "type_converter": lambda x: convert_todo_completed(x)[0],
        "description": "Todo completion status",
    },
    "todo_due": {
        "type_converter": lambda x: timestamp_converter(x, "todo_due"),
        "description": "Todo due date (epoch ms or ISO 8601)",
    },
    "parent_id": {
        "type_converter": lambda x: x,
        "description": "Notebook ID",
    },
    "author": {
        "type_converter": lambda x: x,
        "description": "Note author",
    },
    "source_url": {
        "type_converter": lambda x: x,
        "description": "Source URL",
    },
    "latitude": {
        "type_converter": lambda x: x,
        "description": "GPS latitude coordinate",
    },
    "longitude": {
        "type_converter": lambda x: x,
        "description": "GPS longitude coordinate",
    },
    "altitude": {
        "type_converter": lambda x: x,
        "description": "GPS altitude coordinate",
    },
    "markup_language": {
        "type_converter": lambda x: x,
        "description": "Note markup format: 1=Markdown, 2=HTML",
    },
    "user_created_time": {
        "type_converter": lambda x: x,
        "description": "Custom creation timestamp in milliseconds",
    },
    "user_updated_time": {
        "type_converter": lambda x: x,
        "description": "Custom update timestamp in milliseconds",
    },
}

# All fields to request from the API — COMMON_NOTE_FIELDS + registry fields.
# SQLite fetches the full row regardless, so requesting extra columns is free.
ALL_NOTE_FIELDS = ",".join(sorted(set(
    COMMON_NOTE_FIELDS.split(",") + list(JOPLIN_NOTE_FIELDS.keys())
)))


# ---------------------------------------------------------------------------
# Search and filter
# ---------------------------------------------------------------------------


def _search_notes(
    client,
    query: str,
    **filters: Any,
) -> Tuple[List[Any], int]:
    """Search Joplin notes and apply field-value filters.

    Two-phase approach:
    1. Joplin API text search (handles full-text, notebook:, tag:, title:, etc.)
    2. Python post-filtering for field-value conditions the API can't express
       (e.g., author="Albert", is_todo=True). All filters are AND logic.

    The query string is passed to Joplin untouched — never parsed for field
    names. All fields from the registry are always fetched so filters can
    inspect any field without a second API call.

    Args:
        client: Joplin ClientApi instance.
        query: Search query for Joplin. Supports Joplin search operators
            (notebook:, tag:, title:, body:, type:, etc.) and "*" for all notes.
        **filters: Field conditions (AND logic). Keys must be valid field names
            from JOPLIN_NOTE_FIELDS. Example: is_todo=True, author="Albert".

    Returns:
        (matching_notes, skipped_count) tuple.
    """
    # Phase 1: Joplin API search
    if query.strip() == "*":
        results = client.get_all_notes(fields=ALL_NOTE_FIELDS)
        notes = process_search_results(results)
        notes.sort(
            key=lambda x: getattr(x, "updated_time", 0), reverse=True
        )
    else:
        results = client.search_all(query=query, fields=ALL_NOTE_FIELDS)
        notes = process_search_results(results)

    # Phase 2: Python field-value filtering (AND logic)
    if not filters:
        return notes, 0

    matching = []
    skipped = 0
    for note in notes:
        match = True
        for field, expected in filters.items():
            if expected is not None and getattr(note, field, None) != expected:
                match = False
                break
        if match:
            matching.append(note)
        else:
            skipped += 1

    return matching, skipped


# ---------------------------------------------------------------------------
# Update parameter parsing
# ---------------------------------------------------------------------------


def _parse_update_params(**kwargs: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Separate update values from filter conditions.

    Convention: parameters ending in ``_filter`` are conditions (used by
    _search_notes for post-fetch filtering). All other parameters matching
    JOPLIN_NOTE_FIELDS keys are update values. Unknown keys are ignored.

    Args:
        **kwargs: All tool parameters (field values, filters, and anything else).

    Returns:
        (updates, filters) tuple.
        - updates: {field_name: new_value} for fields to modify.
        - filters: {field_name: required_value} for _search_notes filtering.
    """
    updates: Dict[str, Any] = {}
    filters: Dict[str, Any] = {}

    for key, value in kwargs.items():
        if value is None:
            continue
        if key.endswith("_filter"):
            field = key[:-7]  # strip "_filter"
            if field in JOPLIN_NOTE_FIELDS:
                filters[field] = value
        elif key in JOPLIN_NOTE_FIELDS:
            updates[key] = value

    return updates, filters


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def extract_note_ids_from_result(formatted_result: str, limit: int) -> List[str]:
    """Extract note IDs from formatted search results.

    Parses output looking for lines matching ``note_id: <32-hex-chars>``.

    Args:
        formatted_result: Formatted string output from find_notes/preview.
        limit: Maximum number of note IDs to extract.

    Returns:
        List of note IDs (up to *limit*).
    """
    note_ids: List[str] = []
    pattern = r"^\s*note_id:\s*([a-f0-9]{32})"

    for line in formatted_result.split("\n"):
        match = re.match(pattern, line)
        if match and len(note_ids) < limit:
            note_ids.append(match.group(1))

    return note_ids
