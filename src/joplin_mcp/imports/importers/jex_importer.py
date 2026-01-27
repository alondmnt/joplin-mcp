"""JEX (Joplin Export) file importer for Joplin MCP server."""
import tarfile
import tempfile
from pathlib import Path
from typing import List

from ..types import ImportedNote
from .base import BaseImporter, ImportProcessingError, ImportValidationError


class JEXImporter(BaseImporter):
    """Importer for JEX (Joplin Export) files.

    JEX format is a TAR archive containing:
    - Individual .md files for each note
    - JSON metadata files for notes, notebooks, tags
    - Resources (attachments) as separate files
    - Directory structure representing notebooks

    This is Joplin's native lossless export format.
    """

    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return ["jex"]

    def supports_directory(self) -> bool:
        """JEX format only supports individual files (TAR archives)."""
        return False

    async def validate(self, source: str) -> bool:
        """Validate that the source is a valid JEX file."""
        path = Path(source)

        # Use enhanced base class validation for basic checks
        self.validate_file_comprehensive(path)

        # Additional JEX-specific validation
        try:
            with tarfile.open(source, "r") as tar:
                # Check if it looks like a JEX file
                members = tar.getnames()
                if not members:
                    raise ImportValidationError("JEX file appears to be empty")

                # Look for expected JEX structure (should have some .md files or .json metadata)
                has_md_files = any(name.endswith(".md") for name in members)
                has_json_files = any(name.endswith(".json") for name in members)

                if not (has_md_files or has_json_files):
                    raise ImportValidationError(
                        "JEX file does not contain expected .md or .json files"
                    )

        except tarfile.TarError as e:
            raise ImportValidationError(
                f"Invalid JEX file (not a valid TAR archive): {str(e)}"
            ) from e

        return True

    async def parse(self, source: str) -> List[ImportedNote]:
        """Parse JEX file and return ImportedNote objects."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract JEX archive (directory-style Joplin export)
                with tarfile.open(source, "r") as tar:
                    tar.extractall(temp_path)

                # Delegate parsing to RAWImporter to avoid duplication
                from .raw_importer import RAWImporter

                raw_importer = RAWImporter(self.options)
                return await raw_importer.parse(str(temp_path))

        except Exception as e:
            raise ImportProcessingError(f"Failed to parse JEX file {source}: {str(e)}") from e

    # Parsing is fully delegated to RAWImporter to avoid duplication.
