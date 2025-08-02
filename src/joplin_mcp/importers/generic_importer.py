"""
Generic importer for Joplin MCP.

Handles unknown file formats and "Other applications..." imports.
Acts as a fallback importer for unsupported formats with intelligent content detection.
"""

import mimetypes
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..types.import_types import ImportedNote
from .base import BaseImporter, ImportProcessingError, ImportValidationError


class GenericImporter(BaseImporter):
    """Generic importer for unknown file formats and custom applications."""

    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions (generic handles any)."""
        return [".*"]  # Wildcard for any extension

    def can_import(self, file_path: Path) -> bool:
        """Check if file can be imported (generic can handle any text file)."""
        # Generic importer can handle any file
        return True

    def supports_directory(self) -> bool:
        """Generic format supports both files and directories."""
        return True

    async def validate(self, source_path: str) -> bool:
        """Validate source can be processed by generic importer."""
        path = Path(source_path)

        # Check source exists
        if not path.exists():
            raise ImportValidationError(f"Source not found: {source_path}")

        # Handle directory
        if path.is_dir():
            # Check if directory contains any files
            files = list(path.rglob("*"))
            actual_files = [f for f in files if f.is_file()]
            if not actual_files:
                raise ImportValidationError(
                    f"Directory contains no files: {source_path}"
                )
            return True

        # Handle single file
        if not path.is_file():
            raise ImportValidationError(
                f"Path is not a file or directory: {source_path}"
            )

        if path.stat().st_size == 0:
            # Empty files are still valid - we'll create a minimal note
            pass

        # Try to detect if it's a binary file that we can't process
        if self._is_binary_file(path):
            # For binary files, we'll create a metadata note instead
            pass

        return True

    async def parse(self, source_path: str) -> List[ImportedNote]:
        """Parse source and convert to ImportedNote objects."""
        try:
            path = Path(source_path)
            notes = []

            if path.is_dir():
                # Process directory recursively
                notes = await self._parse_directory(path)
            else:
                # Process single file
                note = await self._parse_file(path)
                if note:
                    notes.append(note)

            return notes

        except Exception as e:
            if isinstance(e, (ImportValidationError, ImportProcessingError)):
                raise
            raise ImportProcessingError(
                f"Error parsing generic source {source_path}: {str(e)}"
            ) from e

    async def _parse_directory(self, directory_path: Path) -> List[ImportedNote]:
        """Parse all files in a directory."""
        notes = []

        # Get all files recursively
        for file_path in directory_path.rglob("*"):
            if file_path.is_file():
                try:
                    note = await self._parse_file(file_path)
                    if note:
                        notes.append(note)
                except Exception as e:
                    # Log error but continue with other files
                    print(f"Warning: Failed to process {file_path}: {str(e)}")
                    continue

        return notes

    async def _parse_file(self, file_path: Path) -> Optional[ImportedNote]:
        """Parse a single file into an ImportedNote."""
        try:
            # Detect file characteristics
            is_binary = self._is_binary_file(file_path)
            mime_type = self._detect_mime_type(file_path)
            file_size = file_path.stat().st_size

            # Extract title from filename
            title = self._extract_title_from_path(file_path)

            # Process content based on file type
            if is_binary:
                body = self._create_binary_file_note(file_path, mime_type, file_size)
                tags = ["binary", "attachment"]
            else:
                # Try to read as text
                content = self._read_text_file(file_path)
                if not content.strip():
                    # Handle empty files
                    body = f"# {title}\n\n*This file was empty when imported.*"
                    tags = ["empty-file", "generic-import"]
                else:
                    body = self._process_text_content(content, file_path, mime_type)
                    tags = self._extract_tags_from_content(content) + ["generic-import"]

            # Add file type tags
            extension = file_path.suffix.lower()
            if extension:
                tags.append(f"ext{extension.replace('.', '-')}")

            if mime_type:
                main_type = mime_type.split("/")[0]
                tags.append(f"type-{main_type}")

            # Get file metadata
            stat = file_path.stat()
            created_time = datetime.fromtimestamp(stat.st_ctime)
            updated_time = datetime.fromtimestamp(stat.st_mtime)

            # Create imported note
            note = ImportedNote(
                title=title,
                body=body,
                created_time=created_time,
                updated_time=updated_time,
                tags=list(set(tags)),  # Remove duplicates
                notebook=None,
                metadata={
                    "original_format": "generic",
                    "source_file": str(file_path),
                    "file_extension": extension,
                    "mime_type": mime_type,
                    "file_size": file_size,
                    "is_binary": is_binary,
                    "import_method": "generic_importer",
                },
            )

            return note

        except Exception as e:
            raise ImportProcessingError(
                f"Error processing file {file_path}: {str(e)}"
            ) from e

    def _is_binary_file(self, file_path: Path) -> bool:
        """Check if file is binary."""
        try:
            # Read first 8192 bytes to check for binary content
            with open(file_path, "rb") as f:
                chunk = f.read(8192)

            # Check for null bytes (common in binary files)
            if b"\x00" in chunk:
                return True

            # Try to decode as text
            try:
                chunk.decode("utf-8")
                return False
            except UnicodeDecodeError:
                return True

        except Exception:
            # If we can't read the file, assume it's binary
            return True

    def _detect_mime_type(self, file_path: Path) -> Optional[str]:
        """Detect MIME type of file."""
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return mime_type

    def _extract_title_from_path(self, file_path: Path) -> str:
        """Extract title from file path."""
        # Use filename without extension as title
        title = file_path.stem

        # Clean up the title
        title = title.replace("_", " ").replace("-", " ")

        # Capitalize first letter of each word
        title = " ".join(word.capitalize() for word in title.split())

        return title or "Untitled"

    def _read_text_file(self, file_path: Path) -> str:
        """Read text file with encoding detection."""
        encodings = ["utf-8", "utf-16", "latin-1", "cp1252", "iso-8859-1"]

        for encoding in encodings:
            try:
                with open(file_path, encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue

        # If all encodings fail, read as binary and decode with errors='replace'
        with open(file_path, "rb") as f:
            content = f.read()
        return content.decode("utf-8", errors="replace")

    def _process_text_content(
        self, content: str, file_path: Path, mime_type: Optional[str]
    ) -> str:
        """Process text content based on file type."""
        extension = file_path.suffix.lower()

        # Handle specific text formats
        if extension in {".md", ".markdown"}:
            return content  # Already Markdown
        elif extension in {".html", ".htm"}:
            return self._convert_html_to_markdown(content)
        elif extension in {".csv", ".tsv"}:
            return self._convert_tabular_to_markdown(content, extension)
        elif extension in {".json"}:
            return self._format_json_content(content)
        elif extension in {".xml"}:
            return self._format_xml_content(content)
        elif extension in {".py", ".js", ".java", ".cpp", ".c", ".h", ".css", ".sql"}:
            return self._format_code_content(content, extension)
        elif extension in {".log"}:
            return self._format_log_content(content)
        else:
            # Default: plain text with some formatting
            return self._format_plain_text(content, file_path.name)

    def _create_binary_file_note(
        self, file_path: Path, mime_type: Optional[str], file_size: int
    ) -> str:
        """Create note content for binary files."""
        size_mb = file_size / (1024 * 1024)

        content = f"# {self._extract_title_from_path(file_path)}\n\n"
        content += "**Binary File Information**\n\n"
        content += f"- **File**: `{file_path.name}`\n"
        content += f"- **Size**: {file_size:,} bytes ({size_mb:.2f} MB)\n"
        content += f"- **Type**: {mime_type or 'Unknown'}\n"
        content += f"- **Extension**: {file_path.suffix}\n"
        content += f"- **Location**: `{file_path.parent}`\n\n"
        content += "This is a binary file that cannot be displayed as text. "
        content += (
            "The original file should be accessed directly from its location.\n\n"
        )
        content += f"**Original Path**: `{file_path}`\n"

        return content

    def _convert_html_to_markdown(self, content: str) -> str:
        """Convert HTML to Markdown."""
        try:
            import markdownify
            from bs4 import BeautifulSoup

            # Parse and convert HTML to Markdown
            soup = BeautifulSoup(content, "html.parser")

            # Remove script and style tags for security
            for tag in soup.find_all(["script", "style"]):
                tag.decompose()

            # Convert to Markdown
            markdown = markdownify.markdownify(
                str(soup), heading_style="ATX", bullets="-", strip=["script", "style"]
            )

            return markdown.strip()

        except ImportError:
            # If BeautifulSoup/markdownify not available, return as code block
            return f"```html\n{content}\n```"

    def _convert_tabular_to_markdown(self, content: str, extension: str) -> str:
        """Convert CSV/TSV to Markdown table."""
        import csv
        from io import StringIO

        try:
            # Determine delimiter
            delimiter = "\t" if extension == ".tsv" else ","

            # Parse tabular data
            reader = csv.reader(StringIO(content), delimiter=delimiter)
            rows = list(reader)

            if not rows:
                return "Empty tabular file."

            # Create Markdown table
            markdown_lines = []

            # Add headers
            if rows:
                headers = rows[0]
                markdown_lines.append("| " + " | ".join(headers) + " |")
                markdown_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

                # Add data rows
                for row in rows[1:]:
                    # Pad row to match header count
                    padded_row = row + [""] * (len(headers) - len(row))
                    clean_row = [
                        cell.replace("|", "\\|") for cell in padded_row[: len(headers)]
                    ]
                    markdown_lines.append("| " + " | ".join(clean_row) + " |")

            return "\n".join(markdown_lines)

        except Exception:
            # Fallback: return as code block
            return f"```{extension[1:]}\n{content}\n```"

    def _format_json_content(self, content: str) -> str:
        """Format JSON content."""
        try:
            import json

            # Try to parse and prettify JSON
            data = json.loads(content)
            formatted = json.dumps(data, indent=2, ensure_ascii=False)
            return f"```json\n{formatted}\n```"
        except Exception:
            # If parsing fails, return as-is in code block
            return f"```json\n{content}\n```"

    def _format_xml_content(self, content: str) -> str:
        """Format XML content."""
        try:
            import xml.etree.ElementTree as ET
            from xml.dom import minidom

            # Try to parse and prettify XML
            root = ET.fromstring(content)
            rough_string = ET.tostring(root, encoding="unicode")
            reparsed = minidom.parseString(rough_string)
            formatted = reparsed.toprettyxml(indent="  ")

            # Remove empty lines
            lines = [line for line in formatted.split("\n") if line.strip()]
            formatted = "\n".join(lines)

            return f"```xml\n{formatted}\n```"
        except Exception:
            # If parsing fails, return as-is in code block
            return f"```xml\n{content}\n```"

    def _format_code_content(self, content: str, extension: str) -> str:
        """Format code content with syntax highlighting."""
        # Map extensions to language identifiers
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".css": "css",
            ".sql": "sql",
        }

        language = lang_map.get(extension, extension[1:])
        return f"```{language}\n{content}\n```"

    def _format_log_content(self, content: str) -> str:
        """Format log file content."""
        # Split into lines and add some basic formatting
        lines = content.strip().split("\n")

        # Limit to last 1000 lines for very large logs
        if len(lines) > 1000:
            content = "\n".join(lines[-1000:])
            header = f"**Log File** (showing last 1000 of {len(lines)} lines)\n\n"
        else:
            header = "**Log File Content**\n\n"

        return header + f"```log\n{content}\n```"

    def _format_plain_text(self, content: str, filename: str) -> str:
        """Format plain text content."""
        # Add filename as title
        title = self._extract_title_from_path(Path(filename))

        # Check if content already has markdown-style headers
        if content.strip().startswith("#"):
            return content

        # Add title and format as markdown
        return f"# {title}\n\n{content}"

    def _extract_tags_from_content(self, content: str) -> List[str]:
        """Extract hashtags and other tags from content."""
        import re

        tags = []

        # Find hashtags
        hashtag_pattern = r"#([a-zA-Z0-9_-]+)"
        hashtags = re.findall(hashtag_pattern, content)
        tags.extend(hashtags)

        # Look for common tag patterns
        tag_patterns = [
            r"(?i)tags?:\s*([^\n]+)",  # "Tags: tag1, tag2"
            r"(?i)keywords?:\s*([^\n]+)",  # "Keywords: word1, word2"
        ]

        for pattern in tag_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # Split by common separators
                tag_parts = re.split(r"[,;|]", match)
                for tag in tag_parts:
                    tag = tag.strip().lower()
                    if tag and len(tag) > 1:
                        tags.append(tag)

        return list(set(tags))  # Remove duplicates
