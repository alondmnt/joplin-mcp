#!/usr/bin/env python3
"""Canonical install runner for joplin-mcp.

Two entry points reach this module:

* ``joplin-mcp-install`` (the pip console script defined in pyproject.toml)
  -- calls ``main()`` directly, pip mode.
* ``python -m joplin_mcp.install [--dev]`` -- the ``__main__`` block below
  parses argv. ``bootstrap.py`` invokes it with ``--dev`` after the dev
  environment is set up, so the config lands inside the repo rather than
  ``$HOME``.
"""

import argparse
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
        # together. bootstrap.py invokes us from the repo root.
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
        is_development: True when invoked from a cloned repo (via
            ``bootstrap.py``); False (the default) for pip-installed users.

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


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse argv for ``python -m joplin_mcp.install``.

    Extracted so tests can exercise the flag wiring without re-execing.
    """
    parser = argparse.ArgumentParser(
        prog="python -m joplin_mcp.install",
        description="Interactive installer for the Joplin MCP server.",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help=(
            "Run in development mode (config written to the current "
            "directory instead of $HOME). Used by the dev-install bootstrap."
        ),
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])
    sys.exit(main(is_development=args.dev))
