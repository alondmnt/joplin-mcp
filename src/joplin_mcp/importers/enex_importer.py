"""
ENEX (Evernote Export) importer for Joplin MCP.

Handles ENEX files by parsing XML structure and converting notes to Markdown format.
Supports both HTML and Markdown output modes based on configuration.
"""

import re
import warnings
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    import markdownify
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

    # Suppress XML parsing warnings for ENEX content
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except ImportError as e:
    raise ImportError(
        "ENEX import requires additional dependencies. Install with: "
        "pip install beautifulsoup4 markdownify"
    ) from e

from ..types.import_types import ImportedNote
from .base import BaseImporter, ImportProcessingError, ImportValidationError
from .utils import html_to_markdown


class ENEXImporter(BaseImporter):
    """Importer for ENEX (Evernote Export) files."""

    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return ["enex"]

    def can_import(self, file_path: Path) -> bool:
        """Check if file can be imported as ENEX."""
        extension = file_path.suffix.lower().lstrip(".")
        return extension in self.get_supported_extensions()

    def supports_directory(self) -> bool:
        """ENEX format supports both files and directories containing ENEX files."""
        return True

    async def validate(self, source_path: str) -> bool:
        """Validate ENEX file or directory can be processed."""
        path = Path(source_path)

        if path.is_file():
            # Use enhanced base class validation
            self.validate_file_comprehensive(path)
            # Additional ENEX-specific validation
            await self._validate_enex_structure(path)
        elif path.is_dir():
            # Use enhanced base class validation
            self.validate_directory_comprehensive(path)
        else:
            from .base import ImportValidationError
            raise ImportValidationError(
                f"Path is neither file nor directory: {source_path}"
            )

        return True

    async def _validate_enex_structure(self, file_path: Path) -> None:
        """Validate ENEX-specific XML structure."""
        # Read file content using enhanced base class utilities
        content, _ = self.read_file_safe(file_path)

        # Parse XML and validate ENEX structure
        try:
            root = ET.fromstring(content)

            # Check if it's a valid ENEX file
            if root.tag != "en-export":
                from .base import ImportValidationError
                raise ImportValidationError(
                    f"File is not a valid ENEX export (root element: {root.tag})"
                )

            # Check for at least one note
            notes = root.findall("note")
            if not notes:
                from .base import ImportValidationError
                raise ImportValidationError(f"ENEX file contains no notes: {file_path}")

        except ET.ParseError as e:
            from .base import ImportValidationError
            raise ImportValidationError(f"Invalid XML in ENEX file: {str(e)}") from e

    async def parse(self, source_path: str) -> List[ImportedNote]:
        """Parse ENEX file or directory and convert to ImportedNote objects."""
        path = Path(source_path)

        if path.is_file():
            # Parse single ENEX file
            return await self._parse_enex_file(path)
        elif path.is_dir():
            # Parse all ENEX files in directory using enhanced base class
            all_notes = []
            enex_files = self.scan_directory_safe(path)

            for enex_file in enex_files:
                try:
                    notes = await self._parse_enex_file(enex_file)
                    all_notes.extend(notes)
                except Exception as e:
                    # Log error but continue with other files
                    print(f"Warning: Failed to parse {enex_file}: {str(e)}")
                    continue

            return all_notes
        else:
            from .base import ImportProcessingError
            raise ImportProcessingError(
                f"Source is neither file nor directory: {source_path}"
            )

    async def _parse_enex_file(self, file_path: Path) -> List[ImportedNote]:
        """Parse a single ENEX file and convert to ImportedNote objects."""
        # Read ENEX content using enhanced base class utilities
        content, used_encoding = self.read_file_safe(file_path)

        # Parse XML
        root = ET.fromstring(content)

        # Extract notes
        notes = []
        note_elements = root.findall("note")

        for i, note_elem in enumerate(note_elements):
            try:
                imported_note = self._parse_note_element(
                    note_elem, file_path, used_encoding, i + 1
                )
                if imported_note:
                    notes.append(imported_note)
            except Exception as e:
                # Log error but continue with other notes
                print(
                    f"Warning: Failed to parse note {i + 1} from {file_path}: {str(e)}"
                )
                continue

        return notes

    def _parse_note_element(
        self, note_elem: ET.Element, source_path: Path, encoding: str, note_number: int
    ) -> Optional[ImportedNote]:
        """Parse a single note element from ENEX."""
        try:
            # Extract basic note information
            title_elem = note_elem.find("title")
            title = (
                title_elem.text
                if title_elem is not None and title_elem.text
                else f"Untitled Note {note_number}"
            )

            content_elem = note_elem.find("content")
            if content_elem is None or not content_elem.text:
                # Skip notes without content
                return None

            # Get raw content (it's usually HTML wrapped in CDATA)
            raw_content = content_elem.text.strip()

            # Convert content based on output mode preference
            output_mode = getattr(self.options, "enex_output_mode", "markdown")
            if output_mode == "html":
                body = self._process_html_content(raw_content)
            else:
                body = self._convert_to_markdown(raw_content, title)

            # Parse timestamps
            created_time = self._parse_timestamp(note_elem.find("created"))
            updated_time = self._parse_timestamp(note_elem.find("updated"))

            # Extract tags
            tags = self._extract_tags(note_elem)

            # Extract notebook (if specified)
            notebook = self._extract_notebook(note_elem)

            # Prepare additional metadata
            additional_metadata = {
                "encoding": encoding,
                "original_format": "enex",
                "output_mode": output_mode,
                "note_number": note_number,
            }

            # Add source URL if present
            source_url_elem = note_elem.find("source-url")
            if source_url_elem is not None and source_url_elem.text:
                additional_metadata["source_url"] = source_url_elem.text

            # Add author if present
            author_elem = note_elem.find("author")
            if author_elem is not None and author_elem.text:
                additional_metadata["author"] = author_elem.text

            # Create note using enhanced base class utilities
            return self.create_imported_note_safe(
                title=title,
                body=body,
                file_path=source_path,
                tags=tags,
                notebook=notebook,
                created_time=created_time,
                updated_time=updated_time,
                additional_metadata=additional_metadata,
            )

        except Exception as e:
            raise ImportProcessingError(f"Error parsing note element: {str(e)}") from e

    def _process_html_content(self, raw_content: str) -> str:
        """Process HTML content for HTML output mode."""
        # Clean up the HTML content
        soup = BeautifulSoup(raw_content, "html.parser")

        # Remove any script tags for security
        for script in soup.find_all("script"):
            script.decompose()

        # Clean up the HTML
        cleaned_html = str(soup)

        return cleaned_html

    def _convert_to_markdown(self, raw_content: str, title: str) -> str:
        """Convert HTML content to Markdown using shared utility with ENEX-specific pre-processing."""
        try:
            # ENEX-specific pre-processing: Clean the raw content first
            # This removes XML declarations, DOCTYPE, and <en-note> wrapper tags
            cleaned_content = self._clean_enex_content(raw_content)

            # Use shared HTML to Markdown conversion utility
            # This provides consistent conversion logic, better cleanup, and robust fallback
            markdown = html_to_markdown(cleaned_content, title)

            return markdown.strip()

        except Exception:
            # Fallback: return cleaned text with title
            try:
                soup = BeautifulSoup(raw_content, "html.parser")
                cleaned_text = soup.get_text()
                return f"# {title}\n\n{cleaned_text}"
            except Exception:
                # Ultimate fallback
                return f"# {title}\n\n{raw_content}"


    def _clean_enex_content(self, content: str) -> str:
        """Clean ENEX content by removing XML declarations and DOCTYPE."""
        # Remove XML declaration
        content = re.sub(r"<\?xml[^>]*\?>", "", content)

        # Remove DOCTYPE declaration
        content = re.sub(r"<!DOCTYPE[^>]*>", "", content)

        # Remove en-note wrapper tags but keep content
        content = re.sub(r"</?en-note[^>]*>", "", content)

        # Clean up extra whitespace
        content = re.sub(r"\s+", " ", content)
        content = content.strip()

        return content

    def _parse_timestamp(
        self, timestamp_elem: Optional[ET.Element]
    ) -> Optional[datetime]:
        """Parse Evernote timestamp format."""
        if timestamp_elem is None or not timestamp_elem.text:
            return None

        try:
            # Evernote timestamps are in format: YYYYMMDDTHHMMSSZ
            timestamp_str = timestamp_elem.text

            # Handle different timestamp formats
            if "T" in timestamp_str:
                # Format: 20230101T120000Z
                clean_timestamp = timestamp_str.replace("T", "").replace("Z", "")
                if len(clean_timestamp) >= 14:
                    return datetime.strptime(clean_timestamp[:14], "%Y%m%d%H%M%S")
            else:
                # Try other common formats
                for fmt in ["%Y%m%d%H%M%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
                    try:
                        return datetime.strptime(timestamp_str, fmt)
                    except ValueError:
                        continue

            return None

        except Exception:
            return None

    def _extract_tags(self, note_elem: ET.Element) -> List[str]:
        """Extract tags from note element."""
        tags = []

        # Look for tag elements
        for tag_elem in note_elem.findall("tag"):
            if tag_elem.text:
                tags.append(tag_elem.text.strip())

        # Also look for tags in attributes (some ENEX variants)
        tag_attr = note_elem.get("tags")
        if tag_attr:
            tags.extend([tag.strip() for tag in tag_attr.split(",") if tag.strip()])

        return list(set(tags))  # Remove duplicates

    def _extract_notebook(self, note_elem: ET.Element) -> Optional[str]:
        """Extract notebook name from note element."""
        # Look for notebook element
        notebook_elem = note_elem.find("notebook")
        if notebook_elem is not None and notebook_elem.text:
            return notebook_elem.text.strip()

        # Look for notebook attribute
        notebook_attr = note_elem.get("notebook")
        if notebook_attr:
            return notebook_attr.strip()

        return None
