"""Joplin MCP Import functionality.

This package contains all import-related code:
- engine.py: Core import engine for processing batches
- tools.py: Import tool (import_from_file) and utilities
- types.py: Data types (ImportedNote, ImportResult, ImportOptions)
- importers/: Format-specific importers (md, html, csv, jex, raw, generic)
"""
from .engine import JoplinImportEngine
from .types import (
    ImportedNote,
    ImportOptions,
    ImportProcessingError,
    ImportResult,
    ImportValidationError,
)
from .tools import (
    detect_directory_format,
    detect_file_format,
    detect_source_format,
    format_import_result,
    get_importer_for_format,
    import_from_file,
    import_source,
)

__all__ = [
    # Engine
    "JoplinImportEngine",
    # Types
    "ImportedNote",
    "ImportOptions",
    "ImportProcessingError",
    "ImportResult",
    "ImportValidationError",
    # Tools and utilities
    "detect_directory_format",
    "detect_file_format",
    "detect_source_format",
    "format_import_result",
    "get_importer_for_format",
    "import_from_file",
    "import_source",
]
