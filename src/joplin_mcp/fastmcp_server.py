"""FastMCP-based Joplin MCP Server Implementation.

📝 FINDING NOTES:
- find_notes(query, limit, offset, task, completed) - Find notes by text OR list all notes with pagination ⭐ MAIN FUNCTION FOR TEXT SEARCHES AND LISTING ALL NOTES!
- find_notes_with_tag(tag_name, limit, offset, task, completed) - Find all notes with a specific tag with pagination ⭐ MAIN FUNCTION FOR TAG SEARCHES!
- find_notes_in_notebook(notebook_name, limit, offset, task, completed) - Find all notes in a specific notebook with pagination ⭐ MAIN FUNCTION FOR NOTEBOOK SEARCHES!
- get_all_notes() - Get all notes, most recent first (simple version without pagination)

📋 MANAGING NOTES:
- create_note(title, notebook_name, body) - Create a new note
- get_note(note_id) - Get a specific note by ID
- get_links(note_id) - Extract all links to other notes from a note
- update_note(note_id, title, body) - Update an existing note
- delete_note(note_id) - Delete a note

🏷️ MANAGING TAGS:
- list_tags() - List all available tags
- tag_note(note_id, tag_name) - Add a tag to a note
- untag_note(note_id, tag_name) - Remove a tag from a note
- get_tags_by_note(note_id) - See what tags a note has

📁 MANAGING NOTEBOOKS:
- list_notebooks() - List all available notebooks
- create_notebook(title) - Create a new notebook
"""

import os
import logging
import datetime
from typing import Optional, List, Dict, Any, Callable, TypeVar, Union, Annotated
from enum import Enum
from functools import wraps

# FastMCP imports
from fastmcp import FastMCP, Context

# Pydantic imports for proper Field annotations
from pydantic import Field

# Direct joppy import
from joppy.client_api import ClientApi

# Import our existing configuration for compatibility
from joplin_mcp.config import JoplinMCPConfig
from joplin_mcp import __version__ as MCP_VERSION

# Configure logging
logger = logging.getLogger(__name__)

# Create FastMCP server instance
mcp = FastMCP("Joplin MCP Server")

# Type for generic functions
T = TypeVar('T')

# Global config instance for tool registration
_config: Optional[JoplinMCPConfig] = None

# Load configuration at module level for tool filtering
def _load_module_config() -> JoplinMCPConfig:
    """Load configuration at module level for tool registration filtering."""
    import os
    from pathlib import Path
    
    # Get the current working directory and script directory
    cwd = Path.cwd()
    script_dir = Path(__file__).parent.parent.parent  # Go up to project root
    
    # List of paths to try for configuration file
    config_paths = [
        cwd / "joplin-mcp.json",
        script_dir / "joplin-mcp.json",
        Path("/Users/alondmnt/projects/joplin/mcp/joplin-mcp.json"),  # Absolute path as fallback
    ]
    
    # Try each path
    for config_path in config_paths:
        if config_path.exists():
            try:
                logger.info(f"Loading configuration from: {config_path}")
                config = JoplinMCPConfig.from_file(config_path)
                logger.info(f"Successfully loaded config from {config_path}")
                return config
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")
                continue
    
    # If no config file found, use defaults from config module
    logger.warning("No configuration file found. Using safe default configuration.")
    return JoplinMCPConfig()

# Load config for tool registration filtering
_module_config = _load_module_config()

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

# === UTILITY FUNCTIONS ===

def get_joplin_client() -> ClientApi:
    """Get a configured joppy client instance."""
    try:
        config = JoplinMCPConfig.load()
        if config.token:
            return ClientApi(token=config.token, url=config.base_url)
        else:
            token = os.getenv("JOPLIN_TOKEN")
            if not token:
                raise ValueError("No token found in config file or JOPLIN_TOKEN environment variable")
            return ClientApi(token=token, url=config.base_url)
    except Exception:
        token = os.getenv("JOPLIN_TOKEN")
        if not token:
            raise ValueError("JOPLIN_TOKEN environment variable is required")
        url = os.getenv("JOPLIN_URL", "http://localhost:41184")
        return ClientApi(token=token, url=url)

def validate_required_param(value: str, param_name: str) -> str:
    """Validate that a parameter is provided and not empty."""
    if not value or not value.strip():
        raise ValueError(f"{param_name} parameter is required and cannot be empty")
    return value.strip()

def validate_limit(limit: int) -> int:
    """Validate limit parameter."""
    if not (1 <= limit <= 100):
        raise ValueError("Limit must be between 1 and 100")
    return limit

def validate_offset(offset: int) -> int:
    """Validate offset parameter."""
    if offset < 0:
        raise ValueError("Offset must be 0 or greater")
    return offset

def apply_pagination(notes: List[Any], limit: int, offset: int) -> tuple[List[Any], int]:
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

def format_search_criteria(base_criteria: str, task: Optional[bool], completed: Optional[bool]) -> str:
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

def format_no_results_with_pagination(item_type: str, criteria: str, offset: int, limit: int) -> str:
    """Format no results message with pagination info."""
    if offset > 0:
        page_info = f" - Page {(offset // limit) + 1} (offset {offset})"
        return format_no_results_message(item_type, criteria + page_info)
    else:
        return format_no_results_message(item_type, criteria)

# Common fields list for note operations
COMMON_NOTE_FIELDS = "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed"

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
    
    lines = body.split('\n')
    headings = []
    
    # Regex patterns
    heading_pattern = r'^(#{1,6})\s+(.+)$'
    code_block_pattern = r'^(```|~~~)'
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
                
                headings.append({
                    'level': level,
                    'title': title,
                    'line_idx': abs_line_idx,
                    'relative_line_idx': rel_line_idx,
                    'original_line': line,
                    'markdown': f"{hashes} {title}"
                })
    
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
    lines = body.split('\n')
    
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
            title_lower = heading['title'].lower()
            if title_lower == identifier_lower:
                target_heading = heading
                break
        
        # Priority 2: Try slug matches only if no exact match found
        if not target_heading:
            # Convert identifier to slug format
            identifier_slug = re.sub(r'[^\w\s-]', '', identifier_lower)
            identifier_slug = re.sub(r'[-\s_]+', '-', identifier_slug).strip('-')
            
            for heading in headings:
                title_lower = heading['title'].lower()
                
                # Convert title to slug and compare
                title_slug = re.sub(r'[^\w\s-]', '', title_lower)  # Remove special chars
                title_slug = re.sub(r'[-\s]+', '-', title_slug).strip('-')  # Normalize spaces/hyphens
                
                # Only exact slug matches, not partial slug matches
                if title_slug == identifier_slug:
                    target_heading = heading
                    break
        
        # Priority 3: Try partial matches only if no slug match found
        if not target_heading:
            for heading in headings:
                title_lower = heading['title'].lower()
                if identifier_lower in title_lower:
                    target_heading = heading
                    break
    
    if not target_heading:
        return "", ""
    
    # Find content boundaries based on hierarchy
    start_line = target_heading['line_idx']
    end_line = len(lines)
    target_level = target_heading['level']
    
    # Find end of section: next heading at same level or higher
    for heading in headings:
        if heading['line_idx'] > start_line and heading['level'] <= target_level:
            end_line = heading['line_idx']
            break
    
    # Extract the section content
    section_lines = lines[start_line:end_line]
    section_content = '\n'.join(section_lines).strip()
    
    return section_content, target_heading['title']

def create_content_preview(body: str, max_length: int, include_toc: bool = True) -> str:
    """Create a content preview that preserves front matter if present and optionally includes table of contents.
    
    If the content starts with front matter (delimited by ---), includes the entire
    front matter in the preview. Then optionally extracts headings to create a table of contents,
    followed by regular content preview with remaining character budget.
    
    Args:
        body: The note content to create a preview for
        max_length: Maximum length for the preview (excluding front matter)
        include_toc: Whether to include table of contents in the preview
    
    Returns:
        str: The content preview with front matter, optional TOC, and content preview
    """
    if not body:
        return ""
    
    import re
    
    lines = body.split('\n')
    preview_parts = []
    front_matter_end = -1
    content_start_index = 0
    
    # Check if content starts with front matter
    if body.startswith('---'):
        # Find the closing front matter delimiter
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == '---':
                front_matter_end = i
                break
        
        if front_matter_end != -1:
            # Include the front matter up to 20 lines maximum
            front_matter_lines = lines[:front_matter_end + 1]
            if len(front_matter_lines) > 20:
                # Truncate front matter if it exceeds 20 lines
                # Keep opening --- + 18 lines of content + closing --- = 20 lines total
                front_matter_lines = lines[:19]  # Opening --- + 18 lines of content
                front_matter_lines.append('---')  # Add back the closing delimiter
            
            front_matter = '\n'.join(front_matter_lines)
            preview_parts.append(front_matter)
            content_start_index = front_matter_end + 1
    
    # Extract headings for table of contents from remaining content (if enabled)
    remaining_lines = lines[content_start_index:]
    remaining_content = '\n'.join(remaining_lines)
    
    if include_toc:
        # Parse headings from remaining content using helper function
        remaining_content = '\n'.join(remaining_lines)
        headings = parse_markdown_headings(remaining_content, content_start_index)
        
        # Create TOC entries
        toc_entries = []
        for heading in headings:
            level = heading['level']
            title = heading['title']
            
            # Create indentation based on heading level (level 1 = no indent, level 2 = 2 spaces, etc.)
            indent = '  ' * (level - 1)
            toc_entries.append(f"{indent}- {title}")
        
        # Add TOC if we found headings
        if toc_entries:
            toc_header = "TOC:"
            toc_content = '\n'.join(toc_entries)
            toc_section = f"{toc_header}\n{toc_content}"
            
            # Calculate dynamic TOC limit (up to full max_length, minimum 80 chars)
            # This allows TOC to use the full preview space when needed, while preventing excessive TOC size
            toc_max_length = max(80, int(max_length))
            
            if len(toc_section) > toc_max_length:
                # Truncate TOC entries if too long
                truncated_entries = []
                current_length = len(toc_header) + 1  # +1 for newline
                remaining_space = toc_max_length - current_length - 3  # Leave 3 chars for "..."
                
                for entry in toc_entries:
                    if current_length + len(entry) + 1 <= remaining_space:
                        truncated_entries.append(entry)
                        current_length += len(entry) + 1
                    else:
                        break
                
                if len(truncated_entries) < len(toc_entries):
                    truncated_entries.append("  ...")
                
                toc_section = f"{toc_header}\n" + '\n'.join(truncated_entries)
            
            preview_parts.append(toc_section)
    
    # Calculate remaining space for content preview
    used_space = sum(len(part) + 1 for part in preview_parts)  # +1 for newlines between parts
    remaining_space = max(50, max_length - used_space)  # Ensure at least 50 chars for content
    
    # Add content preview with remaining space
    if remaining_content:
        content_preview = remaining_content.strip()
        if len(content_preview) > remaining_space:
            content_preview = content_preview[:remaining_space] + "..."
        
        # Only add content preview if it's meaningful (more than just "...")
        if len(content_preview.replace("...", "").strip()) > 10:
            preview_parts.append(content_preview)
    
    # If no meaningful content remains after TOC, and no front matter, show regular preview
    if not preview_parts:
        preview = body[:max_length]
        if len(body) > max_length:
            preview += "..."
        return preview
    
    return '\n\n'.join(preview_parts)

def validate_boolean_param(value: Union[bool, str, None], param_name: str) -> Optional[bool]:
    """Validate and convert boolean parameter that might come as string."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        value_lower = value.lower().strip()
        if value_lower in ('true', '1', 'yes', 'on'):
            return True
        elif value_lower in ('false', '0', 'no', 'off'):
            return False
        else:
            raise ValueError(f"{param_name} must be a boolean value or string representation (true/false, 1/0, yes/no, on/off)")
    # Handle non-None values that are not boolean or string (e.g., default values)
    if value is False:
        return False
    elif value is True:
        return True
    raise ValueError(f"{param_name} must be a boolean value or string representation")

def format_timestamp(timestamp: Optional[Union[int, datetime.datetime]], format_str: str = "%Y-%m-%d %H:%M:%S") -> Optional[str]:
    """Format a timestamp safely."""
    if not timestamp:
        return None
    try:
        if isinstance(timestamp, datetime.datetime):
            return timestamp.strftime(format_str)
        elif isinstance(timestamp, int):
            return datetime.datetime.fromtimestamp(timestamp / 1000).strftime(format_str)
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
        return {'characters': 0, 'words': 0, 'lines': 0}
    
    # Character count (including whitespace and special characters)
    char_count = len(body)
    
    # Line count
    line_count = len(body.split('\n'))
    
    # Word count (split by whitespace and filter empty strings)
    words = [word for word in body.split() if word.strip()]
    word_count = len(words)
    
    return {
        'characters': char_count,
        'words': word_count, 
        'lines': line_count
    }

def process_search_results(results: Any) -> List[Any]:
    """Process search results from joppy client into a consistent list format."""
    if hasattr(results, 'items'):
        return results.items or []
    elif isinstance(results, list):
        return results
    else:
        return [results] if results else []

def filter_items_by_title(items: List[Any], query: str) -> List[Any]:
    """Filter items by title using case-insensitive search."""
    return [
        item for item in items 
        if query.lower() in getattr(item, 'title', '').lower()
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
        if _module_config.tools.get(tool_name, True):  # Default to True if not specified
            # Tool is enabled - register it with FastMCP
            return mcp.tool()(func)
        else:
            # Tool is disabled - return function without registering
            logger.info(f"Tool '{tool_name}' disabled in configuration - not registering")
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
    name = validate_required_param(name, "notebook_name")
    client = get_joplin_client()
    
    # Find notebook by name
    fields_list = "id,title,created_time,updated_time,parent_id"
    all_notebooks = client.get_all_notebooks(fields=fields_list)
    matching_notebooks = [nb for nb in all_notebooks if getattr(nb, 'title', '').lower() == name.lower()]
    
    if not matching_notebooks:
        available_notebooks = [getattr(nb, 'title', 'Untitled') for nb in all_notebooks]
        raise ValueError(f"Notebook '{name}' not found. Available notebooks: {', '.join(available_notebooks)}")
    
    if len(matching_notebooks) > 1:
        notebook_details = [f"'{getattr(nb, 'title', 'Untitled')}' (ID: {getattr(nb, 'id', 'unknown')})" for nb in matching_notebooks]
        raise ValueError(f"Multiple notebooks found with name '{name}': {', '.join(notebook_details)}. Please be more specific.")
    
    notebook_id = getattr(matching_notebooks[0], 'id', None)
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
    name = validate_required_param(name, "tag_name")
    client = get_joplin_client()
    
    # Find tag by name
    tag_fields_list = "id,title,created_time,updated_time"
    all_tags = client.get_all_tags(fields=tag_fields_list)
    matching_tags = [tag for tag in all_tags if getattr(tag, 'title', '').lower() == name.lower()]
    
    if not matching_tags:
        available_tags = [getattr(tag, 'title', 'Untitled') for tag in all_tags]
        raise ValueError(f"Tag '{name}' not found. Available tags: {', '.join(available_tags)}. Use create_tag to create a new tag.")
    
    if len(matching_tags) > 1:
        tag_details = [f"'{getattr(tag, 'title', 'Untitled')}' (ID: {getattr(tag, 'id', 'unknown')})" for tag in matching_tags]
        raise ValueError(f"Multiple tags found with name '{name}': {', '.join(tag_details)}. Please be more specific.")
    
    tag_id = getattr(matching_tags[0], 'id', None)
    if not tag_id:
        raise ValueError(f"Could not get ID for tag '{name}'")
    
    return tag_id

# === FORMATTING UTILITIES ===

def get_item_emoji(item_type: ItemType) -> str:
    """Get emoji for item type."""
    emoji_map = {
        ItemType.note: "📝",
        ItemType.notebook: "📁",
        ItemType.tag: "🏷️"
    }
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

def format_relation_success(operation: str, item1_type: ItemType, item1_id: str, item2_type: ItemType, item2_id: str) -> str:
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
    result_parts = [
        f"ITEM_TYPE: {item_type.value}",
        f"TOTAL_ITEMS: {count}",
        ""
    ]
    
    for i, item in enumerate(items, 1):
        title = getattr(item, 'title', 'Untitled')
        item_id = getattr(item, 'id', 'unknown')
        
        # Structured item entry
        result_parts.extend([
            f"ITEM_{i}:",
            f"  {item_type.value}_id: {item_id}",
            f"  title: {title}",
        ])
        
        # Add parent folder ID if available (for notebooks)
        parent_id = getattr(item, 'parent_id', None)
        if parent_id:
            result_parts.append(f"  parent_id: {parent_id}")
        
        # Add creation time if available
        created_time = getattr(item, 'created_time', None)
        if created_time:
            created_date = format_timestamp(created_time, "%Y-%m-%d %H:%M")
            if created_date:
                result_parts.append(f"  created: {created_date}")
        
        # Add update time if available
        updated_time = getattr(item, 'updated_time', None)
        if updated_time:
            updated_date = format_timestamp(updated_time, "%Y-%m-%d %H:%M")
            if updated_date:
                result_parts.append(f"  updated: {updated_date}")
        
        result_parts.append("")
    
    return "\n".join(result_parts)

def format_item_details(item: Any, item_type: ItemType) -> str:
    """Format a single item (notebook, tag, etc.) for detailed display."""
    emoji = get_item_emoji(item_type)
    title = getattr(item, 'title', 'Untitled')
    item_id = getattr(item, 'id', 'unknown')
    
    result_parts = [f"{emoji} **{title}**", f"ID: {item_id}", ""]
    
    # Add metadata
    metadata = []
    
    # Timestamps
    created_time = getattr(item, 'created_time', None)
    if created_time:
        created_date = format_timestamp(created_time)
        if created_date:
            metadata.append(f"Created: {created_date}")
    
    updated_time = getattr(item, 'updated_time', None)
    if updated_time:
        updated_date = format_timestamp(updated_time)
        if updated_date:
            metadata.append(f"Updated: {updated_date}")
    
    # Parent (for notebooks)
    parent_id = getattr(item, 'parent_id', None)
    if parent_id:
        metadata.append(f"Parent: {parent_id}")
    
    if metadata:
        result_parts.append("**Metadata:**")
        result_parts.extend(f"- {m}" for m in metadata)
    
    return "\n".join(result_parts)

def format_note_details(note: Any, include_body: bool = True, context: str = "individual_notes") -> str:
    """Format a note for detailed display optimized for LLM comprehension."""
    title = getattr(note, 'title', 'Untitled')
    note_id = getattr(note, 'id', 'unknown')
    
    # Check content exposure settings
    config = _module_config
    should_show_content = config.should_show_content(context)
    should_show_full_content = config.should_show_full_content(context)
    
    # Structured note details - metadata first
    result_parts = [
        f"NOTE_ID: {note_id}",
        f"TITLE: {title}",
    ]
    
    # Add structured metadata first
    created_time = getattr(note, 'created_time', None)
    if created_time:
        created_date = format_timestamp(created_time)
        if created_date:
            result_parts.append(f"CREATED: {created_date}")
    
    updated_time = getattr(note, 'updated_time', None)
    if updated_time:
        updated_date = format_timestamp(updated_time)
        if updated_date:
            result_parts.append(f"UPDATED: {updated_date}")
    
    # Notebook reference
    parent_id = getattr(note, 'parent_id', None)
    if parent_id:
        result_parts.append(f"NOTEBOOK_ID: {parent_id}")
    
    # Todo status
    is_todo = getattr(note, 'is_todo', 0)
    if is_todo:
        result_parts.append("IS_TODO: true")
        todo_completed = getattr(note, 'todo_completed', 0)
        result_parts.append(f"TODO_COMPLETED: {'true' if todo_completed else 'false'}")
    else:
        result_parts.append("IS_TODO: false")
    
    # Add content size statistics
    body = getattr(note, 'body', '')
    content_stats = calculate_content_stats(body)
    result_parts.append(f"CONTENT_SIZE_CHARS: {content_stats['characters']}")
    result_parts.append(f"CONTENT_SIZE_WORDS: {content_stats['words']}")
    result_parts.append(f"CONTENT_SIZE_LINES: {content_stats['lines']}")
    
    # Add content last to avoid breaking metadata flow
    if include_body and should_show_content:
        body = getattr(note, 'body', '')
        if body:
            if should_show_full_content:
                result_parts.append(f"CONTENT: {body}")
            else:
                # Show preview only
                max_length = config.get_max_preview_length()
                include_toc = config.should_include_toc()
                preview = create_content_preview(body, max_length, include_toc)
                result_parts.append(f"CONTENT_PREVIEW: {preview}")
        else:
            result_parts.append("CONTENT: (empty)")
    
    return "\n".join(result_parts)


def format_search_results_with_pagination(query: str, results: List[Any], total_count: int, limit: int, offset: int, context: str = "search_results") -> str:
    """Format search results with pagination information for display optimized for LLM comprehension."""
    count = len(results)
    
    # Check content exposure settings
    config = _module_config
    should_show_content = config.should_show_content(context)
    should_show_full_content = config.should_show_full_content(context)
    max_preview_length = config.get_max_preview_length()
    include_toc = config.should_include_toc()
    
    # Calculate pagination info
    current_page = (offset // limit) + 1
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
    start_result = offset + 1 if count > 0 else 0
    end_result = offset + count
    
    # Start with structured header including pagination
    result_parts = [
        f"SEARCH_QUERY: {query}",
        f"TOTAL_RESULTS: {total_count}",
        f"SHOWING_RESULTS: {start_result}-{end_result}",
        f"CURRENT_PAGE: {current_page}",
        f"TOTAL_PAGES: {total_pages}",
        f"LIMIT: {limit}",
        f"OFFSET: {offset}",
        ""
    ]
    
    # Add pagination guidance
    if total_count > end_result:
        next_offset = offset + limit
        result_parts.extend([
            f"NEXT_PAGE: Use offset={next_offset} to get the next {limit} results",
            ""
        ])
    
    for i, note in enumerate(results, 1):
        title = getattr(note, 'title', 'Untitled')
        note_id = getattr(note, 'id', 'unknown')
        
        # Structured note entry - metadata first
        result_parts.extend([
            f"RESULT_{i}:",
            f"  note_id: {note_id}",
            f"  title: {title}",
        ])
        
        # Add structured timestamps
        created_time = getattr(note, 'created_time', None)
        if created_time:
            created_date = format_timestamp(created_time, "%Y-%m-%d %H:%M")
            if created_date:
                result_parts.append(f"  created: {created_date}")
        
        updated_time = getattr(note, 'updated_time', None)
        if updated_time:
            updated_date = format_timestamp(updated_time, "%Y-%m-%d %H:%M")
            if updated_date:
                result_parts.append(f"  updated: {updated_date}")
        
        # Add notebook reference if available
        parent_id = getattr(note, 'parent_id', None)
        if parent_id:
            result_parts.append(f"  notebook_id: {parent_id}")
        
        # Add todo status
        is_todo = getattr(note, 'is_todo', 0)
        if is_todo:
            todo_completed = getattr(note, 'todo_completed', 0)
            result_parts.append(f"  is_todo: true")
            result_parts.append(f"  todo_completed: {'true' if todo_completed else 'false'}")
        else:
            result_parts.append(f"  is_todo: false")
        
        # Add content size statistics
        body = getattr(note, 'body', '')
        content_stats = calculate_content_stats(body)
        result_parts.append(f"  content_size_chars: {content_stats['characters']}")
        result_parts.append(f"  content_size_words: {content_stats['words']}")
        result_parts.append(f"  content_size_lines: {content_stats['lines']}")
        
        # Handle content last to avoid breaking metadata flow
        if should_show_content:
            body = getattr(note, 'body', '')
            if body:
                if should_show_full_content:
                    result_parts.append(f"  content: {body}")
                else:
                    # Show preview only
                    preview = create_content_preview(body, max_preview_length, include_toc)
                    result_parts.append(f"  content_preview: {preview}")
        
        result_parts.append("")
    
    # Add pagination summary at the end
    if total_pages > 1:
        result_parts.extend([
            f"PAGINATION_SUMMARY:",
            f"  showing_page: {current_page} of {total_pages}",
            f"  showing_results: {start_result}-{end_result} of {total_count}",
            f"  results_per_page: {limit}",
        ])
        
        if current_page < total_pages:
            next_offset = offset + limit
            result_parts.append(f"  next_page_offset: {next_offset}")
        
        if current_page > 1:
            prev_offset = max(0, offset - limit)
            result_parts.append(f"  prev_page_offset: {prev_offset}")
    
    return "\n".join(result_parts)

def format_tag_list_with_counts(tags: List[Any], client: Any) -> str:
    """Format a list of tags with note counts for display optimized for LLM comprehension."""
    if not tags:
        return "ITEM_TYPE: tag\nTOTAL_ITEMS: 0\nSTATUS: No tags found in Joplin instance"
    
    count = len(tags)
    result_parts = [
        "ITEM_TYPE: tag",
        f"TOTAL_ITEMS: {count}",
        ""
    ]
    
    for i, tag in enumerate(tags, 1):
        title = getattr(tag, 'title', 'Untitled')
        tag_id = getattr(tag, 'id', 'unknown')
        
        # Get note count for this tag
        try:
            notes_result = client.get_notes(tag_id=tag_id, fields=COMMON_NOTE_FIELDS)
            notes = process_search_results(notes_result)
            note_count = len(notes)
        except Exception:
            note_count = 0
        
        # Structured tag entry
        result_parts.extend([
            f"ITEM_{i}:",
            f"  tag_id: {tag_id}",
            f"  title: {title}",
            f"  note_count: {note_count}",
        ])
        
        # Add creation time if available
        created_time = getattr(tag, 'created_time', None)
        if created_time:
            created_date = format_timestamp(created_time, "%Y-%m-%d %H:%M")
            if created_date:
                result_parts.append(f"  created: {created_date}")
        
        # Add update time if available
        updated_time = getattr(tag, 'updated_time', None)
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

@create_tool("get_note", "Get note")
async def get_note(
    note_id: Annotated[str, Field(description="Note ID to retrieve")], 
    include_body: Annotated[Union[bool, str], Field(description="Include note content (default: True)")] = True,
    section: Annotated[Optional[str], Field(description="Extract specific section (heading text, slug, or number)")] = None
) -> str:
    """Retrieve a specific note by its unique identifier, optionally extracting a specific section.
    
    Fetches a single note from Joplin and returns its title, content, dates, and metadata.
    If a section is specified, extracts only that section's content based on markdown headings.
    
    Args:
        note_id: Unique identifier of the note
        include_body: Whether to include note content (default: True)
        section: Optional section to extract. Can be:
            - Section number: "1" (first heading), "2" (second heading), etc.
            - Heading text (case insensitive): "Introduction", "Getting Started"
            - Slug format: "introduction", "getting-started", "my_section"
            - Partial text: "config" matches "Configuration"
            Priority: Number → Exact → Slug → Partial
    
    Returns:
        str: Formatted note details including title, ID, content (if requested), and dates.
             If section is specified and found, only that section's content is included.
    
    Examples:
        - get_note("a1b2c3d4e5f6...") - Get full note with content
        - get_note("a1b2c3d4e5f6...", True, "Introduction") - Get only Introduction section
        - get_note("a1b2c3d4e5f6...", True, "getting-started") - Get section by slug
        - get_note("a1b2c3d4e5f6...", True, "1") - Get first section
        - get_note("a1b2c3d4e5f6...", False) - Get metadata only
    """
    note_id = validate_required_param(note_id, "note_id")
    include_body = validate_boolean_param(include_body, "include_body")
    client = get_joplin_client()
    
    # Use string format for fields (list format causes SQL errors)
    note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
    
    # Handle section extraction if requested
    if section and include_body:
        body = getattr(note, 'body', '')
        if body:
            section_content, section_title = extract_section_content(body, section)
            if section_content:
                # Create a modified note object with only the section content
                # We'll modify the body attribute for display
                note_dict = {
                    'id': getattr(note, 'id', ''),
                    'title': getattr(note, 'title', ''),
                    'body': section_content,
                    'created_time': getattr(note, 'created_time', None),
                    'updated_time': getattr(note, 'updated_time', None),
                    'parent_id': getattr(note, 'parent_id', None),
                    'is_todo': getattr(note, 'is_todo', 0),
                    'todo_completed': getattr(note, 'todo_completed', 0)
                }
                
                # Create a simple object to hold the modified data
                class SectionNote:
                    def __init__(self, data):
                        for key, value in data.items():
                            setattr(self, key, value)
                
                modified_note = SectionNote(note_dict)
                result = format_note_details(modified_note, include_body, "individual_notes")
                
                # Add section info to the result
                section_info = f"EXTRACTED_SECTION: {section_title}\nSECTION_QUERY: {section}\n"
                return section_info + result
            else:
                # Section not found, return error with available sections
                headings = parse_markdown_headings(body)
                
                # Format available sections with numbering and indentation
                section_list = []
                for i, heading in enumerate(headings, 1):
                    level = heading['level']
                    title = heading['title']
                    indent = '  ' * (level - 1)
                    section_list.append(f"{indent}{i}. {title}")
                
                available_sections = "\n".join(section_list) if section_list else "No sections found"
                return f"""SECTION_NOT_FOUND: {section}
NOTE_ID: {note_id}
NOTE_TITLE: {getattr(note, 'title', 'Untitled')}
AVAILABLE_SECTIONS:
{available_sections}
ERROR: Section '{section}' not found in note"""
    
    return format_note_details(note, include_body, "individual_notes")

@create_tool("get_links", "Get links")
async def get_links(
    note_id: Annotated[str, Field(description="Note ID to extract links from")]
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
    note_id = validate_required_param(note_id, "note_id")
    client = get_joplin_client()
    
    # Get the note
    note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
    
    note_title = getattr(note, 'title', 'Untitled')
    body = getattr(note, 'body', '')
    
    # Parse outgoing links using regex (with optional section slugs)
    import re
    link_pattern = r'\[([^\]]+)\]\(:/([a-zA-Z0-9]+)(?:#([^)]+))?\)'
    
    outgoing_links = []
    if body:
        lines = body.split('\n')
        for line_num, line in enumerate(lines, 1):
            matches = re.finditer(link_pattern, line)
            for match in matches:
                link_text = match.group(1)
                target_note_id = match.group(2)
                section_slug = match.group(3) if match.group(3) else None
                
                # Try to get the target note title
                try:
                    target_note = client.get_note(target_note_id, fields="id,title")
                    target_title = getattr(target_note, 'title', 'Unknown Note')
                    target_exists = True
                except:
                    target_title = "Note not found"
                    target_exists = False
                
                link_data = {
                    'text': link_text,
                    'target_id': target_note_id,
                    'target_title': target_title,
                    'target_exists': target_exists,
                    'line_number': line_num,
                    'line_context': line.strip()
                }
                
                # Add section slug if present
                if section_slug:
                    link_data['section_slug'] = section_slug
                
                outgoing_links.append(link_data)
    
    # Search for backlinks - notes that link to this note
    backlinks = []
    try:
        # Search for notes containing this note's ID in link format
        search_query = f":/{note_id}"
        backlink_results = client.search_all(query=search_query, fields=COMMON_NOTE_FIELDS)
        backlink_notes = process_search_results(backlink_results)
        
        # Filter out the current note and parse backlinks
        for source_note in backlink_notes:
            source_note_id = getattr(source_note, 'id', '')
            source_note_title = getattr(source_note, 'title', 'Untitled')
            source_body = getattr(source_note, 'body', '')
            
            # Skip if it's the same note
            if source_note_id == note_id:
                continue
                
            # Parse links in the source note that point to our note
            if source_body:
                lines = source_body.split('\n')
                for line_num, line in enumerate(lines, 1):
                    matches = re.finditer(link_pattern, line)
                    for match in matches:
                        link_text = match.group(1)
                        target_note_id = match.group(2)
                        section_slug = match.group(3) if match.group(3) else None
                        
                        # Only include if this link points to our note
                        if target_note_id == note_id:
                            backlink_data = {
                                'text': link_text,
                                'source_id': source_note_id,
                                'source_title': source_note_title,
                                'line_number': line_num,
                                'line_context': line.strip()
                            }
                            
                            # Add section slug if present
                            if section_slug:
                                backlink_data['section_slug'] = section_slug
                            
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
        ""
    ]
    
    # Add outgoing links section
    if outgoing_links:
        result_parts.append("OUTGOING_LINKS:")
        for i, link in enumerate(outgoing_links, 1):
            status = "VALID" if link['target_exists'] else "BROKEN"
            link_details = [
                f"  LINK_{i}:",
                f"    link_text: {link['text']}",
                f"    target_note_id: {link['target_id']}",
                f"    target_note_title: {link['target_title']}",
                f"    link_status: {status}",
            ]
            
            # Add section slug if present
            if 'section_slug' in link:
                link_details.append(f"    section_slug: {link['section_slug']}")
            
            link_details.extend([
                f"    line_number: {link['line_number']}",
                f"    line_context: {link['line_context']}",
                ""
            ])
            
            result_parts.extend(link_details)
    else:
        result_parts.extend([
            "OUTGOING_LINKS: None",
            ""
        ])
    
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
            if 'section_slug' in backlink:
                backlink_details.append(f"    section_slug: {backlink['section_slug']}")
            
            backlink_details.extend([
                f"    line_number: {backlink['line_number']}",
                f"    line_context: {backlink['line_context']}",
                ""
            ])
            
            result_parts.extend(backlink_details)
    else:
        result_parts.extend([
            "BACKLINKS: None",
            ""
        ])
    
    # Add status message
    if not outgoing_links and not backlinks:
        if not body:
            result_parts.append("STATUS: No content found in this note and no backlinks found")
        else:
            result_parts.append("STATUS: No note links found in this note and no backlinks found")
    else:
        result_parts.append("STATUS: Links and backlinks retrieved successfully")
    
    return "\n".join(result_parts)

@create_tool("create_note", "Create note")
async def create_note(
    title: Annotated[str, Field(description="Note title")], 
    notebook_name: Annotated[str, Field(description="Notebook name")], 
    body: Annotated[str, Field(description="Note content")] = "",
    is_todo: Annotated[Union[bool, str], Field(description="Create as todo (default: False)")] = False,
    todo_completed: Annotated[Union[bool, str], Field(description="Mark todo as completed (default: False)")] = False
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
    title = validate_required_param(title, "title")
    is_todo = validate_boolean_param(is_todo, "is_todo")
    todo_completed = validate_boolean_param(todo_completed, "todo_completed")
    
    # Use helper function to get notebook ID
    parent_id = get_notebook_id_by_name(notebook_name)
    
    client = get_joplin_client()
    note = client.add_note(
        title=title, body=body, parent_id=parent_id,
        is_todo=1 if is_todo else 0, todo_completed=1 if todo_completed else 0
    )
    return format_creation_success(ItemType.note, title, str(note))

@create_tool("update_note", "Update note")
async def update_note(
    note_id: Annotated[str, Field(description="Note ID to update")],
    title: Annotated[Optional[str], Field(description="New title (optional)")] = None,
    body: Annotated[Optional[str], Field(description="New content (optional)")] = None,
    is_todo: Annotated[Union[bool, str, None], Field(description="Convert to/from todo (optional)")] = None,
    todo_completed: Annotated[Union[bool, str, None], Field(description="Mark todo completed (optional)")] = None
) -> str:
    """Update an existing note in Joplin.
    
    Updates one or more properties of an existing note. At least one field must be provided.
    
    Returns:
        str: Success message confirming the note was updated.
    
    Examples:
        - update_note("note123", title="New Title") - Update only the title
        - update_note("note123", body="New content", is_todo=True) - Update content and convert to todo
    """
    note_id = validate_required_param(note_id, "note_id")
    is_todo = validate_boolean_param(is_todo, "is_todo")
    todo_completed = validate_boolean_param(todo_completed, "todo_completed")
    
    update_data = {}
    if title is not None: update_data["title"] = title
    if body is not None: update_data["body"] = body
    if is_todo is not None: update_data["is_todo"] = 1 if is_todo else 0
    if todo_completed is not None: update_data["todo_completed"] = 1 if todo_completed else 0
    
    if not update_data:
        raise ValueError("At least one field must be provided for update")
    
    client = get_joplin_client()
    client.modify_note(note_id, **update_data)
    return format_update_success(ItemType.note, note_id)

@create_tool("delete_note", "Delete note")
async def delete_note(
    note_id: Annotated[str, Field(description="Note ID to delete")]
) -> str:
    """Delete a note from Joplin.
    
    Permanently removes a note from Joplin. This action cannot be undone.
    
    Returns:
        str: Success message confirming the note was deleted.
    
    Warning: This action is permanent and cannot be undone.
    """
    note_id = validate_required_param(note_id, "note_id")
    client = get_joplin_client()
    client.delete_note(note_id)
    return format_delete_success(ItemType.note, note_id)

@create_tool("find_notes", "Find notes")
async def find_notes(
    query: Annotated[str, Field(description="Search text or '*' for all notes")],
    limit: Annotated[int, Field(description="Max results (1-100, default: 20)")] = 20,
    offset: Annotated[int, Field(description="Skip count for pagination (default: 0)")] = 0,
    task: Annotated[Union[bool, str, None], Field(description="Filter by task type (default: None)")] = None,
    completed: Annotated[Union[bool, str, None], Field(description="Filter by completion status (default: None)")] = None
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
    limit = validate_limit(limit)
    offset = validate_offset(offset)
    task = validate_boolean_param(task, "task")
    completed = validate_boolean_param(completed, "completed")
    
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
            notes = sorted(notes, key=lambda x: getattr(x, 'updated_time', 0), reverse=True)
    else:
        # Build search query with text and filters
        search_parts = [query]
        search_parts.extend(build_search_filters(task, completed))
        
        search_query = " ".join(search_parts)
        search_query = validate_required_param(search_query, "query")
        
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
        search_description = f'text search: {query}'
    
    return format_search_results_with_pagination(
        search_description, paginated_notes, total_count, limit, offset, "search_results"
    )

@create_tool("get_all_notes", "Get all notes")
async def get_all_notes(
    limit: Annotated[int, Field(description="Max results (1-100, default: 20)")] = 20
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
    limit = validate_limit(limit)
    
    client = get_joplin_client()
    results = client.get_all_notes(fields=COMMON_NOTE_FIELDS)
    notes = process_search_results(results)
    
    # Sort by updated time, newest first
    notes = sorted(notes, key=lambda x: getattr(x, 'updated_time', 0), reverse=True)
    
    # Apply limit (using consistent pattern but keeping simple offset=0)
    notes = notes[:limit]
    
    if not notes:
        return format_no_results_message("note")
    
    return format_search_results_with_pagination("all notes", notes, len(notes), limit, 0, "search_results")

@create_tool("find_notes_with_tag", "Find notes with tag")
async def find_notes_with_tag(
    tag_name: Annotated[str, Field(description="Tag name to search for")],
    limit: Annotated[int, Field(description="Max results (1-100, default: 20)")] = 20,
    offset: Annotated[int, Field(description="Skip count for pagination (default: 0)")] = 0,
    task: Annotated[Union[bool, str, None], Field(description="Filter by task type (default: None)")] = None,
    completed: Annotated[Union[bool, str, None], Field(description="Filter by completion status (default: None)")] = None
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
    tag_name = validate_required_param(tag_name, "tag_name")
    limit = validate_limit(limit)
    offset = validate_offset(offset)
    task = validate_boolean_param(task, "task")
    completed = validate_boolean_param(completed, "completed")
    
    # Build search query with tag and filters
    search_parts = [f"tag:{tag_name.strip()}"]
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
        f'tag search: {search_query}', paginated_notes, total_count, limit, offset, "search_results"
    )

@create_tool("find_notes_in_notebook", "Find notes in notebook")  
async def find_notes_in_notebook(
    notebook_name: Annotated[str, Field(description="Notebook name to search in")],
    limit: Annotated[int, Field(description="Max results (1-100, default: 20)")] = 20,
    offset: Annotated[int, Field(description="Skip count for pagination (default: 0)")] = 0,
    task: Annotated[Union[bool, str, None], Field(description="Filter by task type (default: None)")] = None,
    completed: Annotated[Union[bool, str, None], Field(description="Filter by completion status (default: None)")] = None
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
    notebook_name = validate_required_param(notebook_name, "notebook_name")
    limit = validate_limit(limit)
    offset = validate_offset(offset)
    task = validate_boolean_param(task, "task")
    completed = validate_boolean_param(completed, "completed")
    
    # Build search query with notebook and filters
    search_parts = [f"notebook:{notebook_name.strip()}"]
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
        f'notebook search: {search_query}', paginated_notes, total_count, limit, offset, "search_results"
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
    title: Annotated[str, Field(description="Notebook title")], 
    parent_id: Annotated[Optional[str], Field(description="Parent notebook ID (optional)")] = None
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
    title = validate_required_param(title, "title")
    
    client = get_joplin_client()
    notebook_kwargs = {"title": title}
    if parent_id:
        notebook_kwargs["parent_id"] = parent_id.strip()
    
    notebook = client.add_notebook(**notebook_kwargs)
    return format_creation_success(ItemType.notebook, title, str(notebook))

@create_tool("update_notebook", "Update notebook")
async def update_notebook(
    notebook_id: Annotated[str, Field(description="Notebook ID to update")],
    title: Annotated[str, Field(description="New notebook title")]
) -> str:
    """Update an existing notebook.
    
    Updates the title of an existing notebook. Currently only the title can be updated.
    
    Returns:
        str: Success message confirming the notebook was updated.
    """
    notebook_id = validate_required_param(notebook_id, "notebook_id")
    title = validate_required_param(title, "title")
    
    client = get_joplin_client()
    client.modify_notebook(notebook_id, title=title)
    return format_update_success(ItemType.notebook, notebook_id)

@create_tool("delete_notebook", "Delete notebook")
async def delete_notebook(
    notebook_id: Annotated[str, Field(description="Notebook ID to delete")]
) -> str:
    """Delete a notebook from Joplin.
    
    Permanently removes a notebook from Joplin. This action cannot be undone.
    
    Returns:
        str: Success message confirming the notebook was deleted.
    
    Warning: This action is permanent and cannot be undone. All notes in the notebook will also be deleted.
    """
    notebook_id = validate_required_param(notebook_id, "notebook_id")
    client = get_joplin_client()
    client.delete_notebook(notebook_id)
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
    title: Annotated[str, Field(description="Tag title")]
) -> str:
    """Create a new tag.
    
    Creates a new tag that can be applied to notes for categorization and organization.
    
    Returns:
        str: Success message with the created tag's title and unique ID.
    
    Examples:
        - create_tag("work") - Create a new tag named "work"
        - create_tag("important") - Create a new tag named "important"
    """
    title = validate_required_param(title, "title")
    client = get_joplin_client()
    tag = client.add_tag(title=title)
    return format_creation_success(ItemType.tag, title, str(tag))

@create_tool("update_tag", "Update tag")
async def update_tag(
    tag_id: Annotated[str, Field(description="Tag ID to update")],
    title: Annotated[str, Field(description="New tag title")]
) -> str:
    """Update an existing tag.
    
    Updates the title of an existing tag. Currently only the title can be updated.
    
    Returns:
        str: Success message confirming the tag was updated.
    """
    tag_id = validate_required_param(tag_id, "tag_id")
    title = validate_required_param(title, "title")
    
    client = get_joplin_client()
    client.modify_tag(tag_id, title=title)
    return format_update_success(ItemType.tag, tag_id)

@create_tool("delete_tag", "Delete tag")
async def delete_tag(
    tag_id: Annotated[str, Field(description="Tag ID to delete")]
) -> str:
    """Delete a tag from Joplin.
    
    Permanently removes a tag from Joplin. This action cannot be undone.
    The tag will be removed from all notes that currently have it.
    
    Returns:
        str: Success message confirming the tag was deleted.
    
    Warning: This action is permanent and cannot be undone. The tag will be removed from all notes.
    """
    tag_id = validate_required_param(tag_id, "tag_id")
    client = get_joplin_client()
    client.delete_tag(tag_id)
    return format_delete_success(ItemType.tag, tag_id)



@create_tool("get_tags_by_note", "Get tags by note")
async def get_tags_by_note(
    note_id: Annotated[str, Field(description="Note ID to get tags from")]
) -> str:
    """Get all tags for a specific note.
    
    Retrieves all tags that are currently applied to a specific note.
    
    Returns:
        str: Formatted list of tags applied to the note with title, ID, and creation date.
    """
    note_id = validate_required_param(note_id, "note_id")
    
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
    note_id = validate_required_param(note_id, "note_id")
    tag_name = validate_required_param(tag_name, "tag_name")
    
    client = get_joplin_client()
    
    # Verify note exists by getting it
    try:
        note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
        note_title = getattr(note, 'title', 'Unknown Note')
    except Exception:
        raise ValueError(f"Note with ID '{note_id}' not found. Use find_notes to find available notes.")
    
    # Use helper function to get tag ID
    tag_id = get_tag_id_by_name(tag_name)
    
    client.add_tag_to_note(tag_id, note_id)
    return format_relation_success("tagged note", ItemType.note, f"{note_title} (ID: {note_id})", ItemType.tag, tag_name)

async def _untag_note_impl(note_id: str, tag_name: str) -> str:
    """Shared implementation for removing a tag from a note using note ID and tag name."""
    note_id = validate_required_param(note_id, "note_id")
    tag_name = validate_required_param(tag_name, "tag_name")
    
    client = get_joplin_client()
    
    # Verify note exists by getting it
    try:
        note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
        note_title = getattr(note, 'title', 'Unknown Note')
    except Exception:
        raise ValueError(f"Note with ID '{note_id}' not found. Use find_notes to find available notes.")
    
    # Use helper function to get tag ID
    tag_id = get_tag_id_by_name(tag_name)
    
    client.remove_tag_from_note(tag_id, note_id)
    return format_relation_success("removed tag from note", ItemType.note, f"{note_title} (ID: {note_id})", ItemType.tag, tag_name)

# Primary tag operations
@create_tool("tag_note", "Tag note")
async def tag_note(
    note_id: Annotated[str, Field(description="Note ID to add tag to")], 
    tag_name: Annotated[str, Field(description="Tag name to add")]
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
    note_id: Annotated[str, Field(description="Note ID to remove tag from")], 
    tag_name: Annotated[str, Field(description="Tag name to remove")]
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
            "url": getattr(client, 'url', 'unknown'),
            "version": f"FastMCP-based Joplin Server v{MCP_VERSION}"
        }
    except Exception:
        return {"connected": False}

# === MAIN RUNNER ===

def main(config_file: Optional[str] = None, transport: str = "stdio", host: str = "127.0.0.1", port: int = 8000, path: str = "/mcp", log_level: str = "info"):
    """Main entry point for the FastMCP Joplin server."""
    global _config
    
    try:
        logger.info("🚀 Starting FastMCP Joplin server...")
        
        # Set the runtime config (tools are already filtered at import time)
        if config_file:
            _config = JoplinMCPConfig.from_file(config_file)
            logger.info(f"Runtime configuration loaded from {config_file}")
        else:
            # Use the same config that was used for tool filtering
            _config = _module_config
            logger.info(f"Using module-level configuration for runtime")
        
        # Log final tool registration status
        registered_tools = list(mcp._tool_manager._tools.keys())
        logger.info(f"FastMCP server has {len(registered_tools)} tools registered")
        logger.info(f"Registered tools: {sorted(registered_tools)}")
        
        # Verify we can connect to Joplin
        logger.info("Initializing Joplin client...")
        client = get_joplin_client()
        logger.info("Joplin client initialized successfully")
        
        # Run the FastMCP server with specified transport
        if transport.lower() == "http":
            logger.info(f"Starting FastMCP server with HTTP transport on {host}:{port}{path}")
            mcp.run(transport="http", host=host, port=port, path=path, log_level=log_level)
        else:
            logger.info("Starting FastMCP server with STDIO transport")
            mcp.run(transport="stdio")
    except Exception as e:
        logger.error(f"Failed to start FastMCP Joplin server: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main() 