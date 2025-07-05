# FastMCP Joplin Server - Clean Rewrite Strategy

## 🎯 Strategy Overview
**Approach**: Build a new FastMCP server from scratch using direct joppy integration
**Goal**: Create a ~150-200 line implementation that replaces the current 3,144-line server
**Timeline**: 1-2 weeks instead of 4-6 weeks
**Key Principle**: Minimal abstraction layers, maximum FastMCP leverage

---

## 🏗️ Architecture Design

### Clean Architecture
```
┌─────────────────┐
│   MCP Client    │ (Claude, etc.)
├─────────────────┤
│    FastMCP      │ (Handles MCP protocol, validation, schemas)
├─────────────────┤
│ Thin Wrappers   │ (5-10 lines per tool, formatting only)
├─────────────────┤
│     joppy       │ (Direct Joplin API calls)
├─────────────────┤
│  Joplin API     │ (REST API)
└─────────────────┘
```

### Benefits
- **95% less code** (3,144 → ~150 lines)
- **No migration complexity**
- **Modern FastMCP patterns from day 1**
- **Direct joppy integration**
- **Built-in FastMCP features (auth, validation, etc.)**

---

## 📁 Project Structure

```
src/
├── joplin_fastmcp/
│   ├── __init__.py
│   ├── server.py           # Main FastMCP server (~150 lines)
│   ├── formatters.py       # Response formatting utilities (~50 lines)
│   └── config.py           # Configuration handling (~20 lines)
├── tests/
│   ├── test_server.py      # Comprehensive server tests
│   ├── test_tools.py       # Tool-specific tests
│   └── conftest.py         # Test fixtures
└── examples/
    ├── basic_usage.py
    └── claude_desktop_config.json
```

---

## 🛠️ Implementation Plan

### Phase 1: Core Setup (Day 1)
**Goal**: Get basic FastMCP server running with joppy

#### Task 1.1: Basic Server Setup
```python
# src/joplin_fastmcp/server.py
from fastmcp import FastMCP, Context
import joppy
from typing import Optional, List
import os

# Initialize FastMCP server
mcp = FastMCP("Joplin MCP Server")

# Initialize joppy client
def get_joplin_client():
    return joppy.Api(
        token=os.getenv("JOPLIN_TOKEN", "your-default-token"),
        url=os.getenv("JOPLIN_URL", "http://localhost:41184")
    )

@mcp.tool()
async def ping_joplin() -> str:
    """Test connection to Joplin server."""
    try:
        client = get_joplin_client()
        # Simple ping - try to get version or make basic request
        client.ping()  # or whatever joppy provides
        return "✅ Joplin server connection successful"
    except Exception as e:
        return f"❌ Joplin server connection failed: {str(e)}"

if __name__ == "__main__":
    mcp.run()
```

#### Task 1.2: Test Framework
```python
# tests/test_server.py
import pytest
from fastmcp import Client
from joplin_fastmcp.server import mcp

@pytest.mark.asyncio
async def test_ping_success():
    async with Client(mcp) as client:
        result = await client.call_tool("ping_joplin")
        assert "✅" in result.text
```

### Phase 2: Core Tools (Day 2-3)
**Goal**: Implement essential CRUD operations

#### Task 2.1: Note Operations
```python
@mcp.tool()
async def get_note(note_id: str, include_body: bool = True) -> str:
    """Get a specific note by ID."""
    client = get_joplin_client()
    try:
        note = client.get_note(note_id, fields="id,title,body,created_time,updated_time,parent_id" if include_body else "id,title,created_time,updated_time,parent_id")
        return format_note_details(note, include_body)
    except Exception as e:
        raise ValueError(f"Failed to get note {note_id}: {str(e)}")

@mcp.tool()
async def create_note(title: str, parent_id: str, body: str = "", is_todo: bool = False) -> str:
    """Create a new note in Joplin."""
    client = get_joplin_client()
    try:
        note = client.create_note(
            title=title,
            body=body,
            parent_id=parent_id,
            is_todo=1 if is_todo else 0
        )
        return f"✅ Successfully created note: {title}\n📝 Note ID: {note.id}"
    except Exception as e:
        raise ValueError(f"Failed to create note: {str(e)}")

@mcp.tool()
async def search_notes(query: str, limit: int = 20, notebook_id: Optional[str] = None) -> str:
    """Search notes with full-text query."""
    if not (1 <= limit <= 100):
        raise ValueError("Limit must be between 1 and 100")
    
    client = get_joplin_client()
    try:
        # Use joppy's search functionality
        results = client.search(query, type_="note", limit=limit)
        
        if notebook_id:
            # Filter by notebook if specified
            results = [r for r in results if r.parent_id == notebook_id]
        
        if not results:
            return f'No notes found for query: "{query}"'
        
        return format_search_results(query, results[:limit])
    except Exception as e:
        raise ValueError(f"Search failed: {str(e)}")
```

#### Task 2.2: Notebook Operations
```python
@mcp.tool()
async def list_notebooks() -> str:
    """List all notebooks."""
    client = get_joplin_client()
    try:
        notebooks = client.get_folders()  # joppy calls them folders
        return format_notebooks_list(notebooks)
    except Exception as e:
        raise ValueError(f"Failed to list notebooks: {str(e)}")

@mcp.tool()
async def create_notebook(title: str, parent_id: Optional[str] = None) -> str:
    """Create a new notebook."""
    client = get_joplin_client()
    try:
        notebook = client.create_folder(title=title, parent_id=parent_id)
        return f"✅ Successfully created notebook: {title}\n📁 Notebook ID: {notebook.id}"
    except Exception as e:
        raise ValueError(f"Failed to create notebook: {str(e)}")
```

#### Task 2.3: Tag Operations
```python
@mcp.tool()
async def list_tags() -> str:
    """List all tags."""
    client = get_joplin_client()
    try:
        tags = client.get_tags()
        return format_tags_list(tags)
    except Exception as e:
        raise ValueError(f"Failed to list tags: {str(e)}")

@mcp.tool()
async def tag_note(note_id: str, tag_id: str) -> str:
    """Add a tag to a note."""
    client = get_joplin_client()
    try:
        client.add_tag_to_note(tag_id, note_id)
        return f"✅ Successfully tagged note {note_id} with tag {tag_id}"
    except Exception as e:
        raise ValueError(f"Failed to tag note: {str(e)}")
```

### Phase 3: Formatting & Polish (Day 4-5)
**Goal**: Match existing response formats and add remaining tools

#### Task 3.1: Response Formatters
```python
# src/joplin_fastmcp/formatters.py
from typing import List, Any
import datetime

def format_note_details(note: Any, include_body: bool = True) -> str:
    """Format a note for display."""
    title = note.title or "Untitled"
    note_id = note.id
    
    result_parts = [f"**{title}**", f"ID: {note_id}", ""]
    
    if include_body and hasattr(note, 'body') and note.body:
        result_parts.extend(["**Content:**", note.body, ""])
    
    # Add metadata
    metadata = []
    if hasattr(note, 'created_time') and note.created_time:
        created_date = datetime.datetime.fromtimestamp(note.created_time / 1000).strftime("%Y-%m-%d %H:%M")
        metadata.append(f"Created: {created_date}")
    
    if hasattr(note, 'parent_id') and note.parent_id:
        metadata.append(f"Notebook: {note.parent_id}")
    
    if metadata:
        result_parts.append("**Metadata:**")
        result_parts.extend(f"- {m}" for m in metadata)
    
    return "\n".join(result_parts)

def format_search_results(query: str, results: List[Any]) -> str:
    """Format search results for display."""
    count = len(results)
    result_parts = [f'Found {count} note(s) for query: "{query}"', ""]
    
    for note in results:
        title = note.title or "Untitled"
        note_id = note.id
        
        # Truncate body for search results
        body = ""
        if hasattr(note, 'body') and note.body:
            body = note.body[:200] + "..." if len(note.body) > 200 else note.body
        
        result_parts.append(f"**{title}** (ID: {note_id})")
        if body:
            result_parts.append(body)
        result_parts.append("")
    
    return "\n".join(result_parts)

def format_notebooks_list(notebooks: List[Any]) -> str:
    """Format notebooks list for display."""
    if not notebooks:
        return "📁 No notebooks found"
    
    count = len(notebooks)
    result_parts = [f"📁 Found {count} notebook{'s' if count != 1 else ''}", ""]
    
    for i, notebook in enumerate(notebooks, 1):
        title = notebook.title or "Untitled"
        notebook_id = notebook.id
        result_parts.append(f"**{i}. {title}**")
        result_parts.append(f"   ID: {notebook_id}")
        result_parts.append("")
    
    return "\n".join(result_parts)
```

#### Task 3.2: Complete Tool Set
Add remaining tools following the same pattern:
- `update_note`
- `delete_note`
- `get_notebook`
- `update_notebook`
- `delete_notebook`
- `search_notebooks`
- `create_tag`
- `update_tag`
- `delete_tag`
- etc.

### Phase 4: Configuration & Resources (Day 6-7)
**Goal**: Add configuration support and MCP resources

#### Task 4.1: Configuration
```python
# src/joplin_fastmcp/config.py
from dataclasses import dataclass
from typing import Optional
import os

@dataclass
class JoplinConfig:
    token: str
    url: str = "http://localhost:41184"
    timeout: int = 30
    
    @classmethod
    def from_env(cls) -> "JoplinConfig":
        token = os.getenv("JOPLIN_TOKEN")
        if not token:
            raise ValueError("JOPLIN_TOKEN environment variable is required")
        
        return cls(
            token=token,
            url=os.getenv("JOPLIN_URL", "http://localhost:41184"),
            timeout=int(os.getenv("JOPLIN_TIMEOUT", "30"))
        )
```

#### Task 4.2: Resources
```python
@mcp.resource("joplin://server_info")
async def get_server_info() -> dict:
    """Get Joplin server information."""
    client = get_joplin_client()
    try:
        # Get basic server info
        return {
            "url": client.url,
            "connected": True,
            "version": "1.0.0"  # Or get from joppy if available
        }
    except Exception:
        return {"connected": False}

@mcp.resource("joplin://notebooks")
async def get_notebooks_resource() -> str:
    """Get all notebooks as a resource."""
    return await list_notebooks()
```

---

## 🧪 Testing Strategy

### Simple Test Structure
```python
# tests/test_tools.py
import pytest
from fastmcp import Client
from joplin_fastmcp.server import mcp

@pytest.mark.asyncio
async def test_create_and_get_note():
    """Test creating a note and retrieving it."""
    async with Client(mcp) as client:
        # Create a notebook first
        notebook_result = await client.call_tool("create_notebook", {"title": "Test Notebook"})
        notebook_id = extract_id_from_response(notebook_result.text)
        
        # Create a note
        note_result = await client.call_tool("create_note", {
            "title": "Test Note",
            "parent_id": notebook_id,
            "body": "Test content"
        })
        note_id = extract_id_from_response(note_result.text)
        
        # Get the note
        get_result = await client.call_tool("get_note", {"note_id": note_id})
        assert "Test Note" in get_result.text
        assert "Test content" in get_result.text

def extract_id_from_response(response: str) -> str:
    """Extract ID from create response."""
    # Simple regex or string parsing to get ID
    import re
    match = re.search(r'ID: ([a-f0-9]+)', response)
    return match.group(1) if match else None
```

---

## ✅ Advantages of This Approach

### 1. **Simplicity**
- **No complex migration** - start fresh
- **Direct joppy integration** - minimal abstraction
- **FastMCP handles complexity** - schemas, validation, protocol

### 2. **Maintainability**
- **~150 lines vs 3,144 lines** - 95% code reduction
- **Modern patterns** - type hints, async/await
- **Clear separation** - tools, formatters, config

### 3. **Development Speed**
- **1-2 weeks vs 4-6 weeks** - much faster delivery
- **No legacy baggage** - clean implementation
- **Easier testing** - fewer moving parts

### 4. **Future-Proof**
- **Built on FastMCP** - gets all future improvements
- **Modular design** - easy to extend
- **Standard patterns** - follows FastMCP best practices

---

## 🚀 Getting Started

### Step 1: Install Dependencies
```bash
pip install fastmcp joppy python-dotenv
```

### Step 2: Create Basic Server
```bash
mkdir joplin-fastmcp-server
cd joplin-fastmcp-server
# Copy the basic server.py implementation above
```

### Step 3: Test with Simple Tool
```bash
export JOPLIN_TOKEN="your-token"
python server.py
```

### Step 4: Add Tools Incrementally
Follow the day-by-day plan above, adding tools one at a time with tests.

---

This rewrite strategy is much more pragmatic and will result in a cleaner, more maintainable codebase with significantly less development time. 