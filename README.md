# Joplin MCP Server

A **FastMCP-based Model Context Protocol (MCP) server** for [Joplin](https://joplinapp.org/) note-taking application via its Python API [joppy](https://github.com/marph91/joppy), enabling AI assistants to interact with your Joplin notes, notebooks, and tags through a standardized interface.

## Table of Contents

- [What You Can Do](#what-you-can-do)
- [Quick Start](#quick-start)
- [Example Usage](#example-usage)
- [Tool Permissions](#tool-permissions)
- [Advanced Configuration](#advanced-configuration)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Complete Tool Reference](#complete-tool-reference)

## What You Can Do

This MCP server provides **18 optimized tools** for comprehensive Joplin integration:

### **Note Management**
- **Find & Search**: `find_notes`, `find_notes_with_tag`, `find_notes_in_notebook`, `get_all_notes`
- **CRUD Operations**: `get_note`, `create_note`, `update_note`, `delete_note`

### **Notebook Management** 
- **Organize**: `list_notebooks`, `create_notebook`, `update_notebook`, `delete_notebook`

### **Tag Management**
- **Categorize**: `list_tags`, `create_tag`, `delete_tag`, `get_tags_by_note`
- **Link**: `tag_note`, `untag_note`

### **System**
- **Health**: `ping_joplin`

## Quick Start

### 1. Install the Package

```bash
pip install joplin-mcp
```

### 2. Configure Joplin

1. Open **Joplin Desktop** → **Tools** → **Options** → **Web Clipper**
2. **Enable** the Web Clipper service
3. **Copy** the Authorization token

### 3. Run Setup Script

```bash
joplin-mcp-install
```

This interactive script will:
- Configure your Joplin API token
- Set tool permissions (Create/Update/Delete)
- Set up Claude Desktop automatically
- Test the connection

### 4. Choose Your AI Client

#### Option A: Claude Desktop
After running the setup script, restart Claude Desktop and you're ready to go!

```
"List my notebooks" or "Create a note about today's meeting"
```

#### Option B: OllMCP (Local AI Models)

If Claude Desktop was configured above, you can run the following to detect joplin-mcp automatically by OllMCP (Ollama served agents).

```bash
# Install ollmcp
pip install ollmcp

# Run with auto-discovery and your preferred Ollama model, such as:
ollmcp --auto-discovery --model qwen3:4b
```

## Example Usage

Once configured, you can ask your AI assistant:

- **"List all my notebooks"** - See your Joplin organization
- **"Find notes about Python programming"** - Search your knowledge base  
- **"Create a meeting note for today's standup"** - Quick note creation
- **"Tag my recent AI notes as 'important'"** - Organize with tags
- **"Show me my todos"** - Find task items with `find_notes(task=True)`

## Tool Permissions

The setup script offers **3 security levels**:

- **Read** (always enabled): Browse and search your notes safely
- **Write** (optional): Create new notes, notebooks, and tags  
- **Update** (optional): Modify existing content
- **Delete** (optional): Remove content permanently

Choose the level that matches your comfort and use case.

---

## Advanced Configuration

### Alternative Installation (Development)

For developers or users who want the latest features:

#### macOS/Linux:
```bash
git clone https://github.com/alondmnt/joplin-mcp.git
cd joplin-mcp
./install.sh
```

#### Windows:
```batch
git clone https://github.com/alondmnt/joplin-mcp.git
cd joplin-mcp
install.bat
```

### Manual Configuration

If you prefer manual setup or the script doesn't work:

#### 1. Create Configuration File

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

#### 2. Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

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

#### 3. OllMCP Manual Configuration

```bash
# Set environment variable
export JOPLIN_TOKEN="your_token_here"

# Run with manual server configuration
ollmcp --server "joplin:joplin-mcp-server" --model qwen3:4b
```

### Tool Permission Configuration

Fine-tune which operations the AI can perform by editing your config:

```json
{
  "tools": {
    "create_note": true,
    "update_note": true, 
    "delete_note": false,
    "create_notebook": true,
    "delete_notebook": false,
    "create_tag": true,
    "delete_tag": false
  }
}
```

### Environment Variables

Alternative to JSON configuration:

```bash
export JOPLIN_TOKEN="your_api_token_here"
export JOPLIN_HOST="localhost"
export JOPLIN_PORT="41184"
export JOPLIN_TIMEOUT="30"
```

### HTTP Transport Support

The server supports both STDIO and HTTP transports:

```bash
# STDIO (default)
joplin-mcp-server

# HTTP transport 
python run_fastmcp_server.py --transport http --port 8000
```

# Claude Desktop HTTP config
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

### Configuration Reference

#### Basic Settings
| Option | Default | Description |
|--------|---------|-------------|
| `token` | *required* | Joplin API authentication token |
| `host` | `localhost` | Joplin server hostname |
| `port` | `41184` | Joplin Web Clipper port |
| `timeout` | `30` | Request timeout in seconds |
| `verify_ssl` | `false` | SSL certificate verification |

#### Tool Permissions
| Option | Default | Description |
|--------|---------|-------------|
| `tools.create_note` | `true` | Allow creating new notes |
| `tools.update_note` | `true` | Allow modifying existing notes |
| `tools.delete_note` | `true` | Allow deleting notes |
| `tools.create_notebook` | `true` | Allow creating new notebooks |
| `tools.update_notebook` | `false` | Allow modifying notebook titles |
| `tools.delete_notebook` | `true` | Allow deleting notebooks |
| `tools.create_tag` | `true` | Allow creating new tags |
| `tools.update_tag` | `false` | Allow modifying tag titles |
| `tools.delete_tag` | `true` | Allow deleting tags |
| `tools.tag_note` | `true` | Allow adding tags to notes |
| `tools.untag_note` | `true` | Allow removing tags from notes |
| `tools.find_notes` | `true` | Allow text search across notes (with task filtering) |
| `tools.find_notes_with_tag` | `true` | Allow finding notes by tag (with task filtering) |
| `tools.find_notes_in_notebook` | `true` | Allow finding notes by notebook (with task filtering) |
| `tools.get_all_notes` | `false` | Allow getting all notes (disabled by default - can fill context window) |
| `tools.get_note` | `true` | Allow getting specific notes |
| `tools.list_notebooks` | `true` | Allow listing all notebooks |
| `tools.list_tags` | `true` | Allow listing all tags |
| `tools.get_tags_by_note` | `true` | Allow getting tags for specific notes |
| `tools.ping_joplin` | `true` | Allow testing server connectivity |

#### Content Exposure (Privacy Settings)
| Option | Default | Description |
|--------|---------|-------------|
| `content_exposure.search_results` | `"preview"` | Content visibility in search results: `"none"`, `"preview"`, `"full"` |
| `content_exposure.individual_notes` | `"full"` | Content visibility for individual notes: `"none"`, `"preview"`, `"full"` |
| `content_exposure.listings` | `"none"` | Content visibility in note listings: `"none"`, `"preview"`, `"full"` |
| `content_exposure.max_preview_length` | `200` | Maximum length of content previews (characters) |

## Project Structure

- **`run_fastmcp_server.py`** - FastMCP server launcher
- **`src/joplin_mcp/`** - Main package directory
  - `fastmcp_server.py` - Server implementation with 17 tools (by default)
  - `models.py` - Data models and schemas
  - `config.py` - Configuration management
- **`docs/`** - API documentation
- **`tests/`** - Test suite

## Testing

Test your connection:

```bash
# For pip install
joplin-mcp-server

# For development  
python run_fastmcp_server.py
```

You should see:
```
Starting Joplin FastMCP Server...
Successfully connected to Joplin!
Found X notebooks, Y notes, Z tags
FastMCP server starting...
Available tools: 17 tools ready
```

## Complete Tool Reference

| Tool | Permission | Description |
|------|------------|-------------|
| **Finding Notes** | | |
| `find_notes` | Read | Full-text search across all notes (supports task filtering) |
| `find_notes_with_tag` | Read | Find notes with specific tag (supports task filtering) |
| `find_notes_in_notebook` | Read | Find notes in specific notebook (supports task filtering) |
| `get_all_notes` | Read | Get all notes, most recent first *(disabled by default)* |
| `get_note` | Read | Get specific note by ID |
| **Managing Notes** | | |
| `create_note` | Write | Create new notes |
| `update_note` | Update | Modify existing notes |
| `delete_note` | Delete | Remove notes |
| **Managing Notebooks** | | |
| `list_notebooks` | Read | Browse all notebooks |
| `create_notebook` | Write | Create new notebooks |
| `update_notebook` | Update | Modify notebook titles |
| `delete_notebook` | Delete | Remove notebooks |
| **Managing Tags** | | |
| `list_tags` | Read | View all available tags |
| `create_tag` | Write | Create new tags |
| `delete_tag` | Delete | Remove tags |
| `get_tags_by_note` | Read | List tags on specific note |
| **Tag-Note Relationships** | | |
| `tag_note` | Update | Add tags to notes |
| `untag_note` | Update | Remove tags from notes |
| **System Tools** | | |
| `ping_joplin` | Read | Test connectivity |
