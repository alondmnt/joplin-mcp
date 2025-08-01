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

        # Check source exists and is readable
        if not path.exists():
            raise ImportValidationError(f"ENEX source not found: {source_path}")

        if path.is_file():
            # Validate single ENEX file
            extension = path.suffix.lower().lstrip(".")
            if extension not in self.get_supported_extensions():
                raise ImportValidationError(
                    f"Unsupported ENEX file extension: {path.suffix}"
                )
            # Validate it's a valid XML file
            await self._validate_enex_file(path)

        elif path.is_dir():
            # Validate directory contains ENEX files
            enex_files = list(path.rglob("*.enex"))
            if not enex_files:
                raise ImportValidationError(
                    f"No ENEX files found in directory: {source_path}"
                )
            # Validate at least one ENEX file is valid
            for enex_file in enex_files[:3]:  # Check first 3 files for performance
                try:
                    await self._validate_enex_file(enex_file)
                    break  # If one is valid, assume others are too
                except ImportValidationError:
                    continue
            else:
                raise ImportValidationError(
                    f"No valid ENEX files found in directory: {source_path}"
                )
        else:
            raise ImportValidationError(
                f"Path is neither file nor directory: {source_path}"
            )

        return True

    async def _validate_enex_file(self, file_path: Path) -> None:
        """Validate a single ENEX file's XML structure."""
        if file_path.stat().st_size == 0:
            raise ImportValidationError(f"File is empty: {file_path}")

        # Try to parse as XML and validate ENEX structure
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Parse XML
            root = ET.fromstring(content)

            # Check if it's a valid ENEX file
            if root.tag != "en-export":
                raise ImportValidationError(
                    f"File is not a valid ENEX export (root element: {root.tag})"
                )

            # Check for at least one note
            notes = root.findall("note")
            if not notes:
                raise ImportValidationError(f"ENEX file contains no notes: {file_path}")

        except ET.ParseError as e:
            raise ImportValidationError(f"Invalid XML in ENEX file: {str(e)}") from e
        except UnicodeDecodeError:
            # Try other encodings
            for encoding in ["latin-1", "cp1252", "iso-8859-1"]:
                try:
                    with open(file_path, encoding=encoding) as f:
                        content = f.read()
                    root = ET.fromstring(content)
                    break
                except (UnicodeDecodeError, ET.ParseError):
                    continue
            else:
                raise ImportValidationError(
                    f"Unable to decode ENEX file with common encodings: {file_path}"
                )
        except Exception as e:
            raise ImportValidationError(f"Error reading ENEX file: {str(e)}") from e

    async def parse(self, source_path: str) -> List[ImportedNote]:
        """Parse ENEX file or directory and convert to ImportedNote objects."""
        try:
            path = Path(source_path)

            if path.is_file():
                # Parse single ENEX file
                return await self._parse_enex_file(path)
            elif path.is_dir():
                # Parse all ENEX files in directory
                all_notes = []
                enex_files = list(path.rglob("*.enex"))

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
                raise ImportProcessingError(
                    f"Source is neither file nor directory: {source_path}"
                )

        except Exception as e:
            if isinstance(e, (ImportValidationError, ImportProcessingError)):
                raise
            raise ImportProcessingError(f"ENEX import failed: {str(e)}") from e

    async def _parse_enex_file(self, file_path: Path) -> List[ImportedNote]:
        """Parse a single ENEX file and convert to ImportedNote objects."""
        # Read ENEX content with proper encoding
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
                f"Could not read ENEX file with any supported encoding: {file_path}"
            )

        # Parse XML
        root = ET.fromstring(content)

        # Extract notes
        notes = []
        note_elements = root.findall("note")

        for i, note_elem in enumerate(note_elements):
            try:
                imported_note = self._parse_note_element(
                    note_elem, file_path, used_encoding or "utf-8", i + 1
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

            # Extract additional metadata
            metadata = {
                "original_format": "enex",
                "source_file": str(source_path),
                "encoding": encoding,
                "import_method": "enex_importer",
                "output_mode": output_mode,
                "note_number": note_number,
            }

            # Add source URL if present
            source_url_elem = note_elem.find("source-url")
            if source_url_elem is not None and source_url_elem.text:
                metadata["source_url"] = source_url_elem.text

            # Add author if present
            author_elem = note_elem.find("author")
            if author_elem is not None and author_elem.text:
                metadata["author"] = author_elem.text

            # Create the imported note
            note = ImportedNote(
                title=title,
                body=body,
                created_time=created_time,
                updated_time=updated_time,
                tags=tags,
                notebook=notebook,
                metadata=metadata,
            )

            return note

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
        """Convert HTML content to Markdown."""
        try:
            # Clean the raw content first
            cleaned_content = self._clean_enex_content(raw_content)

            # Parse HTML content
            soup = BeautifulSoup(cleaned_content, "html.parser")

            # Remove script tags for security
            for script in soup.find_all("script"):
                script.decompose()

            # Convert to Markdown using markdownify
            markdown = markdownify.markdownify(
                str(soup),
                heading_style="ATX",  # Use # style headers
                bullets="-",  # Use - for bullets
                strip=["script", "style"],  # Strip these elements
            )

            # Clean up the markdown
            markdown = self._clean_markdown(markdown)

            # Add title if not already present
            if not markdown.startswith("#"):
                markdown = f"# {title}\n\n{markdown}"

            return markdown.strip()

        except Exception:
            # Fallback: return cleaned text
            soup = BeautifulSoup(raw_content, "html.parser")
            cleaned_text = soup.get_text()
            return f"# {title}\n\n{cleaned_text}"

    def _clean_markdown(self, markdown: str) -> str:
        """Clean up markdown formatting."""
        # Remove excessive whitespace
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)

        # Clean up list formatting
        markdown = re.sub(r"\n\s*\n\s*-", "\n-", markdown)

        # Remove empty list items
        markdown = re.sub(r"\n-\s*\n", "\n", markdown)

        return markdown.strip()

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
