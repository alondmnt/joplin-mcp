#!/usr/bin/env python3
"""Installation script for Joplin MCP Server.

This script helps users set up the Joplin MCP server by:
1. Prompting for their Joplin API token
2. Creating/updating the joplin-mcp.json configuration file
3. Finding and updating the Claude Desktop configuration file
4. Providing helpful instructions
"""

import json
import os
import sys
import shutil
from pathlib import Path
from typing import Optional, Dict, Any

# Import UI functions from centralized module
from src.joplin_mcp.ui_integration import run_installation_process, print_step, print_success

def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent

def create_joplin_config(token: str) -> Path:
    """Create or update the joplin-mcp.json configuration file."""
    print_step("Creating Joplin MCP Configuration")
    
    project_root = get_project_root()
    config_path = project_root / "joplin-mcp.json"
    
    # Use centralized interactive config creation
    from src.joplin_mcp.config import JoplinMCPConfig
    
    config = JoplinMCPConfig.create_interactively(
        token=token,
        include_permissions=True,
        host="localhost",
        port=41184,
        timeout=30,
        verify_ssl=False
    )
    
    # Save configuration
    saved_path = config.save_interactively(config_path, include_token=True)
    print_success(f"Configuration saved to {saved_path}")
    return saved_path

def main():
    """Main installation function for development install."""
    return run_installation_process(
        config_path_resolver=create_joplin_config,
        is_development=True,
        welcome_message="Welcome! This script will help you set up the Joplin MCP server."
    )

if __name__ == "__main__":
    sys.exit(main()) 