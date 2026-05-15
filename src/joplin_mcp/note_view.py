"""Note rendering: cache, formatters, and the get_note display dispatch.

The module owns three concerns:

- Single-note cache for sequential reading (``get_cached_note`` /
  ``set_cached_note`` / ``clear_note_cache``; mutation tools call
  ``clear_note_cache`` to invalidate after writes).
- Formatters shared across get_note, find_notes, and find_in_note:
  ``format_note_details``, ``format_search_results_with_pagination``,
  and ``_build_find_in_note_header``.
- get_note display dispatch (``render_note``) across section extraction,
  line-range extraction, explicit TOC, smart TOC, and default full-note
  formatting.
"""

import time
from typing import Any, Dict, List, Optional

from joplin_mcp.content_utils import (
    calculate_content_stats,
    create_content_preview,
    create_content_preview_with_search,
    create_toc_only,
    extract_section_content,
    format_timestamp,
    parse_markdown_headings,
)
from joplin_mcp.fastmcp_server import _module_config
from joplin_mcp.formatting import (
    build_pagination_header,
    build_pagination_summary,
    format_find_in_note_summary,
    format_note_metadata_lines,
)
from joplin_mcp.notebook_utils import _compute_notebook_path, notebook_resolver


# === CACHE ===
# Single-slot cache: stores one note keyed by ID. The 30s TTL is long enough
# to span an LLM's chunked reads of a long note but short enough that a stale
# read won't surprise an interactive caller. Mutations invalidate eagerly via
# clear_note_cache.

_CACHE_TTL_SECONDS = 30

_cached_note: Any = None
_cached_note_id: Optional[str] = None
_cached_at: float = 0.0


def get_cached_note(note_id: str) -> Any:
    """Return the cached note if it matches the ID and is within TTL, else None."""
    if _cached_note_id == note_id and (time.monotonic() - _cached_at) < _CACHE_TTL_SECONDS:
        return _cached_note
    return None


def set_cached_note(note_id: str, note: Any) -> None:
    """Cache a note (replaces any previous entry)."""
    global _cached_note, _cached_note_id, _cached_at
    _cached_note = note
    _cached_note_id = note_id
    _cached_at = time.monotonic()


def clear_note_cache() -> None:
    """Drop the cached note. Call after any mutation that may invalidate it."""
    global _cached_note, _cached_note_id, _cached_at
    _cached_note = None
    _cached_note_id = None
    _cached_at = 0.0


# === FORMATTERS ===


def _collect_note_metadata(
    note: Any,
    *,
    include_timestamps: bool = True,
    include_todo: bool = True,
    include_content_stats: bool = True,
    content_stats_body: Optional[str] = None,
    notebooks_map: Optional[Dict[str, Dict[str, Optional[str]]]] = None,
    notebook_path_override: Optional[str] = None,
    timestamp_format: Optional[str] = None,
    default_notebook_id_if_missing: Optional[str] = None,
) -> Dict[str, Any]:
    """Collect note metadata fields with configurable sections."""

    metadata: Dict[str, Any] = {}
    metadata["note_id"] = getattr(note, "id", "unknown")
    metadata["title"] = getattr(note, "title", "Untitled")

    if include_timestamps:
        created_time = getattr(note, "created_time", None)
        if created_time:
            created_date = (
                format_timestamp(created_time, timestamp_format)
                if timestamp_format
                else format_timestamp(created_time)
            )
            if created_date:
                metadata["created"] = created_date

        updated_time = getattr(note, "updated_time", None)
        if updated_time:
            updated_date = (
                format_timestamp(updated_time, timestamp_format)
                if timestamp_format
                else format_timestamp(updated_time)
            )
            if updated_date:
                metadata["updated"] = updated_date

    parent_id = getattr(note, "parent_id", None)
    if parent_id:
        metadata["notebook_id"] = parent_id
        notebook_path = notebook_path_override
        if notebook_path is None:
            map_to_use = notebooks_map
            if map_to_use is None:
                try:
                    map_to_use = notebook_resolver.get_map()
                except Exception:
                    map_to_use = None
            if map_to_use is not None:
                try:
                    notebook_path = _compute_notebook_path(parent_id, map_to_use)
                except Exception:
                    notebook_path = None
        if notebook_path:
            metadata["notebook_path"] = notebook_path
    elif default_notebook_id_if_missing is not None:
        metadata["notebook_id"] = default_notebook_id_if_missing

    # joppy converts deleted_time=0 to None, so truthy check is sufficient
    deleted_time = getattr(note, "deleted_time", None)
    if deleted_time:
        deleted_date = (
            format_timestamp(deleted_time, timestamp_format)
            if timestamp_format
            else format_timestamp(deleted_time)
        )
        if deleted_date:
            metadata["deleted"] = deleted_date

    if include_todo:
        is_todo = bool(getattr(note, "is_todo", 0))
        metadata["is_todo"] = is_todo
        if is_todo:
            todo_completed = bool(getattr(note, "todo_completed", 0))
            metadata["todo_completed"] = todo_completed

    if include_content_stats:
        stats_source = (
            content_stats_body
            if content_stats_body is not None
            else getattr(note, "body", "")
        )
        metadata["content_stats"] = calculate_content_stats(stats_source or "")

    return metadata


def format_note_details(
    note: Any,
    include_body: bool = True,
    context: str = "individual_notes",
    original_body: Optional[str] = None,
) -> str:
    """Format a note for detailed display optimized for LLM comprehension."""
    config = _module_config
    should_show_content = config.should_show_content(context)
    should_show_full_content = config.should_show_full_content(context)

    stats_body = original_body if original_body is not None else getattr(note, "body", "")
    metadata = _collect_note_metadata(
        note,
        include_timestamps=True,
        include_todo=True,
        include_content_stats=True,
        content_stats_body=stats_body,
    )
    result_parts = format_note_metadata_lines(metadata, style="upper")

    if include_body:
        body = getattr(note, "body", "")
        if should_show_content:
            if body:
                if should_show_full_content:
                    result_parts.append(f"CONTENT: {body}")
                else:
                    max_length = config.get_max_preview_length()
                    preview = create_content_preview(body, max_length)
                    result_parts.append(f"CONTENT_PREVIEW: {preview}")
            else:
                result_parts.append("CONTENT: (empty)")
        else:
            if body:
                result_parts.append("CONTENT: (hidden by privacy settings)")
            else:
                result_parts.append("CONTENT: (empty)")

    return "\n".join(result_parts)


def _format_note_entry(
    note: Any,
    index: int,
    config: Any,
    context: str,
    original_query: Optional[str],
    query: str,
    notebooks_map: Optional[Dict[str, Dict[str, Optional[str]]]] = None,
) -> List[str]:
    """Format a single note entry for search results."""
    body = getattr(note, "body", "")

    entry = [f"RESULT_{index}:"]

    metadata = _collect_note_metadata(
        note,
        include_timestamps=True,
        include_todo=True,
        include_content_stats=True,
        content_stats_body=body,
        notebooks_map=notebooks_map,
        timestamp_format="%Y-%m-%d %H:%M",
    )
    entry.extend(
        format_note_metadata_lines(metadata, style="lower", indent="  ")
    )

    should_show_content = config.should_show_content(context)
    if should_show_content and body:
        if config.should_show_full_content(context):
            entry.append(f"  content: {body}")
        else:
            search_query_for_terms = (
                original_query if original_query is not None else query
            )
            preview = create_content_preview_with_search(
                body, config.get_max_preview_length(), search_query_for_terms
            )
            entry.append(f"  content_preview: {preview}")
    elif should_show_content:
        entry.append("  content: (empty)")
    else:
        content_status = "(hidden by privacy settings)" if body else "(empty)"
        entry.append(f"  content: {content_status}")

    entry.append("")
    return entry


def _build_find_in_note_header(
    note: Any,
    pattern: str,
    flags_str: str,
    limit: int,
    offset: int,
    total_count: int,
    showing_count: int,
    *,
    notebook_path_override: Optional[str] = None,
    status: Optional[str] = None,
) -> List[str]:
    """Build the standardized header for find_in_note output."""
    metadata = _collect_note_metadata(
        note,
        include_timestamps=False,
        include_todo=False,
        include_content_stats=False,
        notebook_path_override=notebook_path_override,
        default_notebook_id_if_missing="unknown",
    )

    parts = ["ITEM_TYPE: note_match"]
    parts.extend(format_note_metadata_lines(metadata, style="upper"))

    parts.extend(
        [
            f"PATTERN: {pattern}",
            f"FLAGS: {flags_str}",
            f"TOTAL_MATCHES: {total_count}",
        ]
    )

    if status:
        parts.append(status)

    parts.extend(
        [
            "",
            format_find_in_note_summary(
                limit, offset, total_count, showing_count
            ),
        ]
    )

    return parts


def format_search_results_with_pagination(
    query: str,
    results: List[Any],
    total_count: int,
    limit: int,
    offset: int,
    context: str = "search_results",
    original_query: Optional[str] = None,
    order_by: Optional[str] = None,
    order_dir: Optional[str] = None,
) -> str:
    """Format search results with pagination information for display optimized for LLM comprehension."""
    config = _module_config

    notebooks_map: Optional[Dict[str, Dict[str, Optional[str]]]] = None
    try:
        notebooks_map = notebook_resolver.get_map()
    except Exception:
        notebooks_map = None  # Best-effort only

    result_parts = build_pagination_header(
        query, total_count, limit, offset,
        order_by=order_by, order_dir=order_dir,
    )

    for i, note in enumerate(results, 1):
        result_parts.extend(
            _format_note_entry(
                note, i, config, context, original_query, query, notebooks_map
            )
        )

    result_parts.extend(build_pagination_summary(total_count, limit, offset))

    return "\n".join(result_parts)


# === RENDERING ===


def _create_note_object(note: Any, body_override: str = None) -> Any:
    """Return a shallow copy of ``note`` with an optional body override.

    Used by the rendering helpers to feed a modified note (different body) to
    ``format_note_details`` without mutating the cached original.
    """

    class ModifiedNote:
        def __init__(self, original_note, body_override=None):
            for attr in [
                "id",
                "title",
                "created_time",
                "updated_time",
                "parent_id",
                "is_todo",
                "todo_completed",
            ]:
                setattr(self, attr, getattr(original_note, attr, None))
            self.body = (
                body_override
                if body_override is not None
                else getattr(original_note, "body", "")
            )

    return ModifiedNote(note, body_override)


def _render_section(
    note: Any, section: str, note_id: str, include_body: bool
) -> Optional[str]:
    """Render a single section by heading text, slug, or number."""
    if not (section and include_body):
        return None

    body = getattr(note, "body", "")
    if not body:
        return None

    section_content, section_title = extract_section_content(body, section)
    if section_content:
        modified_note = _create_note_object(note, section_content)
        result = format_note_details(modified_note, include_body, "individual_notes")
        return f"EXTRACTED_SECTION: {section_title}\nSECTION_QUERY: {section}\n{result}"

    # Section not found - show available sections with line numbers so the
    # agent can self-correct without an extra round trip.
    headings = parse_markdown_headings(body)
    section_list = [
        f"{'  ' * (heading['level'] - 1)}{i}. {heading['title']} (line {heading['line_idx']})"
        for i, heading in enumerate(headings, 1)
    ]
    available_sections = (
        "\n".join(section_list) if section_list else "No sections found"
    )

    return f"""SECTION_NOT_FOUND: {section}
NOTE_ID: {note_id}
NOTE_TITLE: {getattr(note, 'title', 'Untitled')}
AVAILABLE_SECTIONS:
{available_sections}
ERROR: Section '{section}' not found in note"""


def _render_toc(
    note: Any, note_id: str, display_mode: str, original_body: str = None
) -> Optional[str]:
    """Render a TOC view with metadata header and navigation hints."""
    toc = create_toc_only(original_body or getattr(note, "body", ""))
    if not toc:
        return None

    toc_note = _create_note_object(note, "")
    metadata_result = format_note_details(
        toc_note,
        include_body=False,
        context="individual_notes",
        original_body=original_body,
    )

    if display_mode == "explicit":
        steps = f"""NEXT_STEPS:
- To get specific section: get_note("{note_id}", section="1") or get_note("{note_id}", section="Introduction")
- To jump to line number: get_note("{note_id}", start_line=45) (using line numbers from TOC above)
- To get full content: get_note("{note_id}", force_full=True)"""
    else:  # smart_toc_auto
        steps = f"""NEXT_STEPS:
- To get specific section: get_note("{note_id}", section="1") or get_note("{note_id}", section="Introduction")
- To jump to line number: get_note("{note_id}", start_line=45) (using line numbers from TOC above)
- To force full content: get_note("{note_id}", force_full=True)"""

    toc_info = f"DISPLAY_MODE: {display_mode}\n\n{toc}\n\n{steps}"
    return f"{metadata_result}\n\n{toc_info}"


def _render_line_range(
    note: Any,
    start_line: int,
    line_count: Optional[int],
    note_id: str,
    include_body: bool,
) -> Optional[str]:
    """Render a contiguous line range for sequential reading."""
    if not include_body:
        return None

    body = getattr(note, "body", "")
    if not body:
        return None

    lines = body.split("\n")
    total_lines = len(lines)

    if start_line < 1 or start_line > total_lines:
        return f"""LINE_EXTRACTION_ERROR: Invalid start_line
NOTE_ID: {note_id}
NOTE_TITLE: {getattr(note, 'title', 'Untitled')}
START_LINE: {start_line}
TOTAL_LINES: {total_lines}
ERROR: start_line must be between 1 and {total_lines}"""

    if line_count is not None:
        if line_count < 1:
            return f"""LINE_EXTRACTION_ERROR: Invalid line_count
NOTE_ID: {note_id}
LINE_COUNT: {line_count}
ERROR: line_count must be >= 1"""
        actual_end_line = min(start_line + line_count - 1, total_lines)
    else:
        actual_end_line = min(start_line + 49, total_lines)

    start_idx = start_line - 1
    end_idx = actual_end_line
    extracted_lines = lines[start_idx:end_idx]
    extracted_content = "\n".join(extracted_lines)

    modified_note = _create_note_object(note, extracted_content)
    result = format_note_details(
        modified_note, include_body, "individual_notes", original_body=body
    )

    lines_extracted = len(extracted_lines)
    next_line = actual_end_line + 1 if actual_end_line < total_lines else None

    extraction_info = f"""EXTRACTED_LINES: {start_line}-{actual_end_line} ({lines_extracted} lines)
TOTAL_LINES: {total_lines}
EXTRACTION_TYPE: sequential_reading"""

    if next_line:
        extraction_info += f'\nNEXT_CHUNK: get_note("{note_id}", start_line={next_line}) for continuation'
    else:
        extraction_info += "\nSTATUS: End of note reached"

    return f"{extraction_info}\n\n{result}"


def _render_smart_toc(note: Any, note_id: str, config: Any) -> Optional[str]:
    """For long notes, fall back to a TOC view; otherwise return None.

    If the note is over ``config.get_smart_toc_threshold()`` chars and has
    headings, return the TOC. If it's long but has no headings, return a
    truncated view with guidance. Otherwise (disabled, empty, or short),
    return None so the caller falls through to the default full render.
    """
    if not config.is_smart_toc_enabled():
        return None

    body = getattr(note, "body", "")
    if not body:
        return None

    body_length = len(body)
    toc_threshold = config.get_smart_toc_threshold()

    if body_length <= toc_threshold:
        return None

    toc_result = _render_toc(note, note_id, "smart_toc_auto", body)
    if toc_result:
        return toc_result

    truncated_content = body[:toc_threshold] + (
        "..." if body_length > toc_threshold else ""
    )
    truncated_note = _create_note_object(note, truncated_content)
    result = format_note_details(
        truncated_note, True, "individual_notes", original_body=body
    )

    truncation_info = f'CONTENT_TRUNCATED: Note is long ({body_length} chars) but has no headings for navigation\nNEXT_STEPS: To force full content: get_note("{note_id}", force_full=True) or start sequential reading: get_note("{note_id}", start_line=1)\n'
    return f"{truncation_info}{result}"


def render_note(
    note: Any,
    *,
    note_id: str,
    section: Optional[str] = None,
    start_line: Optional[int] = None,
    line_count: Optional[int] = None,
    toc_only: bool = False,
    force_full: bool = False,
    include_body: bool = True,
    config: Any,
) -> str:
    """Return the formatted view of ``note`` for the requested display mode.

    Dispatches across the five modes in precedence order: line range,
    section extraction, explicit TOC, smart TOC (auto for long notes),
    and default full render. Each mode returns None if not applicable so
    the next mode gets a chance; the default render always returns a string.
    """
    if start_line is not None:
        line_result = _render_line_range(
            note, start_line, line_count, note_id, include_body
        )
        if line_result is not None:
            return line_result

    section_result = _render_section(note, section, note_id, include_body)
    if section_result is not None:
        return section_result

    if toc_only and include_body:
        body = getattr(note, "body", "")
        if body:
            toc_result = _render_toc(note, note_id, "toc_only", body)
            if toc_result is not None:
                return toc_result

    if include_body and not force_full:
        smart_toc_result = _render_smart_toc(note, note_id, config)
        if smart_toc_result is not None:
            return smart_toc_result

    return format_note_details(note, include_body, "individual_notes")
