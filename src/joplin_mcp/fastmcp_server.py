"""FastMCP-based Joplin MCP Server Implementation.
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
    include_body: Annotated[bool, "Whether to include the note's content/body in the response. Set to True to see the full note content, False to only see metadata like title, dates, and IDs. Default is True."] = True
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
    client = get_joplin_client()
    
    # Use string format for fields (list format causes SQL errors)
    fields_list = "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed"
    note = client.get_note(note_id, fields=fields_list)
    
    return format_note_details(note, include_body, "individual_notes")

@create_tool("create_note", "Create note")
async def create_note(
    title: Annotated[str, "The title/name of the new note. This is required and will be displayed in Joplin's note list. Example: 'My Important Note' or 'Meeting Notes - Jan 15'"], 
    parent_id: Annotated[str, "The unique identifier of the notebook where this note should be created. This is required - you must specify which notebook to put the note in. Use list_notebooks or get_notebook tools to find the correct notebook ID."], 
    body: Annotated[str, "The content/text of the note. This can be plain text or Markdown. Leave empty to create a note with no content initially. Example: 'This is my note content with **bold** and *italic* text.'"] = "",
    is_todo: Annotated[bool, "Whether this note should be created as a todo/task item. Set to True to make it a checkable todo item, False for a regular note. Default is False."] = False,
    todo_completed: Annotated[bool, "Whether the todo item should be marked as completed when created. Only relevant if is_todo=True. Set to True to create a completed todo, False for uncompleted. Default is False."] = False
) -> str:
    """Create a new note in a specified notebook in Joplin.
    
    This tool creates a new note with the specified title, content, and properties in the given notebook.
    Creates a new note with the specified title, content, and properties. The note can be a regular note or a todo item.
    
    Parameters:
        title (str): The title of the new note. Required.
        parent_id (str): The unique identifier of the notebook where the note should be created. Required.
                        Use list_notebooks() to find available notebook IDs.
        body (str): The content of the note. Can be plain text or Markdown. Optional, defaults to empty.
        is_todo (bool): Whether to create as a todo/task item. Optional, defaults to False.
        todo_completed (bool): Whether the todo should be marked as completed when created. 
                              Only relevant if is_todo=True. Optional, defaults to False.
    
    Returns:
        str: Success message with the created note's title and unique ID that can be used to reference this note.
    
    Examples:
        - create_note("Shopping List", "notebook123", "- Milk\n- Eggs", True, False) - Create uncompleted todo
        - create_note("Meeting Notes", "work_notebook", "# Meeting with Client", False, False) - Create regular note
    """
    title = validate_required_param(title, "title")
    parent_id = validate_required_param(parent_id, "parent_id")
    
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
    is_todo: Annotated[Optional[bool], "Whether to convert the note to/from a todo item. Optional - only updates if provided."] = None,
    todo_completed: Annotated[Optional[bool], "Whether to mark the todo as completed. Only relevant if note is a todo. Optional - only updates if provided."] = None
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

@create_tool("search_notes", "Search notes")
async def search_notes(
    query: Annotated[str, "The search query to find notes. Can be a word, phrase, or '*' to get all notes. Joplin supports full-text search through note titles and content. Example: 'meeting' or 'project planning' or 'grocery list'"], 
    limit: Annotated[int, "Maximum number of notes to return in the search results. Must be between 1 and 100. Default is 20. Use smaller values for quick overviews, larger values for comprehensive searches."] = 20,
    notebook_id: Annotated[Optional[str], "Optional notebook ID to limit search to notes within a specific notebook. If provided, only notes in that notebook will be searched. Leave empty to search all notebooks. Example: 'notebook123456789abcdef'"] = None,
    sort_by: Annotated[SortBy, "How to sort the search results. Options: 'title' (alphabetical), 'created_time' (when created), 'updated_time' (when last modified), 'relevance' (search relevance). Default is 'updated_time' to show most recently modified notes first."] = SortBy.updated_time,
    sort_order: Annotated[SortOrder, "Sort direction for the results. Options: 'asc' (ascending/oldest first), 'desc' (descending/newest first). Default is 'desc' to show newest/most recent results first."] = SortOrder.desc
) -> str:
    """Search for notes using full-text search across titles and content.
    
    Searches through all notes in Joplin using the provided query. Performs full-text search on both note titles and content.
    
    Parameters:
        query (str): The search term or phrase to look for in notes. Required.
                    Use "*" to get all notes. Search is case-insensitive.
        limit (int): Maximum number of results to return. Must be between 1 and 100. Default is 20.
        notebook_id (str, optional): Limit search to notes within a specific notebook. Use list_notebooks() to find IDs.
        sort_by (SortBy): How to sort results. Options: 'title', 'created_time', 'updated_time', 'relevance'. Default is 'updated_time'.
        sort_order (SortOrder): Sort direction. 'asc' (ascending) or 'desc' (descending). Default is 'desc'.
    
    Returns:
        str: Formatted list of matching notes with title, ID, content (if privacy allows), and dates.
    
    Examples:
        - search_notes("meeting") - Find all notes containing "meeting"
        - search_notes("project", 10) - Find up to 10 notes about projects
        - search_notes("*", 5, None, "title", "asc") - Get 5 notes sorted by title A-Z
    """
    query = validate_required_param(query, "query")
    limit = validate_limit(limit)
    
    client = get_joplin_client()
    
    # Get notes based on query with timestamp fields
    fields_list = "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed"
    if query == "*":
        results = client.get_notes(fields=fields_list)
    else:
        results = client.search(query=query, fields=fields_list)
    
    notes = process_search_results(results)
    
    # Filter by notebook if specified
    if notebook_id:
        notes = [n for n in notes if getattr(n, 'parent_id', None) == notebook_id]
    
    # Apply limit
    notes = notes[:limit]
    
    if not notes:
        return format_no_results_message("note", f'for query: "{query}"')
    
    return format_search_results(query, notes, "search_results")

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

@create_tool("get_notebook", "Get notebook")
async def get_notebook(
    notebook_id: Annotated[str, "The unique identifier of the notebook to retrieve. Required."]
) -> str:
    """Get a specific notebook by ID.
    
    Retrieves detailed information about a single notebook including its title, ID, parent notebook, and creation date.
    
    Parameters:
        notebook_id (str): The unique identifier of the notebook to retrieve. Required.
    
    Returns:
        str: Formatted notebook details including title, ID, parent notebook (if sub-notebook), and creation date.
    
    Examples:
        - get_notebook("notebook123") - Get details for the specified notebook
    """
    notebook_id = validate_required_param(notebook_id, "notebook_id")
    client = get_joplin_client()
    fields_list = "id,title,created_time,updated_time,parent_id"
    notebook = client.get_notebook(notebook_id, fields=fields_list)
    return format_item_details(notebook, ItemType.notebook)

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

@create_tool("search_notebooks", "Search notebooks")
async def search_notebooks(
    query: Annotated[str, "The search query to find notebooks by title. Required."],
    limit: Annotated[int, "Maximum number of notebooks to return. Must be between 1 and 100. Default is 20."] = 20
) -> str:
    """Search notebooks by title.
    
    Searches for notebooks that match the query in their title. Search is case-insensitive.
    
    Parameters:
        query (str): The search query to find notebooks by title. Required.
        limit (int): Maximum number of notebooks to return. Must be between 1 and 100. Default is 20.
    
    Returns:
        str: Formatted list of matching notebooks with title, ID, parent notebook, and creation date.
    
    Examples:
        - search_notebooks("work") - Find notebooks with "work" in the title
        - search_notebooks("project", 5) - Find up to 5 notebooks with "project" in the title
    """
    query = validate_required_param(query, "query")
    limit = validate_limit(limit)
    
    client = get_joplin_client()
    fields_list = "id,title,created_time,updated_time,parent_id"
    all_notebooks = client.get_all_notebooks(fields=fields_list)
    matching_notebooks = filter_items_by_title(all_notebooks, query)[:limit]
    
    if not matching_notebooks:
        return format_no_results_message("notebook", f'for query: "{query}"')
    
    return format_item_list(matching_notebooks, ItemType.notebook)

@create_tool("get_notes_by_notebook", "Get notes by notebook")
async def get_notes_by_notebook(
    notebook_id: Annotated[str, "The unique identifier of the notebook to get notes from. Required."],
    limit: Annotated[int, "Maximum number of notes to return. Must be between 1 and 100. Default is 20."] = 20
) -> str:
    """Get all notes in a specific notebook.
    
    Retrieves all notes contained within a specific notebook, showing their titles, IDs, content, and metadata.
    
    Parameters:
        notebook_id (str): The unique identifier of the notebook to get notes from. Required.
        limit (int): Maximum number of notes to return. Must be between 1 and 100. Default is 20.
    
    Returns:
        str: Formatted list of notes in the notebook with title, ID, content (if privacy allows), and dates.
    
    Examples:
        - get_notes_by_notebook("notebook123") - Get all notes from the specified notebook
        - get_notes_by_notebook("notebook123", 10) - Get up to 10 notes from the notebook
    """
    notebook_id = validate_required_param(notebook_id, "notebook_id")
    limit = validate_limit(limit)
    
    client = get_joplin_client()
    fields_list = "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed"
    notes_result = client.get_notes(notebook_id=notebook_id, fields=fields_list)
    notes = process_search_results(notes_result)[:limit]
    
    if not notes:
        return format_no_results_message("note", f"in notebook: {notebook_id}")
    
    return format_search_results(f"notebook {notebook_id}", notes, "listings")

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

@create_tool("get_tag", "Get tag")
async def get_tag(
    tag_id: Annotated[str, "The unique identifier of the tag to retrieve. Required."]
) -> str:
    """Get a specific tag by ID.
    
    Retrieves detailed information about a single tag including its title, ID, and creation date.
    
    Parameters:
        tag_id (str): The unique identifier of the tag to retrieve. Required.
    
    Returns:
        str: Formatted tag details including title, ID, and creation date.
    
    Examples:
        - get_tag("tag123") - Get details for the specified tag
    """
    tag_id = validate_required_param(tag_id, "tag_id")
    client = get_joplin_client()
    fields_list = "id,title,created_time,updated_time"
    tag = client.get_tag(tag_id, fields=fields_list)
    return format_item_details(tag, ItemType.tag)

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

@create_tool("search_tags", "Search tags")
async def search_tags(
    query: Annotated[str, "The search query to find tags by title. Required."],
    limit: Annotated[int, "Maximum number of tags to return. Must be between 1 and 100. Default is 20."] = 20
) -> str:
    """Search tags by title.
    
    Searches for tags that match the query in their title. Search is case-insensitive.
    
    Parameters:
        query (str): The search query to find tags by title. Required.
        limit (int): Maximum number of tags to return. Must be between 1 and 100. Default is 20.
    
    Returns:
        str: Formatted list of matching tags with title, ID, and creation date.
    
    Examples:
        - search_tags("work") - Find tags with "work" in the title
        - search_tags("project", 5) - Find up to 5 tags with "project" in the title
    """
    query = validate_required_param(query, "query")
    limit = validate_limit(limit)
    
    client = get_joplin_client()
    fields_list = "id,title,created_time,updated_time"
    all_tags = client.get_all_tags(fields=fields_list)
    matching_tags = filter_items_by_title(all_tags, query)[:limit]
    
    if not matching_tags:
        return format_no_results_message("tag", f'for query: "{query}"')
    
    return format_item_list(matching_tags, ItemType.tag)

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

@create_tool("get_notes_by_tag", "Get notes by tag")
async def get_notes_by_tag(
    tag_id: Annotated[str, "The unique identifier of the tag to get notes from. Required."],
    limit: Annotated[int, "Maximum number of notes to return. Must be between 1 and 100. Default is 20."] = 20
) -> str:
    """Get all notes with a specific tag.
    
    Retrieves all notes that have been tagged with a specific tag, showing their titles, IDs, content, and metadata.
    
    Parameters:
        tag_id (str): The unique identifier of the tag to get notes from. Required.
        limit (int): Maximum number of notes to return. Must be between 1 and 100. Default is 20.
    
    Returns:
        str: Formatted list of notes with the specified tag including title, ID, content (if privacy allows), and dates.
             Returns "No notes found with tag" if no notes have this tag.
    
    Examples:
        - get_notes_by_tag("tag123") - Get all notes with the specified tag
        - get_notes_by_tag("tag123", 10) - Get up to 10 notes with the tag
    """
    tag_id = validate_required_param(tag_id, "tag_id")
    limit = validate_limit(limit)
    
    client = get_joplin_client()
    fields_list = "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed"
    notes_result = client.get_notes(tag_id=tag_id, fields=fields_list)
    notes = process_search_results(notes_result)[:limit]
    
    if not notes:
        return format_no_results_message("note", f"with tag: {tag_id}")
    
    return format_search_results(f"tag {tag_id}", notes, "listings")

# === TAG-NOTE RELATIONSHIP OPERATIONS ===

async def _tag_note_impl(note_id: str, tag_id: str) -> str:
    """Shared implementation for adding a tag to a note."""
    note_id = validate_required_param(note_id, "note_id")
    tag_id = validate_required_param(tag_id, "tag_id")
    
    client = get_joplin_client()
    client.add_tag_to_note(tag_id, note_id)
    return format_relation_success("tagged note", ItemType.note, note_id, ItemType.tag, tag_id)

async def _untag_note_impl(note_id: str, tag_id: str) -> str:
    """Shared implementation for removing a tag from a note."""
    note_id = validate_required_param(note_id, "note_id")
    tag_id = validate_required_param(tag_id, "tag_id")
    
    client = get_joplin_client()
    client.remove_tag_from_note(tag_id, note_id)
    return format_relation_success("removed tag from note", ItemType.note, note_id, ItemType.tag, tag_id)

# Primary tag operations
@create_tool("tag_note", "Tag note")
async def tag_note(
    note_id: Annotated[str, "The unique identifier of the note to add a tag to. This is the note that will be tagged. Example: 'note123456789abcdef'"], 
    tag_id: Annotated[str, "The unique identifier of the tag to add to the note. This tag will be applied to the note for categorization. Example: 'tag987654321fedcba'"]
) -> str:
    """Add a tag to a note for categorization and organization.
    
    Applies an existing tag to a note, creating a relationship between them. Tags help you
    categorize and organize notes across different notebooks.
    
    Parameters:
        note_id (str): The unique identifier of the note to tag. Required.
                      Use get_note() or search_notes() to find note IDs.
        tag_id (str): The unique identifier of the tag to apply to the note. Required.
                     Use list_tags() or create_tag() to find or create tag IDs.
    
    Returns:
        str: Success message confirming the tag was added to the note.
    
    Examples:
        - tag_note("note123", "tag_work") - Add 'work' tag to a note
        - tag_note("meeting_note_id", "tag_important") - Mark a meeting note as important
    
    Note: Both the note and tag must exist in Joplin. A note can have multiple tags.
    """
    return await _tag_note_impl(note_id, tag_id)

@create_tool("untag_note", "Untag note")
async def untag_note(
    note_id: Annotated[str, "The unique identifier of the note to remove a tag from. Required."], 
    tag_id: Annotated[str, "The unique identifier of the tag to remove from the note. Required."]
) -> str:
    """Remove a tag from a note.
    
    Removes an existing tag from a note, breaking the relationship between them.
    
    Parameters:
        note_id (str): The unique identifier of the note to remove a tag from. Required.
        tag_id (str): The unique identifier of the tag to remove from the note. Required.
    
    Returns:
        str: Success message confirming the tag was removed from the note.
    
    Examples:
        - untag_note("note123", "tag_work") - Remove 'work' tag from a note
        - untag_note("meeting_note_id", "tag_important") - Remove 'important' tag from meeting note
    
    Note: Both the note and tag must exist in Joplin.
    """
    return await _untag_note_impl(note_id, tag_id)

# Alias tools (for backward compatibility)
@create_tool("add_tag_to_note", "Add tag to note")
async def add_tag_to_note(
    note_id: Annotated[str, "The unique identifier of the note to add a tag to. Required."], 
    tag_id: Annotated[str, "The unique identifier of the tag to add to the note. Required."]
) -> str:
    """Add a tag to a note (alias for tag_note).
    
    This is an alias for the tag_note function. Applies an existing tag to a note.
    
    Parameters:
        note_id (str): The unique identifier of the note to add a tag to. Required.
        tag_id (str): The unique identifier of the tag to add to the note. Required.
    
    Returns:
        str: Success message confirming the tag was added to the note.
    
    Examples:
        - add_tag_to_note("note123", "tag_work") - Add 'work' tag to a note
    """
    return await _tag_note_impl(note_id, tag_id)

@create_tool("remove_tag_from_note", "Remove tag from note")
async def remove_tag_from_note(
    note_id: Annotated[str, "The unique identifier of the note to remove a tag from. Required."], 
    tag_id: Annotated[str, "The unique identifier of the tag to remove from the note. Required."]
) -> str:
    """Remove a tag from a note (alias for untag_note).
    
    This is an alias for the untag_note function. Removes an existing tag from a note.
    
    Parameters:
        note_id (str): The unique identifier of the note to remove a tag from. Required.
        tag_id (str): The unique identifier of the tag to remove from the note. Required.
    
    Returns:
        str: Success message confirming the tag was removed from the note.
    
    Examples:
        - remove_tag_from_note("note123", "tag_work") - Remove 'work' tag from a note
    """
    return await _untag_note_impl(note_id, tag_id)

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
            "version": "FastMCP-based Joplin Server v1.0.0"
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