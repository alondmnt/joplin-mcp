"""FastMCP-based Joplin MCP Server Implementation.

📝 FINDING NOTES:
- find_notes(query, limit, offset, task, completed) - Find notes by text OR list all notes with pagination ⭐ MAIN FUNCTION FOR TEXT SEARCHES AND LISTING ALL NOTES!
- find_notes_with_tag(tag_name, limit, offset, task, completed) - Find all notes with a specific tag with pagination ⭐ MAIN FUNCTION FOR TAG SEARCHES!
- find_notes_in_notebook(notebook_name, limit, offset, task, completed) - Find all notes in a specific notebook with pagination ⭐ MAIN FUNCTION FOR NOTEBOOK SEARCHES!
- find_in_note(note_id, pattern, limit, offset, case_sensitive, multiline, dotall) - Run regex searches inside a single note with context and pagination
- get_all_notes() - Get all notes, most recent first (simple version without pagination)

📋 MANAGING NOTES:
- create_note(title, notebook_name, body) - Create a new note
- get_note(note_id) - Get a specific note by ID with smart display (sections, line ranges, TOC)
- get_links(note_id) - Extract all links to other notes from a note
- update_note(note_id, title, body) - Update an existing note
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
"""

import datetime
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
from joplin_mcp.config import JoplinMCPConfig

# Import content utilities
from joplin_mcp.content_utils import (
    calculate_content_stats,
    create_content_preview,
    create_content_preview_with_search,
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
    build_pagination_header,
    build_pagination_summary,
    format_creation_success,
    format_delete_success,
    format_find_in_note_summary,
    format_no_results_message,
    format_note_metadata_lines,
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

# Global config instance for tool registration
_config: Optional[JoplinMCPConfig] = None


# Load configuration at module level for tool filtering
def _load_module_config() -> JoplinMCPConfig:
    """Load configuration at module level for tool registration filtering."""
    from pathlib import Path

    # Use the built-in auto-discovery that checks standard global config locations
    # This includes: ~/.joplin-mcp.json, ~/.config/joplin-mcp/config.json, etc.
    logger.info("Auto-discovering Joplin MCP configuration...")

    try:
        loaded_from: Optional[Path] = None

        # Highest priority: explicit config path via environment
        explicit_config = os.getenv("JOPLIN_MCP_CONFIG") or os.getenv(
            "JOPLIN_CONFIG_FILE"
        )
        if explicit_config:
            cfg_path = Path(explicit_config)
            if cfg_path.exists():
                logger.info(f"Using explicit configuration from: {cfg_path}")
                config = JoplinMCPConfig.from_file(cfg_path)
                loaded_from = cfg_path
            else:
                logger.warning(
                    f"Explicit config path set but not found: {cfg_path}. Falling back to discovery."
                )
                config = JoplinMCPConfig.auto_discover()
        else:
            config = JoplinMCPConfig.auto_discover()

        # Only emit the "not found" warning when we truly didn't load from any file
        if loaded_from is None:
            # See if auto-discovery found a file
            for path in JoplinMCPConfig.get_default_config_paths():
                if path.exists():
                    loaded_from = path
                    break
            # Also check current directory (for development)
            if loaded_from is None:
                cwd = Path.cwd()
                for path in [
                    cwd / "joplin-mcp.json",
                    cwd / "joplin-mcp.yaml",
                    cwd / "joplin-mcp.yml",
                ]:
                    if path.exists():
                        loaded_from = path
                        break

        if loaded_from is None:
            logger.warning(
                "No configuration file found. Using environment variables and defaults."
            )
        else:
            logger.info(f"Successfully loaded configuration from: {loaded_from}")

        return config

    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        logger.warning("Falling back to default configuration.")
        return JoplinMCPConfig()


# Load config for tool registration filtering
_module_config = _load_module_config()
try:
    enabled = sorted([k for k, v in _module_config.tools.items() if v])
    logger.info(
        "Module config loaded; enabled tools count=%d", len(enabled)
    )
    logger.debug("Enabled tools: %s", enabled)
except Exception:
    pass


# Enums for type safety
class SortBy(str, Enum):
    title = "title"
    created_time = "created_time"
    updated_time = "updated_time"
    relevance = "relevance"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


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

    Priority:
    1) Use runtime config if set (server --config)
    2) Else use module config (auto-discovered on import, honors JOPLIN_MCP_CONFIG)
    3) Else fall back to environment variables
    """
    # Prefer the runtime config if available, else the module-level config
    config = _config or _module_config

    # If for some reason neither exists (unlikely), try loader
    if config is None:
        try:
            config = JoplinMCPConfig.load()
        except Exception:
            config = None

    if config and getattr(config, "token", None):
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


# === NOTEBOOK PATH UTILITIES ===

def _build_notebook_map(notebooks: List[Any]) -> Dict[str, Dict[str, Optional[str]]]:
    """Build a map of notebook_id -> {title, parent_id}."""
    mapping: Dict[str, Dict[str, Optional[str]]] = {}
    for nb in notebooks or []:
        try:
            nb_id = getattr(nb, "id", None)
            if not nb_id:
                continue
            mapping[nb_id] = {
                "title": getattr(nb, "title", "Untitled"),
                "parent_id": getattr(nb, "parent_id", None),
            }
        except Exception:
            # Be resilient to unexpected notebook structures
            continue
    return mapping


def _compute_notebook_path(
    notebook_id: Optional[str],
    notebooks_map: Dict[str, Dict[str, Optional[str]]],
    sep: str = " / ",
) -> Optional[str]:
    """Compute full notebook path from root to the specified notebook.

    Returns a string like "Parent / Child / Notebook" or None if unavailable.
    """
    if not notebook_id:
        return None

    parts: List[str] = []
    seen: set[str] = set()
    curr = notebook_id
    while curr and curr not in seen:
        seen.add(curr)
        info = notebooks_map.get(curr)
        if not info:
            break
        title = (info.get("title") or "Untitled").strip()
        parts.append(title)
        curr = info.get("parent_id")

    if not parts:
        return None
    return sep.join(reversed(parts))


# === NOTEBOOK MAP CACHE ===

_NOTEBOOK_MAP_CACHE: Dict[str, Any] = {"built_at": 0.0, "map": None}
_DEFAULT_NOTEBOOK_TTL_SECONDS = 90  # sensible default; adjustable via env var


def _get_notebook_cache_ttl() -> int:
    try:
        env_val = os.getenv("JOPLIN_MCP_NOTEBOOK_CACHE_TTL")
        if env_val:
            ttl = int(env_val)
            # Clamp to reasonable bounds to avoid accidental huge/small values
            return max(5, min(ttl, 3600))
    except Exception:
        pass
    return _DEFAULT_NOTEBOOK_TTL_SECONDS


def get_notebook_map_cached(force_refresh: bool = False) -> Dict[str, Dict[str, Optional[str]]]:
    """Return cached notebook map with TTL; refresh if stale or forced."""
    ttl = _get_notebook_cache_ttl()
    now = time.monotonic()

    if not force_refresh:
        built_at = _NOTEBOOK_MAP_CACHE.get("built_at", 0.0) or 0.0
        cached_map = _NOTEBOOK_MAP_CACHE.get("map")
        if cached_map is not None and (now - built_at) < ttl:
            return cached_map

    client = get_joplin_client()
    fields_list = "id,title,parent_id"
    notebooks = client.get_all_notebooks(fields=fields_list)
    nb_map = _build_notebook_map(notebooks)
    _NOTEBOOK_MAP_CACHE["map"] = nb_map
    _NOTEBOOK_MAP_CACHE["built_at"] = now
    return nb_map


def invalidate_notebook_map_cache() -> None:
    """Invalidate the cached notebook map so next access refreshes it."""
    _NOTEBOOK_MAP_CACHE["built_at"] = 0.0
    _NOTEBOOK_MAP_CACHE["map"] = None


def apply_pagination(
    notes: List[Any], limit: int, offset: int
) -> tuple[List[Any], int]:
    """Apply pagination to a list of notes and return paginated results with total count."""
    total_count = len(notes)
    start_index = offset
    end_index = offset + limit
    paginated_notes = notes[start_index:end_index]
    return paginated_notes, total_count


def build_search_filters(task: Optional[bool], completed: Optional[bool]) -> List[str]:
    """Build search filter parts for task and completion status."""
    search_parts = []

    # Add task filter if specified
    if task is not None:
        if task:
            search_parts.append("type:todo")
        else:
            search_parts.append("type:note")

    # Add completion filter if specified (only relevant for tasks)
    if completed is not None and task is True:
        if completed:
            search_parts.append("iscompleted:1")
        else:
            search_parts.append("iscompleted:0")

    return search_parts


def format_search_criteria(
    base_criteria: str, task: Optional[bool], completed: Optional[bool]
) -> str:
    """Format search criteria description with filters."""
    criteria_parts = [base_criteria]

    if task is True:
        criteria_parts.append("(tasks only)")
    elif task is False:
        criteria_parts.append("(regular notes only)")

    if completed is True:
        criteria_parts.append("(completed)")
    elif completed is False:
        criteria_parts.append("(uncompleted)")

    return " ".join(criteria_parts)


def format_no_results_with_pagination(
    item_type: str, criteria: str, offset: int, limit: int
) -> str:
    """Format no results message with pagination info."""
    if offset > 0:
        page_info = f" - Page {(offset // limit) + 1} (offset {offset})"
        return format_no_results_message(item_type, criteria + page_info)
    else:
        return format_no_results_message(item_type, criteria)


# Common fields list for note operations
COMMON_NOTE_FIELDS = (
    "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed,todo_due"
)



# Content utility functions moved to joplin_mcp/content_utils.py:
# parse_markdown_headings, extract_section_content, create_content_preview,
# create_toc_only, extract_frontmatter, extract_text_terms_from_query,
# _find_matching_lines, create_matching_lines_preview, create_content_preview_with_search,
# format_timestamp, calculate_content_stats

def process_search_results(results: Any) -> List[Any]:
    """Process search results from joppy client into a consistent list format."""
    if hasattr(results, "items"):
        return results.items or []
    elif isinstance(results, list):
        return results
    else:
        return [results] if results else []


def filter_items_by_title(items: List[Any], query: str) -> List[Any]:
    """Filter items by title using case-insensitive search."""
    return [
        item for item in items if query.lower() in getattr(item, "title", "").lower()
    ]


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
                raise ValueError(f"{operation_name} failed: {str(e)}")

        return wrapper

    return decorator


def conditional_tool(tool_name: str):
    """Decorator to conditionally register tools based on configuration."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Check if tool is enabled in configuration
        if _module_config.tools.get(
            tool_name, True
        ):  # Default to True if not specified
            # Tool is enabled - register it with FastMCP
            logger.debug("Registering tool: %s", tool_name)
            return mcp.tool()(func)
        else:
            # Tool is disabled - return function without registering
            logger.info(
                f"Tool '{tool_name}' disabled in configuration - not registering"
            )
            return func

    return decorator


def _get_item_id_by_name(
    name: str,
    item_type: str,
    fetch_fn: Callable[..., List[Any]],
    fields: str,
    not_found_hint: str = "",
) -> str:
    """Generic helper to find notebook/tag ID by name with helpful error messages.

    Args:
        name: The item name to search for
        item_type: Type of item for error messages (e.g., "notebook", "tag")
        fetch_fn: Function to fetch all items (e.g., client.get_all_notebooks)
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
            "Use a path like 'Parent/Child' to specify the exact notebook."
        )

    item_id = getattr(matching_items[0], "id", None)
    if not item_id:
        raise ValueError(f"Could not get ID for {item_type} '{name}'")

    return item_id


def _resolve_notebook_by_path(path: str) -> str:
    """Resolve notebook ID from path like 'Parent/Child/Notebook'.

    Args:
        path: Notebook path with '/' separators (e.g., 'Projects/Work/Tasks')

    Returns:
        str: The notebook ID of the final path component

    Raises:
        ValueError: If path is empty or any component not found/ambiguous
    """
    parts = [p.strip() for p in path.split("/") if p.strip()]
    if not parts:
        raise ValueError("Empty notebook path")

    notebooks_map = get_notebook_map_cached(force_refresh=True)

    current_parent: Optional[str] = None
    for part in parts:
        matches = [
            nb_id for nb_id, info in notebooks_map.items()
            if info["title"].lower() == part.lower()
            and (info.get("parent_id") or None) == current_parent
        ]
        if not matches:
            raise ValueError(f"Notebook '{part}' not found in path '{path}'")
        if len(matches) > 1:
            raise ValueError(f"Multiple notebooks named '{part}' in path '{path}'")
        current_parent = matches[0]

    return current_parent


def get_notebook_id_by_name(name: str) -> str:
    """Get notebook ID by name or path with helpful error messages.

    Args:
        name: Notebook name or path (e.g., 'Work' or 'Projects/Work/Tasks')

    Returns:
        str: The notebook ID

    Raises:
        ValueError: If notebook not found or multiple matches
    """
    # If path contains '/', resolve by path
    if "/" in name:
        return _resolve_notebook_by_path(name)

    # Otherwise, use flat name matching
    client = get_joplin_client()
    return _get_item_id_by_name(
        name=name,
        item_type="notebook",
        fetch_fn=client.get_all_notebooks,
        fields="id,title,created_time,updated_time,parent_id",
    )


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
# format_delete_success, format_relation_success, format_no_results_message,
# build_pagination_header, build_pagination_summary, format_find_in_note_summary,
# format_note_metadata_lines
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
            nb_map = get_notebook_map_cached()
            path = _compute_notebook_path(getattr(item, "id", None), nb_map)
            if path:
                metadata.append(f"Path: {path}")
        except Exception:
            pass

    if metadata:
        result_parts.append("**Metadata:**")
        result_parts.extend(f"- {m}" for m in metadata)

    return "\n".join(result_parts)


def format_note_details(
    note: Any,
    include_body: bool = True,
    context: str = "individual_notes",
    original_body: Optional[str] = None,
) -> str:
    """Format a note for detailed display optimized for LLM comprehension."""
    # Check content exposure settings
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

    # Add content last to avoid breaking metadata flow
    if include_body:
        body = getattr(note, "body", "")
        if should_show_content:
            if body:
                if should_show_full_content:
                    # Standard full content display
                    result_parts.append(f"CONTENT: {body}")
                else:
                    # Show preview only (for search results context)
                    max_length = config.get_max_preview_length()
                    preview = create_content_preview(body, max_length)
                    result_parts.append(f"CONTENT_PREVIEW: {preview}")
            else:
                result_parts.append("CONTENT: (empty)")
        else:
            # Content hidden due to privacy settings, but show status
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

    # Add content based on privacy settings
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

    entry.append("")  # Empty line separator
    return entry


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
                    map_to_use = get_notebook_map_cached()
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
) -> str:
    """Format search results with pagination information for display optimized for LLM comprehension."""
    config = _module_config

    # Build notebook map once for efficient path resolution
    notebooks_map: Optional[Dict[str, Dict[str, Optional[str]]]] = None
    try:
        notebooks_map = get_notebook_map_cached()
    except Exception:
        notebooks_map = None  # Best-effort only

    # Build all parts
    result_parts = build_pagination_header(query, total_count, limit, offset)

    # Add note entries
    for i, note in enumerate(results, 1):
        result_parts.extend(
            _format_note_entry(
                note, i, config, context, original_query, query, notebooks_map
            )
        )

    # Add pagination summary
    result_parts.extend(build_pagination_summary(total_count, limit, offset))

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
    """Create a tool decorator with consistent error handling."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        return conditional_tool(tool_name)(
            with_client_error_handling(operation_name)(func)
        )

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
    global _config

    try:
        logger.info("🚀 Starting FastMCP Joplin server...")

        # Config loading as before...
        if config_file:
            _config = JoplinMCPConfig.from_file(config_file)
            logger.info(f"Runtime configuration loaded from {config_file}")
        else:
            _config = _module_config
            logger.info("Using module-level configuration for runtime")

        registered_tools = list(mcp._tool_manager._tools.keys())
        logger.info(f"FastMCP server has {len(registered_tools)} tools registered")
        logger.info(f"Registered tools: {sorted(registered_tools)}")

        logger.info("Initializing Joplin client...")
        client = get_joplin_client()
        logger.info("Joplin client initialized successfully")

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
