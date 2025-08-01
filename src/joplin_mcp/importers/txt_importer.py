"""
Plain text (.txt) importer for Joplin MCP.

Handles plain text files by converting them to Markdown format while preserving
the original text content and extracting basic metadata.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List

from ..types.import_types import ImportedNote
from .base import BaseImporter, ImportProcessingError, ImportValidationError


class TxtImporter(BaseImporter):
    """Importer for plain text (.txt) files."""

    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return [".txt", ".text"]

    def can_import(self, file_path: Path) -> bool:
        """Check if file can be imported as plain text."""
        return file_path.suffix.lower() in self.get_supported_extensions()

    async def validate(self, file_path: str) -> bool:
        """Validate plain text file can be processed."""
        path = Path(file_path)

        # Check file exists and is readable
        if not path.exists():
            raise ImportValidationError(f"Text file not found: {file_path}")

        if not path.is_file():
            raise ImportValidationError(f"Path is not a file: {file_path}")

        # Check file extension
        if path.suffix.lower() not in self.get_supported_extensions():
            raise ImportValidationError(
                f"Unsupported text file extension: {path.suffix}"
            )

        if path.stat().st_size == 0:
            raise ImportValidationError(f"File is empty: {file_path}")

        # Try to read the file to check if it's readable text
        content = None
        for encoding in ["utf-8", "latin-1", "cp1252", "iso-8859-1"]:
            try:
                with open(file_path, encoding=encoding) as f:
                    content = f.read(1024)  # Read first 1KB to check
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            raise ImportValidationError(
                f"Unable to decode text file with common encodings: {file_path}"
            )

        return True

    async def parse(self, file_path: str) -> List[ImportedNote]:
        """Parse plain text file and convert to ImportedNote."""
        try:
            path = Path(file_path)

            # Read file content with proper encoding
            content = None
            used_encoding = None
            for encoding in ["utf-8", "latin-1", "cp1252", "iso-8859-1"]:
                try:
                    with open(file_path, encoding=encoding) as f:
                        content = f.read()
                    used_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                raise ImportProcessingError(
                    f"Could not read text file with any supported encoding: {file_path}"
                )

            # Extract title from filename or first line
            title = self._extract_title(path, content)

            # Convert plain text to basic Markdown
            markdown_content = self._convert_to_markdown(content)

            # Extract any hashtags from content
            tags = self._extract_hashtags(content)

            # Get file metadata
            stat = path.stat()
            created_time = datetime.fromtimestamp(stat.st_ctime)
            updated_time = datetime.fromtimestamp(stat.st_mtime)

            # Create the imported note
            note = ImportedNote(
                title=title,
                body=markdown_content,
                created_time=created_time,
                updated_time=updated_time,
                tags=tags,
                notebook=None,  # Will be set by import engine
                metadata={
                    "original_format": "plain_text",
                    "source_file": str(path),
                    "encoding": used_encoding,
                    "file_size": stat.st_size,
                    "import_method": "txt_importer",
                },
            )

            return [note]

        except Exception as e:
            if isinstance(e, (ImportValidationError, ImportProcessingError)):
                raise
            raise ImportProcessingError(
                f"Error parsing text file {file_path}: {str(e)}"
            ) from e

    def _extract_title(self, file_path: Path, content: str) -> str:
        """Extract title from filename or first line of content."""
        # Try to use first non-empty line as title if it's reasonably short
        lines = content.strip().split("\n")
        if lines:
            first_line = lines[0].strip()
            # Use first line as title if it's short and looks like a title
            if len(first_line) <= 100 and not first_line.endswith("."):
                # Check if it looks like a title (no paragraph text indicators)
                if not any(
                    phrase in first_line.lower()
                    for phrase in ["the ", "this ", "here ", "when ", "where "]
                ):
                    return first_line

        # Fall back to filename without extension
        return file_path.stem

    def _convert_to_markdown(self, content: str) -> str:
        """Convert plain text to basic Markdown format."""
        # Start with the original content
        markdown = content

        # Preserve existing line breaks but ensure proper paragraph spacing
        lines = markdown.split("\n")
        processed_lines = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                processed_lines.append("")
                continue

            # Detect potential headers (lines that are short and followed by empty line or end)
            is_potential_header = (
                len(stripped) <= 80
                and not stripped.endswith(".")
                and (i == len(lines) - 1 or lines[i + 1].strip() == "")
            )

            # Convert potential headers to Markdown headers
            if (
                is_potential_header and i > 0
            ):  # Don't convert first line (already used as title)
                processed_lines.append(f"## {stripped}")
            else:
                processed_lines.append(line)

        return "\n".join(processed_lines)

    def _extract_hashtags(self, content: str) -> List[str]:
        """Extract hashtags from text content."""
        # Find hashtags in the content
        hashtag_pattern = r"#([a-zA-Z0-9_-]+)"
        hashtags = re.findall(hashtag_pattern, content)

        # Remove duplicates and return
        return list(set(hashtags))
