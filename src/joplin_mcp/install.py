#!/usr/bin/env python3
"""Canonical install runner for joplin-mcp.

Three entry points all land here:

* ``joplin-mcp-install`` (the pip console script defined in pyproject.toml)
* ``python -m joplin_mcp.install``
* the top-level ``install.py`` shim invoked by ``install.sh`` / ``install.bat``
  in a cloned-repo dev workflow

The dev shim passes ``is_development=True`` to flip the config location and
welcome message; the other two paths use the pip defaults.
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


def _config_path(is_development: bool) -> Path:
    """Where the joplin-mcp.json file lives for each install mode."""
    if is_development:
        # Dev: write next to the cloned repo so the script and its config sit
        # together. install.sh / install.bat invoke us from the repo root.
        return Path.cwd() / "joplin-mcp.json"
    # Pip: write to the user's home for global access (dot-prefixed).
    return Path.home() / ".joplin-mcp.json"


def _welcome_message(is_development: bool) -> str:
    if is_development:
        return "Welcome! This script will help you set up the Joplin MCP server."
    return "Welcome! This will configure the Joplin MCP server from your pip install."


def main(is_development: bool = False) -> int:
    """Run the interactive installer.

    Args:
        is_development: True when invoked from a cloned repo (via install.sh
            or install.bat); False (the default) for pip-installed users.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    config_path = _config_path(is_development)

    def create_joplin_config(token: str) -> Path:
        print_step("Creating Joplin MCP Configuration")
        config = create_config_interactively(
            token=token,
            include_permissions=True,
            **JoplinMCPConfig.DEFAULT_CONNECTION,
        )
        saved_path = save_config_to_path(config, config_path, include_token=True)
        print_success(f"Configuration saved to {saved_path}")
        return saved_path

    return run_installation_process(
        config_path_resolver=create_joplin_config,
        is_development=is_development,
        welcome_message=_welcome_message(is_development),
    )


if __name__ == "__main__":
    sys.exit(main())
