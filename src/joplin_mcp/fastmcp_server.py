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


class ItemType(str, Enum):
    note = "note"
    notebook = "notebook"
    tag = "tag"


# === PYDANTIC VALIDATION TYPES ===


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
    "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed"
)


def parse_markdown_headings(body: str, start_line: int = 0) -> List[Dict[str, Any]]:
    """Parse markdown headings from content, skipping those in code blocks.

    Args:
        body: The markdown content to parse
        start_line: Starting line index (for offset calculations)

    Returns:
        List of heading dictionaries with keys:
        - level: Heading level (1-6)
        - title: Heading text (cleaned)
        - line_idx: Absolute line index in original content
        - relative_line_idx: Line index relative to start_line
        - original_line: Full original line text
        - markdown: Original markdown heading (e.g., "## Title")
    """
    if not body:
        return []

    import re

    lines = body.split("\n")
    headings = []

    # Regex patterns
    heading_pattern = r"^(#{1,6})\s+(.+)$"
    code_block_pattern = r"^(```|~~~)"
    in_code_block = False

    for rel_line_idx, line in enumerate(lines):
        line_stripped = line.strip()
        abs_line_idx = start_line + rel_line_idx

        # Check for code block delimiters
        if re.match(code_block_pattern, line_stripped):
            in_code_block = not in_code_block
            continue

        # Only process headings outside code blocks
        if not in_code_block:
            match = re.match(heading_pattern, line_stripped)
            if match:
                hashes = match.group(1)
                title = match.group(2).strip()
                level = len(hashes)

                headings.append(
                    {
                        "level": level,
                        "title": title,
                        "line_idx": abs_line_idx,
                        "relative_line_idx": rel_line_idx,
                        "original_line": line,
                        "markdown": f"{hashes} {title}",
                    }
                )

    return headings


def extract_section_content(body: str, section_identifier: str) -> tuple[str, str]:
    """Extract a specific section from note content.

    Args:
        body: The note content to extract from
        section_identifier: Can be:
            - Section number (1-based): "1", "2", etc. (highest priority)
            - Heading text (case insensitive): "Introduction" (exact match)
            - Slug format: "introduction" or "my-section" (intentional format)
            - Partial text: "config" matches "Configuration" (fuzzy fallback)

    Priority order: Number → Exact → Slug → Partial

    Returns:
        tuple: (extracted_content, section_title) or ("", "") if not found
    """
    if not body or not section_identifier:
        return "", ""

    import re

    # Parse headings using helper function
    headings = parse_markdown_headings(body)

    if not headings:
        return "", ""

    # Split body into lines for content extraction
    lines = body.split("\n")

    # Find target section
    target_heading = None

    # Try to parse as section number first
    try:
        section_num = int(section_identifier)
        if 1 <= section_num <= len(headings):
            target_heading = headings[section_num - 1]
        else:
            # Number out of range, fall back to text matching
            target_heading = None
    except ValueError:
        # Not a number, will try text matching below
        target_heading = None

    # If no valid section number found, try text/slug matching
    if target_heading is None:
        identifier_lower = section_identifier.lower().strip()

        # Priority 1: Try exact matches first (case insensitive)
        for heading in headings:
            title_lower = heading["title"].lower()
            if title_lower == identifier_lower:
                target_heading = heading
                break

        # Priority 2: Try slug matches only if no exact match found
        if not target_heading:
            # Convert identifier to slug format
            identifier_slug = re.sub(r"[^\w\s-]", "", identifier_lower)
            identifier_slug = re.sub(r"[-\s_]+", "-", identifier_slug).strip("-")

            for heading in headings:
                title_lower = heading["title"].lower()

                # Convert title to slug and compare
                title_slug = re.sub(
                    r"[^\w\s-]", "", title_lower
                )  # Remove special chars
                title_slug = re.sub(r"[-\s]+", "-", title_slug).strip(
                    "-"
                )  # Normalize spaces/hyphens

                # Only exact slug matches, not partial slug matches
                if title_slug == identifier_slug:
                    target_heading = heading
                    break

        # Priority 3: Try partial matches only if no slug match found
        if not target_heading:
            for heading in headings:
                title_lower = heading["title"].lower()
                if identifier_lower in title_lower:
                    target_heading = heading
                    break

    if not target_heading:
        return "", ""

    # Find content boundaries based on hierarchy
    start_line = target_heading["line_idx"]
    end_line = len(lines)
    target_level = target_heading["level"]

    # Find end of section: next heading at same level or higher
    for heading in headings:
        if heading["line_idx"] > start_line and heading["level"] <= target_level:
            end_line = heading["line_idx"]
            break

    # Extract the section content
    section_lines = lines[start_line:end_line]
    section_content = "\n".join(section_lines).strip()

    return section_content, target_heading["title"]


def create_content_preview(body: str, max_length: int) -> str:
    """Create a content preview that preserves front matter if present.

    If the content starts with front matter (delimited by ---), includes the entire
    front matter in the preview, followed by regular content preview.

    Args:
        body: The note content to create a preview for
        max_length: Maximum length for the preview (excluding front matter)

    Returns:
        str: The content preview with front matter and content preview
    """
    if not body:
        return ""


    lines = body.split("\n")
    preview_parts = []

    # Extract frontmatter using utility function
    front_matter, content_start_index = extract_frontmatter(body, max_lines=20)

    if front_matter:
        preview_parts.append(front_matter)

    # Get remaining content after front matter
    remaining_lines = lines[content_start_index:]
    remaining_content = "\n".join(remaining_lines)

    # Calculate remaining space for content preview
    used_space = sum(
        len(part) + 1 for part in preview_parts
    )  # +1 for newlines between parts
    remaining_space = max(
        50, max_length - used_space
    )  # Ensure at least 50 chars for content

    # Add content preview with remaining space
    if remaining_content:
        content_preview = remaining_content.strip()
        if len(content_preview) > remaining_space:
            content_preview = content_preview[:remaining_space] + "..."

        # Only add content preview if it's meaningful (more than just "...")
        if len(content_preview.replace("...", "").strip()) > 10:
            preview_parts.append(content_preview)

    # If no meaningful content remains and no front matter, show regular preview
    if not preview_parts:
        preview = body[:max_length]
        if len(body) > max_length:
            preview += "..."
        return preview

    return "\n\n".join(preview_parts)


def create_toc_only(body: str) -> str:
    """Create a table of contents with line numbers from note content.

    Args:
        body: The note content to extract TOC from

    Returns:
        str: Table of contents with heading structure and line numbers, or empty string if no headings
    """
    if not body:
        return ""

    headings = parse_markdown_headings(body)

    if not headings:
        return ""

    # Create TOC entries with line numbers
    toc_entries = []
    for i, heading in enumerate(headings, 1):
        level = heading["level"]
        title = heading["title"]
        line_num = heading["line_idx"]  # 1-based line number

        # Create indentation based on heading level (level 1 = no indent, level 2 = 2 spaces, etc.)
        indent = "  " * (level - 1)
        toc_entries.append(f"{indent}{i}. {title} (line {line_num})")

    toc_header = "TABLE_OF_CONTENTS:"
    toc_content = "\n".join(toc_entries)

    return f"{toc_header}\n{toc_content}"


def extract_frontmatter(body: str, max_lines: int = 20) -> tuple[str, int]:
    """Extract frontmatter from note content if present.

    Args:
        body: The note content to extract frontmatter from
        max_lines: Maximum number of frontmatter lines to include

    Returns:
        tuple: (frontmatter_content, content_start_index)
    """
    if not body or not body.startswith("---"):
        return "", 0

    lines = body.split("\n")

    # Find the closing front matter delimiter
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            front_matter_end = i
            break
    else:
        return "", 0  # No closing delimiter found

    # Get frontmatter lines with limit
    front_matter_lines = lines[: front_matter_end + 1]

    if len(front_matter_lines) > max_lines:
        # Truncate front matter if it exceeds max_lines
        # Keep opening --- + (max_lines-2) lines of content + closing ---
        front_matter_lines = lines[: max_lines - 1]  # Opening --- + content lines
        front_matter_lines.append("---")  # Add back the closing delimiter

    front_matter = "\n".join(front_matter_lines)
    content_start_index = front_matter_end + 1

    return front_matter, content_start_index


def extract_text_terms_from_query(query: str) -> List[str]:
    """Extract text search terms from a Joplin search query, removing operators.

    Removes Joplin search operators like tag:, notebook:, type:, iscompleted:, etc.
    and extracts the actual text terms for content matching.

    Args:
        query: The search query that may contain operators and text terms

    Returns:
        List of text terms for content matching
    """
    import re

    if not query or query.strip() == "*":
        return []

    # Known Joplin search operators to remove
    operator_patterns = [
        r"tag:\S+",  # tag:work
        r"notebook:\S+",  # notebook:project
        r"type:\S+",  # type:todo
        r"iscompleted:\d+",  # iscompleted:1
        r"created:\S+",  # created:20231201
        r"updated:\S+",  # updated:20231201
        r"latitude:\S+",  # latitude:123.456
        r"longitude:\S+",  # longitude:123.456
        r"altitude:\S+",  # altitude:123.456
        r"resource:\S+",  # resource:image
        r"sourceurl:\S+",  # sourceurl:http
        r"any:\d+",  # any:1
    ]

    # Remove all operators
    cleaned_query = query
    for pattern in operator_patterns:
        cleaned_query = re.sub(pattern, "", cleaned_query, flags=re.IGNORECASE)

    # Handle quoted phrases - extract them as single terms
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, cleaned_query)

    # Remove quoted phrases from the query to avoid double processing
    for phrase in phrases:
        cleaned_query = cleaned_query.replace(f'"{phrase}"', "")

    # Split remaining text into individual words
    individual_words = cleaned_query.split()

    # Combine phrases and individual words, filtering out empty strings
    all_terms = phrases + [word.strip() for word in individual_words if word.strip()]

    return all_terms


def _find_matching_lines(
    content_lines: List[str], search_terms: List[str], content_start_index: int
) -> tuple[List[tuple[int, str]], List[tuple[int, str]]]:
    """Find lines matching search terms, separated by AND vs OR logic."""
    search_terms_lower = [term.lower() for term in search_terms]

    and_matches = []
    or_matches = []
    and_indices = set()

    for i, line in enumerate(content_lines):
        line_index = i + content_start_index
        line_lower = line.lower()

        # Check for AND matches (all terms present)
        if all(term in line_lower for term in search_terms_lower):
            and_matches.append((line_index, line))
            and_indices.add(line_index)
        # Check for OR matches (any terms present), excluding AND matches
        elif any(term in line_lower for term in search_terms_lower):
            or_matches.append((line_index, line))

    return and_matches, or_matches


def create_matching_lines_preview(
    body: str,
    search_terms: List[str],
    max_length: int = 300,
    max_lines: int = 10,
    context_lines: int = 0,
) -> tuple[str, List[int], int, int]:
    """Create a preview showing only lines that match search terms with priority system.

    Priority system:
    1. Lines matching ALL search terms (AND logic) - highest priority
    2. Lines matching any search terms (OR logic) - lower priority
    3. Builds incrementally while respecting max_length limit

    Args:
        body: The note content to search in
        search_terms: List of terms to search for
        max_length: Maximum length for the preview content
        max_lines: Maximum number of matching lines to include
        context_lines: Number of context lines to show around matches

    Returns:
        tuple: (preview_content, list_of_displayed_line_numbers, and_matches_count, or_matches_count)
    """
    if not body or not search_terms:
        return "", [], 0, 0

    lines = body.split("\n")
    _, content_start_index = extract_frontmatter(body)
    content_lines = lines[content_start_index:]

    # Find all matching lines
    and_matches, or_matches = _find_matching_lines(
        content_lines, search_terms, content_start_index
    )
    and_count, or_count = len(and_matches), len(or_matches)

    # Combine matches with priority (AND first, then OR)
    all_matches = and_matches + or_matches
    if not all_matches:
        return "", [], 0, 0

    # Build preview incrementally
    preview_parts = []
    included_line_numbers = []
    used_indices = set()
    current_length = 0

    for line_index, _ in all_matches:
        if len(included_line_numbers) >= max_lines:
            break

        # Calculate what this match would add to the preview
        context_block = []
        block_indices = []

        # Calculate context range
        start_context = max(content_start_index, line_index - context_lines)
        end_context = min(len(lines), line_index + context_lines + 1)

        # Build context block for this match
        for ctx_i in range(start_context, end_context):
            if ctx_i not in used_indices:
                block_indices.append(ctx_i)
                line_num = ctx_i + 1  # 1-based
                line_content = lines[ctx_i]

                # Mark the actual matching line vs context
                if ctx_i == line_index:
                    context_block.append(f"[L{line_num}] {line_content}")
                else:
                    context_block.append(f" L{line_num}  {line_content}")

        if context_block:
            block_content = "\n".join(context_block)
            separator_length = 1 if preview_parts else 0  # Newline separator
            block_length = len(block_content) + separator_length

            # Check length limit
            if current_length + block_length > max_length and preview_parts:
                break

            # Add block with separator
            if preview_parts:
                preview_parts.append("")
            preview_parts.extend(context_block)

            current_length += block_length
            used_indices.update(block_indices)
            included_line_numbers.append(line_index + 1)  # 1-based

    preview_content = "\n".join(preview_parts) if preview_parts else ""
    return preview_content, included_line_numbers, and_count, or_count


def create_content_preview_with_search(
    body: str, max_length: int, search_query: str = ""
) -> str:
    """Create a content preview that shows matching lines for search queries, with fallback.

    Enhancement to create_content_preview that prioritizes showing lines matching
    the search query instead of just the first lines of content.

    Args:
        body: The note content to create a preview for
        max_length: Maximum length for the preview (excluding front matter)
        search_query: The search query to extract terms from

    Returns:
        str: The content preview with matching lines or fallback to regular preview
    """
    if not body:
        return ""

    search_terms = extract_text_terms_from_query(search_query)
    if not search_terms:
        return create_content_preview(body, max_length)

    # Extract frontmatter and calculate available space
    front_matter, _ = extract_frontmatter(body, max_lines=10)
    available_length = max(50, max_length - len(front_matter))

    matching_preview, line_numbers, and_matches, or_matches = (
        create_matching_lines_preview(
            body,
            search_terms,
            max_length=available_length,
            max_lines=8,
            context_lines=0,
        )
    )

    if not matching_preview:
        return create_content_preview(body, max_length)

    # Build preview with metadata
    preview_parts = []

    if front_matter:
        preview_parts.append(front_matter)

    # Build match quality description
    displayed_matches = len(line_numbers)
    total_matches = and_matches + or_matches

    if and_matches > 0 and or_matches > 0:
        quality_info = f"({and_matches} match all terms, {or_matches} match any terms)"
    elif and_matches > 0:
        quality_info = "(all match all search terms)"
    else:
        quality_info = "(all match some search terms)"

    # Build main message with truncation info
    if displayed_matches < total_matches:
        match_info = f"MATCHING_LINES: {total_matches} total lines match search terms {quality_info} - showing first {displayed_matches}"
    else:
        match_info = (
            f"MATCHING_LINES: {total_matches} lines match search terms {quality_info}"
        )

    # Add search terms info
    if search_terms:
        terms_str = ", ".join(f'"{term}"' for term in search_terms[:3])
        if len(search_terms) > 3:
            terms_str += f" (+{len(search_terms)-3} more)"
        match_info += f" [{terms_str}]"

    preview_parts.append(match_info)
    preview_parts.append("")
    preview_parts.append(matching_preview)

    return "\n".join(preview_parts)


def format_timestamp(
    timestamp: Optional[Union[int, datetime.datetime]],
    format_str: str = "%Y-%m-%d %H:%M:%S",
) -> Optional[str]:
    """Format a timestamp safely."""
    if not timestamp:
        return None
    try:
        if isinstance(timestamp, datetime.datetime):
            return timestamp.strftime(format_str)
        elif isinstance(timestamp, int):
            return datetime.datetime.fromtimestamp(timestamp / 1000).strftime(
                format_str
            )
        else:
            return None
    except:
        return None


def calculate_content_stats(body: str) -> Dict[str, int]:
    """Calculate content statistics for a note body.

    Args:
        body: The note content to analyze

    Returns:
        Dict with keys: 'characters', 'words', 'lines'
    """
    if not body:
        return {"characters": 0, "words": 0, "lines": 0}

    # Character count (including whitespace and special characters)
    char_count = len(body)

    # Line count
    line_count = len(body.split("\n"))

    # Word count (split by whitespace and filter empty strings)
    words = [word for word in body.split() if word.strip()]
    word_count = len(words)

    return {"characters": char_count, "words": word_count, "lines": line_count}


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


def format_no_results_message(item_type: str, context: str = "") -> str:
    """Format a standardized no results message optimized for LLM comprehension."""
    return f"ITEM_TYPE: {item_type}\nTOTAL_ITEMS: 0\nCONTEXT: {context}\nSTATUS: No {item_type}s found"


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


def get_notebook_id_by_name(name: str) -> str:
    """Get notebook ID by name with helpful error messages.

    Args:
        name: The notebook name to search for

    Returns:
        str: The notebook ID

    Raises:
        ValueError: If notebook not found or multiple matches
    """
    client = get_joplin_client()

    # Find notebook by name
    fields_list = "id,title,created_time,updated_time,parent_id"
    all_notebooks = client.get_all_notebooks(fields=fields_list)
    matching_notebooks = [
        nb for nb in all_notebooks if getattr(nb, "title", "").lower() == name.lower()
    ]

    if not matching_notebooks:
        available_notebooks = [getattr(nb, "title", "Untitled") for nb in all_notebooks]
        raise ValueError(
            f"Notebook '{name}' not found. Available notebooks: {', '.join(available_notebooks)}"
        )

    if len(matching_notebooks) > 1:
        notebook_details = [
            f"'{getattr(nb, 'title', 'Untitled')}' (ID: {getattr(nb, 'id', 'unknown')})"
            for nb in matching_notebooks
        ]
        raise ValueError(
            f"Multiple notebooks found with name '{name}': {', '.join(notebook_details)}. Please be more specific."
        )

    notebook_id = getattr(matching_notebooks[0], "id", None)
    if not notebook_id:
        raise ValueError(f"Could not get ID for notebook '{name}'")

    return notebook_id


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

    # Find tag by name
    tag_fields_list = "id,title,created_time,updated_time"
    all_tags = client.get_all_tags(fields=tag_fields_list)
    matching_tags = [
        tag for tag in all_tags if getattr(tag, "title", "").lower() == name.lower()
    ]

    if not matching_tags:
        available_tags = [getattr(tag, "title", "Untitled") for tag in all_tags]
        raise ValueError(
            f"Tag '{name}' not found. Available tags: {', '.join(available_tags)}. Use create_tag to create a new tag."
        )

    if len(matching_tags) > 1:
        tag_details = [
            f"'{getattr(tag, 'title', 'Untitled')}' (ID: {getattr(tag, 'id', 'unknown')})"
            for tag in matching_tags
        ]
        raise ValueError(
            f"Multiple tags found with name '{name}': {', '.join(tag_details)}. Please be more specific."
        )

    tag_id = getattr(matching_tags[0], "id", None)
    if not tag_id:
        raise ValueError(f"Could not get ID for tag '{name}'")

    return tag_id


# === FORMATTING UTILITIES ===


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
    result_parts = _format_note_metadata_lines(metadata, style="upper")

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


def _build_pagination_header(
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
        _format_note_metadata_lines(metadata, style="lower", indent="  ")
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


def _build_pagination_summary(total_count: int, limit: int, offset: int) -> List[str]:
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


def _format_find_in_note_summary(
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


def _format_note_metadata_lines(
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
    parts.extend(_format_note_metadata_lines(metadata, style="upper"))

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
            _format_find_in_note_summary(
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
    result_parts = _build_pagination_header(query, total_count, limit, offset)

    # Add note entries
    for i, note in enumerate(results, 1):
        result_parts.extend(
            _format_note_entry(
                note, i, config, context, original_query, query, notebooks_map
            )
        )

    # Add pagination summary
    result_parts.extend(_build_pagination_summary(total_count, limit, offset))

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


# === NOTE OPERATIONS ===


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
    # Runtime validation for Jan AI compatibility while preserving functionality
    note_id = validate_joplin_id(note_id)

    client = get_joplin_client()

    # Get the note
    note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)

    note_title = getattr(note, "title", "Untitled")
    body = getattr(note, "body", "")

    # Parse outgoing links using regex (with optional section slugs)
    import re

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
                except:
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
                        target_note_id = match.group(2)
                        section_slug = match.group(3) if match.group(3) else None

                        # Only include if this link points to our note
                        if target_note_id == note_id:
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
    notebook_name: Annotated[RequiredStringType, Field(description="Notebook name")],
    body: Annotated[str, Field(description="Note content")] = "",
    is_todo: Annotated[
        OptionalBoolType, Field(description="Create as todo (default: False)")
    ] = False,
    todo_completed: Annotated[
        OptionalBoolType, Field(description="Mark todo as completed (default: False)")
    ] = False,
) -> str:
    """Create a new note in a specified notebook in Joplin.

    Creates a new note with the specified title, content, and properties. Uses notebook name
    for easier identification instead of requiring notebook IDs.

    Returns:
        str: Success message with the created note's title and unique ID.

    Examples:
        - create_note("Shopping List", "Personal Notes", "- Milk\n- Eggs", True, False) - Create uncompleted todo
        - create_note("Meeting Notes", "Work Projects", "# Meeting with Client") - Create regular note
    """

    # Runtime validation for Jan AI compatibility while preserving functionality
    is_todo = flexible_bool_converter(is_todo)
    todo_completed = flexible_bool_converter(todo_completed)

    # Use helper function to get notebook ID
    parent_id = get_notebook_id_by_name(notebook_name)

    client = get_joplin_client()
    note = client.add_note(
        title=title,
        body=body,
        parent_id=parent_id,
        is_todo=1 if is_todo else 0,
        todo_completed=1 if todo_completed else 0,
    )
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
) -> str:
    """Update an existing note in Joplin.

    Updates one or more properties of an existing note. At least one field must be provided.

    Returns:
        str: Success message confirming the note was updated.

    Examples:
        - update_note("note123", title="New Title") - Update only the title
        - update_note("note123", body="New content", is_todo=True) - Update content and convert to todo
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

    if not update_data:
        raise ValueError("At least one field must be provided for update")

    client = get_joplin_client()
    client.modify_note(note_id, **update_data)
    return format_update_success(ItemType.note, note_id)


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
    """Find notes by searching their titles and content, with support for listing all notes and pagination.

    ⭐ MAIN FUNCTION FOR TEXT SEARCHES AND LISTING ALL NOTES!

    Versatile search function that can find specific text in notes OR list all notes with filtering and pagination.
    Use query="*" to list all notes without text filtering. Use specific text to find notes containing those words.

    Returns:
        str: List of notes matching criteria, with title, ID, content preview, and dates.
             Includes pagination info (total results, current page range).

    Examples:
        - find_notes("*") - List first 20 notes (all notes)
        - find_notes("meeting") - Find all notes containing "meeting"
        - find_notes("*", task=True) - List all tasks
        - find_notes("*", limit=20, offset=20) - List notes 21-40 (page 2)

        💡 TIP: For tag-specific searches, use find_notes_with_tag("tag_name") instead.
        💡 TIP: For notebook-specific searches, use find_notes_in_notebook("notebook_name") instead.
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
        header_parts.extend(_build_pagination_summary(0, limit, offset))
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

    def _pos_to_line_col(pos: int) -> tuple[int, int]:
        idx = bisect_right(line_offsets, pos) - 1
        if idx < 0:
            idx = 0
        line_start = line_offsets[idx]
        column = (pos - line_start) + 1
        return idx, column

    def _build_context(start_pos: int, end_pos: int) -> tuple[str, int]:
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
        result_parts.extend(_build_pagination_summary(0, limit, offset))
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
        result_parts.extend(_build_pagination_summary(total_count, limit, offset))
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

    result_parts.extend(_build_pagination_summary(total_count, limit, offset))

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

    ⭐ MAIN FUNCTION FOR TAG SEARCHES!

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
    search_parts = [f"tag:{tag_name}"]
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
        RequiredStringType, Field(description="Notebook name to search in")
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

    ⭐ MAIN FUNCTION FOR NOTEBOOK SEARCHES!

    Use this when you want to find all notes in a specific notebook.

    Returns:
        str: List of all notes in the specified notebook, with pagination information.

    Examples:
        - find_notes_in_notebook("Work Projects") - Find all notes in "Work Projects"
        - find_notes_in_notebook("Personal Notes", limit=10, offset=10) - Find notes in "Personal Notes" (page 2)
        - find_notes_in_notebook("Personal Notes", task=True) - Find only tasks in "Personal Notes"
        - find_notes_in_notebook("Projects", task=True, completed=False) - Find only uncompleted tasks in "Projects"
    """

    # Build search query with notebook and filters
    search_parts = [f"notebook:{notebook_name}"]
    search_parts.extend(build_search_filters(task, completed))
    search_query = " ".join(search_parts)

    # Use search_all API with notebook constraint for full pagination support
    client = get_joplin_client()
    results = client.search_all(query=search_query, fields=COMMON_NOTE_FIELDS)
    notes = process_search_results(results)

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


# === NOTEBOOK OPERATIONS ===


@create_tool("list_notebooks", "List notebooks")
async def list_notebooks() -> str:
    """List all notebooks/folders in your Joplin instance.

    Retrieves and displays all notebooks (folders) in your Joplin application.

    Returns:
        str: Formatted list of all notebooks including title, unique ID, parent notebook (if sub-notebook), and creation date.
    """
    client = get_joplin_client()
    fields_list = "id,title,created_time,updated_time,parent_id"
    notebooks = client.get_all_notebooks(fields=fields_list)
    return format_item_list(notebooks, ItemType.notebook)


@create_tool("create_notebook", "Create notebook")
async def create_notebook(
    title: Annotated[RequiredStringType, Field(description="Notebook title")],
    parent_id: Annotated[
        Optional[str], Field(description="Parent notebook ID (optional)")
    ] = None,
) -> str:
    """Create a new notebook (folder) in Joplin to organize your notes.

    Creates a new notebook that can be used to organize and contain notes. You can create
    top-level notebooks or sub-notebooks within existing notebooks.

    Returns:
        str: Success message containing the created notebook's title and unique ID.

    Examples:
        - create_notebook("Work Projects") - Create a top-level notebook
        - create_notebook("2024 Projects", "work_notebook_id") - Create a sub-notebook
    """

    client = get_joplin_client()
    notebook_kwargs = {"title": title}
    if parent_id:
        notebook_kwargs["parent_id"] = parent_id.strip()

    notebook = client.add_notebook(**notebook_kwargs)
    # Invalidate notebook path cache to reflect new structure immediately
    invalidate_notebook_map_cache()
    return format_creation_success(ItemType.notebook, title, str(notebook))


@create_tool("update_notebook", "Update notebook")
async def update_notebook(
    notebook_id: Annotated[JoplinIdType, Field(description="Notebook ID to update")],
    title: Annotated[RequiredStringType, Field(description="New notebook title")],
) -> str:
    """Update an existing notebook.

    Updates the title of an existing notebook. Currently only the title can be updated.

    Returns:
        str: Success message confirming the notebook was updated.
    """
    client = get_joplin_client()
    client.modify_notebook(notebook_id, title=title)
    # Invalidate cache in case the notebook moved/renamed
    invalidate_notebook_map_cache()
    return format_update_success(ItemType.notebook, notebook_id)


@create_tool("delete_notebook", "Delete notebook")
async def delete_notebook(
    notebook_id: Annotated[JoplinIdType, Field(description="Notebook ID to delete")],
) -> str:
    """Delete a notebook from Joplin.

    Permanently removes a notebook from Joplin. This action cannot be undone.

    Returns:
        str: Success message confirming the notebook was deleted.

    Warning: This action is permanent and cannot be undone. All notes in the notebook will also be deleted.
    """
    client = get_joplin_client()
    client.delete_notebook(notebook_id)
    # Invalidate cache since structure changed
    invalidate_notebook_map_cache()
    return format_delete_success(ItemType.notebook, notebook_id)


# === TAG OPERATIONS ===


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


# Primary tag operations
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


# === IMPORT TOOLS ===


@create_tool("import_from_file", "Import from file")
async def import_from_file(
    file_path: Annotated[str, Field(description="Path to the file to import")],
    format: Annotated[
        Optional[str],
        Field(description="File format (md, html, csv, jex, generic) - auto-detected if not specified"),
    ] = None,
    target_notebook: Annotated[
        Optional[str], Field(description="Target notebook name (optional, defaults to 'Imported')")
    ] = 'Imported',
    import_options: Annotated[
        Optional[Union[Dict[str, Any], str]],
        Field(description="Additional import options (object/dict; string is auto-parsed)")
    ] = None,
) -> str:
    """Import notes from a file or directory.

    - Formats: md, html, csv, jex, generic (auto-detected if omitted).
    - Directories: recursive; RAW exports auto-detected; mixed dirs supported.
    - import_options (dict, not JSON string). Common: csv_import_mode (table|rows),
      csv_delimiter (e.g., ";"), extract_hashtags (bool).
      In csv row mode, each note body is YAML frontmatter built from the row.

    Returns a compact result summary with counts and errors/warnings.

    Examples:
      import_from_file("/path/note.md")
      import_from_file("/path/data.csv", format="csv", target_notebook="CSV Rows",
                       import_options={"csv_import_mode": "rows"})
    """
    # Import required modules (lazy import to avoid circular dependencies)
    from pathlib import Path

    from .import_engine import JoplinImportEngine
    from .importers.base import ImportProcessingError, ImportValidationError
    from .types.import_types import ImportOptions
    from .import_tools import (
        format_import_result,
        get_importer_for_format,
        detect_file_format,
        detect_directory_format,
    )

    try:
        # Load configuration
        config = JoplinMCPConfig.load()

        # Validate file path (support both files and directories)
        path = Path(file_path)
        if not path.exists():
            return format_import_result(type('Result', (), {
                'is_complete_success': False,
                'is_partial_success': False,
                'total_processed': 0,
                'successful_imports': 0,
                'failed_imports': 0,
                'skipped_items': 0,
                'processing_time': 0.0,
                'created_notebooks': [],
                'created_tags': [],
                'errors': [f"Path does not exist: {file_path}"],
                'warnings': []
            })(), "IMPORT_FROM_FILE")
        if not (path.is_file() or path.is_dir()):
            return format_import_result(type('Result', (), {
                'is_complete_success': False,
                'is_partial_success': False,
                'total_processed': 0,
                'successful_imports': 0,
                'failed_imports': 0,
                'skipped_items': 0,
                'processing_time': 0.0,
                'created_notebooks': [],
                'created_tags': [],
                'errors': [f"Path is neither a file nor directory: {file_path}"],
                'warnings': []
            })(), "IMPORT_FROM_FILE")

        # Detect format if not specified
        if not format:
            if path.is_file():
                try:
                    format = detect_file_format(file_path)
                except ValueError:
                    format = "generic"
            else:
                # For directories, detect format (raw, md, html, csv) with fallback to generic
                try:
                    format = detect_directory_format(file_path)
                except Exception:
                    format = "generic"

        # Create import options
        base_options = ImportOptions(
            target_notebook=target_notebook,
            create_missing_notebooks=config.import_settings.get(
                "create_missing_notebooks", True
            ),
            create_missing_tags=config.import_settings.get("create_missing_tags", True),
            preserve_timestamps=config.import_settings.get("preserve_timestamps", True),
            handle_duplicates=config.import_settings.get("handle_duplicates", "skip"),
            max_batch_size=config.import_settings.get("max_batch_size", 100),
            attachment_handling=config.import_settings.get(
                "attachment_handling", "embed"
            ),
            max_file_size_mb=config.import_settings.get("max_file_size_mb", 100),
        )

        # Apply additional options (accept dict or JSON/Python-dict string)
        if import_options:
            if isinstance(import_options, str):
                try:
                    import json, ast
                    try:
                        parsed = json.loads(import_options)
                    except json.JSONDecodeError:
                        parsed = ast.literal_eval(import_options)
                    if isinstance(parsed, dict):
                        import_options = parsed
                    else:
                        return "VALIDATION_ERROR: import_options string did not parse to an object"
                except Exception:
                    return "VALIDATION_ERROR: import_options must be an object or JSON/dict string"
            # Merge structured options
            for key, value in import_options.items():
                if hasattr(base_options, key):
                    setattr(base_options, key, value)
                else:
                    base_options.import_options[key] = value

        # Get appropriate importer
        importer = get_importer_for_format(format, base_options)

        # If importing a directory with an importer that doesn't support directories,
        # fall back to GenericImporter which can delegate per-file.
        if path.is_dir() and hasattr(importer, "supports_directory"):
            try:
                if not importer.supports_directory():
                    from .importers.generic_importer import GenericImporter as _Generic
                    importer = _Generic(base_options)
            except Exception:
                pass

        # Validate and parse file
        try:
            await importer.validate(file_path)
            notes = await importer.parse(file_path)
        except ImportValidationError as e:
            return f"VALIDATION_ERROR: {str(e)}"
        except ImportProcessingError as e:
            return f"PROCESSING_ERROR: {str(e)}"
        except Exception as e:
            return f"ERROR: Unexpected error during parsing: {str(e)}"

        if not notes:
            return "WARNING: No notes were extracted from the file"

        # Import notes using the import engine
        try:
            client = get_joplin_client()
            engine = JoplinImportEngine(client, config)
            result = await engine.import_batch(notes, base_options)
        except Exception as e:
            return f"ERROR: Import engine failed: {str(e)}"

        # Format and return result
        return format_import_result(result, "IMPORT_FROM_FILE")

    except Exception as e:
        logger.error(f"import_from_file failed: {e}")
        return f"ERROR: Tool execution failed: {str(e)}"


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
