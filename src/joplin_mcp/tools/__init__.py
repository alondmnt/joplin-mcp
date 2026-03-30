"""Joplin MCP Tools - importing registers all tools with the server."""
from joplin_mcp.tools import (
    notes,
    notebooks,
    tags,
    notes_bulk,
    tags_bulk,
    trash,
    notes_revisions,
    backup_database,
)

__all__ = [
    "notes",
    "notebooks",
    "tags",
    "notes_bulk",
    "tags_bulk",
    "trash",
    "notes_revisions",
    "backup_database",
]
