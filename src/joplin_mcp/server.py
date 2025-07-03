"""Joplin MCP Server Implementation."""

import logging
import time
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import Mock
import asyncio

# Import MCP components - with fallback for development
try:
    from mcp.server import Server
    from mcp.types import (
        Prompt,
        PromptsCapability,
        Resource,
        ResourcesCapability,
        ServerCapabilities,
        Tool,
        ToolsCapability,
    )

    MCP_AVAILABLE = True
except ImportError:
    # Mock MCP components for development
    from unittest.mock import MagicMock

    Server = MagicMock()
    Tool = MagicMock()
    Prompt = MagicMock()
    Resource = MagicMock()
    ServerCapabilities = MagicMock()
    ToolsCapability = MagicMock()
    PromptsCapability = MagicMock()
    ResourcesCapability = MagicMock()
    MCP_AVAILABLE = False

from joplin_mcp.client import JoplinMCPClient

# Configure structured logging
logger = logging.getLogger(__name__)

# Add rate limiting constants for security
RATE_LIMIT_REQUESTS_PER_MINUTE = 60
RATE_LIMIT_WINDOW_SIZE = 60  # seconds

class JoplinMCPServer:
    """MCP Server for Joplin note-taking application."""

    def __init__(
        self,
        token: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        timeout: Optional[int] = None,
        config: Optional[Any] = None,
        client: Optional[JoplinMCPClient] = None,
        skip_ping: Optional[bool] = False,
    ):
        """Initialize Joplin MCP Server.

        Args:
            token: Joplin API token
            host: Joplin server host
            port: Joplin server port
            timeout: Request timeout
            config: Configuration object (optional)
            client: Pre-configured client (optional)
            skip_ping: Skip ping validation during init (optional)
        """
        logger.info("Initializing Joplin MCP Server", extra={
            "host": host or "localhost",
            "port": port or 41184,
            "has_token": bool(token),
            "has_config": bool(config),
            "has_client": bool(client),
            "skip_ping": skip_ping
        })
        
        # Initialize rate limiting
        self._request_timestamps = []
        
        # Validate required parameters
        if not token and not config and not client:
            logger.error("Server initialization failed: missing token")
            raise Exception("Token is required for Joplin MCP server initialization")

        # Validate configuration parameters BEFORE creating client
        if host == "":
            logger.error("Invalid configuration: empty host parameter")
            raise Exception("Invalid host parameter")
        if port is not None and (port < 1 or port > 65535):
            logger.error("Invalid configuration: port out of range", extra={"port": port})
            raise Exception("Invalid port parameter - must be between 1 and 65535")
        if timeout is not None and timeout < 0:
            logger.error("Invalid configuration: negative timeout", extra={"timeout": timeout})
            raise Exception("Invalid timeout parameter - must be positive")

        # Store configuration
        self.token = token
        self.host = host or "localhost"
        self.port = port or 41184
        self.timeout = timeout or 30
        self.config = config

        # Server metadata
        self.server_name = "joplin-mcp"
        self.server_version = "0.1.0"

        # Initialize Joplin client
        if client:
            self.client = client
        elif config:
            # Use the config object directly
            self.client = JoplinMCPClient(config=config)
        else:
            self.client = JoplinMCPClient(
                host=self.host, port=self.port, token=self.token, timeout=self.timeout
            )

        # Validate connection to Joplin (skip if client is mocked for testing or explicitly skipped)
        if not skip_ping:
            try:
                # Check if client is a mock (for testing)
                if (
                    hasattr(self.client, "_mock_name")
                    or str(type(self.client)).find("Mock") != -1
                ):
                    # Skip validation for mock clients
                    pass
                else:
                    if not self.client.ping():
                        logger.warning("Failed initial ping to Joplin server - continuing anyway")
            except Exception as e:
                # Only raise if it's not a mock client
                if not (
                    hasattr(self.client, "_mock_name")
                    or str(type(self.client)).find("Mock") != -1
                ):
                    logger.warning(f"Joplin connection validation failed: {e} - continuing anyway")

        # Create underlying MCP server
        self._mcp_server: Any = Server(self.server_name)

        # Initialize server state
        self.is_running = False

        # Setup MCP handlers
        self._setup_mcp_handlers()

    def _setup_mcp_handlers(self) -> None:
        """Setup MCP protocol handlers."""
        if not MCP_AVAILABLE:
            return
            
        # Set up tool handlers using the correct MCP Python SDK approach
        @self._mcp_server.call_tool()
        async def handle_tool_call(name: str, arguments: dict) -> list:
            """Handle MCP tool calls with automatic parameter validation and hints."""
            try:
                self._check_rate_limit()
                
                # Pre-validate parameters and provide hints if needed
                validation_result = self._validate_and_enhance_parameters(name, arguments)
                if validation_result["enhanced_params"] is not None:
                    arguments = validation_result["enhanced_params"]
                
                # Route to appropriate handler based on tool name
                if name == "search_notes":
                    result = await self.handle_search_notes(arguments)
                elif name == "get_note":
                    result = await self.handle_get_note(arguments)
                elif name == "create_note":
                    result = await self.handle_create_note(arguments)
                elif name == "update_note":
                    result = await self.handle_update_note(arguments)
                elif name == "delete_note":
                    result = await self.handle_delete_note(arguments)
                elif name == "list_notebooks":
                    result = await self.handle_list_notebooks(arguments)
                elif name == "get_notebook":
                    result = await self.handle_get_notebook(arguments)
                elif name == "create_notebook":
                    result = await self.handle_create_notebook(arguments)
                elif name == "delete_notebook":
                    result = await self.handle_delete_notebook(arguments)
                elif name == "list_tags":
                    result = await self.handle_list_tags(arguments)
                elif name == "create_tag":
                    result = await self.handle_create_tag(arguments)
                elif name == "delete_tag":
                    result = await self.handle_delete_tag(arguments)
                elif name == "tag_note":
                    result = await self.handle_tag_note(arguments)
                elif name == "add_tag_to_note":
                    result = await self.handle_tag_note(arguments)  # Same as tag_note
                elif name == "untag_note":
                    result = await self.handle_untag_note(arguments)
                elif name == "remove_tag_from_note":
                    result = await self.handle_untag_note(arguments)  # Same as untag_note
                elif name == "ping_joplin":
                    result = await self.handle_ping_joplin(arguments)
                else:
                    return [{"type": "text", "text": f"Unknown tool: {name}"}]
                
                # Convert result to MCP format
                if isinstance(result, dict) and "content" in result:
                    return result["content"]
                else:
                    return [{"type": "text", "text": str(result)}]
                    
            except Exception as e:
                error_context = self.get_error_context(e, f"tool_{name}")
                logger.error("Tool execution failed", extra=error_context)
                
                # Check if this is a parameter validation error that we can help with
                error_str = str(e)
                if any(hint in error_str.lower() for hint in ["parameter", "required", "missing", "empty"]):
                    # Try to provide enhanced error guidance
                    validation_result = self._validate_and_enhance_parameters(name, arguments)
                    if validation_result["error"]:
                        return [{"type": "text", "text": validation_result["error"]}]
                
                # Fallback to basic error message
                return [{"type": "text", "text": f"Error executing {name}: {str(e)}"}]
        
        @self._mcp_server.list_tools()
        async def handle_list_tools() -> list:
            """Handle MCP list tools request."""
            return self.get_available_tools()
            
        logger.info("MCP tool handlers registered successfully")

    def get_capabilities(self) -> Any:
        """Get MCP server capabilities."""
        # Create mock capabilities object with required attributes
        capabilities = Mock()

        # Tool capabilities
        tools = Mock()
        tools.listChanged = True
        capabilities.tools = tools

        # Prompt capabilities
        prompts = Mock()
        prompts.listChanged = True
        capabilities.prompts = prompts

        # Resource capabilities
        resources = Mock()
        resources.subscribe = True
        resources.listChanged = True
        capabilities.resources = resources

        return capabilities

    def get_available_tools(self) -> List[Any]:
        """Get list of available MCP tools."""
        tools = []

        # Define all expected tools
        tool_definitions = [
            ("search_notes", "Search notes with full-text query"),
            ("get_note", "Retrieve a specific note by ID"),
            ("create_note", "Create a new note"),
            ("update_note", "Update an existing note"),
            ("delete_note", "Delete a note"),
            ("list_notebooks", "List all notebooks"),
            ("get_notebook", "Get notebook details"),
            ("create_notebook", "Create a new notebook"),
            ("delete_notebook", "Delete a notebook"),
            ("list_tags", "List all tags"),
            ("create_tag", "Create a new tag"),
            ("delete_tag", "Delete a tag"),
            ("tag_note", "Add tag to note"),
            ("add_tag_to_note", "Add tag to note"),
            ("untag_note", "Remove tag from note"),
            ("remove_tag_from_note", "Remove tag from note"),
            ("ping_joplin", "Test Joplin server connection"),
        ]

        for name, description in tool_definitions:
            # Use proper Tool object if MCP is available, otherwise Mock
            if MCP_AVAILABLE:
                tool = Tool(name=name, description=description, inputSchema={})
            else:
                tool = Mock()
                tool.name = name
                tool.description = description

            # Initialize basic schema structure
            schema: Dict[str, Any] = {"properties": {}}

            if name == "search_notes":
                schema["properties"] = {
                    "query": {
                        "type": "string",
                        "description": "Search query for full-text search across notes",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 20)",
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "notebook_id": {
                        "type": "string",
                        "description": "Optional notebook ID to limit search scope",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of tags to filter notes",
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Field to sort results by",
                        "enum": ["title", "created_time", "updated_time", "relevance"],
                    },
                    "sort_order": {
                        "type": "string",
                        "description": "Sort order for results",
                        "enum": ["asc", "desc"],
                    },
                }
                schema["required"] = ["query"]
            elif name == "get_note":
                schema["properties"] = {
                    "note_id": {
                        "type": "string",
                        "description": "Unique identifier of the note to retrieve",
                    },
                    "include_body": {
                        "type": "boolean",
                        "description": "Whether to include the note body in the response",
                        "default": True,
                    },
                }
                schema["required"] = ["note_id"]
            elif name == "create_note":
                schema["properties"] = {
                    "title": {
                        "type": "string",
                        "description": "Title of the new note (required)",
                    },
                    "body": {
                        "type": "string",
                        "description": "Content body of the note (optional)",
                        "default": "",
                    },
                    "parent_id": {
                        "type": "string",
                        "description": "ID of the parent notebook where the note will be created (required)",
                    },
                    "is_todo": {
                        "type": "boolean",
                        "description": "Whether this note is a todo item",
                        "default": False,
                    },
                    "todo_completed": {
                        "type": "boolean",
                        "description": "Whether the todo item is completed (only relevant if is_todo is true)",
                        "default": False,
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of tags to assign to the note (optional)",
                    },
                }
                schema["required"] = ["title", "parent_id"]
            elif name == "create_notebook":
                schema["properties"] = {
                    "title": {
                        "type": "string",
                        "description": "Title of the new notebook (required)",
                    },
                    "parent_id": {
                        "type": "string",
                        "description": "ID of the parent notebook (optional)",
                    },
                }
                schema["required"] = ["title"]
            elif name == "create_tag":
                schema["properties"] = {
                    "title": {
                        "type": "string",
                        "description": "Title of the new tag (required)",
                    },
                }
                schema["required"] = ["title"]
            elif name == "update_note":
                schema["properties"] = {
                    "note_id": {
                        "type": "string",
                        "description": "ID of the note to update (required)",
                    },
                    "title": {
                        "type": "string",
                        "description": "New title for the note (optional)",
                    },
                    "body": {
                        "type": "string",
                        "description": "New content body for the note (optional)",
                    },
                    "is_todo": {
                        "type": "boolean",
                        "description": "Whether this note is a todo item (optional)",
                    },
                    "todo_completed": {
                        "type": "boolean",
                        "description": "Whether the todo item is completed (optional)",
                    },
                    "parent_id": {
                        "type": "string",
                        "description": "ID of the parent notebook (optional)",
                    },
                }
                schema["required"] = ["note_id"]
            elif name == "delete_note":
                schema["properties"] = {
                    "note_id": {
                        "type": "string",
                        "description": "ID of the note to delete (required)",
                    },
                }
                schema["required"] = ["note_id"]
            elif name == "list_notebooks":
                # No required parameters for list_notebooks
                schema["required"] = []
            elif name == "get_notebook":
                schema["properties"] = {
                    "notebook_id": {
                        "type": "string",
                        "description": "ID of the notebook to retrieve (required)",
                    },
                }
                schema["required"] = ["notebook_id"]
            elif name == "delete_notebook":
                schema["properties"] = {
                    "notebook_id": {
                        "type": "string",
                        "description": "ID of the notebook to delete (required)",
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Whether to force deletion even if notebook has children (optional)",
                        "default": False,
                    },
                }
                schema["required"] = ["notebook_id"]
            elif name == "list_tags":
                # No required parameters for list_tags
                schema["required"] = []
            elif name == "delete_tag":
                schema["properties"] = {
                    "tag_id": {
                        "type": "string",
                        "description": "ID of the tag to delete (required)",
                    },
                }
                schema["required"] = ["tag_id"]
            elif name == "tag_note":
                schema["properties"] = {
                    "note_id": {
                        "type": "string",
                        "description": "ID of the note to tag (required)",
                    },
                    "tag_id": {
                        "type": "string",
                        "description": "ID of the tag to add (required)",
                    },
                }
                schema["required"] = ["note_id", "tag_id"]
            elif name == "untag_note":
                schema["properties"] = {
                    "note_id": {
                        "type": "string",
                        "description": "ID of the note to untag (required)",
                    },
                    "tag_id": {
                        "type": "string",
                        "description": "ID of the tag to remove (required)",
                    },
                }
                schema["required"] = ["note_id", "tag_id"]
            elif name == "add_tag_to_note":
                schema["properties"] = {
                    "note_id": {
                        "type": "string",
                        "description": "ID of the note to tag (required)",
                    },
                    "tag_id": {
                        "type": "string",
                        "description": "ID of the tag to add (required)",
                    },
                }
                schema["required"] = ["note_id", "tag_id"]
            elif name == "remove_tag_from_note":
                schema["properties"] = {
                    "note_id": {
                        "type": "string",
                        "description": "ID of the note to untag (required)",
                    },
                    "tag_id": {
                        "type": "string",
                        "description": "ID of the tag to remove (required)",
                    },
                }
                schema["required"] = ["note_id", "tag_id"]
            elif name == "ping_joplin":
                # No required parameters for ping
                schema["required"] = []

            # Add type and set required fields
            schema["type"] = "object"
            
            # Set the input schema based on tool type
            if MCP_AVAILABLE:
                # For proper Tool objects, we need to recreate with the schema
                tool = Tool(name=name, description=description, inputSchema=schema)
            else:
                # For Mock objects, just set the attribute
                tool.inputSchema = schema
                
            tools.append(tool)

        return tools

    def get_available_prompts(self) -> List[Any]:
        """Get list of available MCP prompts."""
        prompts = []

        # Define expected prompts
        prompt_definitions = [
            ("search_help", "Help with search syntax and tips"),
            ("note_template", "Template for creating structured notes"),
            ("tag_organization", "Help with organizing tags effectively"),
        ]

        for name, description in prompt_definitions:
            prompt = Mock()
            prompt.name = name
            prompt.description = description
            prompts.append(prompt)

        return prompts

    def get_available_resources(self) -> List[Any]:
        """Get list of available MCP resources."""
        resources = []

        # Define expected resources
        resource_definitions = [
            ("joplin://server_info", "Server Information"),
            ("joplin://notebooks", "Notebooks List"),
            ("joplin://tags", "Tags List"),
            ("joplin://statistics", "Usage Statistics"),
        ]

        for uri, name in resource_definitions:
            resource = Mock()
            resource.uri = uri
            resource.name = name
            resources.append(resource)

        return resources

    async def start(self) -> None:
        """Start the MCP server."""
        logger.info("Starting MCP server loop...")
        self.is_running = True
        
        # Check if MCP is available
        if not MCP_AVAILABLE:
            logger.warning("MCP framework not available - running in mock mode")
            # In mock mode, just run indefinitely
            try:
                while self.is_running:
                    await asyncio.sleep(1)
            except (KeyboardInterrupt, asyncio.CancelledError):
                logger.info("MCP server stopped")
                self.is_running = False
            return
        
        # Start the actual MCP server
        try:
            from mcp.server.stdio import stdio_server
            
            logger.info("Starting MCP server with stdio transport")
            
            # Setup tool list for MCP
            tools = self.get_available_tools()
            
            # Configure the server
            async with stdio_server() as (read_stream, write_stream):
                await self._mcp_server.run(
                    read_stream, 
                    write_stream, 
                    self._mcp_server.create_initialization_options()
                )
                
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("MCP server stopped")
            self.is_running = False
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            self.is_running = False
            # For now, fallback to mock mode to keep server running
            logger.info("Falling back to mock mode...")
            try:
                while self.is_running:
                    await asyncio.sleep(1)
            except (KeyboardInterrupt, asyncio.CancelledError):
                logger.info("MCP server stopped")
                self.is_running = False

    async def stop(self) -> None:
        """Stop the MCP server."""
        logger.info("Stopping MCP server...")
        self.is_running = False
        
        # If we have an actual MCP server, stop it
        if hasattr(self, '_mcp_server') and self._mcp_server:
            try:
                # MCP server cleanup if needed
                pass
            except Exception as e:
                logger.warning(f"Error during MCP server cleanup: {e}")
        
        logger.info("MCP server stopped")

    def __enter__(self) -> "JoplinMCPServer":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        pass

    async def __aenter__(self) -> "JoplinMCPServer":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        pass

    def get_server_info(self) -> Dict[str, Any]:
        """Get comprehensive server information."""
        return {
            "name": self.server_name,
            "version": self.server_version,
            "capabilities": self.get_capabilities(),
            "joplin_connection": {
                "host": self.host,
                "port": self.port,
                "connected": self.client.is_connected,
            },
        }

    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get schema for a specific tool."""
        tools = self.get_available_tools()
        for tool in tools:
            if tool.name == tool_name:
                return {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                }
        return None

    def validate_tool_input(
        self, tool_name: str, input_data: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """Validate tool input against schema."""
        schema = self.get_tool_schema(tool_name)
        if not schema:
            return False, [f"Unknown tool: {tool_name}"]

        errors = []
        required = schema["inputSchema"].get("required", [])
        properties = schema["inputSchema"].get("properties", {})

        # Check required parameters
        for param in required:
            if param not in input_data:
                errors.append(f"Missing required parameter: {param}")

        # Check parameter types and values
        for param, value in input_data.items():
            if param not in properties:
                errors.append(f"Unknown parameter: {param}")
                continue

            prop_schema = properties[param]
            expected_type = prop_schema.get("type")

            # Type validation
            if expected_type == "string":
                if not isinstance(value, str):
                    errors.append(f"Parameter '{param}' must be a string")
                elif value == "":
                    errors.append(f"Parameter '{param}' cannot be empty")
                # Check enum values
                elif "enum" in prop_schema and value not in prop_schema["enum"]:
                    errors.append(
                        f"Parameter '{param}' must be one of: {prop_schema['enum']}"
                    )
            elif expected_type == "integer":
                if not isinstance(value, int):
                    errors.append(f"Parameter '{param}' must be an integer")
                else:
                    # Check min/max constraints
                    if "minimum" in prop_schema and value < prop_schema["minimum"]:
                        errors.append(
                            f"Parameter '{param}' must be at least {prop_schema['minimum']}"
                        )
                    if "maximum" in prop_schema and value > prop_schema["maximum"]:
                        errors.append(
                            f"Parameter '{param}' must be at most {prop_schema['maximum']}"
                        )
            elif expected_type == "array":
                if not isinstance(value, list):
                    errors.append(f"Parameter '{param}' must be an array")
                elif "items" in prop_schema:
                    item_type = prop_schema["items"].get("type")
                    for i, item in enumerate(value):
                        if item_type == "string" and not isinstance(item, str):
                            errors.append(f"Parameter '{param}[{i}]' must be a string")

        return len(errors) == 0, errors

    def get_error_context(self, error: Exception, operation: str) -> Dict[str, Any]:
        """Get error context for debugging."""
        import time

        return {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "operation": operation,
            "timestamp": time.time(),
            "server_state": {
                "running": self.is_running,
                "server_name": self.server_name,
                "server_version": self.server_version,
            },
        }

    def _check_rate_limit(self) -> None:
        """Check rate limiting for security."""
        current_time = time.time()
        # Remove timestamps older than the window
        self._request_timestamps = [
            ts for ts in self._request_timestamps 
            if current_time - ts < RATE_LIMIT_WINDOW_SIZE
        ]
        
        if len(self._request_timestamps) >= RATE_LIMIT_REQUESTS_PER_MINUTE:
            logger.warning("Rate limit exceeded", extra={
                "requests_in_window": len(self._request_timestamps),
                "limit": RATE_LIMIT_REQUESTS_PER_MINUTE
            })
            raise Exception("Rate limit exceeded. Please try again later.")
        
        self._request_timestamps.append(current_time)
    
    def _validate_string_input(self, value: str, max_length: int = 1000) -> str:
        """Validate and sanitize string input for security."""
        if not isinstance(value, str):
            raise ValueError("Input must be a string")
        
        # Remove null bytes and control characters
        sanitized = ''.join(char for char in value if ord(char) >= 32 or char in '\t\n\r')
        
        if len(sanitized) > max_length:
            logger.warning("Input truncated due to length limit", extra={
                "original_length": len(sanitized),
                "max_length": max_length
            })
            sanitized = sanitized[:max_length]
        
        return sanitized

    def _build_parameter_correction_hint(
        self, 
        tool_name: str, 
        expected_param: str, 
        received_params: List[str], 
        common_alternatives: List[str] = None,
        received_value: str = None
    ) -> str:
        """Build a helpful parameter correction message for LLMs.

        Args:
            tool_name: Name of the tool being called
            expected_param: The correct parameter name expected
            received_params: List of parameters actually received
            common_alternatives: List of common alternative parameter names
            received_value: The value that was sent with wrong parameter name

        Returns:
            Formatted correction hint message
        """
        common_alternatives = common_alternatives or []
        
        # Build the correction message
        message_parts = [
            f"❌ Parameter Error in {tool_name}:",
            f"Expected parameter: '{expected_param}'",
        ]
        
        if received_params:
            message_parts.append(f"Received parameters: {received_params}")
            
            # Check if any received params match common alternatives
            matches = [p for p in received_params if p in common_alternatives]
            if matches:
                message_parts.append(f"💡 Hint: Use '{expected_param}' instead of '{matches[0]}'")
                if received_value:
                    message_parts.append(f"🔧 Correct usage: {{\"{expected_param}\": \"{received_value}\"}}")
        
        if common_alternatives:
            message_parts.append(f"✅ Accepted alternatives: {common_alternatives}")
            
        # Add correct usage example based on tool schema
        tool_schema = self.get_tool_schema(tool_name)
        if tool_schema and "inputSchema" in tool_schema:
            required_params = tool_schema["inputSchema"].get("required", [])
            message_parts.append(f"📋 Required parameters: {required_params}")
            
        message_parts.append(f"🔄 Please retry with the correct parameter name.")
        
        return "\n".join(message_parts)

    def _validate_and_enhance_parameters(self, tool_name: str, arguments: dict) -> Dict[str, Any]:
        """Centralized parameter validation and enhancement for all tools.
        
        This method:
        1. Validates parameters against the tool schema
        2. Provides helpful error messages for wrong parameters
        3. Auto-corrects common parameter name variations
        4. Returns enhanced parameters or error guidance
        
        Args:
            tool_name: Name of the tool being called
            arguments: Raw arguments from LLM
            
        Returns:
            Dict with 'enhanced_params' (corrected args) or 'error' (helpful message)
        """
        # Get tool schema
        tool_schema = self.get_tool_schema(tool_name)
        if not tool_schema or "inputSchema" not in tool_schema:
            return {"enhanced_params": arguments, "error": None}
            
        schema = tool_schema["inputSchema"]
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        # Define common parameter aliases for auto-correction
        parameter_aliases = {
            # Universal aliases
            "name": ["title"],
            "content": ["body"], 
            "text": ["body"],
            "notebook_id": ["parent_id"],
            "folder_id": ["parent_id"],
            
            # Tool-specific aliases
            "tag_name": ["title"],  # for create_tag
            "note_name": ["title"], # for create_note
            "notebook_name": ["title"], # for create_notebook
        }
        
        enhanced_args = dict(arguments)
        
        # Special handling for create_note tool when notebook_name is provided
        if tool_name == "create_note" and "notebook_name" in arguments and "parent_id" not in arguments:
            # Try to find notebook by name and convert to parent_id
            notebook_name = str(arguments["notebook_name"]).strip()
            if notebook_name:
                try:
                    notebooks = self.client.get_all_notebooks()
                    matching_notebook = None
                    for notebook in notebooks:
                        if hasattr(notebook, 'title') and notebook.title == notebook_name:
                            matching_notebook = notebook
                            break
                        elif isinstance(notebook, dict) and notebook.get('title') == notebook_name:
                            matching_notebook = notebook
                            break
                    
                    if matching_notebook:
                        notebook_id = matching_notebook.id if hasattr(matching_notebook, 'id') else matching_notebook.get('id')
                        if notebook_id:
                            enhanced_args["parent_id"] = notebook_id
                            logger.info(f"Auto-converted notebook_name '{notebook_name}' to parent_id: {notebook_id}")
                        else:
                            logger.warning(f"Found notebook '{notebook_name}' but couldn't extract ID")
                    else:
                        logger.warning(f"Notebook '{notebook_name}' not found, will use default notebook")
                except Exception as e:
                    logger.warning(f"Error looking up notebook '{notebook_name}': {e}")
            
            # Remove notebook_name from enhanced_args since it's not a valid parameter
            enhanced_args.pop("notebook_name", None)
        missing_required = []
        found_alternatives = {}
        
        # Check each required parameter
        for required_param in required:
            if required_param not in enhanced_args or not str(enhanced_args.get(required_param, "")).strip():
                # Try to find value in aliases
                found_value = None
                found_alias = None
                
                # Check direct aliases
                for alias in parameter_aliases.get(required_param, []):
                    if alias in arguments and str(arguments[alias]).strip():
                        found_value = str(arguments[alias]).strip()
                        found_alias = alias
                        break
                
                # Check reverse aliases (e.g., if they sent "tag_name" but we need "title")
                for alias_key, alias_values in parameter_aliases.items():
                    if required_param in alias_values and alias_key in arguments:
                        if str(arguments[alias_key]).strip():
                            found_value = str(arguments[alias_key]).strip()
                            found_alias = alias_key
                            break
                
                if found_value:
                    # Auto-correct the parameter
                    enhanced_args[required_param] = found_value
                    found_alternatives[required_param] = found_alias
                    logger.info(f"Auto-corrected parameter: {found_alias} -> {required_param}")
                else:
                    missing_required.append(required_param)
        
        # If we have missing required parameters, generate helpful error
        if missing_required:
            error_message = self._build_comprehensive_tool_hint(
                tool_name=tool_name,
                schema=schema,
                received_params=list(arguments.keys()),
                missing_required=missing_required,
                found_alternatives=found_alternatives
            )
            return {"enhanced_params": None, "error": error_message}
        
        # Add helpful defaults for some tools
        enhanced_args = self._add_intelligent_defaults(tool_name, enhanced_args)
        
        return {"enhanced_params": enhanced_args, "error": None}

    def _build_comprehensive_tool_hint(
        self,
        tool_name: str,
        schema: Dict[str, Any],
        received_params: List[str],
        missing_required: List[str],
        found_alternatives: Dict[str, str]
    ) -> str:
        """Build comprehensive usage hints for any tool."""
        
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        message_parts = [
            f"🔧 **{tool_name.upper()} Tool Usage Help**",
            f"❌ Missing required parameters: {missing_required}",
            ""
        ]
        
        # Show what was received vs what's expected
        if received_params:
            message_parts.extend([
                f"📥 **Received parameters:** {received_params}",
                f"📋 **Required parameters:** {required}",
                ""
            ])
        
        # Show parameter details
        message_parts.append("📖 **Parameter Guide:**")
        for param_name, param_info in properties.items():
            is_required = param_name in required
            param_type = param_info.get("type", "string")
            description = param_info.get("description", "No description")
            
            status = "**REQUIRED**" if is_required else "*optional*"
            message_parts.append(f"  • `{param_name}` ({param_type}) - {status}")
            message_parts.append(f"    {description}")
            
            # Show examples or defaults
            if "default" in param_info:
                message_parts.append(f"    Default: {param_info['default']}")
            if "enum" in param_info:
                message_parts.append(f"    Options: {param_info['enum']}")
        
        message_parts.append("")
        
        # Show auto-corrections that were found
        if found_alternatives:
            message_parts.extend([
                "✅ **Auto-corrections applied:**",
                *[f"  • {alias} → {param}" for param, alias in found_alternatives.items()],
                ""
            ])
        
        # Provide usage example
        example_params = {}
        for param in required:
            if param in found_alternatives:
                continue  # Already handled
            param_info = properties.get(param, {})
            param_type = param_info.get("type", "string")
            
            if param_type == "string":
                example_params[param] = f"your_{param}_here"
            elif param_type == "boolean":
                example_params[param] = False
            elif param_type == "integer":
                example_params[param] = 1
            elif param_type == "array":
                example_params[param] = ["item1", "item2"]
        
        if example_params:
            import json
            example_json = json.dumps(example_params, indent=2)
            message_parts.extend([
                "💡 **Correct usage example:**",
                f"```json",
                example_json,
                "```",
                ""
            ])
        
        message_parts.append("🔄 Please retry with the correct parameters.")
        
        return "\n".join(message_parts)

    def _add_intelligent_defaults(self, tool_name: str, arguments: dict) -> dict:
        """Add intelligent defaults for tools when reasonable."""
        enhanced = dict(arguments)
        
        # For create_note, try to default to most recently created notebook if no parent_id
        if tool_name == "create_note" and not enhanced.get("parent_id"):
            try:
                notebooks = self.client.get_all_notebooks()
                if notebooks:
                    # Sort by created_time to get the most recently created notebook first
                    # This is likely the notebook the user just created
                    sorted_notebooks = sorted(
                        notebooks, 
                        key=lambda nb: getattr(nb, 'created_time', 0) if hasattr(nb, 'created_time') else nb.get('created_time', 0),
                        reverse=True
                    )
                    
                    selected_notebook = sorted_notebooks[0]
                    notebook_id = selected_notebook.id if hasattr(selected_notebook, 'id') else selected_notebook.get('id')
                    notebook_title = selected_notebook.title if hasattr(selected_notebook, 'title') else selected_notebook.get('title', 'Unknown')
                    
                    enhanced["parent_id"] = notebook_id
                    logger.info(f"Auto-selected most recent notebook as default: {notebook_title} (ID: {notebook_id})")
            except Exception as e:
                logger.warning(f"Error selecting default notebook: {e}")
        
        return enhanced

    async def handle_search_notes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle search_notes MCP tool call.

        Searches for notes using the provided query and parameters.

        Args:
            params: Dictionary containing search parameters:
                - query (str): Search query string
                - limit (int, optional): Maximum number of results (default: 20)
                - notebook_id (str, optional): Filter by notebook ID
                - tags (List[str], optional): Filter by tags
                - sort_by (str, optional): Sort field (default: "updated_time")
                - sort_order (str, optional): Sort order "asc"/"desc" (default: "desc")

        Returns:
            Dict containing MCP-formatted response with search results

        Raises:
            Exception: Re-raises client exceptions for MCP framework to handle
        """
        # Check rate limiting
        self._check_rate_limit()
        
        logger.info("Processing search_notes request", extra={
            "query_length": len(params.get("query", "")),
            "has_notebook_filter": bool(params.get("notebook_id")),
            "has_tags_filter": bool(params.get("tags")),
            "limit": params.get("limit", 20)
        })
        
        # Extract and validate parameters with security checks
        query = self._validate_string_input(params.get("query", "").strip(), max_length=500)
        limit = max(1, min(params.get("limit", 20), 100))  # Clamp between 1-100
        
        notebook_id = params.get("notebook_id")
        if notebook_id:
            notebook_id = self._validate_string_input(notebook_id, max_length=64)
            
        tags = params.get("tags")
        sort_by = params.get("sort_by", "updated_time")
        sort_order = params.get("sort_order", "desc")

        # Validate tags parameter
        if tags is not None and not isinstance(tags, list):
            logger.warning("Invalid tags parameter type, ignoring", extra={"tags_type": type(tags)})
            tags = None
        elif tags:
            # Sanitize tag values
            tags = [self._validate_string_input(tag, max_length=100) for tag in tags if isinstance(tag, str)][:10]  # Limit to 10 tags

        try:
            # Call client search method
            results = self.client.search_notes(
                query=query,
                limit=limit,
                notebook_id=notebook_id,
                tags=tags,
                sort_by=sort_by,
                sort_order=sort_order,
            )

            # Handle empty results
            if not results:
                return {
                    "content": [
                        {"type": "text", "text": f'No notes found for query: "{query}"'}
                    ]
                }

            # Format results efficiently
            formatted_text = self._format_search_results(query, results)

            return {"content": [{"type": "text", "text": formatted_text}]}

        except Exception as e:
            # Re-raise to be handled by MCP framework
            raise e

    def _format_search_results(self, query: str, results: List[Dict[str, Any]]) -> str:
        """Format search results for display.

        Args:
            query: Original search query
            results: List of note dictionaries

        Returns:
            Formatted text string for display
        """
        result_count = len(results)
        result_summary = f'Found {result_count} note(s) for query: "{query}"\n\n'

        # Format each note efficiently
        formatted_notes = []
        for note in results:
            formatted_note = self._format_single_search_result(note)
            formatted_notes.append(formatted_note)

        return result_summary + "\n".join(formatted_notes)

    def _format_single_search_result(self, note: Dict[str, Any]) -> str:
        """Format a single note for search results display.

        Args:
            note: Note dictionary

        Returns:
            Formatted note string
        """
        title = note.get("title", "Untitled")
        note_id = note.get("id", "unknown")
        body = note.get("body", "")

        # Efficiently truncate body for display
        if len(body) > 200:
            body = body[:197] + "..."

        # Start building result
        result_parts = [f"**{title}** (ID: {note_id})"]

        # Add body if present
        if body:
            result_parts.append(body)

        # Build metadata efficiently
        metadata_parts = []

        # Format timestamps
        created_time = note.get("created_time")
        updated_time = note.get("updated_time")

        if created_time:
            try:
                import datetime

                created_date = datetime.datetime.fromtimestamp(
                    created_time / 1000
                ).strftime("%Y-%m-%d %H:%M")
                metadata_parts.append(f"Created: {created_date}")
            except (ValueError, TypeError):
                pass  # Skip invalid timestamps

        if updated_time:
            try:
                import datetime

                updated_date = datetime.datetime.fromtimestamp(
                    updated_time / 1000
                ).strftime("%Y-%m-%d %H:%M")
                metadata_parts.append(f"Updated: {updated_date}")
            except (ValueError, TypeError):
                pass  # Skip invalid timestamps

        # Add notebook info
        parent_id = note.get("parent_id")
        if parent_id:
            metadata_parts.append(f"Notebook: {parent_id}")

        # Add tags
        tags = note.get("tags")
        if tags and isinstance(tags, list) and tags:
            tags_str = ", ".join(str(tag) for tag in tags if tag)
            if tags_str:
                metadata_parts.append(f"Tags: {tags_str}")

        # Add metadata if present
        if metadata_parts:
            result_parts.append(f"({', '.join(metadata_parts)})")

        return "\n".join(result_parts) + "\n"

    async def handle_get_note(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_note MCP tool call.

        Retrieves a specific note by its ID with optional body inclusion.

        Args:
            params: Dictionary containing:
                - note_id (str): Unique identifier of the note to retrieve
                - include_body (bool, optional): Whether to include note body (default: True)

        Returns:
            Dict containing MCP-formatted response with note details

        Raises:
            ValueError: If note_id is missing or empty
            Exception: Re-raises client exceptions for MCP framework to handle
        """
        # Extract and validate parameters
        note_id = params.get("note_id", "").strip()
        include_body = params.get("include_body", True)

        # Validate note_id - must be non-empty string
        if not note_id:
            raise ValueError("note_id parameter is required and cannot be empty")

        # Validate include_body type
        if not isinstance(include_body, bool):
            include_body = bool(include_body)  # Convert to boolean

        try:
            # Call client get_note method
            note = self.client.get_note(note_id)

            # Validate note response
            if not note or not isinstance(note, dict):
                raise ValueError(f"Invalid note data received for ID: {note_id}")

            # Format note for MCP response
            formatted_text = self._format_note_details(note, include_body)

            return {"content": [{"type": "text", "text": formatted_text}]}

        except Exception as e:
            # Re-raise to be handled by MCP framework
            raise e

    def _format_note_details(
        self, note: Dict[str, Any], include_body: bool = True
    ) -> str:
        """Format a note for detailed display.

        Args:
            note: Note dictionary with note data
            include_body: Whether to include the note body content

        Returns:
            Formatted note string with title, content, and metadata
        """
        # Extract and sanitize note information
        note_id = str(note.get("id", "unknown")).strip()
        title = str(note.get("title", "Untitled")).strip() or "Untitled"
        body = str(note.get("body", "")).strip() if include_body else ""
        created_time = note.get("created_time")
        updated_time = note.get("updated_time")
        parent_id = (
            str(note.get("parent_id", "")).strip() if note.get("parent_id") else ""
        )
        is_todo = bool(note.get("is_todo", False))
        todo_completed = bool(note.get("todo_completed", False))
        tags = note.get("tags", [])

        # Build formatted output efficiently
        result_parts = []

        # Title and ID header with todo status
        title_line = f"**{title}**"
        if is_todo:
            status = "✅ COMPLETED" if todo_completed else "📝 TODO"
            title_line += f" ({status})"

        result_parts.extend(
            [title_line, f"ID: {note_id}", ""]  # Empty line for spacing
        )

        # Body content (if requested and present)
        if include_body and body:
            result_parts.extend(["**Content:**", body, ""])  # Empty line for spacing

        # Metadata section
        metadata_parts = self._build_note_metadata(
            created_time, updated_time, parent_id, tags
        )

        # Add metadata if present
        if metadata_parts:
            result_parts.append("**Metadata:**")
            result_parts.extend(f"- {metadata}" for metadata in metadata_parts)

        return "\n".join(result_parts)

    def _build_note_metadata(
        self, created_time: Any, updated_time: Any, parent_id: str, tags: Any
    ) -> List[str]:
        """Build metadata list for note formatting.

        Args:
            created_time: Note creation timestamp
            updated_time: Note last update timestamp
            parent_id: Parent notebook ID
            tags: Note tags

        Returns:
            List of formatted metadata strings
        """
        metadata_parts = []

        # Format timestamps safely
        for time_value, label in [(created_time, "Created"), (updated_time, "Updated")]:
            if time_value:
                formatted_time = self._format_timestamp(time_value)
                if formatted_time:
                    metadata_parts.append(f"{label}: {formatted_time}")

        # Notebook information
        if parent_id:
            metadata_parts.append(f"Notebook: {parent_id}")

        # Tags - filter and format
        if tags and isinstance(tags, (list, tuple)):
            valid_tags = [str(tag).strip() for tag in tags if tag and str(tag).strip()]
            if valid_tags:
                tags_str = ", ".join(
                    valid_tags[:10]
                )  # Limit to 10 tags for readability
                if len(valid_tags) > 10:
                    tags_str += f" (+{len(valid_tags) - 10} more)"
                metadata_parts.append(f"Tags: {tags_str}")

        return metadata_parts

    def _format_timestamp(self, timestamp: Any) -> Optional[str]:
        """Safely format a timestamp.

        Args:
            timestamp: Timestamp value (milliseconds since epoch)

        Returns:
            Formatted datetime string or None if formatting fails
        """
        try:
            if isinstance(timestamp, (int, float)) and timestamp > 0:
                import datetime

                # Convert from milliseconds to seconds
                timestamp_seconds = timestamp / 1000
                dt = datetime.datetime.fromtimestamp(timestamp_seconds)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError, OSError):
            # Handle invalid timestamps gracefully
            pass

        return None

    async def handle_create_note(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle create_note MCP tool call.

        Creates a new note in Joplin with specified parameters.

        Args:
            params: Dictionary containing:
                - title (str): Title of the new note (required)
                - body (str, optional): Content body of the note (default: '')
                - parent_id (str): ID of the parent notebook (required)
                - is_todo (bool, optional): Whether this is a todo item (default: False)
                - todo_completed (bool, optional): Whether todo is completed (default: False)
                - tags (List[str], optional): List of tags to assign (default: None)

        Returns:
            Dict containing MCP-formatted response with creation confirmation

        Raises:
            ValueError: If required parameters are missing or invalid
            Exception: Re-raises client exceptions for MCP framework to handle
        """
        # Validate and extract parameters
        validated_params = self._validate_create_note_params(params)

        try:
            # Call client create_note method
            note_id = self.client.create_note(**validated_params)

            # Format response for MCP
            formatted_text = self._format_create_note_response(
                note_id=note_id,
                title=validated_params["title"],
                is_todo=validated_params.get("is_todo", False),
                todo_completed=validated_params.get("todo_completed", False),
            )

            # Add structured data for easier parsing by agents
            response_content = [{"type": "text", "text": formatted_text}]
            
            # Add structured metadata that agents can easily extract
            metadata = {
                "type": "text",
                "text": f"\n\n**STRUCTURED_DATA_FOR_AGENT:**\n```json\n{{\n  \"created_note_id\": \"{note_id}\",\n  \"note_title\": \"{validated_params['title']}\",\n  \"parent_notebook_id\": \"{validated_params['parent_id']}\",\n  \"operation\": \"create_note\",\n  \"success\": true\n}}\n```"
            }
            response_content.append(metadata)
            
            return {"content": response_content}

        except Exception as e:
            # Re-raise to be handled by MCP framework
            raise e

    def _validate_create_note_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize create_note parameters.

        Args:
            params: Raw parameters from MCP call

        Returns:
            Dictionary of validated and sanitized parameters

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Extract and validate required parameters with aliases
        title = params.get("title", "").strip() if params.get("title") else ""
        if not title:
            title = params.get("name", "").strip() if params.get("name") else ""
            
        parent_id = (
            params.get("parent_id", "").strip() if params.get("parent_id") else ""
        )
        if not parent_id:
            # Handle notebook_id with type conversion (agent might send int instead of string)
            notebook_id_param = params.get("notebook_id")
            if notebook_id_param is not None:
                parent_id = str(notebook_id_param).strip()
                # If it's just a number like "1", it's likely invalid - provide helpful error
                if parent_id.isdigit() and len(parent_id) < 10:
                    logger.warning(f"Received suspicious notebook_id: {parent_id} - likely not a real Joplin notebook ID")
                    raise ValueError(
                        f"Invalid notebook_id '{parent_id}'. "
                        f"Joplin notebook IDs are typically long alphanumeric strings (e.g., '3f80648342024c64bbb4a0e7adfcd538'). "
                        f"Please use the actual notebook ID from a previous create_notebook response."
                    )

        # Validate required fields
        if not title:
            raise ValueError("title parameter is required and cannot be empty")

        # If no parent_id provided, try alternative approaches
        if not parent_id:
            # First, check if notebook_name was provided
            notebook_name = params.get("notebook_name", "").strip()
            if notebook_name:
                try:
                    notebooks = self.client.get_all_notebooks()
                    matching_notebook = None
                    for notebook in notebooks:
                        nb_title = getattr(notebook, 'title', None) or notebook.get('title', '') if isinstance(notebook, dict) else ''
                        if nb_title == notebook_name:
                            matching_notebook = notebook
                            break
                    
                    if matching_notebook:
                        nb_id = getattr(matching_notebook, 'id', None) or matching_notebook.get('id') if isinstance(matching_notebook, dict) else None
                        if nb_id:
                            parent_id = nb_id
                            logger.info(f"Found notebook '{notebook_name}' with ID: {parent_id}")
                        else:
                            logger.warning(f"Found notebook '{notebook_name}' but couldn't extract ID")
                    else:
                        logger.warning(f"Notebook '{notebook_name}' not found")
                except Exception as e:
                    logger.warning(f"Error looking up notebook '{notebook_name}': {e}")
            
            # If still no parent_id, use most recently created notebook as default
            if not parent_id:
                try:
                    notebooks = self.client.get_all_notebooks()
                    if notebooks:
                        # Sort by created_time to get the most recently created notebook first
                        sorted_notebooks = sorted(
                            notebooks, 
                            key=lambda nb: getattr(nb, 'created_time', 0) if hasattr(nb, 'created_time') else nb.get('created_time', 0),
                            reverse=True
                        )
                        
                        selected_notebook = sorted_notebooks[0]
                        parent_id = getattr(selected_notebook, 'id', None) or selected_notebook.get('id') if isinstance(selected_notebook, dict) else None
                        nb_title = getattr(selected_notebook, 'title', 'Unknown') if hasattr(selected_notebook, 'title') else selected_notebook.get('title', 'Unknown')
                        
                        if parent_id:
                            logger.info(f"No parent_id provided, using most recent notebook: {nb_title} (ID: {parent_id})")
                        else:
                            raise ValueError("parent_id parameter is required and cannot be empty (no notebooks available)")
                    else:
                        raise ValueError("parent_id parameter is required and cannot be empty (no notebooks available)")
                except Exception as e:
                    logger.error(f"Error selecting default notebook: {e}")
                    raise ValueError("parent_id parameter is required and cannot be empty")

        # Build validated parameters dictionary
        validated = {"title": title, "parent_id": parent_id}

        # Process optional parameters with type validation and defaults
        body = params.get("body")
        if body is None:
            body = params.get("content")  # Handle alias
        if body is not None:
            validated["body"] = str(body) if not isinstance(body, str) else body
        else:
            validated["body"] = ""

        # Boolean parameters with type coercion
        is_todo = params.get("is_todo", False)
        validated["is_todo"] = (
            bool(is_todo) if not isinstance(is_todo, bool) else is_todo
        )

        todo_completed = params.get("todo_completed", False)
        validated["todo_completed"] = (
            bool(todo_completed)
            if not isinstance(todo_completed, bool)
            else todo_completed
        )

        # Tags parameter validation and sanitization
        tags = params.get("tags")
        if tags is not None:
            validated["tags"] = self._sanitize_tags_parameter(tags)
        else:
            validated["tags"] = None

        return validated

    def _sanitize_tags_parameter(self, tags: Any) -> Optional[List[str]]:
        """Sanitize and validate tags parameter.

        Args:
            tags: Raw tags parameter (can be list, tuple, string, or other)

        Returns:
            List of valid tag strings or None if invalid/empty
        """
        if isinstance(tags, (list, tuple)):
            # Filter out empty/invalid tags and convert to strings
            sanitized_tags = []
            for tag in tags:
                if tag and isinstance(tag, (str, int, float)):
                    tag_str = str(tag).strip()
                    if tag_str:  # Only add non-empty tags
                        sanitized_tags.append(tag_str)
            return sanitized_tags if sanitized_tags else None

        elif isinstance(tags, str):
            # Convert single tag string to list
            tag_str = tags.strip()
            return [tag_str] if tag_str else None

        else:
            # Invalid type, return None
            return None

    def _format_create_note_response(
        self,
        note_id: str,
        title: str,
        is_todo: bool = False,
        todo_completed: bool = False,
    ) -> str:
        """Format the response for note creation.

        Args:
            note_id: ID of the created note
            title: Title of the created note
            is_todo: Whether the note is a todo item
            todo_completed: Whether the todo is completed

        Returns:
            Formatted response string
        """
        # Build response components
        response_parts = []

        # Success header with note type
        success_message = self._build_success_message(is_todo, todo_completed)
        response_parts.append(success_message)

        # Core note information - make note ID very prominent
        response_parts.extend([
            f"**Title:** {title}", 
            f"**📝 CREATED NOTE ID: {note_id} 📝**",  # Make this very prominent
            ""  # Spacing line
        ])

        # Todo-specific status information
        if is_todo:
            todo_status = self._build_todo_status(todo_completed)
            response_parts.append(todo_status)

        # Confirmation message with ID reminder
        response_parts.extend([
            "The note has been successfully created in Joplin.",
            f"💡 **Remember: The note ID is `{note_id}` - you can use this to reference, update, or tag this note.**"
        ])

        return "\n".join(response_parts)

    def _build_success_message(self, is_todo: bool, todo_completed: bool) -> str:
        """Build the success message based on note type.

        Args:
            is_todo: Whether the note is a todo item
            todo_completed: Whether the todo is completed

        Returns:
            Formatted success message
        """
        if is_todo:
            status = "completed todo" if todo_completed else "todo"
            return f"✅ Successfully created {status} note"
        else:
            return "✅ Successfully created note"

    def _build_todo_status(self, todo_completed: bool) -> str:
        """Build todo status information.

        Args:
            todo_completed: Whether the todo is completed

        Returns:
            Formatted todo status string
        """
        status_emoji = "✅" if todo_completed else "📝"
        status_text = "Completed" if todo_completed else "Pending"
        return f"**Todo Status:** {status_emoji} {status_text}"

    async def handle_ping_joplin(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping_joplin MCP tool call.

        Tests the connection to the Joplin server.

        Args:
            params: Dictionary (no parameters required for ping)

        Returns:
            Dict containing MCP-formatted response with connection status

        Raises:
            Exception: Re-raises client exceptions for MCP framework to handle
        """
        try:
            # Call client ping method
            is_connected = self.client.ping()

            # Build connection status response
            formatted_text = self._build_ping_response(is_connected)

            return {"content": [{"type": "text", "text": formatted_text}]}

        except Exception as e:
            # Re-raise to be handled by MCP framework
            raise e

    def _build_ping_response(self, is_connected: bool) -> str:
        """Build a formatted response for ping operations.

        Args:
            is_connected: Whether the connection was successful

        Returns:
            Formatted ping response string
        """
        if is_connected:
            message = "✅ Joplin server connection successful"
            details = "The Joplin server is responding and accessible."
        else:
            message = "❌ Joplin server connection failed"
            details = "Unable to reach the Joplin server. Please check your connection settings."

        return f"{message}\n\n{details}"

    async def handle_update_note(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle update_note MCP tool call.

        Updates an existing note in Joplin.

        Args:
            params: Dictionary containing:
                - note_id (str): ID of the note to update (required)
                - title (str, optional): New title for the note
                - body (str, optional): New content body for the note
                - is_todo (bool, optional): Whether this is a todo item
                - todo_completed (bool, optional): Whether todo is completed
                - tags (List[str], optional): List of tags to assign

        Returns:
            Dict containing MCP-formatted response with update confirmation

        Raises:
            ValueError: If required parameters are missing or invalid
            Exception: Re-raises client exceptions for MCP framework to handle
        """
        # Validate and sanitize parameters
        update_params = self._validate_update_note_params(params)
        note_id = update_params["note_id"]

        try:
            # Call client update_note method
            success = self.client.update_note(**update_params)

            # Build standardized response
            return self._build_operation_response(
                success=success,
                operation="updated",
                entity_type="note",
                entity_id=note_id,
            )

        except Exception as e:
            # Re-raise to be handled by MCP framework
            raise e

    async def handle_delete_note(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_note MCP tool call.

        Deletes a note from Joplin.

        Args:
            params: Dictionary containing:
                - note_id (str): ID of the note to delete (required)

        Returns:
            Dict containing MCP-formatted response with deletion confirmation

        Raises:
            ValueError: If required parameters are missing or invalid
            Exception: Re-raises client exceptions for MCP framework to handle
        """
        # Validate required parameter
        note_id = self._validate_required_id_parameter(params, "note_id")

        try:
            # Call client delete_note method
            success = self.client.delete_note(note_id=note_id)

            # Build standardized response with custom details for deletion
            return self._build_operation_response(
                success=success,
                operation="deleted",
                entity_type="note",
                entity_id=note_id,
                details=(
                    "The note has been permanently removed from Joplin."
                    if success
                    else None
                ),
            )

        except Exception as e:
            # Re-raise to be handled by MCP framework
            raise e

    async def handle_list_notebooks(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list_notebooks MCP tool call.

        Lists all notebooks in Joplin.

        Args:
            params: Dictionary (no parameters required)

        Returns:
            Dict containing MCP-formatted response with notebooks list

        Raises:
            Exception: Re-raises client exceptions for MCP framework to handle
        """
        try:
            # Call client get_all_notebooks method
            notebooks = self.client.get_all_notebooks()
            
            # Convert MCPNotebook objects to dictionaries for formatting
            notebooks_dict = [notebook.model_dump() if hasattr(notebook, 'model_dump') else notebook.__dict__ for notebook in notebooks]

            # Build standardized list response
            return self._build_list_response(
                items=notebooks_dict,
                entity_type="notebooks",
                formatter_method=self._format_notebooks_list,
            )

        except Exception as e:
            # Re-raise to be handled by MCP framework
            raise e

    def _format_notebooks_list(self, notebooks: List[Dict[str, Any]]) -> str:
        """Format the notebooks list for display.

        Args:
            notebooks: List of notebook dictionaries

        Returns:
            Formatted notebooks list string
        """
        if not notebooks:
            return "📁 No notebooks found\n\nYour Joplin instance doesn't contain any notebooks yet."

        count = len(notebooks)
        result_parts = [f"📁 Found {count} notebook{'s' if count != 1 else ''}"]
        result_parts.append("")  # Empty line

        for i, notebook in enumerate(notebooks, 1):
            title = notebook.get("title", "Untitled")
            notebook_id = notebook.get("id", "Unknown")
            created_time = self._format_timestamp(notebook.get("created_time"))

            result_parts.append(f"**{i}. {title}**")
            result_parts.append(f"   ID: {notebook_id}")
            if created_time:
                result_parts.append(f"   Created: {created_time}")
            result_parts.append("")  # Empty line between notebooks

        return "\n".join(result_parts)

    async def handle_get_notebook(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_notebook MCP tool call.

        Retrieves details for a specific notebook.

        Args:
            params: Dictionary containing:
                - notebook_id (str): ID of the notebook to retrieve (required)

        Returns:
            Dict containing MCP-formatted response with notebook details

        Raises:
            ValueError: If required parameters are missing or invalid
            Exception: Re-raises client exceptions for MCP framework to handle
        """
        # Validate required parameter
        notebook_id = self._validate_required_id_parameter(params, "notebook_id")

        try:
            # Call client get_notebook method
            notebook = self.client.get_notebook(notebook_id=notebook_id)

            # Format response
            formatted_text = self._format_notebook_details(notebook)

            return {"content": [{"type": "text", "text": formatted_text}]}

        except Exception as e:
            # Re-raise to be handled by MCP framework
            raise e

    def _format_notebook_details(self, notebook: Dict[str, Any]) -> str:
        """Format notebook details for display.

        Args:
            notebook: Notebook dictionary

        Returns:
            Formatted notebook details string
        """
        title = notebook.get("title", "Untitled")
        notebook_id = notebook.get("id", "Unknown")

        result_parts = [f"📁 **{title}**", "", f"**Notebook ID:** {notebook_id}"]

        # Add timestamps if available
        created_time = self._format_timestamp(notebook.get("created_time"))
        updated_time = self._format_timestamp(notebook.get("updated_time"))

        if created_time:
            result_parts.append(f"**Created:** {created_time}")
        if updated_time:
            result_parts.append(f"**Updated:** {updated_time}")

        # Add parent information if available
        parent_id = notebook.get("parent_id")
        if parent_id:
            result_parts.append(f"**Parent ID:** {parent_id}")

        return "\n".join(result_parts)

    async def handle_create_notebook(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle create_notebook MCP tool call.

        Creates a new notebook in Joplin.

        Args:
            params: Dictionary containing:
                - title (str): Title of the new notebook (required)
                - parent_id (str, optional): ID of the parent notebook

        Returns:
            Dict containing MCP-formatted response with creation confirmation

        Raises:
            ValueError: If required parameters are missing or invalid
            Exception: Re-raises client exceptions for MCP framework to handle
        """
        # Handle parameter aliases (Ollama might send 'name' instead of 'title')
        title = params.get("title", "").strip()
        if not title:
            title = params.get("name", "").strip()
        if not title:
            raise ValueError("title parameter is required and cannot be empty")

        # Build create parameters
        create_params = {"title": title}

        # Add optional parent_id if provided
        parent_id = params.get("parent_id")
        if parent_id:
            create_params["parent_id"] = parent_id.strip()

        try:
            # Call client create_notebook method
            notebook_id = self.client.create_notebook(**create_params)

            # Build standardized creation response
            return self._build_creation_response(
                entity_type="notebook", title=title, entity_id=notebook_id
            )

        except Exception as e:
            # Re-raise to be handled by MCP framework
            raise e

    async def handle_list_tags(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list_tags MCP tool call.

        Lists all tags in Joplin.

        Args:
            params: Dictionary (no parameters required)

        Returns:
            Dict containing MCP-formatted response with tags list

        Raises:
            Exception: Re-raises client exceptions for MCP framework to handle
        """
        try:
            # Call client get_all_tags method
            tags = self.client.get_all_tags()
            
            # Convert MCPTag objects to dictionaries for formatting
            tags_dict = [tag.model_dump() if hasattr(tag, 'model_dump') else tag.__dict__ for tag in tags]

            # Build standardized list response
            return self._build_list_response(
                items=tags_dict, entity_type="tags", formatter_method=self._format_tags_list
            )

        except Exception as e:
            # Re-raise to be handled by MCP framework
            raise e

    def _format_tags_list(self, tags: List[Dict[str, Any]]) -> str:
        """Format the tags list for display.

        Args:
            tags: List of tag dictionaries

        Returns:
            Formatted tags list string
        """
        if not tags:
            return (
                "🏷️ No tags found\n\nYour Joplin instance doesn't contain any tags yet."
            )

        count = len(tags)
        result_parts = [f"🏷️ Found {count} tag{'s' if count != 1 else ''}"]
        result_parts.append("")  # Empty line

        for i, tag in enumerate(tags, 1):
            title = tag.get("title", "Untitled")
            tag_id = tag.get("id", "Unknown")
            created_time = self._format_timestamp(tag.get("created_time"))

            result_parts.append(f"**{i}. {title}**")
            result_parts.append(f"   ID: {tag_id}")
            if created_time:
                result_parts.append(f"   Created: {created_time}")
            result_parts.append("")  # Empty line between tags

        return "\n".join(result_parts)

    async def handle_create_tag(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle create_tag MCP tool call.

        Creates a new tag in Joplin.

        Args:
            params: Dictionary containing:
                - title (str): Title of the new tag (required)

        Returns:
            Dict containing MCP-formatted response with creation confirmation

        Raises:
            ValueError: If required parameters are missing or invalid
            Exception: Re-raises client exceptions for MCP framework to handle
        """
        try:
            # Get title (parameter validation/enhancement handled centrally)
            title = self._validate_string_input(params["title"], max_length=100)
            
            # Call client create_tag method
            tag_id = self.client.create_tag(title=title)

            # Build standardized creation response
            return self._build_creation_response(
                entity_type="tag", title=title, entity_id=tag_id
            )

        except Exception as e:
            # Re-raise to be handled by MCP framework
            raise e

    async def handle_tag_note(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tag_note MCP tool call.

        Adds a tag to a note in Joplin.

        Args:
            params: Dictionary containing:
                - note_id (str): ID of the note to tag (required)
                - tag_id (str): ID of the tag to add (required)

        Returns:
            Dict containing MCP-formatted response with tagging confirmation

        Raises:
            ValueError: If required parameters are missing or invalid
            Exception: Re-raises client exceptions for MCP framework to handle
        """
        # Validate required parameters
        note_id, tag_id = self._validate_dual_id_parameters(params, "note_id", "tag_id")

        try:
            # Call client tag_note method
            success = self.client.tag_note(note_id=note_id, tag_id=tag_id)

            # Build custom response for tagging operation
            if success:
                message = "✅ Successfully tagged note"
                details = (
                    f"**📝 Note ID:** `{note_id}`\n"
                    f"**🏷️ Tag ID:** `{tag_id}`\n\n"
                    f"The tag has been successfully added to the note.\n"
                    f"💡 **These IDs can be used for future operations:**\n"
                    f"   • Use note ID `{note_id}` to get, update, or delete this note\n"
                    f"   • Use tag ID `{tag_id}` to tag other notes with this same tag\n"
                    f"   • Use both IDs together to untag this note later"
                )
            else:
                message = "❌ Failed to tag note"
                details = f"**📝 Note ID:** `{note_id}`\n**🏷️ Tag ID:** `{tag_id}`\n\nThe tagging operation was not successful."

            formatted_text = f"{message}\n\n{details}"

            # Add structured data for easier parsing by agents
            response_content = [{"type": "text", "text": formatted_text}]
            
            if success:
                # Add structured metadata that agents can easily extract
                metadata = {
                    "type": "text",
                    "text": f"\n\n**STRUCTURED_DATA_FOR_AGENT:**\n```json\n{{\n  \"note_id\": \"{note_id}\",\n  \"tag_id\": \"{tag_id}\",\n  \"operation\": \"tag_note\",\n  \"success\": true\n}}\n```"
                }
                response_content.append(metadata)
            
            return {"content": response_content}

        except Exception as e:
            # Re-raise to be handled by MCP framework
            raise e

    async def handle_untag_note(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle untag_note MCP tool call.

        Removes a tag from a note in Joplin.

        Args:
            params: Dictionary containing:
                - note_id (str): ID of the note to untag (required)
                - tag_id (str): ID of the tag to remove (required)

        Returns:
            Dict containing MCP-formatted response with untagging confirmation

        Raises:
            ValueError: If required parameters are missing or invalid
            Exception: Re-raises client exceptions for MCP framework to handle
        """
        # Validate required parameters
        note_id, tag_id = self._validate_dual_id_parameters(params, "note_id", "tag_id")

        try:
            # Call client untag_note method
            success = self.client.untag_note(note_id=note_id, tag_id=tag_id)

            # Build custom response for untagging operation
            if success:
                message = "✅ Successfully removed tag from note"
                details = f"**📝 Note ID:** `{note_id}`\n**🏷️ Tag ID:** `{tag_id}`\n\nThe tag has been successfully removed from the note.\n💡 **Remember these IDs for future reference!**"
            else:
                message = "❌ Failed to remove tag from note"
                details = f"**📝 Note ID:** `{note_id}`\n**🏷️ Tag ID:** `{tag_id}`\n\nThe untagging operation was not successful."

            formatted_text = f"{message}\n\n{details}"

            return {"content": [{"type": "text", "text": formatted_text}]}

        except Exception as e:
            # Re-raise to be handled by MCP framework
            raise e

    def _validate_required_id_parameter(
        self, params: Dict[str, Any], param_name: str
    ) -> str:
        """Validate and extract a required ID parameter.

        Args:
            params: Dictionary containing parameters
            param_name: Name of the ID parameter to validate

        Returns:
            Validated and stripped ID string

        Raises:
            ValueError: If parameter is missing or empty
        """
        param_raw = params.get(param_name)
        if param_raw is None:
            raise ValueError(f"{param_name} parameter is required and cannot be empty")
        
        param_value = str(param_raw).strip()
        if not param_value:
            raise ValueError(f"{param_name} parameter is required and cannot be empty")
        
        # Check for obviously invalid IDs (like generic placeholders)
        invalid_placeholders = [
            'test note', 'new tag', 'your_note_id_here', 'your_tag_id_here',
            'note_id', 'tag_id', 'notebook_id', 'test', 'example', 'sample'
        ]
        if param_value.lower() in invalid_placeholders:
            example_ids = []
            try:
                # Try to provide context-aware examples based on recent operations
                if param_name == 'note_id':
                    example_ids.append("Use the note ID from a recent create_note response")
                elif param_name == 'tag_id':
                    example_ids.append("Use the tag ID from a recent create_tag response")
                elif param_name == 'notebook_id' or param_name == 'parent_id':
                    example_ids.append("Use the notebook ID from a recent create_notebook response")
            except:
                pass
            
            context_help = " ".join(example_ids) if example_ids else "Use the actual ID from a previous create operation"
            
            raise ValueError(
                f"Invalid {param_name} '{param_value}'. "
                f"This appears to be a placeholder value. "
                f"{context_help}. "
                f"Joplin IDs are long alphanumeric strings like '3f80648342024c64bbb4a0e7adfcd538'."
            )
        
        return param_value

    def _validate_dual_id_parameters(
        self, params: Dict[str, Any], param1_name: str, param2_name: str
    ) -> tuple[str, str]:
        """Validate and extract two required ID parameters.

        Args:
            params: Dictionary containing parameters
            param1_name: Name of the first ID parameter to validate
            param2_name: Name of the second ID parameter to validate

        Returns:
            Tuple of validated and stripped ID strings

        Raises:
            ValueError: If either parameter is missing or empty
        """
        param1_value = self._validate_required_id_parameter(params, param1_name)
        param2_value = self._validate_required_id_parameter(params, param2_name)
        return param1_value, param2_value

    def _build_operation_response(
        self,
        success: bool,
        operation: str,
        entity_type: str,
        entity_id: str,
        details: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a standardized MCP response for CRUD operations.

        Args:
            success: Whether the operation was successful
            operation: Type of operation (e.g., "updated", "deleted", "created")
            entity_type: Type of entity (e.g., "note", "notebook", "tag")
            entity_id: ID of the entity
            details: Optional additional details

        Returns:
            Dict containing MCP-formatted response
        """
        if success:
            emoji = "✅"
            status = "Successfully"
            action_details = (
                details
                or f"The {entity_type} has been successfully {operation} in Joplin."
            )
        else:
            emoji = "❌"
            status = "Failed to"
            action_details = (
                details
                or f"The {entity_type} {operation} operation was not successful."
            )

        message = f"{emoji} {status} {operation} {entity_type}"
        formatted_details = (
            f"**{entity_type.title()} ID:** {entity_id}\n\n{action_details}"
        )
        formatted_text = f"{message}\n\n{formatted_details}"

        return {"content": [{"type": "text", "text": formatted_text}]}

    def _build_creation_response(
        self,
        entity_type: str,
        title: str,
        entity_id: str,
        additional_info: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a standardized MCP response for creation operations.

        Args:
            entity_type: Type of entity created (e.g., "notebook", "tag")
            title: Title/name of the created entity
            entity_id: ID of the created entity
            additional_info: Optional additional information

        Returns:
            Dict containing MCP-formatted response
        """
        message = f"✅ Successfully created {entity_type}"
        
        # Make the ID very prominent based on entity type
        if entity_type == "notebook":
            id_display = f"**📁 CREATED {entity_type.upper()} ID: {entity_id} 📁**"
        elif entity_type == "tag":
            id_display = f"**🏷️ CREATED {entity_type.upper()} ID: {entity_id} 🏷️**"
        else:
            id_display = f"**{entity_type.upper()} ID:** {entity_id}"
            
        details_parts = [
            f"**Title:** {title}",
            id_display,
            f"\nThe {entity_type} has been successfully created in Joplin.",
            f"💡 **Remember: The {entity_type} ID is `{entity_id}` - you can use this to reference this {entity_type}.**"
        ]

        if additional_info:
            details_parts.insert(-2, additional_info)

        formatted_text = f"{message}\n\n{chr(10).join(details_parts)}"

        # Add structured data for easier parsing by agents
        response_content = [{"type": "text", "text": formatted_text}]
        
        # Add structured metadata that agents can easily extract
        metadata = {
            "type": "text",
            "text": f"\n\n**STRUCTURED_DATA_FOR_AGENT:**\n```json\n{{\n  \"created_{entity_type}_id\": \"{entity_id}\",\n  \"{entity_type}_title\": \"{title}\",\n  \"operation\": \"create_{entity_type}\",\n  \"success\": true\n}}\n```"
        }
        response_content.append(metadata)
        
        return {"content": response_content}

    def _validate_update_note_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize update_note parameters.

        Args:
            params: Raw parameters dictionary

        Returns:
            Validated and sanitized parameters dictionary

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Validate required parameter
        note_id = self._validate_required_id_parameter(params, "note_id")

        # Build update parameters (only include provided fields)
        update_params = {"note_id": note_id}

        # Add optional parameters if provided with type validation
        if "title" in params:
            update_params["title"] = (
                str(params["title"]) if params["title"] is not None else ""
            )
        if "body" in params:
            update_params["body"] = (
                str(params["body"]) if params["body"] is not None else ""
            )
        if "is_todo" in params:
            update_params["is_todo"] = bool(params["is_todo"])
        if "todo_completed" in params:
            update_params["todo_completed"] = bool(params["todo_completed"])
        if "tags" in params:
            update_params["tags"] = self._sanitize_tags_parameter(params["tags"])

        return update_params

    def _build_list_response(
        self,
        items: List[Dict[str, Any]],
        entity_type: str,
        formatter_method: Callable[[List[Dict[str, Any]]], str],
    ) -> Dict[str, Any]:
        """Build a standardized MCP response for list operations.

        Args:
            items: List of items to format
            entity_type: Type of entity being listed (e.g., "notebooks", "tags")
            formatter_method: Method to format the items list

        Returns:
            Dict containing MCP-formatted response
        """
        formatted_text = formatter_method(items)

        return {"content": [{"type": "text", "text": formatted_text}]}

    async def handle_delete_notebook(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_notebook MCP tool call.

        Deletes a notebook from Joplin.

        Args:
            params: Dictionary containing:
                - notebook_id (str): ID of the notebook to delete (required)
                - force (bool, optional): Whether to force deletion even if notebook has children (default: False)

        Returns:
            Dict containing MCP-formatted response with deletion confirmation

        Raises:
            ValueError: If required parameters are missing or invalid
            Exception: Re-raises client exceptions for MCP framework to handle
        """
        # Validate required parameter
        notebook_id = self._validate_required_id_parameter(params, "notebook_id")
        force = params.get("force", False)

        try:
            # Call client delete_notebook method
            success = self.client.delete_notebook(notebook_id=notebook_id, force=force)

            # Build standardized response with custom details for deletion
            return self._build_operation_response(
                success=success,
                operation="deleted",
                entity_type="notebook",
                entity_id=notebook_id,
                details=(
                    "The notebook has been permanently removed from Joplin."
                    if success
                    else None
                ),
            )

        except Exception as e:
            # Re-raise to be handled by MCP framework
            raise e

    async def handle_delete_tag(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_tag MCP tool call.

        Deletes a tag from Joplin.

        Args:
            params: Dictionary containing:
                - tag_id (str): ID of the tag to delete (required)

        Returns:
            Dict containing MCP-formatted response with deletion confirmation

        Raises:
            ValueError: If required parameters are missing or invalid
            Exception: Re-raises client exceptions for MCP framework to handle
        """
        # Validate required parameter
        tag_id = self._validate_required_id_parameter(params, "tag_id")

        try:
            # Call client delete_tag method
            success = self.client.delete_tag(tag_id=tag_id)

            # Build standardized response with custom details for deletion
            return self._build_operation_response(
                success=success,
                operation="deleted",
                entity_type="tag",
                entity_id=tag_id,
                details=(
                    "The tag has been permanently removed from Joplin."
                    if success
                    else None
                ),
            )

        except Exception as e:
            # Re-raise to be handled by MCP framework
            raise e
