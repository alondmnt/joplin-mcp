"""Note tools for Joplin MCP."""
import time
from typing import Annotated, Any, Dict, List, Optional, Union

from pydantic import Field


# === NOTE CACHE FOR SEQUENTIAL READING ===
# Caches one note to avoid re-fetching when reading in chunks.

_cached_note: Any = None
_cached_note_id: Optional[str] = None
_cached_at: float = 0.0


def _get_cached_note(note_id: str) -> Any:
    """Return cached note if it matches and is fresh (30s), else None."""
    if _cached_note_id == note_id and (time.monotonic() - _cached_at) < 30:
        return _cached_note
    return None


def _set_cached_note(note_id: str, note: Any) -> None:
    """Cache a note (replaces any previous)."""
    global _cached_note, _cached_note_id, _cached_at
    _cached_note = note
    _cached_note_id = note_id
    _cached_at = time.monotonic()


def _clear_note_cache() -> None:
    """Clear the note cache."""
    global _cached_note, _cached_note_id, _cached_at
    _cached_note = None
    _cached_note_id = None
    _cached_at = 0.0

from joplin_mcp.content_utils import (
    create_content_preview,
    create_toc_only,
    extract_section_content,
    parse_markdown_headings,
)
from joplin_mcp.fastmcp_server import (
    COMMON_NOTE_FIELDS,
    ItemType,
    JoplinIdType,
    LimitType,
    OffsetType,
    OptionalBoolType,
    RequiredStringType,
    _compute_notebook_path,
    _module_config,
    apply_pagination,
    build_pagination_summary,
    build_search_filters,
    create_tool,
    flexible_bool_converter,
    format_creation_success,
    format_delete_success,
    format_no_results_message,
    format_note_details,
    format_search_criteria,
    format_search_results_with_pagination,
    format_update_success,
    get_joplin_client,
    get_notebook_id_by_name,
    get_notebook_map_cached,
    optional_int_converter,
    process_search_results,
    timestamp_converter,
    validate_joplin_id,
)
from joplin_mcp.formatting import (
    build_pagination_header,
    format_find_in_note_summary,
    format_note_metadata_lines,
)


# === NOTE HELPER FUNCTIONS ===


def _create_note_object(note: Any, body_override: str = None) -> Any:
    """Create a note object with optional body override."""

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


def _handle_section_extraction(
    note: Any, section: str, note_id: str, include_body: bool
) -> Optional[str]:
    """Handle section extraction logic, returning formatted result or None if no section handling needed."""
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

    # Section not found - show available sections with line numbers
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


def _handle_toc_display(
    note: Any, note_id: str, display_mode: str, original_body: str = None
) -> str:
    """Handle TOC display with metadata and navigation info."""
    toc = create_toc_only(original_body or getattr(note, "body", ""))
    if not toc:
        return None

    # Create note with empty body for metadata-only display
    toc_note = _create_note_object(note, "")
    metadata_result = format_note_details(
        toc_note,
        include_body=False,
        context="individual_notes",
        original_body=original_body,
    )

    # Build navigation steps based on display mode
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


def _handle_line_extraction(
    note: Any,
    start_line: int,
    line_count: Optional[int],
    note_id: str,
    include_body: bool,
) -> Optional[str]:
    """Handle line-based extraction for sequential reading."""
    if not include_body:
        return None

    body = getattr(note, "body", "")
    if not body:
        return None

    lines = body.split("\n")
    total_lines = len(lines)

    # Validate start_line (1-based)
    if start_line < 1 or start_line > total_lines:
        return f"""LINE_EXTRACTION_ERROR: Invalid start_line
NOTE_ID: {note_id}
NOTE_TITLE: {getattr(note, 'title', 'Untitled')}
START_LINE: {start_line}
TOTAL_LINES: {total_lines}
ERROR: start_line must be between 1 and {total_lines}"""

    # Determine end line
    if line_count is not None:
        if line_count < 1:
            return f"""LINE_EXTRACTION_ERROR: Invalid line_count
NOTE_ID: {note_id}
LINE_COUNT: {line_count}
ERROR: line_count must be >= 1"""
        actual_end_line = min(start_line + line_count - 1, total_lines)
    else:
        # Default to 50 lines if line_count not specified
        actual_end_line = min(start_line + 49, total_lines)

    # Extract lines (convert to 0-based indexing)
    start_idx = start_line - 1
    end_idx = actual_end_line  # end_line is inclusive, so we don't subtract 1
    extracted_lines = lines[start_idx:end_idx]
    extracted_content = "\n".join(extracted_lines)

    # Create modified note with extracted content
    modified_note = _create_note_object(note, extracted_content)
    result = format_note_details(
        modified_note, include_body, "individual_notes", original_body=body
    )

    # Add extraction metadata
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


def _handle_smart_toc_behavior(note: Any, note_id: str, config: Any) -> Optional[str]:
    """Handle smart TOC behavior for long notes."""
    if not config.is_smart_toc_enabled():
        return None

    body = getattr(note, "body", "")
    if not body:
        return None

    body_length = len(body)
    toc_threshold = config.get_smart_toc_threshold()

    if body_length <= toc_threshold:
        return None  # Not long enough for smart TOC

    # Try TOC first
    toc_result = _handle_toc_display(note, note_id, "smart_toc_auto", body)
    if toc_result:
        return toc_result

    # No headings found - show truncated content with warning
    truncated_content = body[:toc_threshold] + (
        "..." if body_length > toc_threshold else ""
    )
    truncated_note = _create_note_object(note, truncated_content)
    result = format_note_details(
        truncated_note, True, "individual_notes", original_body=body
    )

    truncation_info = f'CONTENT_TRUNCATED: Note is long ({body_length} chars) but has no headings for navigation\nNEXT_STEPS: To force full content: get_note("{note_id}", force_full=True) or start sequential reading: get_note("{note_id}", start_line=1)\n'
    return f"{truncation_info}{result}"


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
    from joplin_mcp.fastmcp_server import _collect_note_metadata

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


def format_no_results_with_pagination(
    item_type: str, criteria: str, offset: int, limit: int
) -> str:
    """Format no results message with pagination info."""
    if offset > 0:
        page_info = f" - Page {(offset // limit) + 1} (offset {offset})"
        return format_no_results_message(item_type, criteria + page_info)
    else:
        return format_no_results_message(item_type, criteria)


# === NOTE TOOLS ===


@create_tool("get_note", "Get note")
async def get_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to retrieve")],
    section: Annotated[
        Optional[str],
        Field(description="Extract specific section (heading text, slug, or number)"),
    ] = None,
    start_line: Annotated[
        Optional[Union[int, str]],
        Field(description="Start line for sequential reading (1-based)"),
    ] = None,
    line_count: Annotated[
        Optional[Union[int, str]],
        Field(description="Number of lines to extract from start_line (default: 50)"),
    ] = None,
    toc_only: Annotated[
        OptionalBoolType,
        Field(description="Show only table of contents (default: False)"),
    ] = False,
    force_full: Annotated[
        OptionalBoolType,
        Field(description="Force full content even for long notes (default: False)"),
    ] = False,
    metadata_only: Annotated[
        OptionalBoolType,
        Field(description="Show only metadata without content (default: False)"),
    ] = False,
) -> str:
    """Retrieve a note with smart content display and sequential reading support.

    Smart behavior: Short notes show full content, long notes show TOC only.
    Sequential reading: Extract specific line ranges for progressive consumption.

    Args:
        note_id: Note identifier
        section: Extract specific section (heading text, slug, or number)
        start_line: Start line for sequential reading (1-based, line numbers)
        line_count: Number of lines to extract (default: 50 if start_line specified)
        toc_only: Show only TOC and metadata
        force_full: Force full content even for long notes
        metadata_only: Show only metadata without content

    Examples:
        get_note("id") - Smart display (full if short, TOC if long)
        get_note("id", section="1") - Get first section
        get_note("id", start_line=1) - Start sequential reading from line 1 (50 lines)
        get_note("id", start_line=51, line_count=30) - Continue reading from line 51 (30 lines)
        get_note("id", toc_only=True) - TOC only
        get_note("id", force_full=True) - Force full content
    """

    # Runtime validation for Jan AI compatibility while preserving functionality
    note_id = validate_joplin_id(note_id)
    toc_only = flexible_bool_converter(toc_only)
    force_full = flexible_bool_converter(force_full)
    metadata_only = flexible_bool_converter(metadata_only)

    start_line = optional_int_converter(start_line, "start_line")
    line_count = optional_int_converter(line_count, "line_count")

    include_body = not metadata_only

    # Validate line extraction parameters
    if start_line is not None:
        if start_line < 1:
            raise ValueError("start_line must be >= 1 (line numbers are 1-based)")
        if line_count is not None and line_count < 1:
            raise ValueError("line_count must be >= 1")

    # If start_line is provided but we're extracting sections, that's an error
    if start_line is not None and section is not None:
        raise ValueError(
            "Cannot specify both start_line and section - use one extraction method"
        )

    client = get_joplin_client()

    # For sequential reading, use cache to avoid re-fetching
    if start_line is not None and include_body:
        note = _get_cached_note(note_id)
        if note is None:
            note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
            _set_cached_note(note_id, note)
    else:
        note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)

    # Handle line extraction first (for sequential reading)
    if start_line is not None:
        line_result = _handle_line_extraction(
            note, start_line, line_count, note_id, include_body
        )
        if line_result:
            return line_result

    # Handle section extraction second
    section_result = _handle_section_extraction(note, section, note_id, include_body)
    if section_result:
        return section_result

    # Handle explicit TOC-only mode
    if toc_only and include_body:
        body = getattr(note, "body", "")
        if body:
            toc_result = _handle_toc_display(note, note_id, "toc_only", body)
            if toc_result:
                return toc_result

    # Handle smart TOC behavior (only if not forcing full content)
    if include_body and not force_full:
        smart_toc_result = _handle_smart_toc_behavior(note, note_id, _module_config)
        if smart_toc_result:
            return smart_toc_result

    # Default: return full note details
    return format_note_details(note, include_body, "individual_notes")


@create_tool("get_links", "Get links")
async def get_links(
    note_id: Annotated[
        JoplinIdType, Field(description="Note ID to extract links from")
    ],
) -> str:
    """Extract all links to other notes from a given note and find backlinks from other notes.

    Scans the note's content for links in the format [text](:/noteId) or [text](:/noteId#section-slug)
    and searches for backlinks (other notes that link to this note). Returns link text, target/source
    note info, section slugs (if present), and line context.

    Returns:
        str: Formatted list of outgoing links and backlinks with titles, IDs, section slugs, and line context.

    Link formats:
    - [link text](:/targetNoteId) - Link to note
    - [link text](:/targetNoteId#section-slug) - Link to specific section in note
    """
    import re

    # Runtime validation for Jan AI compatibility while preserving functionality
    note_id = validate_joplin_id(note_id)

    client = get_joplin_client()

    # Get the note
    note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)

    note_title = getattr(note, "title", "Untitled")
    body = getattr(note, "body", "")

    # Parse outgoing links using regex (with optional section slugs)
    link_pattern = r"\[([^\]]+)\]\(:/([a-zA-Z0-9]+)(?:#([^)]+))?\)"

    outgoing_links = []
    if body:
        lines = body.split("\n")
        for line_num, line in enumerate(lines, 1):
            matches = re.finditer(link_pattern, line)
            for match in matches:
                link_text = match.group(1)
                target_note_id = match.group(2)
                section_slug = match.group(3) if match.group(3) else None

                # Try to get the target note title
                try:
                    target_note = client.get_note(target_note_id, fields="id,title")
                    target_title = getattr(target_note, "title", "Unknown Note")
                    target_exists = True
                except Exception:
                    target_title = "Note not found"
                    target_exists = False

                link_data = {
                    "text": link_text,
                    "target_id": target_note_id,
                    "target_title": target_title,
                    "target_exists": target_exists,
                    "line_number": line_num,
                    "line_context": line.strip(),
                }

                # Add section slug if present
                if section_slug:
                    link_data["section_slug"] = section_slug

                outgoing_links.append(link_data)

    # Search for backlinks - notes that link to this note
    backlinks = []
    try:
        import logging
        logger = logging.getLogger(__name__)

        # Search for notes containing this note's ID in link format
        search_query = f":/{note_id}"
        backlink_results = client.search_all(
            query=search_query, fields=COMMON_NOTE_FIELDS
        )
        backlink_notes = process_search_results(backlink_results)

        # Filter out the current note and parse backlinks
        for source_note in backlink_notes:
            source_note_id = getattr(source_note, "id", "")
            source_note_title = getattr(source_note, "title", "Untitled")
            source_body = getattr(source_note, "body", "")

            # Skip if it's the same note
            if source_note_id == note_id:
                continue

            # Parse links in the source note that point to our note
            if source_body:
                lines = source_body.split("\n")
                for line_num, line in enumerate(lines, 1):
                    matches = re.finditer(link_pattern, line)
                    for match in matches:
                        link_text = match.group(1)
                        target_note_id_match = match.group(2)
                        section_slug = match.group(3) if match.group(3) else None

                        # Only include if this link points to our note
                        if target_note_id_match == note_id:
                            backlink_data = {
                                "text": link_text,
                                "source_id": source_note_id,
                                "source_title": source_note_title,
                                "line_number": line_num,
                                "line_context": line.strip(),
                            }

                            # Add section slug if present
                            if section_slug:
                                backlink_data["section_slug"] = section_slug

                            backlinks.append(backlink_data)
    except Exception as e:
        # If backlink search fails, continue without backlinks
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to search for backlinks: {e}")

    # Format output optimized for LLM comprehension
    result_parts = [
        f"SOURCE_NOTE: {note_title}",
        f"NOTE_ID: {note_id}",
        f"TOTAL_OUTGOING_LINKS: {len(outgoing_links)}",
        f"TOTAL_BACKLINKS: {len(backlinks)}",
        "",
    ]

    # Add outgoing links section
    if outgoing_links:
        result_parts.append("OUTGOING_LINKS:")
        for i, link in enumerate(outgoing_links, 1):
            status = "VALID" if link["target_exists"] else "BROKEN"
            link_details = [
                f"  LINK_{i}:",
                f"    link_text: {link['text']}",
                f"    target_note_id: {link['target_id']}",
                f"    target_note_title: {link['target_title']}",
                f"    link_status: {status}",
            ]

            # Add section slug if present
            if "section_slug" in link:
                link_details.append(f"    section_slug: {link['section_slug']}")

            link_details.extend(
                [
                    f"    line_number: {link['line_number']}",
                    f"    line_context: {link['line_context']}",
                    "",
                ]
            )

            result_parts.extend(link_details)
    else:
        result_parts.extend(["OUTGOING_LINKS: None", ""])

    # Add backlinks section
    if backlinks:
        result_parts.append("BACKLINKS:")
        for i, backlink in enumerate(backlinks, 1):
            backlink_details = [
                f"  BACKLINK_{i}:",
                f"    link_text: {backlink['text']}",
                f"    source_note_id: {backlink['source_id']}",
                f"    source_note_title: {backlink['source_title']}",
            ]

            # Add section slug if present
            if "section_slug" in backlink:
                backlink_details.append(f"    section_slug: {backlink['section_slug']}")

            backlink_details.extend(
                [
                    f"    line_number: {backlink['line_number']}",
                    f"    line_context: {backlink['line_context']}",
                    "",
                ]
            )

            result_parts.extend(backlink_details)
    else:
        result_parts.extend(["BACKLINKS: None", ""])

    # Add status message
    if not outgoing_links and not backlinks:
        if not body:
            result_parts.append(
                "STATUS: No content found in this note and no backlinks found"
            )
        else:
            result_parts.append(
                "STATUS: No note links found in this note and no backlinks found"
            )
    else:
        result_parts.append("STATUS: Links and backlinks retrieved successfully")

    return "\n".join(result_parts)


@create_tool("create_note", "Create note")
async def create_note(
    title: Annotated[RequiredStringType, Field(description="Note title")],
    notebook_name: Annotated[
        RequiredStringType,
        Field(description="Notebook name or path (e.g., 'Work' or 'Projects/Work/Tasks')")
    ],
    body: Annotated[str, Field(description="Note content")] = "",
    is_todo: Annotated[
        OptionalBoolType, Field(description="Create as todo (default: False)")
    ] = False,
    todo_completed: Annotated[
        OptionalBoolType, Field(description="Mark todo as completed (default: False)")
    ] = False,
    todo_due: Annotated[
        Optional[Union[int, str]],
        Field(description="Due date: Unix timestamp (ms) or ISO 8601 string (e.g., '2024-12-31T17:00:00'). Only for todos.")
    ] = None,
) -> str:
    """Create a new note in a specified notebook in Joplin.

    Creates a new note with the specified title, content, and properties. Uses notebook name
    for easier identification instead of requiring notebook IDs.

    Notebook can be specified by name or path:
    - "Work" - matches notebook named "Work" (must be unique)
    - "Projects/Work" - matches "Work" notebook inside "Projects"

    Returns:
        str: Success message with the created note's title and unique ID.

    Examples:
        - create_note("Shopping List", "Personal Notes", "- Milk\n- Eggs", True, False) - Create uncompleted todo
        - create_note("Meeting Notes", "Work Projects", "# Meeting with Client") - Create regular note
        - create_note("Task", "Work", "", True, False, "2024-12-31T17:00:00") - Create todo with due date
        - create_note("Task", "Project A/tasks", "body") - Create note in "tasks" sub-notebook under "Project A"
    """

    # Runtime validation for Jan AI compatibility while preserving functionality
    is_todo = flexible_bool_converter(is_todo)
    todo_completed = flexible_bool_converter(todo_completed)
    todo_due_ms = timestamp_converter(todo_due, "todo_due")

    # Use helper function to get notebook ID
    parent_id = get_notebook_id_by_name(notebook_name)

    client = get_joplin_client()
    note_kwargs = {
        "title": title,
        "body": body,
        "parent_id": parent_id,
        "is_todo": 1 if is_todo else 0,
        "todo_completed": 1 if todo_completed else 0,
    }
    if todo_due_ms is not None:
        note_kwargs["todo_due"] = todo_due_ms

    note = client.add_note(**note_kwargs)
    return format_creation_success(ItemType.note, title, str(note))


@create_tool("update_note", "Update note")
async def update_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to update")],
    title: Annotated[Optional[str], Field(description="New title (optional)")] = None,
    body: Annotated[Optional[str], Field(description="New content (optional)")] = None,
    is_todo: Annotated[
        OptionalBoolType, Field(description="Convert to/from todo (optional)")
    ] = None,
    todo_completed: Annotated[
        OptionalBoolType, Field(description="Mark todo completed (optional)")
    ] = None,
    todo_due: Annotated[
        Optional[Union[int, str]],
        Field(description="Due date: Unix timestamp (ms), ISO 8601 string, or 0 to clear. Only for todos.")
    ] = None,
) -> str:
    """Update an existing note in Joplin.

    Updates one or more properties of an existing note. At least one field must be provided.

    Returns:
        str: Success message confirming the note was updated.

    Examples:
        - update_note("note123", title="New Title") - Update only the title
        - update_note("note123", body="New content", is_todo=True) - Update content and convert to todo
        - update_note("note123", todo_due="2024-12-31T17:00:00") - Set due date
        - update_note("note123", todo_due=0) - Clear due date
    """

    # Runtime validation for Jan AI compatibility while preserving functionality
    note_id = validate_joplin_id(note_id)
    is_todo = flexible_bool_converter(is_todo)
    todo_completed = flexible_bool_converter(todo_completed)

    update_data = {}
    if title is not None:
        update_data["title"] = title
    if body is not None:
        update_data["body"] = body
    if is_todo is not None:
        update_data["is_todo"] = 1 if is_todo else 0
    if todo_completed is not None:
        update_data["todo_completed"] = 1 if todo_completed else 0
    if todo_due is not None:
        update_data["todo_due"] = timestamp_converter(todo_due, "todo_due") or 0

    if not update_data:
        raise ValueError("At least one field must be provided for update")

    client = get_joplin_client()
    client.modify_note(note_id, **update_data)
    _clear_note_cache()

    return format_update_success(ItemType.note, note_id)


@create_tool("edit_note", "Edit note")
async def edit_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to edit")],
    new_string: Annotated[str, Field(description="Replacement text (use '' to delete)")],
    old_string: Annotated[
        Optional[str],
        Field(description="Text to find and replace (None for positional insert)"),
    ] = None,
    replace_all: Annotated[
        OptionalBoolType,
        Field(description="Replace all occurrences (default: False)"),
    ] = False,
    position: Annotated[
        Optional[str],
        Field(description="Insert position: 'beginning' or 'end' (only when old_string is None)"),
    ] = None,
) -> str:
    """Edit a note's content with precision string replacement or positional insertion.

    Modes:
    - Replace: provide old_string and new_string to replace text in the note body.
    - Delete: provide old_string and set new_string to '' to remove text.
    - Append: set position='end' (old_string must be None) to append new_string.
    - Prepend: set position='beginning' (old_string must be None) to prepend new_string.

    Args:
        note_id: Note identifier
        new_string: Replacement or insertion text (use '' to delete matches)
        old_string: Text to find (None for positional insert)
        replace_all: Replace all occurrences when True (default: first unique match)
        position: 'beginning' or 'end' (only when old_string is None)

    Examples:
        edit_note("id", new_string="colour", old_string="color") - Replace unique match
        edit_note("id", new_string="colour", old_string="color", replace_all=True) - Replace all
        edit_note("id", new_string="", old_string="delete me") - Delete text
        edit_note("id", new_string="appended text", position="end") - Append
        edit_note("id", new_string="prepended text", position="beginning") - Prepend
    """
    note_id = validate_joplin_id(note_id)
    replace_all = flexible_bool_converter(replace_all) or False

    # Validate mutually exclusive parameters
    if old_string is not None and position is not None:
        raise ValueError(
            "Cannot specify both old_string and position. "
            "Use old_string for replacement, or position for insertion."
        )

    if old_string is None and position is None:
        raise ValueError(
            "Must specify either old_string (for replacement/deletion) "
            "or position (for insertion at 'beginning' or 'end')."
        )

    if old_string is not None and old_string == new_string:
        raise ValueError(
            "old_string and new_string are identical — no change would be made."
        )

    if position is not None and position not in ("beginning", "end"):
        raise ValueError(
            f"position must be 'beginning' or 'end', got '{position}'."
        )

    client = get_joplin_client()
    note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
    body = getattr(note, "body", "") or ""

    if old_string is not None:
        # Replacement / deletion mode
        count = body.count(old_string)

        if count == 0:
            # Show a snippet of the body for context
            preview = body[:200] + ("..." if len(body) > 200 else "")
            raise ValueError(
                f"old_string not found in note body. "
                f"Note content preview: {preview}"
            )

        if count > 1 and not replace_all:
            raise ValueError(
                f"old_string matches {count} times in note body. "
                f"Use replace_all=True to replace all occurrences, "
                f"or provide more context in old_string to make it unique."
            )

        if replace_all:
            new_body = body.replace(old_string, new_string)
            replacements = count
        else:
            new_body = body.replace(old_string, new_string, 1)
            replacements = 1

        client.modify_note(note_id, body=new_body)
        _clear_note_cache()

        if new_string == "":
            return f"EDIT_NOTE: Deleted {replacements} occurrence(s) of the specified text."
        return f"EDIT_NOTE: Replaced {replacements} occurrence(s)."

    else:
        # Positional insertion mode
        if position == "end":
            new_body = body + new_string
            action = "Appended"
        else:
            new_body = new_string + body
            action = "Prepended"

        client.modify_note(note_id, body=new_body)
        _clear_note_cache()

        return f"EDIT_NOTE: {action} {len(new_string)} characters."


@create_tool("delete_note", "Delete note")
async def delete_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to delete")],
) -> str:
    """Delete a note from Joplin.

    Permanently removes a note from Joplin. This action cannot be undone.

    Returns:
        str: Success message confirming the note was deleted.

    Warning: This action is permanent and cannot be undone.
    """
    # Runtime validation for Jan AI compatibility while preserving functionality
    note_id = validate_joplin_id(note_id)

    client = get_joplin_client()
    client.delete_note(note_id)

    # Invalidate cache for deleted note
    _clear_note_cache()

    return format_delete_success(ItemType.note, note_id)


@create_tool("find_notes", "Find notes")
async def find_notes(
    query: Annotated[str, Field(description="Search text or '*' for all notes")],
    limit: Annotated[
        LimitType, Field(description="Max results (1-100, default: 20)")
    ] = 20,
    offset: Annotated[
        OffsetType, Field(description="Skip count for pagination (default: 0)")
    ] = 0,
    task: Annotated[
        OptionalBoolType, Field(description="Filter by task type (default: None)")
    ] = None,
    completed: Annotated[
        OptionalBoolType,
        Field(description="Filter by completion status (default: None)"),
    ] = None,
) -> str:
    """Find notes by searching titles and content. Use "*" to list all notes.

    Query syntax: "exact phrase", title:word, body:word, -exclude, word1 OR word2

    Examples:
        - find_notes("*") - List all notes
        - find_notes("meeting") - Find notes containing "meeting"
        - find_notes("*", task=True) - List all tasks
        - find_notes("*", limit=20, offset=20) - Page 2

    TIP: Use find_notes_with_tag() or find_notes_in_notebook() for filtered searches.
    """

    # Runtime validation for Jan AI compatibility while preserving functionality
    task = flexible_bool_converter(task)
    completed = flexible_bool_converter(completed)

    client = get_joplin_client()

    # Handle special case for listing all notes
    if query.strip() == "*":
        # List all notes with filters
        search_filters = build_search_filters(task, completed)

        if search_filters:
            # Use search with filters
            search_query = " ".join(search_filters)
            results = client.search_all(query=search_query, fields=COMMON_NOTE_FIELDS)
            notes = process_search_results(results)
        else:
            # No filters, get all notes
            results = client.get_all_notes(fields=COMMON_NOTE_FIELDS)
            notes = process_search_results(results)
            # Sort by updated time, newest first (consistent with get_all_notes)
            notes = sorted(
                notes, key=lambda x: getattr(x, "updated_time", 0), reverse=True
            )
    else:
        # Build search query with text and filters
        search_parts = [query]
        search_parts.extend(build_search_filters(task, completed))

        search_query = " ".join(search_parts)

        # Use search_all for full pagination support
        results = client.search_all(query=search_query, fields=COMMON_NOTE_FIELDS)
        notes = process_search_results(results)

    # Apply pagination
    paginated_notes, total_count = apply_pagination(notes, limit, offset)

    if not paginated_notes:
        # Create descriptive message based on search criteria
        if query.strip() == "*":
            base_criteria = "(all notes)"
        else:
            base_criteria = f'containing "{query}"'

        criteria_str = format_search_criteria(base_criteria, task, completed)
        return format_no_results_with_pagination("note", criteria_str, offset, limit)

    # Format results with pagination info
    if query.strip() == "*":
        search_description = "all notes"
    else:
        search_description = f"text search: {query}"

    return format_search_results_with_pagination(
        search_description,
        paginated_notes,
        total_count,
        limit,
        offset,
        "search_results",
        original_query=query,
    )


@create_tool("find_in_note", "Find in note")
async def find_in_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to search within")],
    pattern: Annotated[
        RequiredStringType, Field(description="Regular expression to search for")
    ],
    limit: Annotated[
        LimitType, Field(description="Max matches per page (1-100, default: 20)")
    ] = 20,
    offset: Annotated[
        OffsetType, Field(description="Skip count for pagination (default: 0)")
    ] = 0,
    case_sensitive: Annotated[
        OptionalBoolType,
        Field(description="Use case-sensitive matching (default: False)"),
    ] = False,
    multiline: Annotated[
        OptionalBoolType,
        Field(description="Enable multiline flag (affects ^ and $, default: True)")
    ] = True,
    dotall: Annotated[
        OptionalBoolType,
        Field(description="Dot matches newlines (re.DOTALL, default: False)"),
    ] = False,
) -> str:
    """Search for a regex pattern inside a specific note and return paginated matches.

    Multiline mode is enabled by default so anchors like ``^``/``$`` operate per line,
    matching the common expectations for checklist-style searches.
    """

    import re
    from bisect import bisect_right

    note_id = validate_joplin_id(note_id)
    case_sensitive = flexible_bool_converter(case_sensitive)
    multiline = flexible_bool_converter(multiline)
    dotall = flexible_bool_converter(dotall)

    # Apply defaults if values were provided as None
    case_sensitive = bool(case_sensitive) if case_sensitive is not None else False
    multiline = bool(multiline) if multiline is not None else False
    dotall = bool(dotall) if dotall is not None else False

    flags = 0
    applied_flags = []

    if not case_sensitive:
        flags |= re.IGNORECASE
        applied_flags.append("IGNORECASE")
    if multiline:
        flags |= re.MULTILINE
        applied_flags.append("MULTILINE")
    if dotall:
        flags |= re.DOTALL
        applied_flags.append("DOTALL")

    try:
        pattern_obj = re.compile(pattern, flags)
    except re.error as exc:
        raise ValueError(f"Invalid regular expression: {exc}")

    client = get_joplin_client()
    note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)

    body = getattr(note, "body", "") or ""

    flags_str = ", ".join(applied_flags) if applied_flags else "none"

    parent_id = getattr(note, "parent_id", None)
    notebook_path: Optional[str] = None
    if parent_id:
        try:
            nb_map = get_notebook_map_cached()
            notebook_path = _compute_notebook_path(parent_id, nb_map)
        except Exception:
            notebook_path = None

    if not body:
        header_parts = _build_find_in_note_header(
            note,
            pattern,
            flags_str,
            limit,
            offset,
            0,
            0,
            notebook_path_override=notebook_path,
            status="STATUS: Note has no content to search",
        )
        header_parts.extend(build_pagination_summary(0, limit, offset))
        return "\n".join(header_parts)

    # Split once to derive both offsets and display lines
    lines_with_endings = body.splitlines(True)
    if not lines_with_endings:
        lines_with_endings = [body]
    display_lines = [line.rstrip("\r\n") for line in lines_with_endings]

    line_offsets: List[int] = []
    cursor = 0
    for chunk in lines_with_endings:
        line_offsets.append(cursor)
        cursor += len(chunk)

    def _pos_to_line_col(pos: int) -> tuple:
        idx = bisect_right(line_offsets, pos) - 1
        if idx < 0:
            idx = 0
        line_start = line_offsets[idx]
        column = (pos - line_start) + 1
        return idx, column

    def _build_context(start_pos: int, end_pos: int) -> tuple:
        # Return highlighted multi-line snippet preserving newlines
        inclusive_end = end_pos - 1 if end_pos > start_pos else end_pos

        start_line_idx, _ = _pos_to_line_col(start_pos)
        end_line_idx, _ = _pos_to_line_col(inclusive_end)

        snippet_parts: List[str] = []
        first_display_line_idx: Optional[int] = None
        for idx in range(start_line_idx, end_line_idx + 1):
            line_text = display_lines[idx]
            line_start = line_offsets[idx]
            line_end = line_start + len(lines_with_endings[idx])

            highlight_start = max(start_pos, line_start)
            highlight_end = min(end_pos, line_end)

            if start_pos == end_pos:
                local_idx = max(0, min(len(line_text), start_pos - line_start))
                highlighted = (
                    f"{line_text[:local_idx]}<<>>{line_text[local_idx:]}"
                )
            elif highlight_start < highlight_end:
                local_start = highlight_start - line_start
                local_end = highlight_end - line_start
                highlighted = (
                    f"{line_text[:local_start]}<<{line_text[local_start:local_end]}>>"
                    f"{line_text[local_end:]}"
                )
            else:
                highlighted = line_text

            if highlighted.replace("<<", "").replace(">>", "").strip():
                if first_display_line_idx is None:
                    first_display_line_idx = idx
                snippet_parts.append(highlighted)

        if not snippet_parts:
            snippet_parts.append("")
            first_display_line_idx = start_line_idx

        return "\n".join(snippet_parts), first_display_line_idx or start_line_idx

    matches = list(pattern_obj.finditer(body))
    total_matches = len(matches)

    if total_matches == 0:
        result_parts = _build_find_in_note_header(
            note,
            pattern,
            flags_str,
            limit,
            offset,
            0,
            0,
            notebook_path_override=notebook_path,
            status="STATUS: No matches found",
        )
        result_parts.extend(build_pagination_summary(0, limit, offset))
        return "\n".join(result_parts)

    match_entries: List[Dict[str, Any]] = []

    for index, match in enumerate(matches, 1):
        start_pos = match.start()
        end_pos = match.end()

        start_line_idx, start_col = _pos_to_line_col(start_pos)
        snippet, first_display_idx = _build_context(start_pos, end_pos)

        match_entries.append(
            {
                "global_index": index,
                "start_line": (first_display_idx or start_line_idx) + 1,
                "snippet": snippet,
            }
        )

    paginated_matches, total_count = apply_pagination(match_entries, limit, offset)

    result_parts = _build_find_in_note_header(
        note,
        pattern,
        flags_str,
        limit,
        offset,
        total_count,
        len(paginated_matches),
        notebook_path_override=notebook_path,
    )

    if not paginated_matches:
        result_parts.append(
            f"STATUS: No matches available for offset {offset} with limit {limit}"
        )
        result_parts.extend(build_pagination_summary(total_count, limit, offset))
        return "\n".join(result_parts)

    for page_index, match_info in enumerate(paginated_matches, start=1):
        start_line_label = f"L{match_info['start_line']}:"
        snippet = match_info["snippet"]
        if "\n" in snippet:
            indented_snippet = "\n".join(f"  {line}" for line in snippet.split("\n"))
            result_parts.append(f"{start_line_label}\n{indented_snippet}")
        else:
            result_parts.append(f"{start_line_label} {snippet}")

        result_parts.append("")

    result_parts.extend(build_pagination_summary(total_count, limit, offset))

    return "\n".join(result_parts)


@create_tool("find_notes_with_tag", "Find notes with tag")
async def find_notes_with_tag(
    tag_name: Annotated[
        RequiredStringType, Field(description="Tag name to search for")
    ],
    limit: Annotated[
        LimitType, Field(description="Max results (1-100, default: 20)")
    ] = 20,
    offset: Annotated[
        OffsetType, Field(description="Skip count for pagination (default: 0)")
    ] = 0,
    task: Annotated[
        OptionalBoolType, Field(description="Filter by task type (default: None)")
    ] = None,
    completed: Annotated[
        OptionalBoolType,
        Field(description="Filter by completion status (default: None)"),
    ] = None,
) -> str:
    """Find all notes that have a specific tag, with pagination support.

    MAIN FUNCTION FOR TAG SEARCHES!

    Use this when you want to find all notes tagged with a specific tag name.

    Returns:
        str: List of all notes with the specified tag, with pagination information.

    Examples:
        - find_notes_with_tag("time-slip") - Find all notes tagged with "time-slip"
        - find_notes_with_tag("work", limit=10, offset=10) - Find notes tagged with "work" (page 2)
        - find_notes_with_tag("work", task=True) - Find only tasks tagged with "work"
        - find_notes_with_tag("important", task=True, completed=False) - Find only uncompleted tasks tagged with "important"
    """

    # Build search query with tag and filters
    search_parts = [f'tag:"{tag_name}"']
    search_parts.extend(build_search_filters(task, completed))
    search_query = " ".join(search_parts)

    # Use search_all API with tag constraint for full pagination support
    client = get_joplin_client()
    results = client.search_all(query=search_query, fields=COMMON_NOTE_FIELDS)
    notes = process_search_results(results)

    # Apply pagination
    paginated_notes, total_count = apply_pagination(notes, limit, offset)

    if not paginated_notes:
        base_criteria = f'with tag "{tag_name}"'
        criteria_str = format_search_criteria(base_criteria, task, completed)
        return format_no_results_with_pagination("note", criteria_str, offset, limit)

    return format_search_results_with_pagination(
        f"tag search: {search_query}",
        paginated_notes,
        total_count,
        limit,
        offset,
        "search_results",
        original_query=tag_name,
    )


@create_tool("find_notes_in_notebook", "Find notes in notebook")
async def find_notes_in_notebook(
    notebook_name: Annotated[
        RequiredStringType,
        Field(description="Notebook name or path (e.g., 'Work' or 'Projects/Work/Tasks')")
    ],
    limit: Annotated[
        LimitType, Field(description="Max results (1-100, default: 20)")
    ] = 20,
    offset: Annotated[
        OffsetType, Field(description="Skip count for pagination (default: 0)")
    ] = 0,
    task: Annotated[
        OptionalBoolType, Field(description="Filter by task type (default: None)")
    ] = None,
    completed: Annotated[
        OptionalBoolType,
        Field(description="Filter by completion status (default: None)"),
    ] = None,
) -> str:
    """Find all notes in a specific notebook, with pagination support.

    MAIN FUNCTION FOR NOTEBOOK SEARCHES!

    Use this when you want to find all notes in a specific notebook.

    Notebook can be specified by name or path:
    - "Work" - matches notebook named "Work" (must be unique)
    - "Projects/Work" - matches "Work" notebook inside "Projects"

    Returns:
        str: List of all notes in the specified notebook, with pagination information.

    Examples:
        - find_notes_in_notebook("Work Projects") - Find all notes in "Work Projects"
        - find_notes_in_notebook("Personal Notes", limit=10, offset=10) - Find notes in "Personal Notes" (page 2)
        - find_notes_in_notebook("Personal Notes", task=True) - Find only tasks in "Personal Notes"
        - find_notes_in_notebook("Projects", task=True, completed=False) - Find only uncompleted tasks in "Projects"
        - find_notes_in_notebook("Project A/tasks") - Find notes in "tasks" sub-notebook under "Project A"
    """

    # Runtime validation
    task = flexible_bool_converter(task)
    completed = flexible_bool_converter(completed)

    # Resolve notebook name/path to ID (ensures exact match)
    notebook_id = get_notebook_id_by_name(notebook_name)

    # Fetch notes by notebook_id for precision (search API can't distinguish same-named notebooks)
    client = get_joplin_client()
    results = client.get_all_notes(notebook_id=notebook_id, fields=COMMON_NOTE_FIELDS)
    notes = process_search_results(results)

    # Apply filters client-side
    if task is not None:
        notes = [n for n in notes if bool(getattr(n, "is_todo", 0)) == task]

    if completed is not None and task:
        notes = [n for n in notes if bool(getattr(n, "todo_completed", 0)) == completed]

    # Sort by updated time, newest first
    notes = sorted(notes, key=lambda x: getattr(x, "updated_time", 0), reverse=True)
    search_query = f'notebook:"{notebook_name}"'

    # Apply pagination
    paginated_notes, total_count = apply_pagination(notes, limit, offset)

    if not paginated_notes:
        base_criteria = f'in notebook "{notebook_name}"'
        criteria_str = format_search_criteria(base_criteria, task, completed)
        return format_no_results_with_pagination("note", criteria_str, offset, limit)

    return format_search_results_with_pagination(
        f"notebook search: {search_query}",
        paginated_notes,
        total_count,
        limit,
        offset,
        "search_results",
        original_query=notebook_name,
    )


@create_tool("get_all_notes", "Get all notes")
async def get_all_notes(
    limit: Annotated[
        LimitType, Field(description="Max results (1-100, default: 20)")
    ] = 20,
) -> str:
    """Get all notes in your Joplin instance.

    Simple function to retrieve all notes without any filtering or searching.
    Most recent notes are shown first.

    Returns:
        str: Formatted list of all notes with title, ID, content preview, and dates.

    Examples:
        - get_all_notes() - Get the 20 most recent notes
        - get_all_notes(50) - Get the 50 most recent notes
    """

    client = get_joplin_client()
    results = client.get_all_notes(fields=COMMON_NOTE_FIELDS)
    notes = process_search_results(results)

    # Sort by updated time, newest first
    notes = sorted(notes, key=lambda x: getattr(x, "updated_time", 0), reverse=True)

    # Apply limit (using consistent pattern but keeping simple offset=0)
    notes = notes[:limit]

    if not notes:
        return format_no_results_message("note")

    return format_search_results_with_pagination(
        "all notes", notes, len(notes), limit, 0, "search_results"
    )
