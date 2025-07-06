#!/usr/bin/env python3
"""Embedded installation script for pip-installed joplin-mcp package.

This contains the same installation logic as the main install.py but
adapted to work when installed as a package.
"""

import sys
from pathlib import Path

from .ui_integration import run_installation_process, print_step, print_success

def create_joplin_config(token: str) -> Path:
    """Create or update the joplin-mcp.json configuration file."""
    print_step("Creating Joplin MCP Configuration")
    
    # For pip-installed packages, create config in current directory
    config_path = Path.cwd() / "joplin-mcp.json"
    
    # Use centralized interactive config creation
    from .config import JoplinMCPConfig
    
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
    """Main installation function for pip-installed package."""
    return run_installation_process(
        config_path_resolver=create_joplin_config,
        is_development=False,
        welcome_message="Welcome! This will configure the Joplin MCP server from your pip install."
    )

if __name__ == "__main__":
    sys.exit(main()) 