"""Import tools for Joplin MCP server."""
import ast
import json
import logging
from pathlib import Path
from typing import Annotated, Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from joplin_mcp.config import JoplinMCPConfig
from joplin_mcp.fastmcp_server import create_tool, get_joplin_client

from .engine import JoplinImportEngine
from .importers import (
    CSVImporter,
    GenericImporter,
    HTMLImporter,
    JEXImporter,
    MarkdownImporter,
    RAWImporter,
)
from .importers.base import ImportProcessingError, ImportValidationError
from .importers.utils import looks_like_raw_export
from .types import ImportOptions

logger = logging.getLogger(__name__)


def _require_all_properties(schema: Dict[str, Any], _model: Any) -> None:
    """Make object schemas strict-client compatible.

    Some strict function-schema validators require every declared property to
    appear in ``required`` even when the field itself is nullable.
    """
    properties = schema.get("properties")
    if isinstance(properties, dict):
        schema["required"] = list(properties.keys())


class ImportFromFileOptions(BaseModel):
    """Structured import options exposed through the MCP schema."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra=_require_all_properties,
    )

    handle_duplicates: Optional[Literal["skip", "overwrite", "rename"]] = None
    create_missing_notebooks: Optional[bool] = None
    create_missing_tags: Optional[bool] = None
    preserve_timestamps: Optional[bool] = None
    max_batch_size: Optional[int] = Field(default=None, ge=1)
    attachment_handling: Optional[Literal["link", "embed", "skip"]] = None
    encoding: Optional[str] = None
    max_file_size_mb: Optional[int] = Field(default=None, ge=1)
    file_pattern: Optional[str] = None
    preserve_structure: Optional[bool] = None
    preserve_directory_structure: Optional[bool] = None
    csv_import_mode: Optional[Literal["table", "rows"]] = None
    csv_delimiter: Optional[str] = Field(
        default=None, min_length=1, max_length=1, description="Single-character CSV delimiter override"
    )
    extract_hashtags: Optional[bool] = None


# === UTILITY FUNCTIONS ===


def format_import_result(result, operation_name: str = "IMPORT_BATCH") -> str:
    """Format import result for MCP response."""
    status = (
        "SUCCESS"
        if result.is_complete_success
        else "PARTIAL_SUCCESS" if result.is_partial_success else "FAILED"
    )

    response = f"""OPERATION: {operation_name}
STATUS: {status}
TOTAL_PROCESSED: {result.total_processed}
SUCCESSFUL_IMPORTS: {result.successful_imports}
FAILED_IMPORTS: {result.failed_imports}
SKIPPED_ITEMS: {result.skipped_items}
PROCESSING_TIME: {result.processing_time:.2f}s"""

    if result.created_notebooks:
        response += f"\nCREATED_NOTEBOOKS: {', '.join(result.created_notebooks)}"

    if result.created_tags:
        response += f"\nCREATED_TAGS: {', '.join(result.created_tags)}"

    if result.errors:
        response += f"\nERRORS: {len(result.errors)} error(s)"
        for error in result.errors[:5]:  # Show first 5 errors
            response += f"\n  - {error}"
        if len(result.errors) > 5:
            response += f"\n  ... and {len(result.errors) - 5} more errors"

    if result.warnings:
        response += f"\nWARNINGS: {len(result.warnings)} warning(s)"
        for warning in result.warnings[:3]:  # Show first 3 warnings
            response += f"\n  - {warning}"
        if len(result.warnings) > 3:
            response += f"\n  ... and {len(result.warnings) - 3} more warnings"

    # Add success message
    if result.is_complete_success:
        response += f"\nMESSAGE: Import completed successfully - all {result.successful_imports} items imported"
    elif result.is_partial_success:
        response += f"\nMESSAGE: Import partially successful - {result.successful_imports}/{result.total_processed} items imported"
    else:
        response += "\nMESSAGE: Import failed - no items were successfully imported"

    # Compact per-run summary (kept short for LLM context)
    try:
        if (
            getattr(result, "notes_rewritten", 0)
            or getattr(result, "resources_uploaded", 0)
            or getattr(result, "resources_reused", 0)
            or getattr(result, "unresolved_links", 0)
        ):
            response += (
                f"\nSUMMARY: modified_notes={getattr(result, 'notes_rewritten', 0)}, "
                f"uploaded_resources={getattr(result, 'resources_uploaded', 0)}, "
                f"reused_resources={getattr(result, 'resources_reused', 0)}, "
                f"unresolved_links={getattr(result, 'unresolved_links', 0)}"
            )
    except Exception:
        pass

    return response


def get_importer_for_format(file_format: str, options: ImportOptions):
    """Get the appropriate importer for the specified format."""
    format_map = {
        "md": MarkdownImporter,
        "markdown": MarkdownImporter,
        "jex": JEXImporter,
        "html": HTMLImporter,
        "htm": HTMLImporter,
        "csv": CSVImporter,
        "raw": RAWImporter,
        "generic": GenericImporter,
    }

    importer_class = format_map.get(file_format.lower())
    if not importer_class:
        # Fall back to generic importer for unknown formats
        return GenericImporter(options)

    return importer_class(options)


def detect_file_format(file_path: str) -> str:
    """Detect file format from file extension."""
    path = Path(file_path)
    extension = path.suffix.lstrip(".").lower()

    # Map extensions to formats
    extension_map = {
        "md": "md",
        "markdown": "markdown",
        "mdown": "md",
        "mkd": "md",
        "jex": "jex",
        "html": "html",
        "htm": "html",
        "csv": "csv",
    }

    detected_format = extension_map.get(extension)
    if not detected_format:
        # Fall back to generic format for unknown file types
        return "generic"

    return detected_format


def detect_directory_format(directory_path: str) -> str:
    """Detect format from directory contents.

    Rules:
    - Classify as RAW only when the directory itself looks like a Joplin export
      (resources folder at the root and markdown present at or under the root),
      to avoid misclassifying mixed trees that contain a nested RAW subfolder.
    - If multiple supported types (md/html/csv) are present, return "generic" so the
      GenericImporter can delegate per-file and handle mixed content.
    - Otherwise, return the single supported format present.
    """
    path = Path(directory_path)

    if not path.exists() or not path.is_dir():
        raise ValueError(f"Directory not found: {directory_path}")

    # RAW detection using shared heuristic (root-level sensitive)
    if looks_like_raw_export(path):
        return "raw"

    # Scan extensions in tree
    extension_counts = {}
    for file_path in path.rglob("*"):
        if file_path.is_file():
            extension = file_path.suffix.lstrip(".").lower()
            extension_counts[extension] = extension_counts.get(extension, 0) + 1

    if not extension_counts:
        raise ValueError(f"No files found in directory: {directory_path}")

    # Supported mapping
    extension_map = {
        "md": "md",
        "markdown": "md",
        "mdown": "md",
        "mkd": "md",
        "html": "html",
        "htm": "html",
        "csv": "csv",
    }

    # Collect supported types present
    present_supported = {extension_map[ext] for ext in extension_counts.keys() if ext in extension_map}

    if not present_supported:
        # Fall back to generic when no recognized types
        return "generic"

    if len(present_supported) > 1:
        # Mixed content – use GenericImporter
        return "generic"

    # Single supported type present
    return next(iter(present_supported))


# === IMPORT TOOL ===


@create_tool("import_from_file", "Import from file")
async def import_from_file(
    file_path: Annotated[str, Field(description="Path to the file to import")],
    format: Annotated[
        Optional[str],
        Field(description="File format (md, html, csv, jex, generic) - auto-detected if not specified"),
    ] = None,
    target_notebook: Annotated[
        Optional[str], Field(description="Target notebook name (optional, defaults to 'Imported')")
    ] = 'Imported',
    import_options: Annotated[
        Optional[ImportFromFileOptions],
        Field(description="Additional structured import options")
    ] = None,
) -> str:
    """Import notes from a file or directory.

    - Formats: md, html, csv, jex, generic (auto-detected if omitted).
    - Directories: recursive; RAW exports auto-detected; mixed dirs supported.
    - import_options (dict, not JSON string). Common: csv_import_mode (table|rows),
      csv_delimiter (e.g., ";"), extract_hashtags (bool).
      In csv row mode, each note body is YAML frontmatter built from the row.

    Returns a compact result summary with counts and errors/warnings.

    Examples:
      import_from_file("/path/note.md")
      import_from_file("/path/data.csv", format="csv", target_notebook="CSV Rows",
                       import_options={"csv_import_mode": "rows"})
    """
    try:
        # Load configuration
        config = JoplinMCPConfig.load()

        # Validate file path (support both files and directories)
        path = Path(file_path)
        if not path.exists():
            return format_import_result(type('Result', (), {
                'is_complete_success': False,
                'is_partial_success': False,
                'total_processed': 0,
                'successful_imports': 0,
                'failed_imports': 0,
                'skipped_items': 0,
                'processing_time': 0.0,
                'created_notebooks': [],
                'created_tags': [],
                'errors': [f"Path does not exist: {file_path}"],
                'warnings': []
            })(), "IMPORT_FROM_FILE")
        if not (path.is_file() or path.is_dir()):
            return format_import_result(type('Result', (), {
                'is_complete_success': False,
                'is_partial_success': False,
                'total_processed': 0,
                'successful_imports': 0,
                'failed_imports': 0,
                'skipped_items': 0,
                'processing_time': 0.0,
                'created_notebooks': [],
                'created_tags': [],
                'errors': [f"Path is neither a file nor directory: {file_path}"],
                'warnings': []
            })(), "IMPORT_FROM_FILE")

        # Detect format if not specified
        if not format:
            if path.is_file():
                try:
                    format = detect_file_format(file_path)
                except ValueError:
                    format = "generic"
            else:
                # For directories, detect format (raw, md, html, csv) with fallback to generic
                try:
                    format = detect_directory_format(file_path)
                except Exception:
                    format = "generic"

        # Create import options
        base_options = ImportOptions(
            target_notebook=target_notebook,
            create_missing_notebooks=config.import_settings.get(
                "create_missing_notebooks", True
            ),
            create_missing_tags=config.import_settings.get("create_missing_tags", True),
            preserve_timestamps=config.import_settings.get("preserve_timestamps", True),
            handle_duplicates=config.import_settings.get("handle_duplicates", "skip"),
            max_batch_size=config.import_settings.get("max_batch_size", 100),
            attachment_handling=config.import_settings.get(
                "attachment_handling", "embed"
            ),
            max_file_size_mb=config.import_settings.get("max_file_size_mb", 100),
        )

        # Apply additional options. Older direct Python callers may still pass a
        # JSON/Python-dict string even though the MCP schema now exposes this as
        # an object-only parameter for better client compatibility.
        if import_options:
            if isinstance(import_options, str):
                try:
                    try:
                        parsed = json.loads(import_options)
                    except json.JSONDecodeError:
                        parsed = ast.literal_eval(import_options)
                    if isinstance(parsed, dict):
                        import_options = parsed
                    else:
                        return "VALIDATION_ERROR: import_options string did not parse to an object"
                except Exception:
                    return "VALIDATION_ERROR: import_options must be an object or JSON/dict string"
            elif isinstance(import_options, BaseModel):
                import_options = import_options.model_dump(exclude_none=True)
            elif not isinstance(import_options, dict):
                return "VALIDATION_ERROR: import_options must be an object or JSON/dict string"
            # Merge structured options
            for key, value in import_options.items():
                if hasattr(base_options, key):
                    setattr(base_options, key, value)
                else:
                    base_options.import_options[key] = value

        # Get appropriate importer
        importer = get_importer_for_format(format, base_options)

        # If importing a directory with an importer that doesn't support directories,
        # fall back to GenericImporter which can delegate per-file.
        if path.is_dir() and hasattr(importer, "supports_directory"):
            try:
                if not importer.supports_directory():
                    importer = GenericImporter(base_options)
            except Exception:
                pass

        # Validate and parse file
        try:
            await importer.validate(file_path)
            notes = await importer.parse(file_path)
        except ImportValidationError as e:
            return f"VALIDATION_ERROR: {str(e)}"
        except ImportProcessingError as e:
            return f"PROCESSING_ERROR: {str(e)}"
        except Exception as e:
            return f"ERROR: Unexpected error during parsing: {str(e)}"

        if not notes:
            return "WARNING: No notes were extracted from the file"

        # Import notes using the import engine
        try:
            client = get_joplin_client()
            engine = JoplinImportEngine(client, config)
            result = await engine.import_batch(notes, base_options)
        except Exception as e:
            return f"ERROR: Import engine failed: {str(e)}"

        # Format and return result
        return format_import_result(result, "IMPORT_FROM_FILE")

    except Exception as e:
        logger.error(f"import_from_file failed: {e}")
        return f"ERROR: Tool execution failed: {str(e)}"
