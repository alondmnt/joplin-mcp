# Joplin MCP

A comprehensive **Model Context Protocol (MCP)** server for the [Joplin](https://joplinapp.org) note-taking application. This enables AI assistants and developers to seamlessly interact with Joplin data through standardized protocol interfaces.

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP Version](https://img.shields.io/badge/MCP-1.0.0-purple.svg)](https://modelcontextprotocol.io)

## 🚀 Features

- **Complete CRUD Operations**: Create, read, update, and delete notes, notebooks, and tags
- **Advanced Search**: Full-text search with Joplin syntax support and pagination
- **MCP Compliant**: Follows the official Model Context Protocol specification
- **Built on joppy**: Leverages the proven [joppy library](https://github.com/marph91/joppy) for reliable Joplin API integration
- **Type Safe**: Full TypeScript-style type hints and Pydantic data validation
- **Test Driven**: Comprehensive test suite with 90%+ coverage
- **Easy Integration**: Simple setup with environment variables or config files

## 📋 Requirements

- Python 3.8 or higher
- Joplin desktop application with Web Clipper service enabled
- Joplin API token

## 🔧 Installation

### From PyPI (when available)

```bash
pip install joplin-mcp
```

### From Source

```bash
git clone https://github.com/your-org/joplin-mcp.git
cd joplin-mcp
pip install -e .
```

### Development Installation

```bash
git clone https://github.com/your-org/joplin-mcp.git
cd joplin-mcp
pip install -r requirements.txt
pip install -e .
```

## ⚡ Quick Start

### 1. Get Your Joplin API Token

1. Open Joplin desktop application
2. Go to **Tools** → **Options** → **Web Clipper**
3. Enable the clipper service if not already enabled
4. Copy the **Authorization token**

### 2. Basic Usage

```python
from joplin_mcp import JoplinMCPServer
import asyncio

async def main():
    # Initialize the MCP server
    server = JoplinMCPServer(token="your_joplin_api_token")
    
    # Start the server
    await server.start()
    
    print("Joplin MCP server is running!")

if __name__ == "__main__":
    asyncio.run(main())
```

### 3. Environment Configuration

Set your Joplin API token using environment variables:

```bash
export JOPLIN_TOKEN="your_joplin_api_token"
export JOPLIN_HOST="localhost"  # optional, default: localhost
export JOPLIN_PORT="41184"      # optional, default: 41184
```

## 🛠️ Supported MCP Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `search_notes` | Search notes with full-text query | `query`, `limit`, `page` |
| `get_note` | Retrieve a specific note by ID | `note_id` |
| `create_note` | Create a new note | `title`, `body`, `notebook_id`, `tags` |
| `update_note` | Update an existing note | `note_id`, `title`, `body`, `tags` |
| `delete_note` | Delete a note | `note_id` |
| `list_notebooks` | List all notebooks | `limit`, `page` |
| `get_notebook` | Get notebook details | `notebook_id` |
| `create_notebook` | Create a new notebook | `title`, `parent_id` |
| `list_tags` | List all tags | `limit`, `page` |
| `create_tag` | Create a new tag | `title` |
| `tag_note` | Add tag to note | `note_id`, `tag_id` |
| `untag_note` | Remove tag from note | `note_id`, `tag_id` |
| `ping_joplin` | Test Joplin server connection | none |

## 📖 Usage Examples

### Searching Notes

```python
# Search for notes containing "python"
results = await server.call_tool("search_notes", {
    "query": "python",
    "limit": 10
})
```

### Creating a Note

```python
# Create a new note
note_id = await server.call_tool("create_note", {
    "title": "My Research Notes",
    "body": "# Important Findings\n\n- Discovery 1\n- Discovery 2",
    "tags": ["research", "important"]
})
```

### Managing Notebooks

```python
# Create a new notebook
notebook_id = await server.call_tool("create_notebook", {
    "title": "Project Alpha",
})

# List all notebooks
notebooks = await server.call_tool("list_notebooks")
```

## 🧪 Development

This project follows **Test-Driven Development (TDD)** principles. To contribute:

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/joplin-mcp.git
   cd joplin-mcp
   ```

2. **Install development dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run tests**
   ```bash
   pytest
   ```

4. **Code formatting and linting**
   ```bash
   black src/ tests/
   ruff check src/ tests/
   mypy src/
   ```

### TDD Workflow

1. **RED**: Write a failing test
2. **GREEN**: Write minimal code to make it pass
3. **REFACTOR**: Improve the code while keeping tests green

## 🏗️ Project Structure

```
joplin-mcp/
├── src/joplin_mcp/         # Source code
│   ├── __init__.py         # Package initialization
│   ├── server.py           # MCP server implementation
│   ├── client.py           # Joplin API client wrapper
│   ├── models.py           # Data models
│   └── config.py           # Configuration management
├── tests/                  # Test suite
│   ├── conftest.py         # Pytest fixtures
│   ├── test_server.py      # Server tests
│   ├── test_client.py      # Client tests
│   └── test_models.py      # Model tests
├── tasks/                  # Project management
├── pyproject.toml          # Project configuration
├── requirements.txt        # Dependencies
└── README.md              # This file
```

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Joplin](https://joplinapp.org) - The excellent note-taking application
- [joppy](https://github.com/marph91/joppy) - Python interface for Joplin API
- [Model Context Protocol](https://modelcontextprotocol.io) - Standardized AI-application integration

## 📞 Support

- **Documentation**: [GitHub Wiki](https://github.com/your-org/joplin-mcp/wiki)
- **Issues**: [GitHub Issues](https://github.com/your-org/joplin-mcp/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/joplin-mcp/discussions)

---

**Made with ❤️ for the Joplin and AI communities** 