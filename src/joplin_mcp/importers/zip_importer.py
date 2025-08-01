"""
ZIP importer for Joplin MCP.

Handles ZIP files, particularly OneNote Notebook format and other zipped content.
Extracts and processes supported file formats from ZIP archives.
"""

import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..types.import_types import ImportedNote
from .base import BaseImporter, ImportProcessingError, ImportValidationError


class ZIPImporter(BaseImporter):
    """Importer for ZIP archives, including OneNote Notebook format."""

    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return ["zip"]

    def can_import(self, file_path: Path) -> bool:
        """Check if file can be imported as ZIP."""
        extension = file_path.suffix.lower().lstrip(".")
        return extension in self.get_supported_extensions()

    def supports_directory(self) -> bool:
        """ZIP format only supports file imports."""
        return False

    async def validate(self, file_path: str) -> bool:
        """Validate ZIP file can be processed."""
        path = Path(file_path)

        # Check file exists and is readable
        if not path.exists():
            raise ImportValidationError(f"ZIP file not found: {file_path}")

        if not path.is_file():
            raise ImportValidationError(f"Path is not a file: {file_path}")

        # Check file extension
        if path.suffix.lower() not in self.get_supported_extensions():
            raise ImportValidationError(
                f"Unsupported ZIP file extension: {path.suffix}"
            )

        if path.stat().st_size == 0:
            raise ImportValidationError(f"File is empty: {file_path}")

        # Try to open as ZIP file
        try:
            with zipfile.ZipFile(file_path, "r") as zip_file:
                # Check if it's a valid ZIP file
                zip_file.testzip()

                # Get list of files in the archive
                file_list = zip_file.namelist()
                if not file_list:
                    raise ImportValidationError(f"ZIP file is empty: {file_path}")

                # Check if it contains any supported file types
                supported_extensions = {".md", ".txt", ".html", ".htm", ".csv", ".enex"}
                has_supported_files = any(
                    Path(filename).suffix.lower() in supported_extensions
                    for filename in file_list
                    if not filename.endswith("/")
                )

                if not has_supported_files:
                    raise ImportValidationError(
                        f"ZIP file contains no supported file formats: {file_path}"
                    )

        except zipfile.BadZipFile as e:
            raise ImportValidationError(f"Invalid ZIP file: {file_path}") from e
        except Exception as e:
            raise ImportValidationError(f"Error reading ZIP file: {str(e)}") from e

        return True

    async def parse(self, file_path: str) -> List[ImportedNote]:
        """Parse ZIP file and convert to ImportedNote objects."""
        try:
            path = Path(file_path)
            notes = []

            with zipfile.ZipFile(file_path, "r") as zip_file:
                # Get list of all files in the archive
                file_list = zip_file.namelist()

                # Detect if this is a OneNote Notebook
                is_onenote = self._detect_onenote_format(file_list)

                # Process each file in the archive
                for zip_path in file_list:
                    # Skip directories
                    if zip_path.endswith("/"):
                        continue

                    zip_file_path = Path(zip_path)
                    extension = zip_file_path.suffix.lower()

                    # Check if this is a supported file type
                    if extension in {".md", ".txt", ".html", ".htm", ".csv", ".enex"}:
                        try:
                            # Extract file content
                            with zip_file.open(zip_path) as extracted_file:
                                content = extracted_file.read()

                            # Create a temporary note from the extracted content
                            note = await self._process_extracted_file(
                                zip_file_path, content, path, is_onenote
                            )

                            if note:
                                notes.append(note)

                        except Exception as e:
                            # Log error but continue with other files
                            print(f"Warning: Failed to process {zip_path}: {str(e)}")
                            continue

            return notes

        except Exception as e:
            if isinstance(e, (ImportValidationError, ImportProcessingError)):
                raise
            raise ImportProcessingError(
                f"Error parsing ZIP file {file_path}: {str(e)}"
            ) from e

    def _detect_onenote_format(self, file_list: List[str]) -> bool:
        """Detect if ZIP contains OneNote Notebook structure."""
        # OneNote notebooks typically have specific folder structures and file types
        onenote_indicators = [
            ".one",  # OneNote section files
            "Open Notebook.onetoc2",  # OneNote table of contents
            ".onetoc2",  # Section group files
        ]

        for filename in file_list:
            if any(indicator in filename for indicator in onenote_indicators):
                return True

        return False

    async def _process_extracted_file(
        self, zip_file_path: Path, content: bytes, zip_source: Path, is_onenote: bool
    ) -> Optional[ImportedNote]:
        """Process an extracted file from the ZIP archive."""
        try:
            # Decode content to text
            text_content = self._decode_content(content)
            if not text_content:
                return None

            # Extract title from filename or content
            title = self._extract_title(zip_file_path, text_content)

            # Process content based on file type
            extension = zip_file_path.suffix.lower()
            if extension in {".html", ".htm"}:
                body = self._process_html_content(text_content)
            elif extension in {".md", ".markdown"}:
                body = text_content  # Markdown is already in correct format
            elif extension in {".txt", ".text"}:
                body = self._convert_text_to_markdown(text_content, title)
            elif extension == ".csv":
                body = self._convert_csv_to_markdown(text_content, title)
            else:
                # Default: wrap in code block
                body = f"# {title}\n\n```\n{text_content}\n```"

            # Extract any hashtags from content
            tags = self._extract_hashtags(text_content)

            # Add OneNote tag if detected
            if is_onenote and "onenote" not in tags:
                tags.append("onenote")

            # Get file metadata
            stat = zip_source.stat()
            created_time = datetime.fromtimestamp(stat.st_ctime)
            updated_time = datetime.fromtimestamp(stat.st_mtime)

            # Create imported note
            note = ImportedNote(
                title=title,
                body=body,
                created_time=created_time,
                updated_time=updated_time,
                tags=tags,
                notebook=None,
                metadata={
                    "original_format": "zip",
                    "source_file": str(zip_source),
                    "zip_path": str(zip_file_path),
                    "file_extension": extension,
                    "is_onenote": is_onenote,
                    "import_method": "zip_importer",
                },
            )

            return note

        except Exception as e:
            raise ImportProcessingError(
                f"Error processing extracted file {zip_file_path}: {str(e)}"
            ) from e

    def _decode_content(self, content: bytes) -> Optional[str]:
        """Decode binary content to text."""
        # Try different encodings
        encodings = ["utf-8", "utf-16", "latin-1", "cp1252", "iso-8859-1"]

        for encoding in encodings:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue

        return None

    def _extract_title(self, file_path: Path, content: str) -> str:
        """Extract title from filename or content."""
        # Try to find title in content first
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
            elif line and len(line) <= 100 and not line.startswith("#"):
                return line

        # Fall back to filename
        return file_path.stem.replace("_", " ").replace("-", " ")

    def _process_html_content(self, content: str) -> str:
        """Process HTML content."""
        try:
            import markdownify
            from bs4 import BeautifulSoup

            # Parse and convert HTML to Markdown
            soup = BeautifulSoup(content, "html.parser")

            # Remove script tags for security
            for script in soup.find_all("script"):
                script.decompose()

            # Convert to Markdown
            markdown = markdownify.markdownify(
                str(soup), heading_style="ATX", bullets="-", strip=["script", "style"]
            )

            return markdown.strip()

        except ImportError:
            # If BeautifulSoup/markdownify not available, return as code block
            return f"```html\n{content}\n```"

    def _convert_text_to_markdown(self, content: str, title: str) -> str:
        """Convert plain text to Markdown."""
        # Add title if not present
        if not content.startswith("#"):
            content = f"# {title}\n\n{content}"

        return content

    def _convert_csv_to_markdown(self, content: str, title: str) -> str:
        """Convert CSV content to Markdown table."""
        import csv
        from io import StringIO

        try:
            # Parse CSV
            csv_reader = csv.reader(StringIO(content))
            rows = list(csv_reader)

            if not rows:
                return f"# {title}\n\nEmpty CSV file."

            # Create Markdown table
            markdown_lines = [f"# {title}", "", "CSV Data:", ""]

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
            return f"# {title}\n\n```csv\n{content}\n```"

    def _extract_hashtags(self, content: str) -> List[str]:
        """Extract hashtags from content."""
        import re

        # Find hashtags in the content
        hashtag_pattern = r"#([a-zA-Z0-9_-]+)"
        hashtags = re.findall(hashtag_pattern, content)

        return list(set(hashtags))
