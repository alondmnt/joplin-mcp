# Joplin MCP Server

A **Model Context Protocol (MCP) server** for [Joplin](https://joplinapp.org/) note-taking application, enabling AI assistants to interact with your Joplin notes, notebooks, and tags through a standardized interface.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-385%20passing-green.svg)](https://github.com/your-org/joplin-mcp)
[![Type Checking](https://img.shields.io/badge/mypy-passing-green.svg)](https://mypy.readthedocs.io/)

## 🎯 Overview

This MCP server provides AI assistants with comprehensive access to your Joplin notes through 13 powerful tools:

### 📝 Note Management
- **search_notes** - Full-text search across all notes with advanced filtering
- **get_note** - Retrieve specific notes with metadata and content
- **create_note** - Create new notes with support for todos, tags, and notebooks
- **update_note** - Modify existing notes with flexible parameter support
- **delete_note** - Remove notes with confirmation

### 📁 Notebook Management
- **list_notebooks** - Browse all notebooks with hierarchical structure
- **get_notebook** - Get detailed notebook information
- **create_notebook** - Create new notebooks with parent-child relationships

### 🏷️ Tag Management
- **list_tags** - View all available tags
- **create_tag** - Create new tags for organization
- **tag_note** - Add tags to notes
- **untag_note** - Remove tags from notes

### 🔧 System Tools
- **ping_joplin** - Test server connectivity and health

## ✨ Key Features

### 🦙 **Direct Ollama Integration**
- **Interactive chat client** - Talk to your notes in plain English
- **Zero-config setup** - Just run two commands and start chatting
- **Intelligent tool usage** - Ollama automatically decides when to use Joplin tools
- **Real-time feedback** - See exactly what's happening with your notes

### 🚀 **Production Ready**
- **13 comprehensive tools** for complete note management
- **Rate limiting & security** - Safe for production use
- **300+ tests** - Thoroughly tested and reliable
- **Type-safe** - Full TypeScript compatibility

### 🔌 **MCP Compliant**
- **Industry standard** - Works with any MCP-compatible client
- **Extensible** - Easy to add new tools and capabilities
- **Well-documented** - Comprehensive API documentation

## 🚀 Quick Start

### Option 1: Direct Ollama Integration (Easiest)

The fastest way to get started is with our interactive Ollama client:

```bash
# 1. Clone and install
git clone https://github.com/alondmnt/joplin-mcp.git
cd joplin-mcp
pip install -e .

# 2. Configure Joplin (see Configuration section below)
# Create joplin-mcp.json with your API token

# 3. Install and setup Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull gemma3:4b

# 4. Start chatting!
python run_mcp_server.py        # Terminal 1
python ollama_mcp_client.py     # Terminal 2 - Interactive chat starts
```

You'll immediately have an AI assistant that can search, create, and manage your Joplin notes through natural conversation!

### Option 2: Standard MCP Server Setup

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

#### 4. Test the Connection
```bash
# Test basic connectivity
python test_connection.py

# Run the MCP server
python run_mcp_server.py
```

You should see:
```
🚀 Starting Joplin MCP Server...
✅ Successfully connected to Joplin!
📚 Found X notebooks
🎯 Server starting on localhost:41184
📋 Available tools: 13 tools ready
```

## 📁 Project Structure

### Core Files
- **`run_mcp_server.py`** - Main MCP server launcher script
- **`ollama_mcp_client.py`** - Interactive Ollama chat client (⭐ **New!**)
- **`joplin-mcp.json`** - Configuration file (you create this)
- **`test_connection.py`** - Connection testing utility

### Configuration Files
- **`ollama-mcp-config.json`** - Pre-configured Ollama MCP setup
- **`pyproject.toml`** - Python package configuration
- **`requirements.txt`** - Python dependencies

### Source Code
- **`src/joplin_mcp/`** - Main package directory
  - `server.py` - MCP server implementation
  - `client.py` - Joplin API client
  - `models.py` - Data models and schemas
  - `config.py` - Configuration management
  - `exceptions.py` - Custom exceptions

### Documentation & Testing
- **`docs/`** - API documentation and guides
- **`tests/`** - Comprehensive test suite (300+ tests)
- **`README.md`** - This documentation

## 🦙 Ollama Integration

### Quick Start with Ollama

The easiest way to use this MCP server with Ollama is through our pre-built interactive client:

```bash
# 1. Start the MCP server (in one terminal)
python run_mcp_server.py

# 2. Start the Ollama chat client (in another terminal)
python ollama_mcp_client.py
```

That's it! You'll have an interactive chat session where you can talk to Ollama and it will automatically use your Joplin notes.

### Prerequisites for Ollama Integration

1. **Ollama installed** and running:
   ```bash
   # Install Ollama (macOS/Linux)
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Or download from https://ollama.ai/
   ```

2. **At least one model downloaded**:
   ```bash
   # Download a recommended model
   ollama pull gemma3:4b
   # or
   ollama pull llama3.2
   ```

3. **Joplin MCP server configured** (see Quick Start section above)

### Method 1: Direct Ollama Client (Recommended)

Our custom Ollama client (`ollama_mcp_client.py`) provides the best experience:

#### Features:
- 🗣️ **Natural conversation** with your Joplin notes
- 🔍 **Automatic tool detection** - Ollama decides when to use Joplin tools
- 📝 **Smart JSON parsing** - Handles Ollama's various response formats
- 🎯 **Real-time feedback** - See exactly what tools are being executed
- 🛠️ **All 13 tools** supported seamlessly

#### Usage Examples:

```bash
# Start the client
python ollama_mcp_client.py

# Example conversations:
💬 You: list all my notebooks
🤖 Assistant: I'll list your Joplin notebooks for you...
[Tool executes and returns your 40 notebooks organized by category]

💬 You: find notes about machine learning
🤖 Assistant: Let me search your notes for machine learning content...
[Searches and returns relevant notes with summaries]

💬 You: create a new note called "Meeting Notes" in my work notebook
🤖 Assistant: I'll create that note for you...
[Creates the note and confirms success]
```

#### Configuration:
Edit `ollama_mcp_client.py` to change the model:

```python
# Change the default model (line ~20)
def __init__(self, ollama_model: str = "gemma3:4b"):  # or "llama3.2", "phi3:latest", etc.
```

#### Available Commands in Chat:
- `help` - Show available commands
- `tools` - List all Joplin tools
- `quit` - Exit the chat

### Method 2: MCP Registry Integration

For advanced users who want to integrate with multiple MCP servers:

#### Step 1: Install MCP Registry
```bash
pip install mcp-registry
```

#### Step 2: Initialize and Add Joplin Server
```bash
# Initialize MCP Registry
mcp-registry init

# Add your Joplin MCP server
mcp-registry add joplin python /path/to/your/joplin-mcp/run_mcp_server.py

# Verify it's registered
mcp-registry list
```

#### Step 3: Test the Integration
```bash
# List available tools
mcp-registry list-tools joplin

# Test a specific tool
mcp-registry test-tool joplin list_notebooks '{}'
```

### Method 3: Manual Ollama MCP Configuration

For direct Ollama MCP integration (requires Ollama with MCP support):

#### Step 1: Create Ollama MCP Config
Create or edit `~/.ollama/mcp-config.json`:

```json
{
  "mcpServers": {
    "joplin": {
      "command": "python",
      "args": ["/Users/yourusername/projects/joplin-mcp/run_mcp_server.py"],
      "env": {
        "PYTHONPATH": "/Users/yourusername/projects/joplin-mcp"
      }
    }
  }
}
```

#### Step 2: Update Paths
Replace `/Users/yourusername/projects/joplin-mcp` with your actual project path.

#### Step 3: Restart Ollama
```bash
# Stop Ollama if running
killall ollama

# Start Ollama with MCP support
ollama serve
```

### Example Conversations with Ollama

Here are real examples of what you can ask:

#### 📚 **Notebook Management**
```
You: "Show me all my notebooks"
Ollama: Lists and categorizes your 40 notebooks by purpose

You: "Create a new notebook called 'AI Projects'"
Ollama: Creates the notebook and confirms with the new ID
```

#### 🔍 **Smart Search**
```
You: "Find all notes about Python programming"
Ollama: Searches your notes and returns relevant matches with summaries

You: "Show me my recent todo items"
Ollama: Finds todo notes and shows their completion status
```

#### ✍️ **Note Creation**
```
You: "Create a meeting note for today's standup"
Ollama: Creates a new note with proper title and structure

You: "Make a todo for 'Review MCP integration' in my work notebook"
Ollama: Creates a todo note in the specified notebook
```

#### 🏷️ **Organization**
```
You: "What tags do I have available?"
Ollama: Lists all your tags

You: "Tag my recent notes about AI with 'important'"
Ollama: Finds recent AI notes and adds the tag
```

### Supported Ollama Models

Tested and working models:
- `gemma3:4b` ⭐ (recommended for JSON tool usage)
- `llama3.2`
- `phi3:latest`
- `orca-mini:latest`

### Troubleshooting Ollama Integration

**Client won't start:**
```bash
# Ensure dependencies are installed
pip install mcp

# Check if Ollama is running
ollama list
```

**Tool execution fails:**
```bash
# Ensure MCP server is running first
python run_mcp_server.py
# Then start the client in another terminal
```

**JSON parsing issues:**
- Some models are better at JSON formatting than others
- The client includes robust JSON extraction for various formats
- Try different models if you have issues

**Connection timeouts:**
- Increase timeout in `ollama_mcp_client.py` if needed
- Ensure your Joplin instance is responsive

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
from joplin_mcp.server import JoplinMCPServer
from joplin_mcp.config import JoplinMCPConfig

# Create configuration
config = JoplinMCPConfig(
    token="your_token",
    host="localhost",
    port=41184,
    timeout=30,
    verify_ssl=False
)

# Initialize server
server = JoplinMCPServer(config=config)

# Use server tools
result = await server.handle_search_notes({
    "query": "meeting notes",
    "limit": 10
})
```

## 📚 Comprehensive Examples

### Advanced Note Search

```python
# Search with multiple filters
search_params = {
    "query": "project planning",
    "limit": 20,
    "notebook_id": "work_notebook_id",
    "tags": ["important", "deadline"],
    "sort_by": "updated_time",
    "sort_order": "desc"
}

results = await server.handle_search_notes(search_params)
```