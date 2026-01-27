"""HTML file importer for Joplin MCP server.

Converts HTML files to Markdown format suitable for Joplin import.
Supports both single HTML files and basic HTML document structures.
"""

import logging
from pathlib import Path
from typing import List, Optional

from ..types import ImportedNote
from .base import BaseImporter
from .utils import html_to_markdown, extract_hashtags, extract_html_title

logger = logging.getLogger(__name__)


class HTMLImporter(BaseImporter):
    """Importer for HTML files with conversion to Markdown."""

    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return ["html", "htm"]

    def can_import(self, file_path: Path) -> bool:
        """Check if file can be imported as HTML."""
        extension = file_path.suffix.lower().lstrip(".")
        return extension in self.get_supported_extensions()

    def supports_directory(self) -> bool:
        """HTML format supports both files and directories containing HTML files."""
        return True

    async def validate(self, source_path: str) -> bool:
        """Validate HTML file or directory can be processed."""
        path = Path(source_path)

        if path.is_file():
            # Use enhanced base class validation
            self.validate_file_comprehensive(path)
            
            # Additional HTML-specific validation
            content, _ = self.read_file_safe(path)
            if not any(
                tag in content.lower()
                for tag in ["<html", "<head", "<body", "<div", "<p", "<h1", "<h2"]
            ):
                logger.warning(
                    f"File may not be valid HTML (no common HTML tags found): {source_path}"
                )
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
        """Parse HTML file or directory and convert to ImportedNote objects."""
        path = Path(source_path)

        if path.is_file():
            # Parse single HTML file
            note = await self._parse_html_file(path)
            return [note] if note else []
        elif path.is_dir():
            # Parse all HTML files in directory using enhanced base class
            all_notes = []
            html_files = self.scan_directory_safe(path)

            for html_file in html_files:
                try:
                    note = await self._parse_html_file(html_file)
                    if note:
                        all_notes.append(note)
                except Exception as e:
                    # Log error but continue with other files
                    logger.warning(f"Failed to parse {html_file}: {str(e)}")
                    continue

            return all_notes
        else:
            from .base import ImportProcessingError
            raise ImportProcessingError(
                f"Source is neither file nor directory: {source_path}"
            )

    async def _parse_html_file(self, file_path: Path) -> Optional[ImportedNote]:
        """Parse a single HTML file and convert to ImportedNote."""
        # Read file content using enhanced base class utilities
        content, used_encoding = self.read_file_safe(file_path)

        logger.info(f"Read HTML file with {used_encoding} encoding: {file_path}")

        # Convert HTML to Markdown using shared utility
        markdown_content = html_to_markdown(content)

        # Extract title using HTML-specific extraction
        title = extract_html_title(content, file_path.stem)

        # Extract hashtags from the converted markdown content
        tags = self.extract_hashtags_safe(markdown_content)

        # Extract additional metadata
        file_metadata = self.get_file_metadata_safe(file_path)

        # Create note using enhanced base class utilities
        return self.create_imported_note_safe(
            title=title,
            body=markdown_content,
            file_path=file_path,
            tags=tags,
            additional_metadata={
                "encoding": used_encoding,
                "original_format": "html",
                "source_file": str(file_path),
                "file_size": file_metadata.get("size", 0),
            },
        )

