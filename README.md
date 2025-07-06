# Joplin MCP Server

A **FastMCP-based Model Context Protocol (MCP) server** for [Joplin](https://joplinapp.org/) note-taking application via its Pythohn API [joppy](https://github.com/marph91/joppy), enabling AI assistants to interact with your Joplin notes, notebooks, and tags through a standardized interface.

## 🎯 Overview

This FastMCP server provides AI assistants with comprehensive access to your Joplin notes through **18 optimized tools** with complete CRUD operations:

## 🔧 Complete Tool Reference

**18 tools** organized by category and permission level, optimized for LLM performance:

| Tool | Category | Permission Level | Description |
|------|----------|------------------|-------------|
| **📝 Finding Notes** | | | |
| `find_notes` | Notes | 🔍 Read | Full-text search across all notes with advanced filtering |
| `find_notes_with_tag` | Notes | 🔍 Read | Find all notes with a specific tag ⭐ MAIN TAG SEARCH |
| `find_notes_in_notebook` | Notes | 🔍 Read | Find all notes within a specific notebook ⭐ MAIN NOTEBOOK SEARCH |
| `get_all_notes` | Notes | 🔍 Read | Get all notes, most recent first |
| `get_note` | Notes | 🔍 Read | Retrieve specific notes with metadata and content |
| **📝 Managing Notes** | | | |
| `create_note` | Notes | 📝 Write | Create new notes with support for todos, tags, and notebooks |
| `update_note` | Notes | ✏️ Update | Modify existing notes with flexible parameter support |
| `delete_note` | Notes | 🗑️ Delete | Remove notes with confirmation |
| **📁 Managing Notebooks** | | | |
| `list_notebooks` | Notebooks | 🔍 Read | Browse all notebooks with hierarchical structure |
| `create_notebook` | Notebooks | 📝 Write | Create new notebooks with parent-child relationships |
| `update_notebook` | Notebooks | ✏️ Update | Modify notebook titles and organization |
| `delete_notebook` | Notebooks | 🗑️ Delete | Remove notebooks with confirmation |
| **🏷️ Managing Tags** | | | |
| `list_tags` | Tags | 🔍 Read | View all available tags |
| `create_tag` | Tags | 📝 Write | Create new tags for organization |
| `delete_tag` | Tags | 🗑️ Delete | Remove tags with confirmation |
| `get_tags_by_note` | Tags | 🔍 Read | List all tags assigned to a specific note |
| **🔗 Tag-Note Relationships** | | | |
| `tag_note` | Tags | ✏️ Update | Add tags to notes (create relationships) |
| `untag_note` | Tags | ✏️ Update | Remove tags from notes (remove relationships) |
| **🔧 System Tools** | | | |
| `ping_joplin` | Utilities | 🔍 Read | Test server connectivity and health |

**Permission Levels:**
- 🔍 **Read**: Always enabled - safe operations for browsing and searching
- 📝 **Write**: Create new objects (configurable during installation)
- ✏️ **Update**: Modify existing objects (configurable during installation)  
- 🗑️ **Delete**: Remove objects permanently (configurable during installation)

## 🚀 Quick Start

### Option 1: Pip Install (Recommended for most users)

The simplest way to install for end users:

```bash
# Install the package
pip install joplin-mcp

# Run the configuration script (any of these work):
joplin-mcp-install           # Console command (recommended)
python -m joplin_mcp.install # Module command
```

**Available commands after pip install:**
- `joplin-mcp-install` - Interactive configuration script
- `joplin-mcp-server` - Run the MCP server  
- `joplin-mcp` - Run the MCP server (alias)

This approach:
- ✅ Handles all dependencies automatically
- ✅ Works in any Python environment
- ✅ Provides the same configuration experience
- ✅ Installs the package globally or in your current environment
- ✅ Provides convenient console commands

### Option 2: Development Install

For developers or users who want the latest features:

#### For macOS/Linux users:
```bash
# Clone the repository
git clone https://github.com/alondmnt/joplin-mcp.git
cd joplin-mcp

# Run the installation script (includes virtual environment setup)
./install.sh
```

#### For Windows users:
```batch
REM Clone the repository
git clone https://github.com/alondmnt/joplin-mcp.git
cd joplin-mcp

REM Run the installation script
install.bat
```

#### Or run the Python script directly:
```bash
python install.py
```

**Both approaches provide:**
1. ✅ Prompt you for your Joplin API token
2. ✅ Configure tool permissions (3 levels: Write, Update, Delete)
3. ✅ Create the `joplin-mcp.json` configuration file
4. ✅ Find and update your Claude Desktop configuration
5. ✅ Test the connection to Joplin
6. ✅ Provide detailed setup instructions

### Manual Installation

If you prefer to set up manually or the automated script doesn't work for your setup:

### Prerequisites

- **Python 3.8+**
- **Joplin Desktop** with Web Clipper service enabled
- **Joplin API token** (generated in Joplin settings)

### Installation

```bash
# Clone the repository
git clone https://github.com/alondmnt/joplin-mcp.git
cd joplin-mcp

# Install the package
pip install -e .
```

### Configuration

#### 1. Enable Joplin Web Clipper
- Open Joplin Desktop
- Go to **Tools → Options → Web Clipper**
- Enable the Web Clipper service
- Note the port (default: 41184)

#### 2. Get Your API Token
- In Web Clipper settings, copy the **Authorization token**
- Or click **"Advanced options"** to generate a new token

#### 3. Create Configuration File
Create `joplin-mcp.json` in your project directory:

```json
{
  "token": "your_api_token_here",
  "host": "localhost",
  "port": 41184,
  "timeout": 30,
  "verify_ssl": false
}
```

#### 4. Tool Permission Configuration

The installation script provides **3 levels of permission control** for enhanced security:

##### 📝 **Write Permission** (Creating new objects)
- `create_note` - Create new notes
- `create_notebook` - Create new notebooks  
- `create_tag` - Create new tags

##### ✏️ **Update Permission** (Modifying existing objects)
- `update_note` - Update existing notes
- `update_notebook` - Update existing notebooks
- `update_tag` - Update existing tags
- `tag_note` - Add tags to notes
- `untag_note` - Remove tags from notes

##### 🗑️ **Delete Permission** (Permanently removing objects)
- `delete_note` - Delete notes
- `delete_notebook` - Delete notebooks
- `delete_tag` - Delete tags

The installation script will prompt you for each permission level and configure the tools accordingly. This provides fine-grained control over what operations the AI assistant can perform.

##### Manual Tool Configuration

If you need to modify permissions later, edit the `tools` section in your configuration file:

```json
{
  "token": "your_api_token_here",
  "host": "localhost",
  "port": 41184,
  "tools": {
    "create_note": true,
    "create_notebook": true,
    "create_tag": true,
    "update_note": true,
    "update_notebook": true,
    "update_tag": true,
    "tag_note": true,
    "untag_note": true,
    "delete_note": false,
    "delete_notebook": false,
    "delete_tag": false
  }
}
```

##### Environment Variables

You can also configure tools via environment variables:

```bash
export JOPLIN_TOOL_DELETE_NOTE=false
export JOPLIN_TOOL_DELETE_NOTEBOOK=false
export JOPLIN_TOOL_DELETE_TAG=false
```



##### Configuration Examples

**Recommended (Write + Update, no Delete):**
```json
{
  "host": "localhost",
  "port": 41184,
  "tools": {
    "create_note": true,
    "create_notebook": true,
    "create_tag": true,
    "update_note": true,
    "update_notebook": true,
    "update_tag": true,
    "tag_note": true,
    "untag_note": true,
    "delete_note": false,
    "delete_notebook": false,
    "delete_tag": false
  }
}
```

**Conservative (Write only):**
```json
{
  "host": "localhost",
  "port": 41184,
  "tools": {
    "create_note": true,
    "create_notebook": true,
    "create_tag": true,
    "update_note": false,
    "update_notebook": false,
    "update_tag": false,
    "tag_note": false,
    "untag_note": false,
    "delete_note": false,
    "delete_notebook": false,
    "delete_tag": false
  }
}
```

**Read-only mode:**
```json
{
  "host": "localhost",
  "port": 41184,
  "tools": {
    "create_note": false,
    "create_notebook": false,
    "create_tag": false,
    "update_note": false,
    "update_notebook": false,
    "update_tag": false,
    "tag_note": false,
    "untag_note": false,
    "delete_note": false,
    "delete_notebook": false,
    "delete_tag": false
  }
}
```

#### 5. Test the Connection

**For pip install:**
```bash
# Run the FastMCP server (any of these work):
joplin-mcp-server            # Console command (recommended)
joplin-mcp                   # Alias command
python -m joplin_mcp.server  # Module command
```

**For development install:**
```bash
# Run the FastMCP server
python run_fastmcp_server.py
```

You should see:
```
🚀 Starting Joplin FastMCP Server...
✅ Successfully connected to Joplin!
📚 Found X notebooks, Y notes, Z tags
🎯 FastMCP server starting...
📋 Available tools: 23 tools ready
```

## 📁 Project Structure

### Core Files
- **`run_fastmcp_server.py`** - FastMCP server launcher script
- **`joplin-mcp.json`** - Configuration file (you create this)

### Configuration Files
- **`pyproject.toml`** - Python package configuration
- **`requirements.txt`** - Python dependencies

### Source Code
- **`src/joplin_mcp/`** - Main package directory
  - `fastmcp_server.py` - FastMCP server implementation (23 tools, protocol handling)
  - `models.py` - Data models and schemas
  - `config.py` - Configuration management
  - `exceptions.py` - Custom exceptions

### Documentation & Testing
- **`docs/`** - API documentation and guides
- **`tests/`** - FastMCP test suite
- **`README.md`** - This documentation

## 🔧 Claude Desktop Integration

### Claude Desktop Configuration

The configuration depends on your installation method:

#### For Pip Install:
```json
{
  "mcpServers": {
    "joplin": {
      "command": "joplin-mcp-server",
      "env": {
        "JOPLIN_TOKEN": "your_token_here"
      }
    }
  }
}
```

*Alternative commands that also work:*
```json
{
  "mcpServers": {
    "joplin": {
      "command": "joplin-mcp",
      "env": {
        "JOPLIN_TOKEN": "your_token_here"
      }
    }
  }
}
```

*Or using Python module:*
```json
{
  "mcpServers": {
    "joplin": {
      "command": "python",
      "args": ["-m", "joplin_mcp.server"],
      "env": {
        "JOPLIN_TOKEN": "your_token_here"
      }
    }
  }
}
```

#### For Development Install:
```json
{
  "mcpServers": {
    "joplin": {
      "command": "python",
      "args": ["/path/to/your/joplin-mcp/run_fastmcp_server.py"],
      "env": {
        "PYTHONPATH": "/path/to/your/joplin-mcp",
        "JOPLIN_TOKEN": "your_token_here"
      }
    }
  }
}
```

Replace `/path/to/your/joplin-mcp` with your actual project path.

**Note:** The installation commands (`joplin-mcp-install`, `./install.sh`, or `install.py`) automatically configure this for you!

### Usage with Claude Desktop

Once configured, you can:

- **📚 Manage Notebooks**: "List all my notebooks" or "Create a new notebook called 'AI Projects'"
- **🔍 Search Notes**: "Find all notes about Python programming" or "Show me my recent todo items"
- **✍️ Create Content**: "Create a meeting note for today's standup" or "Make a todo for 'Review MCP integration'"
- **🏷️ Organize**: "What tags do I have available?" or "Tag my recent notes about AI with 'important'"

## 🔧 Advanced Configuration

### Environment Variables (Alternative)

Instead of the JSON config file, you can use environment variables:

```bash
export JOPLIN_TOKEN="your_api_token_here"
export JOPLIN_HOST="localhost"
export JOPLIN_PORT="41184"
export JOPLIN_TIMEOUT="30"
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `token` | *required* | Joplin API authentication token |
| `host` | `localhost` | Joplin server hostname |
| `port` | `41184` | Joplin Web Clipper port |
| `timeout` | `30` | Request timeout in seconds |
| `verify_ssl` | `false` | SSL certificate verification |

### Programmatic Usage

```python
from joplin_mcp.config import JoplinMCPConfig
from joplin_mcp.fastmcp_server import app

# Create configuration
config = JoplinMCPConfig(
    token="your_token",
    host="localhost",
    port=41184,
    timeout=30,
    verify_ssl=False
)

# Configuration is loaded automatically from joplin-mcp.json
# or you can set environment variables:
# export JOPLIN_TOKEN="your_token"
# export JOPLIN_HOST="localhost"
# export JOPLIN_PORT="41184"

# The FastMCP server can be run with:
# pip install: joplin-mcp-server  
# development: python run_fastmcp_server.py

# HTTP Transport Support (NEW)
The server now supports both STDIO and HTTP transports:

## STDIO Transport (Default)
```bash
# Standard STDIO transport (default)
python run_fastmcp_server.py

# With custom config
python run_fastmcp_server.py --config my-config.json
```

## HTTP Transport
```bash
# HTTP transport on default port 8000
python run_fastmcp_server.py --transport http

# HTTP transport on custom port and host
python run_fastmcp_server.py --transport http --port 9000 --host 0.0.0.0

# HTTP transport with custom path
python run_fastmcp_server.py --transport http --port 8000 --path /joplin-mcp
```

## HTTP Transport Configuration
When using HTTP transport, you can access the server at:
- **Default**: `http://localhost:8000/mcp`
- **Custom**: `http://your-host:your-port/your-path`

### For Claude Desktop with HTTP Transport
Use the HTTP configuration in your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "joplin": {
      "transport": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**Note**: When using HTTP transport, you must run the server separately before connecting clients.