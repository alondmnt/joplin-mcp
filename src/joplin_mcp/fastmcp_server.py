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

# Direct joppy import
from joppy.client_api import ClientApi

# Import our existing configuration for compatibility
from joplin_mcp.config import JoplinMCPConfig

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
    
    # Add content last to avoid breaking metadata flow
    if include_body and should_show_content:
        body = getattr(note, 'body', '')
        if body:
            if should_show_full_content:
                result_parts.append(f"CONTENT: {body}")
            else:
                # Show preview only
                max_length = config.get_max_preview_length()
                preview = body[:max_length]
                if len(body) > max_length:
                    preview += "..."
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
        
        # Handle content last to avoid breaking metadata flow
        if should_show_content:
            body = getattr(note, 'body', '')
            if body:
                if should_show_full_content:
                    result_parts.append(f"  content: {body}")
                else:
                    # Show preview only
                    preview = body[:max_preview_length]
                    if len(body) > max_preview_length:
                        preview += "..."
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
    
    Verifies that the Joplin MCP server can connect to the Joplin application.
    Use to troubleshoot connection issues or confirm proper configuration.
    
    Returns:
        str: Structured connection status information optimized for LLM comprehension.
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
    note_id: Annotated[str, "The unique identifier of the note to retrieve. This is typically a long alphanumeric string like 'a1b2c3d4e5f6...' that uniquely identifies the note in Joplin."], 
    include_body: Annotated[Union[bool, str], "Whether to include the note's content/body in the response. Set to True to see the full note content, False to only see metadata like title, dates, and IDs. Default is True."] = True
) -> str:
    """Retrieve a specific note by its unique identifier.
    
    Fetches a single note from Joplin using its unique ID. Returns the note's title, content, 
    creation/modification dates, and other metadata.
    
    Parameters:
        note_id (str): The unique identifier of the note to retrieve. Required.
        include_body (bool): Whether to include the note's content in the response. 
                            True = full note with content (default), False = metadata only.
    
    Returns:
        str: Formatted note details including title, ID, content (if requested), creation/modification dates, and parent notebook ID.
    
    Examples:
        - get_note("a1b2c3d4e5f6...", True) - Get full note with content
        - get_note("a1b2c3d4e5f6...", False) - Get metadata only
    """
    note_id = validate_required_param(note_id, "note_id")
    include_body = validate_boolean_param(include_body, "include_body")
    client = get_joplin_client()
    
    # Use string format for fields (list format causes SQL errors)
    note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
    
    return format_note_details(note, include_body, "individual_notes")

@create_tool("get_links", "Get links")
async def get_links(
    note_id: Annotated[str, "The unique identifier of the note to extract links from. This is typically a long alphanumeric string like 'a1b2c3d4e5f6...' that uniquely identifies the note in Joplin."]
) -> str:
    """Extract all links to other notes from a given note and find backlinks from other notes.
    
    Scans the note's content for links to other notes in the format [text](:/noteId)
    and searches for backlinks (other notes that link to this note). Returns information
    about each link including the link text, target note ID, target note title (if accessible),
    and the line context where the link appears.
    
    Parameters:
        note_id (str): The unique identifier of the note to extract links from. Required.
    
    Returns:
        str: Formatted list of all note links found in the note and backlinks from other notes,
             including link text, target/source note ID, target/source note title, and line context.
             Returns information about both outgoing links and backlinks.
    
    Examples:
        - get_links("a1b2c3d4e5f6...") - Get all note links and backlinks for the specified note
        
    Link format: [link text](:/targetNoteId)
    """
    note_id = validate_required_param(note_id, "note_id")
    client = get_joplin_client()
    
    # Get the note
    note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
    
    note_title = getattr(note, 'title', 'Untitled')
    body = getattr(note, 'body', '')
    
    # Parse outgoing links using regex
    import re
    link_pattern = r'\[([^\]]+)\]\(:/([a-zA-Z0-9]+)\)'
    
    outgoing_links = []
    if body:
        lines = body.split('\n')
        for line_num, line in enumerate(lines, 1):
            matches = re.finditer(link_pattern, line)
            for match in matches:
                link_text = match.group(1)
                target_note_id = match.group(2)
                
                # Try to get the target note title
                try:
                    target_note = client.get_note(target_note_id, fields="id,title")
                    target_title = getattr(target_note, 'title', 'Unknown Note')
                    target_exists = True
                except:
                    target_title = "Note not found"
                    target_exists = False
                
                outgoing_links.append({
                    'text': link_text,
                    'target_id': target_note_id,
                    'target_title': target_title,
                    'target_exists': target_exists,
                    'line_number': line_num,
                    'line_context': line.strip()
                })
    
    # Search for backlinks - notes that link to this note
    backlinks = []
    try:
        # Search for notes containing this note's ID in link format
        search_query = f":/{note_id}"
        backlink_results = client.search_all(query=search_query, fields=fields_list)
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
                        
                        # Only include if this link points to our note
                        if target_note_id == note_id:
                            backlinks.append({
                                'text': link_text,
                                'source_id': source_note_id,
                                'source_title': source_note_title,
                                'line_number': line_num,
                                'line_context': line.strip()
                            })
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
            result_parts.extend([
                f"  LINK_{i}:",
                f"    link_text: {link['text']}",
                f"    target_note_id: {link['target_id']}",
                f"    target_note_title: {link['target_title']}",
                f"    link_status: {status}",
                f"    line_number: {link['line_number']}",
                f"    line_context: {link['line_context']}",
                ""
            ])
    else:
        result_parts.extend([
            "OUTGOING_LINKS: None",
            ""
        ])
    
    # Add backlinks section
    if backlinks:
        result_parts.append("BACKLINKS:")
        for i, backlink in enumerate(backlinks, 1):
            result_parts.extend([
                f"  BACKLINK_{i}:",
                f"    link_text: {backlink['text']}",
                f"    source_note_id: {backlink['source_id']}",
                f"    source_note_title: {backlink['source_title']}",
                f"    line_number: {backlink['line_number']}",
                f"    line_context: {backlink['line_context']}",
                ""
            ])
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
    title: Annotated[str, "The title/name of the new note. This is required and will be displayed in Joplin's note list. Example: 'My Important Note' or 'Meeting Notes - Jan 15'"], 
    notebook_name: Annotated[str, "The name of the notebook where this note should be created. This is required - you must specify which notebook to put the note in. Use the exact notebook name as shown in list_notebooks. Example: 'Work Projects' or 'Personal Notes'"], 
    body: Annotated[str, "The content/text of the note. This can be plain text or Markdown. Leave empty to create a note with no content initially. Example: 'This is my note content with **bold** and *italic* text.'"] = "",
    is_todo: Annotated[Union[bool, str], "Whether this note should be created as a todo/task item. Set to True to make it a checkable todo item, False for a regular note. Default is False."] = False,
    todo_completed: Annotated[Union[bool, str], "Whether the todo item should be marked as completed when created. Only relevant if is_todo=True. Set to True to create a completed todo, False for uncompleted. Default is False."] = False
) -> str:
    """Create a new note in a specified notebook in Joplin.
    
    Creates a new note with the specified title, content, and properties in the given notebook.
    Uses the notebook name for easier identification instead of requiring notebook IDs.
    
    Parameters:
        title (str): The title of the new note. Required.
        notebook_name (str): The name of the notebook where the note should be created. Required.
                             Use list_notebooks() to see available notebook names.
        body (str): The content of the note. Can be plain text or Markdown. Optional, defaults to empty.
        is_todo (bool): Whether to create as a todo/task item. Optional, defaults to False.
        todo_completed (bool): Whether the todo should be marked as completed when created. 
                              Only relevant if is_todo=True. Optional, defaults to False.
    
    Returns:
        str: Success message with the created note's title and unique ID that can be used to reference this note.
    
    Examples:
        - create_note("Shopping List", "Personal Notes", "- Milk\n- Eggs", True, False) - Create uncompleted todo
        - create_note("Meeting Notes", "Work Projects", "# Meeting with Client", False, False) - Create regular note
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
    note_id: Annotated[str, "The unique identifier of the note to update. Required."],
    title: Annotated[Optional[str], "New title for the note. Optional - only updates if provided."] = None,
    body: Annotated[Optional[str], "New content for the note. Can be plain text or Markdown. Optional - only updates if provided."] = None,
    is_todo: Annotated[Union[bool, str, None], "Whether to convert the note to/from a todo item. Optional - only updates if provided."] = None,
    todo_completed: Annotated[Union[bool, str, None], "Whether to mark the todo as completed. Only relevant if note is a todo. Optional - only updates if provided."] = None
) -> str:
    """Update an existing note in Joplin.
    
    Updates one or more properties of an existing note. At least one field must be provided for update.
    
    Parameters:
        note_id (str): The unique identifier of the note to update. Required.
        title (str, optional): New title for the note. Only updates if provided.
        body (str, optional): New content for the note. Can be plain text or Markdown. Only updates if provided.
        is_todo (bool, optional): Whether to convert the note to/from a todo item. Only updates if provided.
        todo_completed (bool, optional): Whether to mark the todo as completed. Only updates if provided.
    
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
    note_id: Annotated[str, "The unique identifier of the note to delete. Required."]
) -> str:
    """Delete a note from Joplin.
    
    Permanently removes a note from Joplin. This action cannot be undone.
    
    Parameters:
        note_id (str): The unique identifier of the note to delete. Required.
    
    Returns:
        str: Success message confirming the note was deleted.
    
    Examples:
        - delete_note("note123") - Delete the specified note
    
    Warning: This action is permanent and cannot be undone.
    """
    note_id = validate_required_param(note_id, "note_id")
    client = get_joplin_client()
    client.delete_note(note_id)
    return format_delete_success(ItemType.note, note_id)

@create_tool("find_notes", "Find notes")
async def find_notes(
    query: Annotated[str, "Text to search for in note titles and content. Use '*' to list all notes without specific text filtering. Examples: 'meeting', 'project planning', 'grocery list', or '*' for all notes."],
    limit: Annotated[int, "Maximum number of notes to return. Must be between 1 and 100. Default is 20."] = 20,
    offset: Annotated[int, "Number of notes to skip for pagination. Use with limit for paging through results. Default is 0."] = 0,
    task: Annotated[Union[bool, str, None], "Filter by task type. True for tasks only, False for regular notes only, None for all notes. Default is None (all notes)."] = None,
    completed: Annotated[Union[bool, str, None], "Filter by completion status (only relevant when task=True). True for completed tasks, False for uncompleted tasks, None for all tasks. Default is None (all tasks)."] = None
) -> str:
    """Find notes by searching their titles and content, with support for listing all notes and pagination.
    
    Versatile search function that can find specific text in notes OR list all notes with filtering and pagination.
    Use this when you want to find notes containing specific words/phrases, or to browse through all notes.
    
    📝 LISTING ALL NOTES:
    Use query="*" to list all notes without text filtering. Perfect for browsing your entire note collection.
    
    🔍 TEXT SEARCH:
    Use specific text to find notes containing those words in titles or content.
    
    📄 PAGINATION:
    Use limit and offset together to page through large result sets:
    - Page 1: limit=20, offset=0 (first 20 notes)
    - Page 2: limit=20, offset=20 (next 20 notes)  
    - Page 3: limit=20, offset=40 (next 20 notes)
    
    Parameters:
        query (str): Text to search for in note titles and content. Use '*' to list all notes. Required.
        limit (int): Maximum number of notes to return. Must be between 1 and 100. Default is 20.
        offset (int): Number of notes to skip for pagination. Use multiples of limit. Default is 0.
        task (bool, optional): Filter by task type. True = tasks only, False = regular notes only, None = all notes. Default is None.
        completed (bool, optional): Filter by completion status (only relevant when task=True). 
                                   True = completed tasks only, False = uncompleted tasks only, None = all tasks. 
                                   Default is None.
    
    Returns:
        str: List of notes matching criteria, with title, ID, content preview, and dates. 
             Includes pagination info (total results, current page range).
    
    Examples:
        📝 LIST ALL NOTES:
        - find_notes("*") - List first 20 notes (all notes)
        - find_notes("*", limit=50) - List first 50 notes
        - find_notes("*", limit=20, offset=20) - List notes 21-40 (page 2)
        - find_notes("*", limit=20, offset=40) - List notes 41-60 (page 3)
        
        🔍 TEXT SEARCH:
        - find_notes("meeting") - Find all notes containing "meeting"
        - find_notes("meeting", limit=10, offset=10) - Find notes with "meeting" (page 2)
        
        🎯 FILTERED SEARCHES:
        - find_notes("*", task=True) - List all tasks
        - find_notes("*", task=True, completed=False) - List uncompleted tasks
        - find_notes("project", task=False) - Find regular notes containing "project"
        
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
    limit: Annotated[int, "Maximum number of notes to return. Must be between 1 and 100. Default is 20."] = 20
) -> str:
    """Get all notes in your Joplin instance.
    
    Simple function to retrieve all notes without any filtering or searching.
    Most recent notes are shown first.
    
    Parameters:
        limit (int): Maximum number of notes to return. Must be between 1 and 100. Default is 20.
    
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
    tag_name: Annotated[str, "The tag name to search for. Example: 'time-slip' or 'work' or 'important'"],
    limit: Annotated[int, "Maximum number of notes to return. Must be between 1 and 100. Default is 20."] = 20,
    offset: Annotated[int, "Number of notes to skip for pagination. Use with limit for paging through results. Default is 0."] = 0,
    task: Annotated[Union[bool, str, None], "Filter by task type. True for tasks only, False for regular notes only, None for all notes. Default is None (all notes)."] = None,
    completed: Annotated[Union[bool, str, None], "Filter by completion status (only relevant when task=True). True for completed tasks, False for uncompleted tasks, None for all tasks. Default is None (all tasks)."] = None
) -> str:
    """Find all notes that have a specific tag, with pagination support.
    
    This is the MAIN function for finding notes by tag. Use this when you want to find
    all notes tagged with a specific tag name.
    
    📄 PAGINATION:
    Use limit and offset together to page through large result sets:
    - Page 1: limit=20, offset=0 (first 20 notes)
    - Page 2: limit=20, offset=20 (next 20 notes)  
    - Page 3: limit=20, offset=40 (next 20 notes)
    
    Parameters:
        tag_name (str): The tag name to search for. Required.
        limit (int): Maximum number of notes to return. Must be between 1 and 100. Default is 20.
        offset (int): Number of notes to skip for pagination. Use multiples of limit. Default is 0.
        task (bool, optional): Filter by task type. True = tasks only, False = regular notes only, None = all notes. Default is None.
        completed (bool, optional): Filter by completion status (only relevant when task=True). 
                                   True = completed tasks only, False = uncompleted tasks only, None = all tasks. 
                                   Default is None.
    
    Returns:
        str: List of all notes with the specified tag, with pagination information.
    
    Examples:
        - find_notes_with_tag("time-slip") - Find all notes tagged with "time-slip"
        - find_notes_with_tag("work", limit=10, offset=10) - Find notes tagged with "work" (page 2)
        - find_notes_with_tag("work", task=True) - Find only tasks tagged with "work"
        - find_notes_with_tag("important", task=True, completed=False) - Find only uncompleted tasks tagged with "important"
        - find_notes_with_tag("personal", task=False) - Find only regular notes tagged with "personal"
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
    notebook_name: Annotated[str, "The notebook name to search in. Example: 'Work Projects' or 'Personal Notes'"],
    limit: Annotated[int, "Maximum number of notes to return. Must be between 1 and 100. Default is 20."] = 20,
    offset: Annotated[int, "Number of notes to skip for pagination. Use with limit for paging through results. Default is 0."] = 0,
    task: Annotated[Union[bool, str, None], "Filter by task type. True for tasks only, False for regular notes only, None for all notes. Default is None (all notes)."] = None,
    completed: Annotated[Union[bool, str, None], "Filter by completion status (only relevant when task=True). True for completed tasks, False for uncompleted tasks, None for all tasks. Default is None (all tasks)."] = None
) -> str:
    """Find all notes in a specific notebook, with pagination support.
    
    This is the MAIN function for finding notes by notebook. Use this when you want to find
    all notes in a specific notebook.
    
    📄 PAGINATION:
    Use limit and offset together to page through large result sets:
    - Page 1: limit=20, offset=0 (first 20 notes)
    - Page 2: limit=20, offset=20 (next 20 notes)  
    - Page 3: limit=20, offset=40 (next 20 notes)
    
    Parameters:
        notebook_name (str): The notebook name to search in. Required.
        limit (int): Maximum number of notes to return. Must be between 1 and 100. Default is 20.
        offset (int): Number of notes to skip for pagination. Use multiples of limit. Default is 0.
        task (bool, optional): Filter by task type. True = tasks only, False = regular notes only, None = all notes. Default is None.
        completed (bool, optional): Filter by completion status (only relevant when task=True). 
                                   True = completed tasks only, False = uncompleted tasks only, None = all tasks. 
                                   Default is None.
    
    Returns:
        str: List of all notes in the specified notebook, with pagination information.
    
    Examples:
        - find_notes_in_notebook("Work Projects") - Find all notes in "Work Projects"
        - find_notes_in_notebook("Personal Notes", limit=10, offset=10) - Find notes in "Personal Notes" (page 2)
        - find_notes_in_notebook("Personal Notes", task=True) - Find only tasks in "Personal Notes"
        - find_notes_in_notebook("Projects", task=True, completed=False) - Find only uncompleted tasks in "Projects"
        - find_notes_in_notebook("Archive", task=False) - Find only regular notes in "Archive"
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
    
    Retrieves and displays all notebooks (folders) in your Joplin application. Notebooks are
    containers that hold your notes, similar to folders in a file system.
    
    Returns:
        str: Formatted list of all notebooks including title, unique ID, parent notebook (if sub-notebook), and creation date.
             Returns "📁 No notebooks found" if no notebooks exist.
    
    Use case: Get notebook IDs for creating new notes or understanding your organizational structure.
    """
    client = get_joplin_client()
    fields_list = "id,title,created_time,updated_time,parent_id"
    notebooks = client.get_all_notebooks(fields=fields_list)
    return format_item_list(notebooks, ItemType.notebook)



@create_tool("create_notebook", "Create notebook")
async def create_notebook(
    title: Annotated[str, "The name of the new notebook/folder. This is required and will be displayed in Joplin's notebook list. Example: 'Work Projects' or 'Personal Notes' or 'Archive 2024'"], 
    parent_id: Annotated[Optional[str], "Optional parent notebook ID to create this as a sub-notebook. If provided, this notebook will be created inside the specified parent notebook. Leave empty to create a top-level notebook. Example: 'notebook123456789abcdef'"] = None
) -> str:
    """Create a new notebook (folder) in Joplin to organize your notes.
    
    Creates a new notebook that can be used to organize and contain notes. You can create top-level notebooks or sub-notebooks within existing notebooks.
    
    Parameters:
        title (str): The name of the new notebook. Required.
        parent_id (str, optional): The unique identifier of a parent notebook to create this as a sub-notebook.
                                  Optional - defaults to None (creates a top-level notebook).
                                  Use list_notebooks() to find available parent notebook IDs.
    
    Returns:
        str: Success message containing the created notebook's title and unique ID that can be used to reference this notebook.
    
    Examples:
        - create_notebook("Work Projects") - Create a top-level notebook for work
        - create_notebook("2024 Projects", "work_notebook_id") - Create a sub-notebook within work notebook
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
    notebook_id: Annotated[str, "The unique identifier of the notebook to update. Required."],
    title: Annotated[str, "The new title for the notebook. Required."]
) -> str:
    """Update an existing notebook.
    
    Updates the title of an existing notebook. Currently only the title can be updated.
    
    Parameters:
        notebook_id (str): The unique identifier of the notebook to update. Required.
        title (str): The new title for the notebook. Required.
    
    Returns:
        str: Success message confirming the notebook was updated.
    
    Examples:
        - update_notebook("notebook123", "New Notebook Name") - Update notebook title
    """
    notebook_id = validate_required_param(notebook_id, "notebook_id")
    title = validate_required_param(title, "title")
    
    client = get_joplin_client()
    client.modify_notebook(notebook_id, title=title)
    return format_update_success(ItemType.notebook, notebook_id)

@create_tool("delete_notebook", "Delete notebook")
async def delete_notebook(
    notebook_id: Annotated[str, "The unique identifier of the notebook to delete. Required."]
) -> str:
    """Delete a notebook from Joplin.
    
    Permanently removes a notebook from Joplin. This action cannot be undone.
    
    Parameters:
        notebook_id (str): The unique identifier of the notebook to delete. Required.
    
    Returns:
        str: Success message confirming the notebook was deleted.
    
    Examples:
        - delete_notebook("notebook123") - Delete the specified notebook
    
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
             Returns "🏷️ No tags found" if no tags exist.
    
    Use case: Get tag IDs for applying to notes or searching. Understand your tagging system.
    """
    client = get_joplin_client()
    fields_list = "id,title,created_time,updated_time"
    tags = client.get_all_tags(fields=fields_list)
    return format_tag_list_with_counts(tags, client)



@create_tool("create_tag", "Create tag")
async def create_tag(
    title: Annotated[str, "The name of the new tag. Required."]
) -> str:
    """Create a new tag.
    
    Creates a new tag that can be applied to notes for categorization and organization.
    
    Parameters:
        title (str): The name of the new tag. Required.
    
    Returns:
        str: Success message with the created tag's title and unique ID that can be used to reference this tag.
    
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
    tag_id: Annotated[str, "The unique identifier of the tag to update. Required."],
    title: Annotated[str, "The new title for the tag. Required."]
) -> str:
    """Update an existing tag.
    
    Updates the title of an existing tag. Currently only the title can be updated.
    
    Parameters:
        tag_id (str): The unique identifier of the tag to update. Required.
        title (str): The new title for the tag. Required.
    
    Returns:
        str: Success message confirming the tag was updated.
    
    Examples:
        - update_tag("tag123", "work-urgent") - Update tag title to "work-urgent"
    """
    tag_id = validate_required_param(tag_id, "tag_id")
    title = validate_required_param(title, "title")
    
    client = get_joplin_client()
    client.modify_tag(tag_id, title=title)
    return format_update_success(ItemType.tag, tag_id)

@create_tool("delete_tag", "Delete tag")
async def delete_tag(
    tag_id: Annotated[str, "The unique identifier of the tag to delete. Required."]
) -> str:
    """Delete a tag from Joplin.
    
    Permanently removes a tag from Joplin. This action cannot be undone.
    The tag will be removed from all notes that currently have it.
    
    Parameters:
        tag_id (str): The unique identifier of the tag to delete. Required.
    
    Returns:
        str: Success message confirming the tag was deleted.
    
    Examples:
        - delete_tag("tag123") - Delete the specified tag
    
    Warning: This action is permanent and cannot be undone. The tag will be removed from all notes.
    """
    tag_id = validate_required_param(tag_id, "tag_id")
    client = get_joplin_client()
    client.delete_tag(tag_id)
    return format_delete_success(ItemType.tag, tag_id)



@create_tool("get_tags_by_note", "Get tags by note")
async def get_tags_by_note(
    note_id: Annotated[str, "The unique identifier of the note to get tags from. Required."]
) -> str:
    """Get all tags for a specific note.
    
    Retrieves all tags that are currently applied to a specific note.
    
    Parameters:
        note_id (str): The unique identifier of the note to get tags from. Required.
    
    Returns:
        str: Formatted list of tags applied to the note with title, ID, and creation date.
             Returns "No tags found for note" if the note has no tags.
    
    Examples:
        - get_tags_by_note("note123") - Get all tags for the specified note
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
    note_id: Annotated[str, "The unique identifier of the note to add a tag to. This ensures we target the exact note even if multiple notes have similar titles. Example: 'a1b2c3d4e5f6...'"], 
    tag_name: Annotated[str, "The name of the tag to add to the note. This tag will be applied to the note for categorization. Example: 'Important' or 'Work'"]
) -> str:
    """Add a tag to a note for categorization and organization.
    
    Applies an existing tag to a specific note using the note's unique ID and the tag's name.
    Uses note ID for precise targeting and tag name for intuitive selection.
    
    Parameters:
        note_id (str): The unique identifier of the note to tag. Required.
                      Use find_notes() or get_note() to find note IDs.
        tag_name (str): The name of the tag to apply to the note. Required.
                         Use list_tags() or create_tag() to find or create tag names.
    
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
    note_id: Annotated[str, "The unique identifier of the note to remove a tag from. Required."], 
    tag_name: Annotated[str, "The name of the tag to remove from the note. Required."]
) -> str:
    """Remove a tag from a note.
    
    Removes an existing tag from a specific note using the note's unique ID and the tag's name.
    
    Parameters:
        note_id (str): The unique identifier of the note to remove a tag from. Required.
        tag_name (str): The name of the tag to remove from the note. Required.
    
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
            "version": "FastMCP-based Joplin Server v0.1.1"
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