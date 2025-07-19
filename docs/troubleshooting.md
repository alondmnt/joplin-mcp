# Joplin MCP Server Troubleshooting Guide

This guide helps you diagnose and resolve common issues when setting up and using the Joplin MCP Server.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Connection Issues](#connection-issues)
- [Authentication Problems](#authentication-problems)
- [Installation Issues](#installation-issues)
- [Configuration Problems](#configuration-problems)
- [Performance Issues](#performance-issues)
- [MCP Integration Issues](#mcp-integration-issues)
- [Development and Testing Issues](#development-and-testing-issues)
- [Advanced Troubleshooting](#advanced-troubleshooting)
- [Getting Help](#getting-help)

---

## Quick Diagnostics

### Health Check Script

Run this quick diagnostic to identify common issues:

```python
import asyncio
from joplin_mcp import JoplinMCPServer

async def diagnose():
    """Quick diagnostic script for Joplin MCP Server."""
    print("🔍 Joplin MCP Server Diagnostics\n")
    
    # Test 1: Check environment variables
    import os
    token = os.getenv('JOPLIN_TOKEN')
    host = os.getenv('JOPLIN_HOST', 'localhost')
    port = os.getenv('JOPLIN_PORT', '41184')
    
    print(f"📋 Configuration Check:")
    print(f"   Token: {'✅ Set' if token else '❌ Missing'}")
    print(f"   Host: {host}")
    print(f"   Port: {port}\n")
    
    if not token:
        print("❌ JOPLIN_TOKEN environment variable is not set!")
        print("   Please set your Joplin API token first.\n")
        return
    
    # Test 2: Try to create server
    try:
        server = JoplinMCPServer(token=token, host=host, port=int(port))
        print("✅ Server initialization successful\n")
    except Exception as e:
        print(f"❌ Server initialization failed: {e}\n")
        return
    
    # Test 3: Test connection
    try:
        result = await server.handle_ping_joplin({})
        if "successful" in result['content'][0]['text'].lower():
            print("✅ Joplin connection successful")
        else:
            print("❌ Joplin connection failed")
            print(f"   Response: {result['content'][0]['text']}")
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
    
    print("\n🎉 Diagnostics complete!")

if __name__ == "__main__":
    asyncio.run(diagnose())
```

### System Requirements Check

```bash
# Check Python version
python --version  # Should be 3.8+

# Check if Joplin is running
curl -s http://localhost:41184/ping || echo "Joplin not responding"

# Check if required packages are installed
python -c "import joplin_mcp; print('✅ joplin_mcp installed')" 2>/dev/null || echo "❌ joplin_mcp not installed"
```

---

## Connection Issues

### Issue: "Failed to connect to Joplin server"

**Symptoms:**
- Connection timeout errors
- "Connection refused" messages
- Server not responding

**Solutions:**

#### 1. Verify Joplin is Running
```bash
# Check if Joplin process is running
ps aux | grep -i joplin

# On macOS
ps aux | grep -i "Joplin"

# On Windows
tasklist | findstr "Joplin"
```

#### 2. Check Web Clipper Service
1. Open Joplin Desktop
2. Go to **Tools** → **Options** → **Web Clipper**
3. Ensure "Enable Web Clipper Service" is checked
4. Note the port number (default: 41184)
5. Click "Apply" and restart Joplin if needed

#### 3. Verify Port Accessibility
```bash
# Test if port is accessible
curl -s http://localhost:41184/ping

# Expected response: {"status":"ok"}
# If no response, the service isn't running
```

#### 4. Check Firewall Settings
- Ensure localhost connections are allowed
- Check if antivirus software is blocking the connection
- Try temporarily disabling firewall to test

#### 5. Alternative Port Configuration
If port 41184 is in use:

```python
# Try different port
server = JoplinMCPServer(
    token="your_token",
    host="localhost",
    port=41185  # Try different port
)
```

### Issue: "Connection timeout"

**Symptoms:**
- Requests hang indefinitely
- Timeout errors after 30 seconds

**Solutions:**

#### 1. Increase Timeout
```python
server = JoplinMCPServer(
    token="your_token",
    timeout=60  # Increase to 60 seconds
)
```

#### 2. Check Network Latency
```bash
# Test response time
time curl -s http://localhost:41184/ping
```

#### 3. Restart Joplin Service
1. Close Joplin completely
2. Wait 10 seconds
3. Restart Joplin
4. Wait for full startup (check system tray)
5. Test connection again

---

## Authentication Problems

### Issue: "Invalid API token"

**Symptoms:**
- 401 Unauthorized errors
- "Authentication failed" messages
- Token-related error responses

**Solutions:**

#### 1. Generate New API Token
1. Open Joplin Desktop
2. Go to **Tools** → **Options** → **Web Clipper**
3. Click "Copy token" or "Generate new token"
4. Update your environment variable:

```bash
export JOPLIN_TOKEN="your_new_token_here"
```

#### 2. Verify Token Format
- Tokens are typically 32-character hexadecimal strings
- Should not contain spaces or special characters
- Example: `a1b2c3d4e5f6789012345678901234567890abcd`

#### 3. Check Token in Code
```python
import os
token = os.getenv('JOPLIN_TOKEN')
print(f"Token length: {len(token) if token else 'None'}")
print(f"Token format: {token[:8]}..." if token else "No token")
```

#### 4. Test Token Manually
```bash
# Test token with curl
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:41184/ping
```

### Issue: "Token not found in environment"

**Solutions:**

#### 1. Set Environment Variable
```bash
# Linux/macOS
export JOPLIN_TOKEN="your_token_here"

# Windows Command Prompt
set JOPLIN_TOKEN=your_token_here

# Windows PowerShell
$env:JOPLIN_TOKEN="your_token_here"
```

#### 2. Use Configuration File
Create `joplin_config.json`:
```json
{
  "joplin": {
    "token": "your_token_here",
    "host": "localhost",
    "port": 41184
  }
}
```

#### 3. Pass Token Directly
```python
server = JoplinMCPServer(token="your_token_here")
```

---

## Installation Issues

### Issue: "ModuleNotFoundError: No module named 'joplin_mcp'"

**Solutions:**

#### 1. Install in Development Mode
```bash
cd joplin-mcp
pip install -e .
```

#### 2. Check Virtual Environment
```bash
# Verify you're in the correct environment
which python
pip list | grep joplin
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Python Path Issues
```python
import sys
sys.path.append('/path/to/joplin-mcp/src')
```

### Issue: "Permission denied" during installation

**Solutions:**

#### 1. Use Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows
pip install -e .
```

#### 2. User Installation
```bash
pip install --user -e .
```

#### 3. Check Permissions
```bash
ls -la /path/to/joplin-mcp
chmod +x setup.py
```

---

## Configuration Problems

### Issue: "Invalid configuration parameters"

**Symptoms:**
- "Invalid host parameter" errors
- "Invalid port parameter" errors
- Configuration validation failures

**Solutions:**

#### 1. Validate Configuration
```python
from joplin_mcp import JoplinMCPConfig

# Test configuration
try:
    config = JoplinMCPConfig(
        token="your_token",
        host="localhost",
        port=41184,
        timeout=30
    )
    print("✅ Configuration valid")
except Exception as e:
    print(f"❌ Configuration error: {e}")
```

#### 2. Check Parameter Types
```python
# Ensure correct types
config = {
    "token": str("your_token"),      # Must be string
    "host": str("localhost"),        # Must be string
    "port": int(41184),             # Must be integer
    "timeout": int(30)              # Must be integer
}
```

#### 3. Default Configuration
```python
# Use minimal configuration
server = JoplinMCPServer(token="your_token")
# Uses defaults: localhost:41184, 30s timeout
```

### Issue: "Configuration file not found"

**Solutions:**

#### 1. Create Configuration File
```bash
# Create in project directory
cat > joplin_config.json << EOF
{
  "joplin": {
    "token": "your_token_here",
    "host": "localhost",
    "port": 41184,
    "timeout": 30
  }
}
EOF
```

#### 2. Specify Configuration Path
```python
from joplin_mcp import JoplinMCPConfig

config = JoplinMCPConfig.from_file("/path/to/config.json")
server = JoplinMCPServer(config=config)
```

---

## Performance Issues

### Issue: "Slow response times"

**Symptoms:**
- Operations taking longer than expected
- Timeouts on large operations
- High memory usage

**Solutions:**

#### 1. Optimize Search Queries
```python
# Use smaller limits for better performance
results = await server.handle_find_notes({
    "query": "specific terms",
    "limit": 20,  # Instead of 100
    "notebook_id": "specific_notebook"  # Narrow scope
})
```

#### 2. Batch Operations Efficiently
```python
# Instead of many individual operations
for note_id in note_ids[:10]:  # Process in smaller batches
    await server.handle_get_note({"note_id": note_id})
    await asyncio.sleep(0.1)  # Small delay between requests
```

#### 3. Monitor Resource Usage
```python
import psutil
import time

# Monitor memory usage
process = psutil.Process()
print(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")
```

### Issue: "Memory leaks"

**Solutions:**

#### 1. Proper Resource Cleanup
```python
async with JoplinMCPServer(token="your_token") as server:
    # Server automatically cleaned up
    results = await server.handle_find_notes({"query": "test"})
```

#### 2. Clear Caches Periodically
```python
# If using custom caching
server.client._search_cache.clear()
```

---

## MCP Integration Issues

### Issue: "MCP server not recognized by Claude Desktop"

**Solutions:**

#### 1. Check MCP Configuration
Verify your Claude Desktop configuration:
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

#### 2. Verify Python Path
```bash
# Ensure Python is in PATH
which python
python -c "import joplin_mcp; print('OK')"
```

#### 3. Check Logs
Look for MCP server logs in Claude Desktop's log directory.

### Issue: "Tools not appearing in Claude"

**Solutions:**

#### 1. Restart Claude Desktop
- Completely quit Claude Desktop
- Wait 10 seconds
- Restart application

#### 2. Verify Server Capabilities
```python
server = JoplinMCPServer(token="your_token")
tools = server.get_available_tools()
print(f"Available tools: {len(tools)}")
for tool in tools:
    print(f"- {tool.name}: {tool.description}")
```

#### 3. Check MCP Protocol Version
Ensure compatibility between MCP server and Claude Desktop versions.

---

## Development and Testing Issues

### Issue: "Tests failing"

**Solutions:**

#### 1. Run Specific Test Categories
```bash
# Run only unit tests
pytest tests/test_server.py -v

# Run only integration tests
pytest tests/test_integration.py -v

# Skip slow tests
pytest -m "not slow"
```

#### 2. Check Test Environment
```bash
# Ensure test dependencies are installed
pip install -e ".[dev]"

# Check test configuration
pytest --collect-only
```

#### 3. Mock Joplin for Testing
```python
# Use mock client for testing
from unittest.mock import Mock

mock_client = Mock()
mock_client.ping.return_value = True
server = JoplinMCPServer(client=mock_client)
```

### Issue: "Type checking errors"

**Solutions:**

#### 1. Run MyPy
```bash
mypy src/joplin_mcp --show-error-codes
```

#### 2. Fix Common Type Issues
```python
# Use proper type annotations
from typing import Optional, List, Dict, Any

def my_function(param: Optional[str] = None) -> Dict[str, Any]:
    return {"result": param or "default"}
```

#### 3. Update Type Configuration
Check `pyproject.toml` for MyPy configuration.

---

## Advanced Troubleshooting

### Debug Mode

Enable detailed logging:

```python
import logging

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create server with debug info
server = JoplinMCPServer(token="your_token")
```

### Network Debugging

```bash
# Monitor network traffic
sudo tcpdump -i lo port 41184

# Check open ports
netstat -an | grep 41184
lsof -i :41184
```

### Joplin Database Issues

If Joplin data seems corrupted:

1. **Backup your data** first!
2. Go to Joplin → Help → Open Profile Directory
3. Close Joplin
4. Rename `database.sqlite` to `database.sqlite.backup`
5. Restart Joplin (will rebuild database)
6. Re-sync if using cloud sync

### Environment Isolation

Create isolated test environment:

```bash
# Create clean environment
python -m venv test_env
source test_env/bin/activate

# Install only required packages
pip install -e .

# Test basic functionality
python -c "from joplin_mcp import JoplinMCPServer; print('OK')"
```

---

## Getting Help

### Before Asking for Help

1. **Run the diagnostic script** from the Quick Diagnostics section
2. **Check the logs** for specific error messages
3. **Try the solutions** in this troubleshooting guide
4. **Test with minimal configuration** to isolate the issue

### Information to Include

When reporting issues, please include:

```bash
# System information
python --version
pip list | grep -E "(joplin|mcp)"
uname -a  # Linux/macOS
systeminfo  # Windows

# Configuration (remove sensitive tokens)
echo "Host: $JOPLIN_HOST"
echo "Port: $JOPLIN_PORT"
echo "Token: ${JOPLIN_TOKEN:0:8}..."

# Error messages
# Include full error traceback
```

### Where to Get Help

1. **GitHub Issues**: [Report bugs and feature requests](https://github.com/your-org/joplin-mcp/issues)
2. **GitHub Discussions**: [Ask questions and share ideas](https://github.com/your-org/joplin-mcp/discussions)
3. **Documentation**: [Check the wiki](https://github.com/your-org/joplin-mcp/wiki)
4. **Joplin Community**: [Joplin Forum](https://discourse.joplinapp.org/)

### Creating a Minimal Reproduction

```python
"""
Minimal reproduction script for bug reports.
Replace with your specific issue.
"""
import asyncio
from joplin_mcp import JoplinMCPServer

async def reproduce_issue():
    # Minimal code that demonstrates the problem
    server = JoplinMCPServer(token="your_token")
    
    try:
        # Your problematic operation here
        result = await server.handle_ping_joplin({})
        print("Success:", result)
    except Exception as e:
        print("Error:", e)
        raise

if __name__ == "__main__":
    asyncio.run(reproduce_issue())
```

---

## Common Error Messages and Solutions

| Error Message | Likely Cause | Solution |
|---------------|--------------|----------|
| `Connection refused` | Joplin not running | Start Joplin Desktop |
| `Invalid API token` | Wrong/expired token | Generate new token |
| `Module not found` | Package not installed | Run `pip install -e .` |
| `Permission denied` | File permissions | Use virtual environment |
| `Port already in use` | Port conflict | Change port or kill process |
| `Timeout error` | Network/performance issue | Increase timeout, check network |
| `JSON decode error` | Malformed response | Check Joplin version compatibility |
| `SSL certificate error` | HTTPS/certificate issue | Use HTTP or update certificates |

---

*This troubleshooting guide is regularly updated based on user feedback and common issues. If you encounter a problem not covered here, please [open an issue](https://github.com/your-org/joplin-mcp/issues) to help improve this guide.* 