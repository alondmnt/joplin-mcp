"""FastMCP-based Joplin MCP Server Implementation.

📝 FINDING NOTES:
- find_notes(query, task, completed) - Find notes containing specific text ⭐ MAIN FUNCTION FOR TEXT SEARCHES!
- find_notes_with_tag(tag_name, task, completed) - Find all notes with a specific tag ⭐ MAIN FUNCTION FOR TAG SEARCHES!
- find_notes_in_notebook(notebook_name, task, completed) - Find all notes in a specific notebook ⭐ MAIN FUNCTION FOR NOTEBOOK SEARCHES!
- get_all_notes() - Get all notes, most recent first
- find_notes(query, tag_name, notebook_name) - Search notes by text with optional filters

📋 MANAGING NOTES:
- create_note(title, notebook_name, body) - Create a new note
- get_note(note_id) - Get a specific note by ID
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
    """Format a standardized no results message."""
    context_part = f" {context}" if context else ""
    return f"No {item_type}s found{context_part}"

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
    """Format a standardized success message for creation operations."""
    emoji = get_item_emoji(item_type)
    return f"""✅ Successfully created {item_type.value}

**Title:** {title}
**{emoji} CREATED {item_type.value.upper()} ID: {item_id} {emoji}**

The {item_type.value} has been successfully created in Joplin.
💡 **Remember: The {item_type.value} ID is `{item_id}` - you can use this to reference this {item_type.value}.**"""

def format_update_success(item_type: ItemType, item_id: str) -> str:
    """Format a standardized success message for update operations."""
    emoji = get_item_emoji(item_type)
    return f"""✅ Successfully updated {item_type.value}

**{emoji} UPDATED {item_type.value.upper()} ID: {item_id} {emoji}**

The {item_type.value} has been successfully updated in Joplin."""

def format_delete_success(item_type: ItemType, item_id: str) -> str:
    """Format a standardized success message for delete operations."""
    emoji = get_item_emoji(item_type)
    return f"""✅ Successfully deleted {item_type.value}

**{emoji} DELETED {item_type.value.upper()} ID: {item_id} {emoji}**

The {item_type.value} has been permanently removed from Joplin."""

def format_relation_success(operation: str, item1_type: ItemType, item1_id: str, item2_type: ItemType, item2_id: str) -> str:
    """Format a standardized success message for relationship operations."""
    emoji1 = get_item_emoji(item1_type)
    emoji2 = get_item_emoji(item2_type)
    return f"""✅ Successfully {operation}

**{emoji1} {item1_type.value.title()} ID:** `{item1_id}`
**{emoji2} {item2_type.value.title()} ID:** `{item2_id}`

The {operation} operation has been completed successfully."""

def format_item_list(items: List[Any], item_type: ItemType) -> str:
    """Format a list of items (notebooks, tags, etc.) for display."""
    emoji = get_item_emoji(item_type)
    
    if not items:
        return f"{emoji} No {item_type.value}s found\n\nYour Joplin instance doesn't contain any {item_type.value}s yet."
    
    count = len(items)
    result_parts = [f"{emoji} Found {count} {item_type.value}{'s' if count != 1 else ''}", ""]
    
    for i, item in enumerate(items, 1):
        title = getattr(item, 'title', 'Untitled')
        item_id = getattr(item, 'id', 'unknown')
        
        result_parts.append(f"**{i}. {title}**")
        result_parts.append(f"   ID: {item_id}")
        
        # Add parent folder ID if available (for notebooks)
        parent_id = getattr(item, 'parent_id', None)
        if parent_id:
            result_parts.append(f"   Parent: {parent_id}")
        
        # Add creation time if available
        created_time = getattr(item, 'created_time', None)
        if created_time:
            created_date = format_timestamp(created_time, "%Y-%m-%d %H:%M")
            if created_date:
                result_parts.append(f"   Created: {created_date}")
        
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
    """Format a note for detailed display."""
    title = getattr(note, 'title', 'Untitled')
    note_id = getattr(note, 'id', 'unknown')
    
    result_parts = [f"**{title}**", f"ID: {note_id}", ""]
    
    # Check content exposure settings
    config = _module_config
    should_show_content = config.should_show_content(context)
    should_show_full_content = config.should_show_full_content(context)
    
    if include_body and should_show_content:
        body = getattr(note, 'body', '')
        if body:
            if should_show_full_content:
                result_parts.extend(["**Content:**", body, ""])
            else:
                # Show preview only
                max_length = config.get_max_preview_length()
                preview = body[:max_length]
                if len(body) > max_length:
                    preview += "..."
                result_parts.extend(["**Content Preview:**", preview, ""])
    
    # Add metadata
    metadata = []
    
    # Timestamps
    created_time = getattr(note, 'created_time', None)
    if created_time:
        created_date = format_timestamp(created_time)
        if created_date:
            metadata.append(f"Created: {created_date}")
    
    updated_time = getattr(note, 'updated_time', None)
    if updated_time:
        updated_date = format_timestamp(updated_time)
        if updated_date:
            metadata.append(f"Updated: {updated_date}")
    
    # Notebook
    parent_id = getattr(note, 'parent_id', None)
    if parent_id:
        metadata.append(f"Notebook: {parent_id}")
    
    if metadata:
        result_parts.append("**Metadata:**")
        result_parts.extend(f"- {m}" for m in metadata)
    
    return "\n".join(result_parts)

def format_search_results(query: str, results: List[Any], context: str = "search_results") -> str:
    """Format search results for display."""
    count = len(results)
    result_parts = [f'Found {count} note(s) for query: "{query}"', ""]
    
    # Check content exposure settings
    config = _module_config
    should_show_content = config.should_show_content(context)
    should_show_full_content = config.should_show_full_content(context)
    max_preview_length = config.get_max_preview_length()
    
    for note in results:
        title = getattr(note, 'title', 'Untitled')
        note_id = getattr(note, 'id', 'unknown')
        
        result_parts.append(f"**{title}** (ID: {note_id})")
        
        # Handle content based on exposure settings
        if should_show_content:
            body = getattr(note, 'body', '')
            if body:
                if should_show_full_content:
                    result_parts.append(body)
                else:
                    # Show preview only
                    preview = body[:max_preview_length]
                    if len(body) > max_preview_length:
                        preview += "..."
                    result_parts.append(preview)
        
        # Add creation and modification dates
        dates = []
        created_time = getattr(note, 'created_time', None)
        if created_time:
            created_date = format_timestamp(created_time, "%Y-%m-%d %H:%M")
            if created_date:
                dates.append(f"Created: {created_date}")
        
        updated_time = getattr(note, 'updated_time', None)
        if updated_time:
            updated_date = format_timestamp(updated_time, "%Y-%m-%d %H:%M")
            if updated_date:
                dates.append(f"Updated: {updated_date}")
        
        if dates:
            result_parts.append(f"   {' | '.join(dates)}")
        
        result_parts.append("")
    
    return "\n".join(result_parts)

def format_tag_list_with_counts(tags: List[Any], client: Any) -> str:
    """Format a list of tags with note counts for display."""
    emoji = get_item_emoji(ItemType.tag)
    
    if not tags:
        return f"{emoji} No tags found\n\nYour Joplin instance doesn't contain any tags yet."
    
    count = len(tags)
    result_parts = [f"{emoji} Found {count} tag{'s' if count != 1 else ''}", ""]
    
    for i, tag in enumerate(tags, 1):
        title = getattr(tag, 'title', 'Untitled')
        tag_id = getattr(tag, 'id', 'unknown')
        
        # Get note count for this tag
        try:
            fields_list = "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed"
            notes_result = client.get_notes(tag_id=tag_id, fields=fields_list)
            notes = process_search_results(notes_result)
            note_count = len(notes)
        except Exception:
            note_count = 0
        
        result_parts.append(f"**{i}. {title}** ({note_count} note{'s' if note_count != 1 else ''})")
        result_parts.append(f"   ID: {tag_id}")
        
        # Add creation time if available
        created_time = getattr(tag, 'created_time', None)
        if created_time:
            created_date = format_timestamp(created_time, "%Y-%m-%d %H:%M")
            if created_date:
                result_parts.append(f"   Created: {created_date}")
        
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
        str: "✅ Joplin server connection successful" if connected, or "❌ Joplin server connection failed" with error details if not.
    """
    try:
        client = get_joplin_client()
        client.ping()
        return "✅ Joplin server connection successful\n\nThe Joplin server is responding and accessible."
    except Exception as e:
        return f"❌ Joplin server connection failed\n\nUnable to reach the Joplin server. Please check your connection settings.\n\nError: {str(e)}"

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
    fields_list = "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed"
    note = client.get_note(note_id, fields=fields_list)
    
    return format_note_details(note, include_body, "individual_notes")

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
    query: Annotated[str, "Text to search for in note titles and content. Example: 'meeting' or 'project planning' or 'grocery list'"],
    limit: Annotated[int, "Maximum number of notes to return. Must be between 1 and 100. Default is 20."] = 20,
    task: Annotated[Union[bool, str, None], "Filter by task type. True for tasks only, False for regular notes only, None for all notes. Default is None (all notes)."] = None,
    completed: Annotated[Union[bool, str, None], "Filter by completion status (only relevant when task=True). True for completed tasks, False for uncompleted tasks, None for all tasks. Default is None (all tasks)."] = None
) -> str:
    """Find notes by searching their titles and content for specific text.
    
    Simple text search through all notes. Use this when you want to find notes containing
    specific words or phrases, regardless of which notebook or tag they have.
    
    Parameters:
        query (str): Text to search for in note titles and content. Required.
        limit (int): Maximum number of notes to return. Must be between 1 and 100. Default is 20.
        task (bool, optional): Filter by task type. True = tasks only, False = regular notes only, None = all notes. Default is None.
        completed (bool, optional): Filter by completion status (only relevant when task=True). 
                                   True = completed tasks only, False = uncompleted tasks only, None = all tasks. 
                                   Default is None.
    
    Returns:
        str: List of notes containing the search text, with title, ID, content preview, and dates.
    
    Examples:
        - find_notes("meeting") - Find all notes containing "meeting"
        - find_notes("meeting", task=True) - Find only tasks containing "meeting"
        - find_notes("meeting", task=True, completed=False) - Find only uncompleted tasks containing "meeting"
        - find_notes("grocery list", task=False) - Find only regular notes containing "grocery list"
        
    💡 TIP: For tag-specific searches, use find_notes_with_tag("tag_name") instead.
    💡 TIP: For notebook-specific searches, use find_notes_in_notebook("notebook_name") instead.
    """
    limit = validate_limit(limit)
    task = validate_boolean_param(task, "task")
    completed = validate_boolean_param(completed, "completed")
    
    client = get_joplin_client()
    
    # Build search query with filters
    search_parts = [query]
    
    # Add task filter if specified
    if task is not None:
        if task:
            search_parts.append("type:todo")
        else:
            search_parts.append("type:note")
    
    # Add completion filter if specified (only relevant for tasks)
    if completed is not None and task is not False:
        if completed:
            search_parts.append("iscompleted:1")
        else:
            search_parts.append("iscompleted:0")
    
    search_query = " ".join(search_parts)
    search_query = validate_required_param(search_query, "query")
    
    # Use search_all for full pagination support
    fields_list = "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed"
    results = client.search_all(query=search_query, fields=fields_list)
    notes = process_search_results(results)
    
    # Apply limit
    notes = notes[:limit]
    
    if not notes:
        # Create descriptive message based on search criteria
        criteria_parts = [f'containing "{query}"']
        if task is True:
            criteria_parts.append("(tasks only)")
        elif task is False:
            criteria_parts.append("(regular notes only)")
        if completed is True:
            criteria_parts.append("(completed)")
        elif completed is False:
            criteria_parts.append("(uncompleted)")
        
        criteria_str = " ".join(criteria_parts)
        return format_no_results_message("note", criteria_str)
    
    return format_search_results(f'text search: {search_query}', notes, "search_results")

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
    fields_list = "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed"
    results = client.get_all_notes(fields=fields_list)
    notes = process_search_results(results)
    
    # Sort by updated time, newest first
    notes = sorted(notes, key=lambda x: getattr(x, 'updated_time', 0), reverse=True)
    
    # Apply limit
    notes = notes[:limit]
    
    if not notes:
        return format_no_results_message("note")
    
    return format_search_results("all notes", notes, "search_results")

@create_tool("find_notes_with_tag", "Find notes with tag")
async def find_notes_with_tag(
    tag_name: Annotated[str, "The tag name to search for. Example: 'time-slip' or 'work' or 'important'"],
    limit: Annotated[int, "Maximum number of notes to return. Must be between 1 and 100. Default is 20."] = 20,
    task: Annotated[Union[bool, str, None], "Filter by task type. True for tasks only, False for regular notes only, None for all notes. Default is None (all notes)."] = None,
    completed: Annotated[Union[bool, str, None], "Filter by completion status (only relevant when task=True). True for completed tasks, False for uncompleted tasks, None for all tasks. Default is None (all tasks)."] = None
) -> str:
    """Find all notes that have a specific tag.
    
    This is the MAIN function for finding notes by tag. Use this when you want to find
    all notes tagged with a specific tag name.
    
    Parameters:
        tag_name (str): The tag name to search for. Required.
        limit (int): Maximum number of notes to return. Must be between 1 and 100. Default is 20.
        task (bool, optional): Filter by task type. True = tasks only, False = regular notes only, None = all notes. Default is None.
        completed (bool, optional): Filter by completion status (only relevant when task=True). 
                                   True = completed tasks only, False = uncompleted tasks only, None = all tasks. 
                                   Default is None.
    
    Returns:
        str: List of all notes with the specified tag.
    
    Examples:
        - find_notes_with_tag("time-slip") - Find all notes tagged with "time-slip"
        - find_notes_with_tag("work", task=True) - Find only tasks tagged with "work"
        - find_notes_with_tag("important", task=True, completed=False) - Find only uncompleted tasks tagged with "important"
        - find_notes_with_tag("personal", task=False) - Find only regular notes tagged with "personal"
    """
    tag_name = validate_required_param(tag_name, "tag_name")
    limit = validate_limit(limit)
    task = validate_boolean_param(task, "task")
    completed = validate_boolean_param(completed, "completed")
    
    # Build search query with filters
    search_parts = [f"tag:{tag_name.strip()}"]
    
    # Add task filter if specified
    if task is not None:
        if task:
            search_parts.append("type:todo")
        else:
            search_parts.append("type:note")
    
    # Add completion filter if specified (only relevant for tasks)
    if completed is not None and task is not False:
        if completed:
            search_parts.append("iscompleted:1")
        else:
            search_parts.append("iscompleted:0")
    
    search_query = " ".join(search_parts)
    
    # Use search_all API with tag constraint for full pagination support
    client = get_joplin_client()
    
    fields_list = "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed"
    results = client.search_all(query=search_query, fields=fields_list)
    notes = process_search_results(results)
    
    # Apply limit
    notes = notes[:limit]
    
    if not notes:
        # Create descriptive message based on search criteria
        criteria_parts = [f'with tag "{tag_name}"']
        if task is True:
            criteria_parts.append("(tasks only)")
        elif task is False:
            criteria_parts.append("(regular notes only)")
        if completed is True:
            criteria_parts.append("(completed)")
        elif completed is False:
            criteria_parts.append("(uncompleted)")
        
        criteria_str = " ".join(criteria_parts)
        return format_no_results_message("note", criteria_str)
    
    return format_search_results(f'tag search: {search_query}', notes, "search_results")

@create_tool("find_notes_in_notebook", "Find notes in notebook")  
async def find_notes_in_notebook(
    notebook_name: Annotated[str, "The notebook name to search in. Example: 'Work Projects' or 'Personal Notes'"],
    limit: Annotated[int, "Maximum number of notes to return. Must be between 1 and 100. Default is 20."] = 20,
    task: Annotated[Union[bool, str, None], "Filter by task type. True for tasks only, False for regular notes only, None for all notes. Default is None (all notes)."] = None,
    completed: Annotated[Union[bool, str, None], "Filter by completion status (only relevant when task=True). True for completed tasks, False for uncompleted tasks, None for all tasks. Default is None (all tasks)."] = None
) -> str:
    """Find all notes in a specific notebook.
    
    This is the MAIN function for finding notes by notebook. Use this when you want to find
    all notes in a specific notebook.
    
    Parameters:
        notebook_name (str): The notebook name to search in. Required.
        limit (int): Maximum number of notes to return. Must be between 1 and 100. Default is 20.
        task (bool, optional): Filter by task type. True = tasks only, False = regular notes only, None = all notes. Default is None.
        completed (bool, optional): Filter by completion status (only relevant when task=True). 
                                   True = completed tasks only, False = uncompleted tasks only, None = all tasks. 
                                   Default is None.
    
    Returns:
        str: List of all notes in the specified notebook.
    
    Examples:
        - find_notes_in_notebook("Work Projects") - Find all notes in "Work Projects"
        - find_notes_in_notebook("Personal Notes", task=True) - Find only tasks in "Personal Notes"
        - find_notes_in_notebook("Projects", task=True, completed=False) - Find only uncompleted tasks in "Projects"
        - find_notes_in_notebook("Archive", task=False) - Find only regular notes in "Archive"
    """
    notebook_name = validate_required_param(notebook_name, "notebook_name")
    limit = validate_limit(limit)
    task = validate_boolean_param(task, "task")
    completed = validate_boolean_param(completed, "completed")
    
    # Build search query with filters
    search_parts = [f"notebook:{notebook_name.strip()}"]
    
    # Add task filter if specified
    if task is not None:
        if task:
            search_parts.append("type:todo")
        else:
            search_parts.append("type:note")
    
    # Add completion filter if specified (only relevant for tasks)
    if completed is not None and task is not False:
        if completed:
            search_parts.append("iscompleted:1")
        else:
            search_parts.append("iscompleted:0")
    
    search_query = " ".join(search_parts)
    
    # Use search_all API with notebook constraint for full pagination support
    client = get_joplin_client()
    
    fields_list = "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed"
    results = client.search_all(query=search_query, fields=fields_list)
    notes = process_search_results(results)
    
    # Apply limit
    notes = notes[:limit]
    
    if not notes:
        # Create descriptive message based on search criteria
        criteria_parts = [f'in notebook "{notebook_name}"']
        if task is True:
            criteria_parts.append("(tasks only)")
        elif task is False:
            criteria_parts.append("(regular notes only)")
        if completed is True:
            criteria_parts.append("(completed)")
        elif completed is False:
            criteria_parts.append("(uncompleted)")
        
        criteria_str = " ".join(criteria_parts)
        return format_no_results_message("note", criteria_str)
    
    return format_search_results(f'notebook search: {search_query}', notes, "search_results")



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
        fields_list = "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed"
        note = client.get_note(note_id, fields=fields_list)
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
        fields_list = "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed"
        note = client.get_note(note_id, fields=fields_list)
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