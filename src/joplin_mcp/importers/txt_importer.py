"""
Plain text (.txt) importer for Joplin MCP.

Handles plain text files by converting them to Markdown format while preserving
the original text content and extracting basic metadata.
"""

from pathlib import Path
from typing import List, Optional

from ..types.import_types import ImportedNote
from .base import BaseImporter
from .utils import convert_plain_text_to_markdown


class TxtImporter(BaseImporter):
    """Importer for plain text (.txt) files."""

    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return ["txt", "text"]

    def can_import(self, file_path: Path) -> bool:
        """Check if file can be imported as plain text."""
        extension = file_path.suffix.lower().lstrip(".")
        return extension in self.get_supported_extensions()

    def supports_directory(self) -> bool:
        """Text format supports both files and directories containing text files."""
        return True

    async def validate(self, source_path: str) -> bool:
        """Validate text file or directory can be processed."""
        path = Path(source_path)

        if path.is_file():
            # Use enhanced base class validation
            self.validate_file_comprehensive(path)
        elif path.is_dir():
            # Use enhanced base class validation
            self.validate_directory_comprehensive(path)
        else:
            from .base import ImportValidationError
            raise ImportValidationError(
                f"Path is neither file nor directory: {source_path}"
            )

        return True

    async def parse(self, source_path: str) -> List[ImportedNote]:
        """Parse text file or directory and convert to ImportedNote objects."""
        path = Path(source_path)

        if path.is_file():
            # Parse single text file
            note = await self._parse_text_file(path)
            return [note] if note else []
        elif path.is_dir():
            # Parse all text files in directory using enhanced base class
            all_notes = []
            txt_files = self.scan_directory_safe(path)

            for txt_file in txt_files:
                try:
                    note = await self._parse_text_file(txt_file)
                    if note:
                        all_notes.append(note)
                except Exception as e:
                    # Log error but continue with other files
                    print(f"Warning: Failed to parse {txt_file}: {str(e)}")
                    continue

            return all_notes
        else:
            from .base import ImportProcessingError
            raise ImportProcessingError(
                f"Source is neither file nor directory: {source_path}"
            )

    async def _parse_text_file(self, file_path: Path) -> Optional[ImportedNote]:
        """Parse a single text file and convert to ImportedNote."""
        # Read file content using enhanced base class utilities
        content, used_encoding = self.read_file_safe(file_path)

        # Extract title using enhanced base class utilities
        title = self.extract_title_safe(content, file_path.stem)

        # Convert plain text to Markdown using shared utility
        markdown_content = convert_plain_text_to_markdown(content, title)

        # Extract hashtags using enhanced base class utilities
        tags = self.extract_hashtags_safe(content)

        # Create note using enhanced base class utilities
        return self.create_imported_note_safe(
            title=title,
            body=markdown_content,
            file_path=file_path,
            tags=tags,
            additional_metadata={
                "encoding": used_encoding,
            },
        )
