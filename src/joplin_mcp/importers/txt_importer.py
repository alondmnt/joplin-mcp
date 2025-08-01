"""
Plain text (.txt) importer for Joplin MCP.

Handles plain text files by converting them to Markdown format while preserving
the original text content and extracting basic metadata.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..types.import_types import ImportedNote
from .base import BaseImporter, ImportProcessingError, ImportValidationError


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

        # Check source exists and is readable
        if not path.exists():
            raise ImportValidationError(f"Text source not found: {source_path}")

        if path.is_file():
            # Validate single text file
            extension = path.suffix.lower().lstrip(".")
            if extension not in self.get_supported_extensions():
                raise ImportValidationError(
                    f"Unsupported text file extension: {path.suffix}"
                )
            
            if path.stat().st_size == 0:
                raise ImportValidationError(f"File is empty: {source_path}")
                
            # Try to read the file to check if it's readable text
            await self._validate_text_file(path)
            
        elif path.is_dir():
            # Validate directory contains text files
            txt_files = []
            for ext in self.get_supported_extensions():
                txt_files.extend(path.rglob(f"*.{ext}"))
            
            if not txt_files:
                raise ImportValidationError(
                    f"No text files (.txt, .text) found in directory: {source_path}"
                )
            
            # Validate at least one text file is readable
            for txt_file in txt_files[:3]:  # Check first 3 files for performance
                try:
                    await self._validate_text_file(txt_file)
                    break  # If one is valid, assume others are too
                except ImportValidationError:
                    continue
            else:
                raise ImportValidationError(
                    f"No readable text files found in directory: {source_path}"
                )
        else:
            raise ImportValidationError(f"Path is neither file nor directory: {source_path}")

        return True

    async def _validate_text_file(self, file_path: Path) -> None:
        """Validate a single text file is readable."""
        if file_path.stat().st_size == 0:
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

    async def parse(self, source_path: str) -> List[ImportedNote]:
        """Parse text file or directory and convert to ImportedNote objects."""
        try:
            path = Path(source_path)
            
            if path.is_file():
                # Parse single text file
                note = await self._parse_text_file(path)
                return [note] if note else []
            elif path.is_dir():
                # Parse all text files in directory
                all_notes = []
                txt_files = []
                for ext in self.get_supported_extensions():
                    txt_files.extend(path.rglob(f"*.{ext}"))
                
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
                raise ImportProcessingError(f"Source is neither file nor directory: {source_path}")
                
        except Exception as e:
            if isinstance(e, (ImportValidationError, ImportProcessingError)):
                raise
            raise ImportProcessingError(f"Text import failed: {str(e)}") from e

    async def _parse_text_file(self, file_path: Path) -> Optional[ImportedNote]:
        """Parse a single text file and convert to ImportedNote."""
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
        title = self._extract_title(file_path, content)

        # Convert plain text to basic Markdown
        markdown_content = self._convert_to_markdown(content)

        # Extract any hashtags from content
        tags = self._extract_hashtags(content)

        # Get file metadata
        stat = file_path.stat()
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
                "source_file": str(file_path),
                "encoding": used_encoding,
                "file_size": stat.st_size,
                "import_method": "txt_importer",
            },
        )

        return note

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
