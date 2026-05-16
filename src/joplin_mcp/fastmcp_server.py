"""FastMCP-based Joplin MCP Server Implementation.

📝 FINDING NOTES:
- find_notes(query, limit, offset, task, completed, trash) - Find notes by text OR list all notes with pagination ⭐ MAIN FUNCTION FOR TEXT SEARCHES AND LISTING ALL NOTES! Use trash=True with query="*" to list trashed notes.
- find_notes_with_tag(tag_name, limit, offset, task, completed) - Find all notes with a specific tag with pagination ⭐ MAIN FUNCTION FOR TAG SEARCHES!
- find_notes_in_notebook(notebook_name, limit, offset, task, completed) - Find all notes in a specific notebook with pagination ⭐ MAIN FUNCTION FOR NOTEBOOK SEARCHES!
- find_in_note(note_id, pattern, limit, offset, case_sensitive, multiline, dotall) - Run regex searches inside a single note with context and pagination
- get_all_notes() - Get all notes, most recent first (simple version without pagination)

📋 MANAGING NOTES:
- create_note(title, notebook_name, body) - Create a new note
- get_note(note_id) - Get a specific note by ID with smart display (sections, line ranges, TOC)
- get_links(note_id) - Extract all links to other notes from a note
- update_note(note_id, title, body) - Update an existing note
- edit_note(note_id, new_string, old_string, replace_all, position) - Precision edit note content
- delete_note(note_id) - Delete a note

📖 SEQUENTIAL READING (for long notes):
- get_note(note_id, start_line=1) - Start reading from line 1 (default: 50 lines)
- get_note(note_id, start_line=51) - Continue from line 51
- get_note(note_id, start_line=1, line_count=100) - Get specific number of lines

🏷️ MANAGING TAGS:
- list_tags() - List all available tags
- tag_note(note_id, tag_name) - Add a tag to a note
- untag_note(note_id, tag_name) - Remove a tag from a note
- get_tags_by_note(note_id) - See what tags a note has

📁 MANAGING NOTEBOOKS:
- list_notebooks() - List all available notebooks
- create_notebook(title) - Create a new notebook

🗑️ TRASH MANAGEMENT:
- restore_from_trash(item_id, item_type) - Restore a soft-deleted note or notebook (item_type: 'note' or 'notebook')
- delete_note / delete_notebook move items to trash (soft delete); find_notes("*", trash=True) lists trashed notes
"""

import datetime
import re
import time
import logging
import os
from enum import Enum
from functools import wraps
from typing import Annotated, Any, Callable, Dict, List, Optional, TypeVar, Union

# FastMCP imports
from fastmcp import FastMCP

# Direct joppy import
from joppy.client_api import ClientApi

# Pydantic imports for proper Field annotations
from pydantic import Field
from typing_extensions import Annotated

from joplin_mcp import __version__ as MCP_VERSION

# Import our existing configuration for compatibility
from joplin_mcp.config import JoplinMCPConfig, get_config, set_config

# Import content utilities
from joplin_mcp.content_utils import (
    create_matching_lines_preview,
    create_toc_only,
    extract_frontmatter,
    extract_section_content,
    extract_text_terms_from_query,
    format_timestamp,
    parse_markdown_headings,
)

# Import formatting utilities
from joplin_mcp.formatting import (
    ItemType,
    format_creation_success,
    format_delete_success,
    format_restore_success,
    format_no_results_message,
    format_relation_success,
    format_update_success,
    get_item_emoji,
)

# Configure logging
logger = logging.getLogger(__name__)

# Create FastMCP server instance with session configuration
mcp = FastMCP(name="Joplin MCP Server", version=MCP_VERSION)

# Type for generic functions
T = TypeVar("T")


# Log the enabled-tool count from the auto-discovered config. Auto-discovery
# itself (and its file/path logging) lives in joplin_mcp.config.
try:
    _enabled = sorted([k for k, v in get_config().tools.items() if v])
    logger.info("Module config loaded; enabled tools count=%d", len(_enabled))
    logger.debug("Enabled tools: %s", _enabled)
except Exception:
    pass


# Enums for type safety
class SortBy(str, Enum):
    title = "title"
    created_time = "created_time"
    updated_time = "updated_time"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


# Type aliases for sort params (accept both enum and string for MCP client compat)
OptionalSortByType = Optional[Union[str, SortBy]]
OptionalSortOrderType = Optional[Union[str, SortOrder]]


def flexible_bool_converter(value: Union[bool, str, None]) -> Optional[bool]:
    """Convert various string representations to boolean for API compatibility."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        value_lower = value.lower().strip()
        if value_lower in ("true", "1", "yes", "on"):
            return True
        elif value_lower in ("false", "0", "no", "off"):
            return False
        else:
            raise ValueError(
                "Must be a boolean value or string representation (true/false, 1/0, yes/no, on/off)"
            )
    # Handle other truthy/falsy values
    return bool(value)


def flexible_enum_converter(
    value: Optional[Union[str, Enum]], enum_cls: type[Enum], field_name: str
) -> Optional[Enum]:
    """Convert string to enum value for MCP client compatibility."""
    if value is None:
        return None
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        value_lower = value.lower().strip()
        try:
            return enum_cls(value_lower)
        except ValueError:
            valid = ", ".join(e.value for e in enum_cls)
            raise ValueError(f"Invalid {field_name}: '{value}'. Must be one of: {valid}")
    raise ValueError(f"Invalid {field_name} type: {type(value)}")


def resolve_sort_params(
    order_by: Optional[SortBy],
    order_dir: Optional[SortOrder],
    default_order_by: SortBy = SortBy.updated_time,
) -> dict:
    """Resolve sort params into joppy/Joplin API kwargs.

    Returns dict with order_by/order_dir keys, ready to unpack into joppy calls.
    """
    sort_field = order_by if order_by is not None else default_order_by

    if order_dir is None:
        direction = "ASC" if sort_field == SortBy.title else "DESC"
    else:
        direction = order_dir.value.upper()  # Joplin API expects uppercase

    return {"order_by": sort_field.value, "order_dir": direction}


def optional_int_converter(
    value: Optional[Union[int, str]], field_name: str
) -> Optional[int]:
    """Convert optional string inputs to integers while validating."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer, not a boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{field_name} must be a valid integer string")
        try:
            return int(stripped)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} must be an integer or string representation of an integer"
            ) from exc
    raise ValueError(f"{field_name} must be an integer or string representation of an integer")


def validate_joplin_id(note_id: str) -> str:
    """Validate that a string is a proper Joplin note ID (32 hex characters)."""
    import re

    if not isinstance(note_id, str):
        raise ValueError("Note ID must be a string")
    if not re.match(r"^[a-f0-9]{32}$", note_id):
        raise ValueError(
            "Note ID must be exactly 32 hexadecimal characters (Joplin UUID format)"
        )
    return note_id


def timestamp_converter(value: Optional[Union[int, str]], field_name: str) -> Optional[int]:
    """Convert timestamp to milliseconds since epoch.

    Accepts: int (ms), ISO 8601 string, or None.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(stripped.replace('Z', '+00:00'))
            return int(dt.timestamp() * 1000)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} must be Unix timestamp (ms) or ISO 8601 string"
            ) from exc
    raise ValueError(f"{field_name} must be int or ISO 8601 string")


# Validation types - simplified for MCP client compatibility but with runtime validation
LimitType = Annotated[
    int, Field(ge=1, le=100)
]  # Range validation + automatic string-to-int conversion
OffsetType = Annotated[
    int, Field(ge=0)
]  # Minimum validation + automatic string-to-int conversion
RequiredStringType = Annotated[
    str, Field(min_length=1)
]  # Simplified: just min length, runtime validation for complex patterns
JoplinIdType = Annotated[
    str, Field(min_length=32, max_length=32)
]  # Length constraints, runtime regex validation
OptionalBoolType = Optional[
    Union[bool, str]
]  # Accepts both bool and string, runtime conversion handles strings

# === UTILITY FUNCTIONS ===


def get_joplin_client() -> ClientApi:
    """Get a configured joppy client instance.

    Reads the live config via the resolver. Falls back to the JOPLIN_TOKEN
    env var if the config has no token.
    """
    config = get_config()

    if config.token:
        return ClientApi(token=config.token, url=config.base_url)

    # Fallback to environment variables
    token = os.getenv("JOPLIN_TOKEN")
    if not token:
        raise ValueError(
            "Authentication token missing. Set 'token' in joplin-mcp.json or JOPLIN_TOKEN env var."
        )

    # Prefer configured base URL if available without token
    url = config.base_url if config else os.getenv("JOPLIN_URL", "http://localhost:41184")
    return ClientApi(token=token, url=url)


# === NOTEBOOK RESOLVER ===
# All notebook cache, path resolution, and invalidation live in
# joplin_mcp.notebook_utils. Tools import the resolver directly from there.
# init_resolver binds the Joplin client factory to the default resolver so it
# can refresh its cache and perform mutations.

from joplin_mcp.notebook_utils import (
    _build_notebook_map,
    _compute_notebook_path,
    init_resolver,
    notebook_resolver,
)

# Bind via a thunk so the resolver looks up get_joplin_client in this module's
# namespace on every call. Tests that patch the module attribute (e.g. the e2e
# fixture) need their patches to flow through to the resolver.
init_resolver(lambda: get_joplin_client())


# Common fields list for note operations
# deleted_time included so the DELETED metadata line surfaces on every
# note-returning path (get_note, find_notes_in_notebook, find_notes_with_tag),
# not just find_notes(trash=True).
COMMON_NOTE_FIELDS = (
    "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed,todo_due,deleted_time"
)



# Content utility functions moved to joplin_mcp/content_utils.py:
# parse_markdown_headings, extract_section_content, create_content_preview,
# create_toc_only, extract_frontmatter, extract_text_terms_from_query,
# _find_matching_lines, create_matching_lines_preview, create_content_preview_with_search,
# format_timestamp, calculate_content_stats

def process_search_results(results: Any) -> List[Any]:
    """Normalise a joppy search/list response into a Python list.

    Shared with ``tools/notes.py``, ``tools/tags.py``, and
    ``format_tag_list_with_counts`` below -- belongs in fastmcp_server
    while no neutral home exists for joppy adapters.
    """
    if hasattr(results, "items"):
        return results.items or []
    elif isinstance(results, list):
        return results
    else:
        return [results] if results else []


_TOKEN_QUERY_RE = re.compile(r"([?&]token=)[^&\s\"'`)\]]+", re.IGNORECASE)
# Drop entire lines that look like JS stack frames ("    at SomeFn (...)") or
# Python frames ('  File "...", line N'). joppy stringifies HTTPError with the
# Joplin response body inline, which Joplin populates with a TS stack trace.
_STACK_FRAME_LINE_RE = re.compile(
    r"^[ \t]+(?:at\s.*|File \"[^\"]*\", line \d+.*)$",
    re.MULTILINE,
)
# Absolute filesystem paths leak the local install location and OS user.
# Match any absolute path (Unix "/foo..." or Windows "C:\foo..."), terminating
# at a quote, bracket, angle, or newline. Spaces inside the match are allowed
# so "/Applications/Some App.app/..." and "C:\Program Files\Joplin\..." get
# fully scrubbed. Distinguishing a filesystem path from a URL path is purely
# contextual: in "http://host/foo" the "/foo" is preceded by an alphanumeric
# (the host) or another "/" (the "//" after "http:"), whereas a real path
# follows whitespace, a delimiter, or start-of-string. The Unix alternative
# uses a negative lookbehind to enforce that; the Windows alternative uses
# \b so it doesn't eat the "p:" in "http://".
_ABS_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9/.])/[A-Za-z][^\"'`)\]<>\r\n]*"
    r"|\b[A-Za-z]:[\\/][^\"'`)\]<>\r\n]*"
)


def _sanitise_error(text: str) -> str:
    """Scrub upstream stack traces, filesystem paths, and token params.

    joppy stringifies requests.HTTPError with the Joplin server response body
    inline. Joplin populates that body with TypeScript stack-trace lines and
    absolute paths from its install location, and the request URL carries the
    full API token. Strip all three before the message reaches MCP clients or
    logs — information disclosure in a hostile-agent setting and confusing UX
    in general.
    """
    text = _TOKEN_QUERY_RE.sub(r"\1***", text)
    text = _STACK_FRAME_LINE_RE.sub("", text)
    text = _ABS_PATH_RE.sub("<path>", text)
    # Collapse blank-line gaps left by stripped trace lines.
    text = re.sub(r"\n[ \t]*\n+", "\n", text)
    return text.strip()


def with_client_error_handling(operation_name: str):
    """Decorator to handle client operations with standardized error handling."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if "parameter is required" in str(e) or "must be between" in str(e):
                    raise e  # Re-raise validation errors as-is
                raise ValueError(f"{operation_name} failed: {_sanitise_error(str(e))}")

        return wrapper

    return decorator


# Tool registry: every @create_tool decoration appends here at import time.
# All tools are eagerly registered with the module ``mcp`` so test paths
# (.fn / .run) work without an explicit registration step. The gating
# decision lives in register_tools(), which reshapes ``mcp``'s tool manager
# to reflect a given config -- so main() can honour the runtime config
# (e.g. --config-file) instead of being frozen at import time.
_tool_registry: List[tuple] = []  # list of (tool_name, tool_obj)


def register_tools(target_mcp: FastMCP, config: "JoplinMCPConfig") -> List[str]:
    """Reshape ``target_mcp``'s tool manager so only tools enabled in
    ``config.tools`` are exposed. Tools missing from ``config.tools`` default
    to enabled.

    Decoration eagerly registers every tool; this function is the one place
    where runtime config takes effect, so it owns both adding (for tools
    that came back after a previous filter) and removing (for tools the
    config disables). Returns the resulting list of enabled tool names.
    """
    enabled: List[str] = []
    target_mcp._tool_manager._tools.clear()
    for tool_name, tool_obj in _tool_registry:
        if config.tools.get(tool_name, True):
            target_mcp._tool_manager._tools[tool_name] = tool_obj
            enabled.append(tool_name)
        else:
            logger.info(
                "Tool '%s' disabled in configuration", tool_name,
            )
    return enabled


def _get_item_id_by_name(
    name: str,
    item_type: str,
    fetch_fn: Callable[..., List[Any]],
    fields: str,
    not_found_hint: str = "",
) -> str:
    """Generic helper to find an item ID by name with helpful error messages.

    Notebook lookups go through get_notebook_id_by_name which walks the
    allowlist-filtered cache directly; this helper is used for tag lookups
    (and any future item type that doesn't need allowlist filtering).

    Args:
        name: The item name to search for
        item_type: Type of item for error messages (e.g., "tag")
        fetch_fn: Function to fetch all items (e.g., client.get_all_tags)
        fields: Fields to request from the API
        not_found_hint: Optional hint to append to "not found" error message

    Returns:
        str: The item ID

    Raises:
        ValueError: If item not found or multiple matches
    """
    all_items = fetch_fn(fields=fields)
    matching_items = [
        item for item in all_items if getattr(item, "title", "").lower() == name.lower()
    ]

    if not matching_items:
        available_items = [getattr(item, "title", "Untitled") for item in all_items]
        hint_suffix = f" {not_found_hint}" if not_found_hint else ""
        raise ValueError(
            f"{item_type.capitalize()} '{name}' not found. "
            f"Available {item_type}s: {', '.join(available_items)}.{hint_suffix}"
        )

    if len(matching_items) > 1:
        item_details = [
            f"'{getattr(item, 'title', 'Untitled')}' (ID: {getattr(item, 'id', 'unknown')})"
            for item in matching_items
        ]
        raise ValueError(
            f"Multiple {item_type}s found with name '{name}': {', '.join(item_details)}. "
            "Please be more specific."
        )

    item_id = getattr(matching_items[0], "id", None)
    if not item_id:
        raise ValueError(f"Could not get ID for {item_type} '{name}'")

    return item_id


def get_tag_id_by_name(name: str) -> str:
    """Get tag ID by name with helpful error messages.

    Args:
        name: The tag name to search for

    Returns:
        str: The tag ID

    Raises:
        ValueError: If tag not found or multiple matches
    """
    client = get_joplin_client()
    return _get_item_id_by_name(
        name=name,
        item_type="tag",
        fetch_fn=client.get_all_tags,
        fields="id,title,created_time,updated_time",
        not_found_hint="Use create_tag to create a new tag.",
    )


# === FORMATTING UTILITIES ===
# Pure formatting functions imported from joplin_mcp.formatting:
# ItemType, get_item_emoji, format_creation_success, format_update_success,
# format_delete_success, format_relation_success, format_no_results_message
#
# Note rendering (format_note_details, _collect_note_metadata,
# _format_note_entry, _build_find_in_note_header,
# format_search_results_with_pagination, plus build_pagination_header,
# build_pagination_summary, format_find_in_note_summary,
# format_note_metadata_lines) lives in joplin_mcp.note_view.
#
# Functions below depend on notebook path utilities or config:


def format_item_list(items: List[Any], item_type: ItemType) -> str:
    """Format a list of items (notebooks, tags, etc.) for display optimized for LLM comprehension."""
    if not items:
        return f"ITEM_TYPE: {item_type.value}\nTOTAL_ITEMS: 0\nSTATUS: No {item_type.value}s found in Joplin instance"

    count = len(items)
    result_parts = [f"ITEM_TYPE: {item_type.value}", f"TOTAL_ITEMS: {count}", ""]

    # Precompute notebook map if listing notebooks to enable path display
    notebooks_map: Optional[Dict[str, Dict[str, Optional[str]]]] = None
    if item_type == ItemType.notebook:
        try:
            notebooks_map = _build_notebook_map(items)  # items already are notebooks
        except Exception:
            notebooks_map = None

    for i, item in enumerate(items, 1):
        title = getattr(item, "title", "Untitled")
        item_id = getattr(item, "id", "unknown")

        # Structured item entry
        result_parts.extend(
            [
                f"ITEM_{i}:",
                f"  {item_type.value}_id: {item_id}",
                f"  title: {title}",
            ]
        )

        # Add parent folder ID if available (for notebooks)
        parent_id = getattr(item, "parent_id", None)
        if parent_id:
            result_parts.append(f"  parent_id: {parent_id}")

        # Add full path for notebooks
        if item_type == ItemType.notebook:
            try:
                if notebooks_map:
                    path = _compute_notebook_path(item_id, notebooks_map)
                else:
                    path = None
                if path:
                    result_parts.append(f"  path: {path}")
            except Exception:
                pass

        # Add creation time if available
        created_time = getattr(item, "created_time", None)
        if created_time:
            created_date = format_timestamp(created_time, "%Y-%m-%d %H:%M")
            if created_date:
                result_parts.append(f"  created: {created_date}")

        # Add update time if available
        updated_time = getattr(item, "updated_time", None)
        if updated_time:
            updated_date = format_timestamp(updated_time, "%Y-%m-%d %H:%M")
            if updated_date:
                result_parts.append(f"  updated: {updated_date}")

        result_parts.append("")

    return "\n".join(result_parts)


def format_item_details(item: Any, item_type: ItemType) -> str:
    """Format a single item (notebook, tag, etc.) for detailed display."""
    emoji = get_item_emoji(item_type)
    title = getattr(item, "title", "Untitled")
    item_id = getattr(item, "id", "unknown")

    result_parts = [f"{emoji} **{title}**", f"ID: {item_id}", ""]

    # Add metadata
    metadata = []

    # Timestamps
    created_time = getattr(item, "created_time", None)
    if created_time:
        created_date = format_timestamp(created_time)
        if created_date:
            metadata.append(f"Created: {created_date}")

    updated_time = getattr(item, "updated_time", None)
    if updated_time:
        updated_date = format_timestamp(updated_time)
        if updated_date:
            metadata.append(f"Updated: {updated_date}")

    # Parent and path (for notebooks)
    parent_id = getattr(item, "parent_id", None)
    if parent_id:
        metadata.append(f"Parent: {parent_id}")
    if item_type == ItemType.notebook:
        try:
            nb_map = notebook_resolver.get_map()
            path = _compute_notebook_path(getattr(item, "id", None), nb_map)
            if path:
                metadata.append(f"Path: {path}")
        except Exception:
            pass

    if metadata:
        result_parts.append("**Metadata:**")
        result_parts.extend(f"- {m}" for m in metadata)

    return "\n".join(result_parts)


def format_tag_list_with_counts(tags: List[Any], client: Any) -> str:
    """Format a list of tags with note counts for display optimized for LLM comprehension."""
    if not tags:
        return (
            "ITEM_TYPE: tag\nTOTAL_ITEMS: 0\nSTATUS: No tags found in Joplin instance"
        )

    count = len(tags)
    result_parts = ["ITEM_TYPE: tag", f"TOTAL_ITEMS: {count}", ""]

    for i, tag in enumerate(tags, 1):
        title = getattr(tag, "title", "Untitled")
        tag_id = getattr(tag, "id", "unknown")

        # Get note count for this tag
        try:
            notes_result = client.get_notes(tag_id=tag_id, fields=COMMON_NOTE_FIELDS)
            notes = process_search_results(notes_result)
            note_count = len(notes)
        except Exception:
            note_count = 0

        # Structured tag entry
        result_parts.extend(
            [
                f"ITEM_{i}:",
                f"  tag_id: {tag_id}",
                f"  title: {title}",
                f"  note_count: {note_count}",
            ]
        )

        # Add creation time if available
        created_time = getattr(tag, "created_time", None)
        if created_time:
            created_date = format_timestamp(created_time, "%Y-%m-%d %H:%M")
            if created_date:
                result_parts.append(f"  created: {created_date}")

        # Add update time if available
        updated_time = getattr(tag, "updated_time", None)
        if updated_time:
            updated_date = format_timestamp(updated_time, "%Y-%m-%d %H:%M")
            if updated_date:
                result_parts.append(f"  updated: {updated_date}")

        result_parts.append("")

    return "\n".join(result_parts)


# === GENERIC CRUD OPERATIONS ===


def create_tool(tool_name: str, operation_name: str):
    """Wrap a tool function with error handling and register it eagerly
    with the module ``mcp``.

    The returned object is the FastMCP tool wrapper, so callers get the
    usual ``.fn`` and ``.run`` attributes. The tool is also added to the
    module registry so register_tools() can later filter the active set
    based on a runtime config.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        wrapped = with_client_error_handling(operation_name)(func)
        tool_obj = mcp.tool()(wrapped)
        _tool_registry.append((tool_name, tool_obj))
        return tool_obj

    return decorator


# === CORE TOOLS ===


# Add health check endpoint for better compatibility
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request) -> dict:
    """Health check endpoint for load balancers and monitoring."""
    from starlette.responses import JSONResponse

    return JSONResponse(
        {
            "status": "healthy",
            "server": "Joplin MCP Server",
            "version": MCP_VERSION,
            "transport": "ready",
        },
        status_code=200,
    )


@create_tool("ping_joplin", "Ping Joplin")
async def ping_joplin() -> str:
    """Test connection to Joplin server.

    Verifies connectivity to the Joplin application. Use to troubleshoot connection issues.

    Returns:
        str: Connection status information.
    """
    try:
        client = get_joplin_client()
        client.ping()
        return """OPERATION: PING_JOPLIN
STATUS: SUCCESS
CONNECTION: ESTABLISHED
MESSAGE: Joplin server connection successful"""
    except Exception as e:
        return f"""OPERATION: PING_JOPLIN
STATUS: FAILED
CONNECTION: FAILED
ERROR: {str(e)}
MESSAGE: Unable to reach Joplin server - check connection settings"""


# Note, notebook, and tag tools are imported at end of file (see joplin_mcp.tools)


# === RESOURCES ===


@mcp.resource("joplin://server_info")
async def get_server_info() -> dict:
    """Get Joplin server information."""
    try:
        client = get_joplin_client()
        is_connected = client.ping()
        return {
            "connected": bool(is_connected),
            "url": getattr(client, "url", "unknown"),
            "version": f"FastMCP-based Joplin Server v{MCP_VERSION}",
        }
    except Exception:
        return {"connected": False}


# Import tool modules to trigger registration with mcp instance
# This MUST be at the end, after mcp, create_tool, and all utilities are defined
import joplin_mcp.tools  # noqa: E402, F401
import joplin_mcp.imports.tools  # noqa: E402, F401


# === MAIN RUNNER ===


from starlette.types import ASGIApp, Scope, Receive, Send
from fastmcp.server.http import create_streamable_http_app, create_sse_app
import uvicorn

class SlashCompatMiddleware:
    """Rewrite selected no-slash paths to their trailing-slash canonical form."""
    def __init__(self, app: ASGIApp, slash_map: dict[str, str]) -> None:
        self.app = app
        self.slash_map = slash_map

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path in self.slash_map:
                scope = dict(scope)
                scope["path"] = self.slash_map[path]
        return await self.app(scope, receive, send)

def run_compat_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    path: str = "/mcp",
    log_level: str = "info",
    *,
    force_json_post: bool = True,
):
    # Canonicalize modern endpoint to trailing slash (matches helpers’ behavior)
    canon_path = (path or "/mcp").rstrip("/") + "/"

    # Base app: modern Streamable HTTP (JSON on POST)
    app = create_streamable_http_app(
        server=mcp,
        streamable_http_path=canon_path,
        json_response=force_json_post,
    )

    # Single legacy SSE app (canonical with trailing slash)
    legacy = create_sse_app(
        server=mcp,
        sse_path="/sse/",
        message_path="/messages/",
    )
    # Merge routes from legacy into the base app (one app, one registry)
    app.router.routes.extend(legacy.routes)

    # Accept no-slash without redirect (avoid 307s) — single **app** handles both
    app = SlashCompatMiddleware(app, {
        canon_path.rstrip("/"): canon_path,   # /mcp  -> /mcp/
        "/sse": "/sse/",                      # /sse  -> /sse/
        "/messages": "/messages/",            # /messages -> /messages/
    })

    uvicorn.run(app, host=host, port=port, log_level=log_level)


def main(
    config_file: Optional[str] = None,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8000,
    path: str = "/mcp",
    log_level: str = "info",
):
    """Main entry point for the FastMCP Joplin server."""
    try:
        logger.info("🚀 Starting FastMCP Joplin server...")

        # Runtime config supersedes the auto-discovered one -- one config
        # identity at a time, wholesale replace.
        if config_file:
            set_config(JoplinMCPConfig.from_file(config_file))
            logger.info(f"Runtime configuration loaded from {config_file}")
        else:
            logger.info("Using auto-discovered configuration for runtime")

        registered_tools = register_tools(mcp, get_config())
        logger.info(f"FastMCP server has {len(registered_tools)} tools registered")
        logger.info(f"Registered tools: {sorted(registered_tools)}")

        logger.info("Initializing Joplin client...")
        client = get_joplin_client()
        logger.info("Joplin client initialized successfully")

        # Validate and log notebook allowlist at startup (D3, D6, D9)
        notebook_resolver.validate_allowlist_at_startup(get_config(), client)

        # ---- Non-breaking compat toggle via env ----
        compat_env = os.getenv("MCP_HTTP_COMPAT", "").strip().lower() in {"1","true","yes","on"}

        # Run the FastMCP server with specified transport
        t = transport.lower()

        if t == "http-compat" or (t in {"http", "streamable-http"} and compat_env):
            # Opt-in compatibility mode (modern + legacy)
            run_compat_server(
                host=host,
                port=port,
                path=path,          # we normalize inside run_compat_server only
                log_level=log_level,
                force_json_post=True,
            )

        elif t in {"http", "http-streamable"}:
            logger.info(f"Starting FastMCP server with HTTP (Streamable HTTP) on {host}:{port}{path}")
            mcp.run(transport="http", host=host, port=port, path=path, log_level=log_level)

        elif t == "sse":
            logger.info(f"Starting FastMCP server with SSE transport on {host}:{port}{path}")
            mcp.run(transport="sse", host=host, port=port, path=path, log_level=log_level)

        elif t == "stdio":
            logger.info("Starting FastMCP server with STDIO transport")
            mcp.run(transport="stdio")

        else:
            logger.warning(f"Unknown transport {transport!r}; falling back to STDIO")
            mcp.run(transport="stdio")

    except Exception as e:
        logger.error(f"Failed to start FastMCP Joplin server: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
