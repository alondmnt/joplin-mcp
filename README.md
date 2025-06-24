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

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+**
- **Joplin Desktop** with Web Clipper service enabled
- **Joplin API token** (generated in Joplin settings)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/joplin-mcp.git
cd joplin-mcp

# Install dependencies
pip install -e .

# Or install development dependencies
pip install -e ".[dev]"
```

### Configuration

1. **Enable Joplin Web Clipper**:
   - Open Joplin Desktop
   - Go to Tools → Options → Web Clipper
   - Enable the Web Clipper service
   - Note the port (default: 41184)

2. **Generate API Token**:
   - In Web Clipper settings, copy the API token
   - Or generate a new token if needed

3. **Set Environment Variables**:
```bash
export JOPLIN_TOKEN="your_api_token_here"
export JOPLIN_HOST="localhost"  # Optional, defaults to localhost
export JOPLIN_PORT="41184"      # Optional, defaults to 41184
```

### Basic Usage

```python
from joplin_mcp import JoplinMCPServer

# Initialize the server
server = JoplinMCPServer(token="your_api_token")

# Start the server
await server.start()

# Search for notes
results = await server.handle_search_notes({
    "query": "meeting notes",
    "limit": 10
})

# Create a new note
note_result = await server.handle_create_note({
    "title": "My New Note",
    "body": "This is the content of my note.",
    "parent_id": "notebook_id_here"
})

# Stop the server
await server.stop()
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

### Creating Todo Notes

```python
# Create a todo item with tags
todo_params = {
    "title": "Complete project documentation",
    "body": "Write comprehensive docs for the new feature",
    "parent_id": "work_notebook_id",
    "is_todo": True,
    "todo_completed": False,
    "tags": ["urgent", "documentation", "project-x"]
}

todo_result = await server.handle_create_note(todo_params)
```

### Notebook Organization

```python
# Create a hierarchical notebook structure
parent_notebook = await server.handle_create_notebook({
    "title": "Work Projects"
})

child_notebook = await server.handle_create_notebook({
    "title": "Project Alpha",
    "parent_id": parent_notebook["notebook_id"]
})

# List all notebooks
notebooks = await server.handle_list_notebooks({})
```

### Tag Management Workflow

```python
# Create tags for organization
await server.handle_create_tag({"title": "urgent"})
await server.handle_create_tag({"title": "review"})

# Tag a note
await server.handle_tag_note({
    "note_id": "note_123",
    "tag_id": "urgent_tag_id"
})

# List all tags
tags = await server.handle_list_tags({})
```

## 🧪 Test-Driven Development (TDD) Approach

This project was built using **strict Test-Driven Development** methodology:

### TDD Cycle: RED → GREEN → REFACTOR

1. **🔴 RED Phase**: Write failing tests first
   - Define expected behavior through tests
   - Ensure tests fail initially (no implementation)
   - Validate test quality and coverage

2. **🟢 GREEN Phase**: Implement minimal code to pass tests
   - Write just enough code to make tests pass
   - Focus on functionality over optimization
   - Maintain test coverage at 100%

3. **🔵 REFACTOR Phase**: Optimize and clean up
   - Improve code structure and performance
   - Extract common patterns and utilities
   - Maintain all tests passing throughout

### Test Coverage

- **385 total tests** with **100% pass rate**
- **Unit tests**: 129 tests for server functionality
- **Integration tests**: 11 end-to-end workflow tests
- **Client tests**: 245 tests for Joplin API integration
- **Model tests**: Comprehensive validation testing
- **Configuration tests**: Environment and file-based config

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src/joplin_mcp --cov-report=html

# Run specific test categories
pytest tests/test_integration.py  # Integration tests
pytest tests/test_server.py       # Server unit tests
pytest tests/test_client.py       # Client tests

# Run tests with verbose output
pytest -v --tb=short
```

## 🔧 Development Setup

### Development Dependencies

```bash
# Install development dependencies
pip install -e ".[dev]"

# This includes:
# - pytest (testing framework)
# - pytest-asyncio (async test support)
# - pytest-mock (mocking utilities)
# - black (code formatting)
# - mypy (type checking)
# - ruff (linting)
# - coverage (test coverage)
```

### Code Quality Tools

```bash
# Format code with Black
black src/ tests/

# Type checking with MyPy
mypy src/joplin_mcp

# Linting with Ruff
ruff check src/ tests/

# Run all quality checks
black src/ tests/ && mypy src/joplin_mcp && ruff check src/ tests/
```

### Project Structure

```
joplin-mcp/
├── src/joplin_mcp/           # Main package
│   ├── __init__.py           # Package exports
│   ├── server.py             # MCP server implementation
│   ├── client.py             # Joplin API client wrapper
│   ├── models.py             # Pydantic data models
│   ├── config.py             # Configuration management
│   ├── exceptions.py         # Custom exceptions
│   └── py.typed              # Type checking marker
├── tests/                    # Test suite
│   ├── conftest.py           # Test fixtures
│   ├── test_server.py        # Server unit tests
│   ├── test_integration.py   # End-to-end tests
│   ├── test_client.py        # Client tests
│   ├── test_models.py        # Model validation tests
│   └── test_config.py        # Configuration tests
├── pyproject.toml            # Project configuration
├── requirements.txt          # Dependencies
└── README.md                 # This file
```

## 🔌 MCP Integration

### Using with Claude Desktop

1. **Install the MCP server** following the installation steps above

2. **Configure Claude Desktop** by adding to your MCP settings:

```json
{
  "mcpServers": {
    "joplin": {
      "command": "python",
      "args": ["-m", "joplin_mcp.server"],
      "env": {
        "JOPLIN_TOKEN": "your_api_token_here",
        "JOPLIN_HOST": "localhost",
        "JOPLIN_PORT": "41184"
      }
    }
  }
}
```

3. **Restart Claude Desktop** to load the MCP server

4. **Start using Joplin tools** in your conversations:
   - "Search my notes for meeting minutes from last week"
   - "Create a new note about project planning"
   - "Show me all my todo items"
   - "Organize my notes with tags"

### MCP Protocol Compliance

This server implements the full MCP specification:

- **Tools**: 13 comprehensive tools for note management
- **Resources**: Access to notebooks, tags, and server information
- **Prompts**: Helper prompts for search syntax and organization
- **Error Handling**: Proper MCP error responses and validation
- **Type Safety**: Full TypeScript-compatible type definitions

## 🛠️ Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JOPLIN_TOKEN` | *required* | Joplin API authentication token |
| `JOPLIN_HOST` | `localhost` | Joplin server hostname |
| `JOPLIN_PORT` | `41184` | Joplin Web Clipper port |
| `JOPLIN_TIMEOUT` | `30` | Request timeout in seconds |

### Configuration File

Create `joplin_config.json` in your project directory:

```json
{
  "joplin": {
    "token": "your_api_token",
    "host": "localhost",
    "port": 41184,
    "timeout": 30
  },
  "mcp": {
    "server_name": "joplin-mcp",
    "version": "0.1.0"
  }
}
```

### Programmatic Configuration

```python
from joplin_mcp import JoplinMCPConfig, JoplinMCPServer

# Create configuration
config = JoplinMCPConfig(
    token="your_token",
    host="localhost",
    port=41184,
    timeout=30
)

# Initialize server with config
server = JoplinMCPServer(config=config)
```

## 🔍 API Reference

### Search Notes

```python
await server.handle_search_notes({
    "query": str,              # Required: search query
    "limit": int,              # Optional: max results (1-100, default: 20)
    "notebook_id": str,        # Optional: filter by notebook
    "tags": List[str],         # Optional: filter by tags
    "sort_by": str,            # Optional: title|created_time|updated_time|relevance
    "sort_order": str          # Optional: asc|desc (default: desc)
})
```

### Create Note

```python
await server.handle_create_note({
    "title": str,              # Required: note title
    "parent_id": str,          # Required: notebook ID
    "body": str,               # Optional: note content
    "is_todo": bool,           # Optional: create as todo (default: False)
    "todo_completed": bool,    # Optional: todo status (default: False)
    "tags": List[str]          # Optional: list of tag names
})
```

### Update Note

```python
await server.handle_update_note({
    "note_id": str,            # Required: note to update
    "title": str,              # Optional: new title
    "body": str,               # Optional: new content
    "is_todo": bool,           # Optional: convert to/from todo
    "todo_completed": bool,    # Optional: update todo status
    "tags": List[str]          # Optional: replace tags
})
```

For complete API documentation, see the [API Documentation](docs/api.md).

## 🐛 Troubleshooting

### Common Issues

**Connection Failed**
```
Error: Failed to connect to Joplin server
```
- Ensure Joplin Desktop is running
- Check Web Clipper is enabled in Joplin settings
- Verify the port number (default: 41184)
- Confirm API token is correct

**Authentication Error**
```
Error: Invalid API token
```
- Generate a new API token in Joplin Web Clipper settings
- Ensure token is set in environment variables or config
- Check for extra spaces or characters in token

**Import Errors**
```
ModuleNotFoundError: No module named 'joplin_mcp'
```
- Install the package: `pip install -e .`
- Ensure you're in the correct virtual environment
- Check Python path includes the package

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

server = JoplinMCPServer(token="your_token")
```

### Health Check

Test your connection:

```python
# Test server connectivity
result = await server.handle_ping_joplin({})
print(result)  # Should show "connection successful"
```

## 🤝 Contributing

We welcome contributions! This project follows strict TDD practices:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Write failing tests first** (RED phase)
4. **Implement minimal code** to pass tests (GREEN phase)
5. **Refactor and optimize** while keeping tests green (REFACTOR phase)
6. **Ensure 100% test coverage**: `pytest --cov=src/joplin_mcp`
7. **Run quality checks**: `black . && mypy src/joplin_mcp && ruff check .`
8. **Commit changes**: `git commit -m 'Add amazing feature'`
9. **Push to branch**: `git push origin feature/amazing-feature`
10. **Open a Pull Request**

### Development Guidelines

- **Test-first development**: Always write tests before implementation
- **100% test coverage**: All code must be covered by tests
- **Type safety**: Use type hints and pass mypy checks
- **Code formatting**: Use Black for consistent formatting
- **Documentation**: Update README and docstrings for new features

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **[Joplin](https://joplinapp.org/)** - The excellent note-taking application
- **[Model Context Protocol](https://modelcontextprotocol.io/)** - The standardized AI integration protocol
- **[joppy](https://github.com/marph91/joppy)** - Python client library for Joplin API
- **TDD Community** - For promoting test-driven development practices

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-org/joplin-mcp/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/joplin-mcp/discussions)
- **Documentation**: [Project Wiki](https://github.com/your-org/joplin-mcp/wiki)

---

**Built with ❤️ using Test-Driven Development** 