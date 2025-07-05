# FastMCP Migration Tasks - TDD Approach

## 🎯 Migration Overview
**Goal**: Migrate Joplin MCP Server from 3,144 lines of custom implementation to ~300 lines using FastMCP framework while maintaining 100% functionality.

**Approach**: Test-Driven Development (TDD) with incremental migration
**Timeline**: 4-6 weeks
**Success Criteria**: 
- All existing functionality preserved
- 90% code reduction achieved
- Comprehensive test coverage (>95%)
- Performance maintained or improved

---

## 📋 Phase 1: Foundation & Core Infrastructure (Week 1)

### Task 1.1: Test Environment Setup
**Priority**: Critical
**Estimated Time**: 1 day

**TDD Steps**:
1. **Red**: Write test that fails because FastMCP isn't installed
2. **Green**: Install FastMCP and create minimal server
3. **Refactor**: Setup proper test configuration

**Acceptance Criteria**:
- [ ] FastMCP installed and importable
- [ ] Test environment can run both old and new servers
- [ ] Mock Joplin client available for testing
- [ ] Basic FastMCP server starts without errors

**Test Files**:
- `tests/test_fastmcp_setup.py`
- `tests/conftest_fastmcp.py`

### Task 1.2: Client Integration Tests
**Priority**: Critical
**Estimated Time**: 2 days

**TDD Steps**:
1. **Red**: Write test for JoplinMCPClient integration with FastMCP Context
2. **Green**: Implement middleware to inject client into context
3. **Refactor**: Optimize client lifecycle management

**Acceptance Criteria**:
- [ ] JoplinMCPClient accessible via FastMCP Context
- [ ] Client connection lifecycle managed properly
- [ ] Rate limiting preserved
- [ ] Connection pooling if needed

**Test Files**:
- `tests/test_client_integration.py`

**Implementation**:
```python
# tests/test_client_integration.py
import pytest
from fastmcp import FastMCP, Context
from joplin_mcp.client import JoplinMCPClient

@pytest.fixture
def fastmcp_server():
    mcp = FastMCP("Test Joplin Server")
    
    @mcp.middleware()
    async def inject_client(ctx: Context, call_next):
        ctx.client = JoplinMCPClient(host="localhost", port=41184, token="test")
        return await call_next()
    
    return mcp

def test_client_injection(fastmcp_server):
    # Test that client is properly injected into context
    pass
```

### Task 1.3: Response Format Compatibility Tests
**Priority**: High
**Estimated Time**: 1 day

**TDD Steps**:
1. **Red**: Write tests comparing old vs new response formats
2. **Green**: Implement response formatters to match existing format
3. **Refactor**: Create reusable formatting utilities

**Acceptance Criteria**:
- [ ] Response formats match existing implementation exactly
- [ ] Error messages maintain same structure
- [ ] Success responses identical to current format

**Test Files**:
- `tests/test_response_formats.py`

---

## 📋 Phase 2: Core Tools Migration (Week 2)

### Task 2.1: Ping Tool - TDD Implementation
**Priority**: High
**Estimated Time**: 0.5 days

**TDD Steps**:
1. **Red**: Write test for ping functionality
2. **Green**: Implement FastMCP ping tool
3. **Refactor**: Ensure error handling matches original

**Acceptance Criteria**:
- [ ] Ping returns same response format as original
- [ ] Connection errors handled identically
- [ ] Performance equals or exceeds original

**Test Files**:
- `tests/test_tools/test_ping.py`

**Implementation**:
```python
# tests/test_tools/test_ping.py
import pytest
from fastmcp import Client

@pytest.mark.asyncio
async def test_ping_success(fastmcp_server, mock_joplin_client):
    """Test successful ping returns expected format."""
    mock_joplin_client.ping.return_value = True
    
    async with Client(fastmcp_server) as client:
        result = await client.call_tool("ping_joplin")
        assert "✅ Joplin server connection successful" in result.text
        assert "The Joplin server is responding and accessible" in result.text

@pytest.mark.asyncio
async def test_ping_failure(fastmcp_server, mock_joplin_client):
    """Test failed ping returns expected error format."""
    mock_joplin_client.ping.return_value = False
    
    async with Client(fastmcp_server) as client:
        result = await client.call_tool("ping_joplin")
        assert "❌ Joplin server connection failed" in result.text
```

### Task 2.2: Get Note Tool - TDD Implementation
**Priority**: High
**Estimated Time**: 1 day

**TDD Steps**:
1. **Red**: Write comprehensive tests for get_note functionality
2. **Green**: Implement FastMCP get_note tool
3. **Refactor**: Optimize parameter validation and formatting

**Acceptance Criteria**:
- [ ] Parameter validation matches original (note_id required, include_body optional)
- [ ] Response format identical to original
- [ ] Error handling for invalid note IDs
- [ ] Timestamp formatting preserved

**Test Files**:
- `tests/test_tools/test_get_note.py`

### Task 2.3: Create Note Tool - TDD Implementation
**Priority**: High
**Estimated Time**: 1.5 days

**TDD Steps**:
1. **Red**: Write tests for all create_note scenarios
2. **Green**: Implement FastMCP create_note tool with validation
3. **Refactor**: Handle parameter aliases and intelligent defaults

**Acceptance Criteria**:
- [ ] Required parameters enforced (title, parent_id)
- [ ] Optional parameters handled (body, is_todo, todo_completed, tags)
- [ ] Parameter aliases work (notebook_name → parent_id lookup)
- [ ] Intelligent defaults for missing parent_id
- [ ] Response format matches original exactly

**Test Files**:
- `tests/test_tools/test_create_note.py`

**Implementation**:
```python
# tests/test_tools/test_create_note.py
import pytest
from fastmcp import Client

@pytest.mark.asyncio
async def test_create_note_minimal(fastmcp_server, mock_joplin_client):
    """Test creating note with minimal parameters."""
    mock_joplin_client.create_note.return_value = "test_note_id_123"
    
    async with Client(fastmcp_server) as client:
        result = await client.call_tool("create_note", {
            "title": "Test Note",
            "parent_id": "test_notebook_id"
        })
        
        assert "✅ Successfully created note" in result.text
        assert "📝 CREATED NOTE ID: test_note_id_123 📝" in result.text
        assert "Test Note" in result.text

@pytest.mark.asyncio  
async def test_create_note_with_notebook_name(fastmcp_server, mock_joplin_client):
    """Test creating note using notebook_name instead of parent_id."""
    mock_notebook = type('MockNotebook', (), {
        'id': 'resolved_notebook_id',
        'title': 'Test Notebook'
    })()
    mock_joplin_client.get_all_notebooks.return_value = [mock_notebook]
    mock_joplin_client.create_note.return_value = "test_note_id_456"
    
    async with Client(fastmcp_server) as client:
        result = await client.call_tool("create_note", {
            "title": "Test Note",
            "notebook_name": "Test Notebook"
        })
        
        assert "✅ Successfully created note" in result.text
        mock_joplin_client.create_note.assert_called_with(
            title="Test Note",
            parent_id="resolved_notebook_id",
            body="",
            is_todo=False,
            todo_completed=False,
            tags=None
        )
```

### Task 2.4: Search Notes Tool - TDD Implementation
**Priority**: Critical
**Estimated Time**: 2 days

**TDD Steps**:
1. **Red**: Write comprehensive tests for search functionality
2. **Green**: Implement FastMCP search_notes with all parameters
3. **Refactor**: Optimize tag resolution and result formatting

**Acceptance Criteria**:
- [ ] All search parameters supported (query, limit, notebook_id, tags, sort_by, sort_order)
- [ ] Parameter validation (limit 1-100, valid sort options)
- [ ] Tag name to ID resolution
- [ ] Result formatting matches original exactly
- [ ] Empty results handled properly

**Test Files**:
- `tests/test_tools/test_search_notes.py`

---

## 📋 Phase 3: CRUD Operations Migration (Week 3)

### Task 3.1: Note CRUD Operations - TDD Implementation
**Priority**: High
**Estimated Time**: 2 days

**Tools to implement**:
- `update_note`
- `delete_note`

**TDD Steps**:
1. **Red**: Write tests for each CRUD operation
2. **Green**: Implement FastMCP tools with proper validation
3. **Refactor**: Ensure error handling and response formats match

**Acceptance Criteria**:
- [ ] Update note handles partial updates correctly
- [ ] Delete note returns proper confirmation
- [ ] Invalid IDs handled with appropriate errors
- [ ] Response formats match original

**Test Files**:
- `tests/test_tools/test_note_crud.py`

### Task 3.2: Notebook CRUD Operations - TDD Implementation
**Priority**: High
**Estimated Time**: 2 days

**Tools to implement**:
- `list_notebooks`
- `get_notebook`
- `create_notebook`
- `update_notebook`
- `delete_notebook`
- `search_notebooks`
- `get_notes_by_notebook`

**TDD Steps**:
1. **Red**: Write comprehensive tests for all notebook operations
2. **Green**: Implement FastMCP tools with proper validation
3. **Refactor**: Optimize listing and search functionality

**Acceptance Criteria**:
- [ ] All notebook operations preserve existing functionality
- [ ] Parameter validation matches original
- [ ] Response formats identical
- [ ] Error handling consistent

**Test Files**:
- `tests/test_tools/test_notebook_crud.py`

### Task 3.3: Tag CRUD Operations - TDD Implementation
**Priority**: High
**Estimated Time**: 2 days

**Tools to implement**:
- `list_tags`
- `get_tag`
- `create_tag`
- `update_tag`
- `delete_tag`
- `search_tags`
- `get_tags_by_note`
- `get_notes_by_tag`
- `tag_note`
- `untag_note`

**TDD Steps**:
1. **Red**: Write tests for all tag operations
2. **Green**: Implement FastMCP tools with tag resolution
3. **Refactor**: Optimize tag name to ID resolution

**Acceptance Criteria**:
- [ ] Tag name to ID resolution works correctly
- [ ] All tag operations preserve existing functionality
- [ ] Note-tag relationships handled properly
- [ ] Response formats match original

**Test Files**:
- `tests/test_tools/test_tag_crud.py`

---

## 📋 Phase 4: Advanced Features & Optimization (Week 4)

### Task 4.1: Error Handling & Validation - TDD Implementation
**Priority**: High
**Estimated Time**: 1.5 days

**TDD Steps**:
1. **Red**: Write tests for all error scenarios
2. **Green**: Implement comprehensive error handling
3. **Refactor**: Create reusable error handling utilities

**Acceptance Criteria**:
- [ ] Parameter validation errors match original format
- [ ] Helpful error messages with correction hints
- [ ] Rate limiting preserved
- [ ] Security validation maintained

**Test Files**:
- `tests/test_error_handling.py`

### Task 4.2: Performance & Security - TDD Implementation
**Priority**: High
**Estimated Time**: 1 day

**TDD Steps**:
1. **Red**: Write performance and security tests
2. **Green**: Implement rate limiting and input validation
3. **Refactor**: Optimize performance bottlenecks

**Acceptance Criteria**:
- [ ] Rate limiting works correctly
- [ ] Input sanitization preserved
- [ ] Performance equals or exceeds original
- [ ] Security features maintained

**Test Files**:
- `tests/test_performance.py`
- `tests/test_security.py`

### Task 4.3: Resources & Prompts - TDD Implementation
**Priority**: Medium
**Estimated Time**: 1 day

**TDD Steps**:
1. **Red**: Write tests for resources and prompts
2. **Green**: Implement FastMCP resources and prompts
3. **Refactor**: Optimize resource loading

**Acceptance Criteria**:
- [ ] All resources available and functional
- [ ] Prompts provide helpful templates
- [ ] Resource URIs match original specification

**Test Files**:
- `tests/test_resources.py`
- `tests/test_prompts.py`

---

## 📋 Phase 5: Integration & Production Readiness (Week 5-6)

### Task 5.1: Integration Testing - TDD Implementation
**Priority**: Critical
**Estimated Time**: 2 days

**TDD Steps**:
1. **Red**: Write comprehensive integration tests
2. **Green**: Ensure all components work together
3. **Refactor**: Optimize integration points

**Acceptance Criteria**:
- [ ] All tools work together seamlessly
- [ ] Real Joplin instance testing passes
- [ ] Performance meets requirements
- [ ] Memory usage optimized

**Test Files**:
- `tests/test_integration_full.py`

### Task 5.2: Backward Compatibility Testing
**Priority**: High
**Estimated Time**: 1 day

**TDD Steps**:
1. **Red**: Write tests comparing old vs new server responses
2. **Green**: Ensure 100% API compatibility
3. **Refactor**: Fix any compatibility issues

**Acceptance Criteria**:
- [ ] All existing clients work without changes
- [ ] Response formats identical
- [ ] Error messages preserved
- [ ] Performance comparable or better

**Test Files**:
- `tests/test_backward_compatibility.py`

### Task 5.3: Configuration & Deployment
**Priority**: Medium
**Estimated Time**: 1 day

**TDD Steps**:
1. **Red**: Write tests for configuration loading
2. **Green**: Implement FastMCP configuration
3. **Refactor**: Optimize configuration management

**Acceptance Criteria**:
- [ ] All configuration options preserved
- [ ] FastMCP deployment options work
- [ ] Documentation updated
- [ ] Migration guide created

**Test Files**:
- `tests/test_configuration.py`

---

## 📋 Phase 6: Cleanup & Documentation (Week 6)

### Task 6.1: Code Cleanup & Documentation
**Priority**: Medium
**Estimated Time**: 1 day

**Acceptance Criteria**:
- [ ] Old implementation removed
- [ ] Code properly documented
- [ ] Type hints comprehensive
- [ ] API documentation updated

### Task 6.2: Final Testing & Validation
**Priority**: Critical
**Estimated Time**: 1 day

**Acceptance Criteria**:
- [ ] All tests pass with >95% coverage
- [ ] Performance benchmarks met
- [ ] Security validation complete
- [ ] Production deployment successful

---

## 🧪 Testing Strategy

### Test Structure
```
tests/
├── conftest.py                    # Shared fixtures
├── conftest_fastmcp.py           # FastMCP-specific fixtures
├── test_fastmcp_setup.py         # Basic setup tests
├── test_client_integration.py    # Client integration tests
├── test_response_formats.py      # Response format compatibility
├── test_tools/                   # Tool-specific tests
│   ├── test_ping.py
│   ├── test_get_note.py
│   ├── test_create_note.py
│   ├── test_search_notes.py
│   ├── test_note_crud.py
│   ├── test_notebook_crud.py
│   └── test_tag_crud.py
├── test_error_handling.py        # Error scenarios
├── test_performance.py           # Performance tests
├── test_security.py              # Security tests
├── test_resources.py             # Resource tests
├── test_prompts.py               # Prompt tests
├── test_integration_full.py      # Full integration tests
├── test_backward_compatibility.py # Compatibility tests
└── test_configuration.py         # Configuration tests
```

### Key Testing Principles
1. **Test First**: Write failing tests before implementation
2. **Comprehensive Coverage**: Test all edge cases and error conditions
3. **Regression Prevention**: Ensure new implementation matches old behavior exactly
4. **Performance Validation**: Verify performance meets or exceeds current implementation
5. **Security Validation**: Ensure all security features preserved

### Mock Strategy
- Mock JoplinMCPClient for unit tests
- Use real Joplin instance for integration tests
- Mock external dependencies (network, file system)
- Parameterized tests for comprehensive coverage

---

## 🎯 Success Metrics

### Code Quality
- [ ] 90%+ code reduction (3,144 lines → ~300 lines)
- [ ] 95%+ test coverage
- [ ] Zero security regressions
- [ ] Type safety throughout

### Performance
- [ ] Response time ≤ current implementation
- [ ] Memory usage ≤ current implementation
- [ ] Startup time ≤ current implementation

### Functionality
- [ ] 100% API compatibility
- [ ] All existing tools preserved
- [ ] Error handling equivalent
- [ ] Configuration options preserved

### Development Experience
- [ ] Code maintainability improved
- [ ] Documentation comprehensive
- [ ] Development setup simplified
- [ ] Testing framework robust

---

## 📚 Resources & References

### Documentation
- [FastMCP Documentation](https://gofastmcp.com)
- [Current Joplin MCP Server Code](./src/joplin_mcp/server.py)
- [Joplin API Documentation](https://joplinapp.org/api/references/rest_api/)

### Example FastMCP Servers
- [Weather Service Example](https://github.com/jlowin/fastmcp/tree/main/examples)
- [FastMCP Best Practices](https://gofastmcp.com/patterns/)

### Testing Resources
- [FastMCP Testing Guide](https://gofastmcp.com/testing/)
- [MCP Testing Best Practices](https://modelcontextprotocol.io/docs/testing/)

---

## 🔧 Development Commands

### Setup
```bash
# Install FastMCP
pip install fastmcp

# Install development dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest tests/ -v --cov=src --cov-report=html
```

### TDD Workflow
```bash
# Run specific test file
pytest tests/test_tools/test_ping.py -v

# Run with coverage
pytest tests/test_tools/test_ping.py --cov=src/joplin_mcp --cov-report=term-missing

# Run in watch mode (with pytest-watch)
ptw tests/test_tools/test_ping.py
```

### Performance Testing
```bash
# Run performance tests
pytest tests/test_performance.py -v

# Profile performance
python -m cProfile -o profile.prof run_mcp_server.py
```

---

This comprehensive TDD-based migration plan ensures a systematic, test-driven approach to converting your Joplin MCP server to FastMCP while maintaining 100% functionality and achieving significant code reduction. 