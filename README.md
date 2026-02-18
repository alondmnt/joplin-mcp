# Joplin MCP Server

A **FastMCP-based Model Context Protocol (MCP) server** for [Joplin](https://joplinapp.org/) note-taking application via its Python API [joppy](https://github.com/marph91/joppy), enabling AI assistants to interact with your Joplin notes, notebooks, and tags through a standardized interface.

<!-- mcp-name: io.github.alondmnt/joplin-mcp -->

## Table of Contents

- [What You Can Do](#what-you-can-do)
- [Quick Start](#quick-start)
- [Example Usage](#example-usage)
- [Tool Permissions](#tool-permissions)
- [Advanced Configuration](#advanced-configuration)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Complete Tool Reference](#complete-tool-reference)
- [Claude Code Plugin](#claude-code-plugin)
- [Changelog](CHANGELOG.md)

## What You Can Do

This MCP server provides **24 optimized tools** for comprehensive Joplin integration:

### **Note Management**
- **Find & Search**: `find_notes`, `find_notes_with_tag`, `find_notes_in_notebook`, `get_all_notes`
- **CRUD Operations**: `get_note`, `get_links`, `create_note`, `update_note`, `edit_note`, `delete_note`

### **Notebook Management** 
- **Organize**: `list_notebooks`, `create_notebook`, `update_notebook`, `delete_notebook`

### **Tag Management**
- **Categorize**: `list_tags`, `create_tag`, `update_tag`, `delete_tag`, `get_tags_by_note`
- **Link**: `tag_note`, `untag_note`

### **Import**
- **File Import**: `import_from_file` - Import Markdown, HTML, CSV, TXT, JEX files and directories
  > **Note**: Import tools are disabled by default for security. Enable with `"import_from_file": true` in your config.

### **System**
- **Health**: `ping_joplin`

## Quick Start


### 1. Configure Joplin

1. Open **Joplin Desktop** → **Tools** → **Options** → **Web Clipper**
2. **Enable** the Web Clipper service
3. **Copy** the Authorization token

### 2. Choose Your AI Client

#### Option A: Claude Desktop (Online, Commercial, Automated Setup)

Run the automated installer:

```bash
# Install and configure everything automatically (pip)
pip install joplin-mcp
joplin-mcp-install

# Or use zero-install with uvx (recommended if you have uv)
uvx --from joplin-mcp joplin-mcp-install

# Optional: pin a specific version/range for stability
uvx --from joplin-mcp==0.4.1 joplin-mcp-install
uvx --from 'joplin-mcp>=0.4,<0.5' joplin-mcp-install
```

This script will:
- Configure your Joplin API token  
- Set tool permissions (Create/Update/Delete)
- Set up Claude Desktop automatically
- Test the connection

After setup, restart Claude Desktop and you're ready to go!

```
"List my notebooks" or "Create a note about today's meeting"
```

#### Option B: Jan AI (Local AI models)

1. **Install Jan AI** from [https://jan.ai](https://jan.ai)

2. **Add MCP Server** in Jan's interface:
   - Open Jan AI
   - Go to **Settings** → **Extensions** → **Model Context Protocol**
   - Click **Add MCP Server**
   - Configure:
     - **Name**: `joplin`
     - **Command**: `uvx --from joplin-mcp joplin-mcp-server` *(requires `uv` installed)*
     - **Environment Variables**:
       - `JOPLIN_TOKEN`: `your_joplin_api_token_here`
   - Enable the server

3. **Start chatting** with access to your Joplin notes!

**B2: Automated Setup (Alternative)**

```bash
# Install and configure Jan AI automatically (if Jan is already installed)
pip install joplin-mcp
joplin-mcp-install
```

This will detect and configure Jan AI automatically, just like Claude Desktop.

```
"Show me my recent notes" or "Create a project planning note"
```

#### Option C: OllMCP (Local AI Models)

For local Ollama models:

**Option C1: Auto-discovery (if you set up Claude Desktop first)**
```bash
# Install ollmcp
pip install ollmcp

# Run with auto-discovery (requires existing Claude Desktop config)
ollmcp --auto-discovery --model qwen3:4b
```

**Option C2: Manual setup (works independently)**
```bash
# Install ollmcp
pip install ollmcp

# Set environment variable
export JOPLIN_TOKEN="your_joplin_api_token_here"

# Run with manual server configuration (requires uv installed)
ollmcp --server "joplin:uvx --from joplin-mcp joplin-mcp-server" --model qwen3:4b
```

### Claude Code Plugin

If you use [Claude Code](https://docs.anthropic.com/en/docs/claude-code), install the orchestration plugin for smarter tool usage (edit vs update, long-note reading, bulk tagging):

```bash
/plugin install github:alondmnt/joplin-mcp
```

This loads a skill that Claude invokes automatically when working with Joplin tools. You can also trigger it manually with `/joplin`.

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

### Alternative Installation Methods

#### Method 1: Traditional pip install

If you don't have `uvx` or prefer to customize MCP settings:

```bash
# Install the package
pip install joplin-mcp

# Run the setup script
joplin-mcp-install
```

This method provides the same functionality as `uvx joplin-mcp-install` but requires a local Python environment.

#### Method 2: Development Installation

For developers or users who want the latest features:

**macOS/Linux:**
```bash
git clone https://github.com/alondmnt/joplin-mcp.git
cd joplin-mcp
./install.sh
```

**Windows:**
```batch
git clone https://github.com/alondmnt/joplin-mcp.git
cd joplin-mcp
install.bat
```

### Manual Configuration

If you prefer manual setup or the script doesn't work:

> Note on `uvx`: `uvx` runs Python applications without permanently installing them (requires `uv`: `pip install uv`). It can read and write user configuration files (e.g., Claude/Jan configs), so `uvx --from joplin-mcp joplin-mcp-install` works for setup just like a pip install.

> Version pinning (optional): For long‑lived client configs or CI, you can pin or range-constrain the version for reproducibility, e.g. `uvx --from joplin-mcp==0.4.1 joplin-mcp-install` or `uvx --from 'joplin-mcp>=0.4,<0.5' joplin-mcp-install`.

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

**Option A: Using uvx (Zero-install)**
```json
{
  "mcpServers": {
    "joplin": {
      "command": "uvx",
      "args": ["--from", "joplin-mcp", "joplin-mcp-server"],
      "env": {
        "JOPLIN_TOKEN": "your_token_here"
      }
    }
  }
}
```
*Requires `uv` installed: `pip install uv`*

**Option B: Using installed package**
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

**Option A: Using uvx (Zero-install)**
```bash
# Set environment variable
export JOPLIN_TOKEN="your_token_here"

# Run with manual server configuration
ollmcp --server "joplin:uvx --from joplin-mcp joplin-mcp-server" --model qwen3:4b
```
*Requires `uv` installed: `pip install uv`*

**Option B: Using installed package**
```bash
# Set environment variable
export JOPLIN_TOKEN="your_token_here"

# Run with manual server configuration
ollmcp --server "joplin:joplin-mcp-server" --model qwen3:4b
```

#### 4. More Client Configuration Examples

For additional client configurations including different transport options (HTTP, SSE, Streamable HTTP), see [client-config.json.example](client-config.json.example).

This file includes configurations for:
- **STDIO transport** (default, most compatible)
- **HTTP transport** (basic HTTP server mode)
- **SSE transport** (recommended for gemini-cli and OpenAI clients)
- **Streamable HTTP transport** (advanced web clients)
- **HTTP-compat transport** (bridges modern `/mcp` JSON-RPC with legacy `/sse`/`/messages` clients)

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
    "update_tag": false,
    "delete_tag": false,
    "import_from_file": true,
    "get_all_notes": false,
    "update_notebook": false,
    "update_tag": false
  }
}
```

### Environment Variables

Alternative to JSON configuration:

```bash
# Connection settings
export JOPLIN_TOKEN="your_api_token_here"
export JOPLIN_HOST="localhost"
export JOPLIN_PORT="41184"
export JOPLIN_TIMEOUT="30"
```

#### Per-Tool Env Vars

Every tool can be toggled individually via `JOPLIN_TOOL_<NAME>=true|false`. These take precedence over config file settings.

| Env var | Default |
|---------|---------|
| `JOPLIN_TOOL_FIND_NOTES` | `true` |
| `JOPLIN_TOOL_FIND_NOTES_WITH_TAG` | `true` |
| `JOPLIN_TOOL_FIND_NOTES_IN_NOTEBOOK` | `true` |
| `JOPLIN_TOOL_FIND_IN_NOTE` | `true` |
| `JOPLIN_TOOL_GET_ALL_NOTES` | `false` |
| `JOPLIN_TOOL_GET_NOTE` | `true` |
| `JOPLIN_TOOL_GET_LINKS` | `true` |
| `JOPLIN_TOOL_CREATE_NOTE` | `true` |
| `JOPLIN_TOOL_UPDATE_NOTE` | `true` |
| `JOPLIN_TOOL_EDIT_NOTE` | `true` |
| `JOPLIN_TOOL_DELETE_NOTE` | `false` |
| `JOPLIN_TOOL_LIST_NOTEBOOKS` | `true` |
| `JOPLIN_TOOL_CREATE_NOTEBOOK` | `true` |
| `JOPLIN_TOOL_UPDATE_NOTEBOOK` | `false` |
| `JOPLIN_TOOL_DELETE_NOTEBOOK` | `false` |
| `JOPLIN_TOOL_LIST_TAGS` | `true` |
| `JOPLIN_TOOL_CREATE_TAG` | `true` |
| `JOPLIN_TOOL_UPDATE_TAG` | `false` |
| `JOPLIN_TOOL_DELETE_TAG` | `false` |
| `JOPLIN_TOOL_GET_TAGS_BY_NOTE` | `true` |
| `JOPLIN_TOOL_TAG_NOTE` | `true` |
| `JOPLIN_TOOL_UNTAG_NOTE` | `true` |
| `JOPLIN_TOOL_PING_JOPLIN` | `true` |
| `JOPLIN_TOOL_IMPORT_FROM_FILE` | `false` |

### HTTP Transport Support

The server supports both STDIO and HTTP transports:

```bash
# STDIO (default)
joplin-mcp-server --config ~/.joplin-mcp.json

# HTTP transport (development, from repo)
PYTHONPATH=src python -m joplin_mcp.server --transport http --port 8000 --config ./joplin-mcp.json

# Opt-in HTTP compatibility bundle (modern + legacy SSE endpoints)
PYTHONPATH=src python -m joplin_mcp.server --transport http-compat --port 8000 --config ./joplin-mcp.json
# or keep --transport http and export MCP_HTTP_COMPAT=1/true to toggle the same behavior.
```

# HTTP client config
Note: Claude Desktop currently uses STDIO transport and does not consume HTTP/SSE configs directly. The following example applies to clients that support network transports.
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
| `tools.delete_note` | `false` | Allow deleting notes *(disabled by default — destructive)* |
| `tools.create_notebook` | `true` | Allow creating new notebooks |
| `tools.update_notebook` | `false` | Allow modifying notebook titles |
| `tools.delete_notebook` | `false` | Allow deleting notebooks *(disabled by default — destructive)* |
| `tools.create_tag` | `true` | Allow creating new tags |
| `tools.update_tag` | `false` | Allow modifying tag titles |
| `tools.delete_tag` | `false` | Allow deleting tags *(disabled by default — destructive)* |
| `tools.tag_note` | `true` | Allow adding tags to notes |
| `tools.untag_note` | `true` | Allow removing tags from notes |
| `tools.find_notes` | `true` | Allow text search across notes (with task filtering) |
| `tools.find_notes_with_tag` | `true` | Allow finding notes by tag (with task filtering) |
| `tools.find_notes_in_notebook` | `true` | Allow finding notes by notebook (with task filtering) |
| `tools.get_all_notes` | `false` | Allow getting all notes (disabled by default - can fill context window) |
| `tools.get_note` | `true` | Allow getting specific notes |
| `tools.get_links` | `true` | Allow extracting links to other notes |
| `tools.list_notebooks` | `true` | Allow listing all notebooks |
| `tools.list_tags` | `true` | Allow listing all tags |
| `tools.get_tags_by_note` | `true` | Allow getting tags for specific notes |
| `tools.ping_joplin` | `true` | Allow testing server connectivity |
| `tools.import_from_file` | `false` | Allow importing files/directories (MD, HTML, CSV, TXT, JEX) |

#### Content Exposure (Privacy Settings)
| Option | Default | Description |
|--------|---------|-------------|
| `content_exposure.search_results` | `"preview"` | Content visibility in search results: `"none"`, `"preview"`, `"full"` |
| `content_exposure.individual_notes` | `"full"` | Content visibility for individual notes: `"none"`, `"preview"`, `"full"` |
| `content_exposure.listings` | `"none"` | Content visibility in note listings: `"none"`, `"preview"`, `"full"` |
| `content_exposure.max_preview_length` | `300` | Maximum length of content previews (characters) |

## Docker

Run the MCP server in a container. Default transport is HTTP for broad compatibility; switch via environment variables.

### Build
```bash
docker build -t joplin-mcp .
```

### Run (HTTP default)
```bash
docker run --rm \
  -p 8000:8000 \
  -e JOPLIN_TOKEN=your_api_token \
  joplin-mcp
```

### With mounted config
```bash
docker run --rm \
  -p 8000:8000 \
  -v $PWD/joplin-mcp.json:/config/joplin-mcp.json:ro \
  joplin-mcp
```

### Choose transport
- SSE (streaming): `-e MCP_TRANSPORT=sse`
- Streamable HTTP: `-e MCP_TRANSPORT=streamable-http`
- STDIO (no port): `-e MCP_TRANSPORT=stdio`

Example (SSE):
```bash
docker run --rm \
  -p 8000:8000 \
  -e JOPLIN_TOKEN=your_api_token \
  -e MCP_TRANSPORT=sse \
  joplin-mcp
```

The container listens on `0.0.0.0:8000` by default. If exposing publicly, place behind a reverse proxy and terminate TLS there. For SSE, ensure proxy keep-alives and buffering are configured appropriately.


## Project Structure

- **`src/joplin_mcp/`** - Main package directory
  - `fastmcp_server.py` - Server implementation with 22 tools and Pydantic validation types
  - `config.py` - Configuration management
  - `server.py` - Server entrypoint (module and CLI)
  - `ui_integration.py` - UI integration utilities
- **`docs/`** - Documentation (troubleshooting, privacy controls, enhancement proposals)
- **`tests/`** - Test suite

## Testing

Test your connection:

```bash
# For pip install
joplin-mcp-server --config ~/.joplin-mcp.json

# For development (from repo)
PYTHONPATH=src python -m joplin_mcp.server --config ./joplin-mcp.json
```

You should see:
```
Starting Joplin FastMCP Server...
Successfully connected to Joplin!
Found X notebooks, Y notes, Z tags
FastMCP server starting...
Available tools: 22 tools ready
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
| `find_in_note` | Read | Regex search within a single note (paginated matches & context, multiline anchors on by default) |
| `get_links` | Read | Extract links to other notes from a note |
| **Managing Notes** | | |
| `create_note` | Write | Create new notes |
| `update_note` | Update | Modify existing notes |
| `edit_note` | Update | Precision edit note content (find/replace, append, prepend) |
| `delete_note` | Delete | Remove notes |
| **Managing Notebooks** | | |
| `list_notebooks` | Read | Browse all notebooks |
| `create_notebook` | Write | Create new notebooks |
| `update_notebook` | Update | Modify notebook titles |
| `delete_notebook` | Delete | Remove notebooks |
| **Managing Tags** | | |
| `list_tags` | Read | View all available tags |
| `create_tag` | Write | Create new tags |
| `update_tag` | Update | Modify tag titles |
| `delete_tag` | Delete | Remove tags |
| `get_tags_by_note` | Read | List tags on specific note |
| **Tag-Note Relationships** | | |
| `tag_note` | Update | Add tags to notes |
| `untag_note` | Update | Remove tags from notes |
| **Import Tools** | | |
| `import_from_file` | Write | Import files/directories (MD, HTML, CSV, TXT, JEX) |
| **System Tools** | | |
| `ping_joplin` | Read | Test connectivity |
