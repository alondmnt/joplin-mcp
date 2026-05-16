#!/usr/bin/env python3
"""Embedded installation script for pip-installed joplin-mcp package.

This contains the same installation logic as the main install.py but
adapted to work when installed as a package.
"""

import sys
from pathlib import Path

from .config import JoplinMCPConfig
from .ui_integration import (
    create_config_interactively,
    print_step,
    print_success,
    run_installation_process,
    save_config_to_path,
)


def create_joplin_config(token: str) -> Path:
    """Create or update the joplin-mcp.json configuration file."""
    print_step("Creating Joplin MCP Configuration")

    # Create config in user's home directory for global access
    config_path = Path.home() / ".joplin-mcp.json"

    config = create_config_interactively(
        token=token, include_permissions=True, **JoplinMCPConfig.DEFAULT_CONNECTION
    )

    saved_path = save_config_to_path(config, config_path, include_token=True)
    print_success(f"Configuration saved to {saved_path}")
    return saved_path


def main():
    """Main installation function for pip-installed package."""
    return run_installation_process(
        config_path_resolver=create_joplin_config,
        is_development=False,
        welcome_message="Welcome! This will configure the Joplin MCP server from your pip install.",
    )


if __name__ == "__main__":
    sys.exit(main())
