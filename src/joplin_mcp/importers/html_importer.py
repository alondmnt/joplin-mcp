"""HTML file importer for Joplin MCP server.

Converts HTML files to Markdown format suitable for Joplin import.
Supports both single HTML files and basic HTML document structures.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    import markdownify
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    raise ImportError(
        "HTML import requires additional dependencies. Install with: "
        "pip install beautifulsoup4 markdownify"
    )

from ..types.import_types import (
    ImportedNote,
    ImportProcessingError,
    ImportValidationError,
)
from .base import BaseImporter

logger = logging.getLogger(__name__)


class HTMLImporter(BaseImporter):
    """Importer for HTML files with conversion to Markdown."""

    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return ["html", "htm"]

    async def validate(self, file_path: str) -> None:
        """Validate HTML file can be processed."""
        path = Path(file_path)

        # Check file exists and is readable
        if not path.exists():
            raise ImportValidationError(f"HTML file not found: {file_path}")

        if not path.is_file():
            raise ImportValidationError(f"Path is not a file: {file_path}")

        # Check file extension
        if path.suffix.lower() not in self.get_supported_extensions():
            raise ImportValidationError(
                f"Unsupported HTML file extension: {path.suffix}"
            )

        # Try to read file with different encodings
        content = None
        for encoding in [self.options.encoding, "utf-8", "latin-1", "cp1252"]:
            try:
                with open(file_path, encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            raise ImportValidationError(
                f"Could not read HTML file with any supported encoding: {file_path}"
            )

        # Basic HTML validation - check for HTML structure
        if not any(
            tag in content.lower()
            for tag in ["<html", "<head", "<body", "<div", "<p", "<h1", "<h2"]
        ):
            logger.warning(
                f"File may not be valid HTML (no common HTML tags found): {file_path}"
            )

    async def parse(self, file_path: str) -> List[ImportedNote]:
        """Parse HTML file and convert to ImportedNote objects."""
        try:
            path = Path(file_path)

            # Read HTML content with proper encoding
            content = None
            used_encoding = None
            for encoding in [self.options.encoding, "utf-8", "latin-1", "cp1252"]:
                try:
                    with open(file_path, encoding=encoding) as f:
                        content = f.read()
                    used_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                raise ImportProcessingError(f"Could not read HTML file: {file_path}")

            logger.info(f"Read HTML file with {used_encoding} encoding: {file_path}")

            # Parse HTML with BeautifulSoup
            try:
                soup = BeautifulSoup(content, "html.parser")
            except Exception as e:
                raise ImportProcessingError(f"Failed to parse HTML: {str(e)}")

            # Extract metadata and content
            note_data = await self._extract_note_data(soup, path)

            # Convert HTML to Markdown
            markdown_content = await self._convert_to_markdown(soup, note_data)

            # Create ImportedNote
            note = ImportedNote(
                title=note_data["title"],
                body=markdown_content,
                notebook=note_data.get("notebook"),
                tags=note_data.get("tags", []),
                created_time=note_data.get("created_time"),
                updated_time=note_data.get("updated_time"),
                is_todo=False,
                metadata={
                    "original_format": "html",
                    "original_file": str(path),
                    "encoding": used_encoding,
                    "html_title": note_data.get("html_title"),
                    "description": note_data.get("description"),
                    "author": note_data.get("author"),
                },
            )

            return [note]

        except Exception as e:
            if isinstance(e, (ImportValidationError, ImportProcessingError)):
                raise
            raise ImportProcessingError(f"HTML import failed: {str(e)}")

    async def _extract_note_data(self, soup: BeautifulSoup, path: Path) -> dict:
        """Extract metadata and title from HTML document."""
        note_data = {}

        # Extract title - priority: <title> tag > <h1> > filename
        title = None

        # Try <title> tag first
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title = title_tag.string.strip()

        # Try first <h1> tag if no title
        if not title:
            h1_tag = soup.find("h1")
            if h1_tag:
                title = h1_tag.get_text().strip()

        # Use filename if no title found
        if not title:
            title = path.stem

        note_data["title"] = title
        note_data["html_title"] = (
            title_tag.string.strip() if title_tag and title_tag.string else None
        )

        # Extract meta tags
        meta_tags = soup.find_all("meta")
        for meta in meta_tags:
            name = meta.get("name", "").lower()
            content = meta.get("content", "").strip()

            if not content:
                continue

            if name == "description":
                note_data["description"] = content
            elif name == "author":
                note_data["author"] = content
            elif name == "keywords":
                # Convert keywords to tags
                keywords = [k.strip() for k in content.split(",") if k.strip()]
                note_data["tags"] = keywords
            elif name in ["created", "date"]:
                # Try to parse creation date
                try:
                    note_data["created_time"] = self._parse_date(content)
                except:
                    pass
            elif name == "modified":
                # Try to parse modified date
                try:
                    note_data["updated_time"] = self._parse_date(content)
                except:
                    pass

        # Extract notebook from directory structure if not specified
        if not note_data.get("notebook"):
            notebook = self._extract_notebook_from_path(path)
            if notebook:
                note_data["notebook"] = notebook

        # Set default timestamps from file if not found in meta
        if not note_data.get("created_time"):
            try:
                note_data["created_time"] = datetime.fromtimestamp(path.stat().st_ctime)
            except:
                pass

        if not note_data.get("updated_time"):
            try:
                note_data["updated_time"] = datetime.fromtimestamp(path.stat().st_mtime)
            except:
                pass

        return note_data

    async def _convert_to_markdown(self, soup: BeautifulSoup, note_data: dict) -> str:
        """Convert HTML content to Markdown."""
        try:
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get body content, or entire document if no body
            body = soup.find("body")
            if body:
                content_element = body
            else:
                content_element = soup

            # Remove title from content if it matches our extracted title
            title = note_data.get("title", "")
            if title:
                # Remove h1 that matches title to avoid duplication
                for h1 in content_element.find_all("h1"):
                    if h1.get_text().strip() == title:
                        h1.decompose()
                        break

            # Convert to markdown using markdownify
            markdown_content = markdownify.markdownify(
                str(content_element),
                heading_style="ATX",  # Use # style headings
                bullets="-",  # Use - for bullets
                # Note: Cannot use both strip and convert parameters
                convert=[
                    "p",
                    "div",
                    "br",
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                    "strong",
                    "b",
                    "em",
                    "i",
                    "u",
                    "code",
                    "pre",
                    "ul",
                    "ol",
                    "li",
                    "blockquote",
                    "a",
                    "img",
                    "table",
                    "thead",
                    "tbody",
                    "tr",
                    "th",
                    "td",
                ],
            )

            # Clean up the markdown
            markdown_content = self._clean_markdown(markdown_content)

            # Add metadata comment at the top if we have interesting metadata
            metadata_lines = []
            if note_data.get("description"):
                metadata_lines.append(f"**Description:** {note_data['description']}")
            if note_data.get("author"):
                metadata_lines.append(f"**Author:** {note_data['author']}")

            if metadata_lines:
                markdown_content = (
                    "\n".join(metadata_lines) + "\n\n---\n\n" + markdown_content
                )

            return markdown_content.strip()

        except Exception as e:
            raise ImportProcessingError(f"HTML to Markdown conversion failed: {str(e)}")

    def _clean_markdown(self, markdown: str) -> str:
        """Clean up converted markdown content."""
        # Remove excessive whitespace
        markdown = re.sub(r"\n\s*\n\s*\n", "\n\n", markdown)

        # Remove trailing whitespace from lines
        lines = [line.rstrip() for line in markdown.split("\n")]
        markdown = "\n".join(lines)

        # Remove leading/trailing whitespace
        markdown = markdown.strip()

        # Fix common conversion issues
        markdown = re.sub(r"\*\*\s+", "**", markdown)  # Fix bold formatting
        markdown = re.sub(r"\s+\*\*", "**", markdown)
        markdown = re.sub(r"\*\s+", "*", markdown)  # Fix italic formatting
        markdown = re.sub(r"\s+\*", "*", markdown)

        # Clean up links
        markdown = re.sub(r"\[\s+", "[", markdown)
        markdown = re.sub(r"\s+\]", "]", markdown)

        return markdown

    def _parse_date(self, date_string: str) -> Optional[datetime]:
        """Parse various date formats commonly found in HTML meta tags."""
        date_string = date_string.strip()

        # Common date formats to try
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d.%m.%Y",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d %B %Y",
            "%d %b %Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue

        # If no format matches, return None
        return None

    def _extract_notebook_from_path(self, path: Path) -> Optional[str]:
        """Extract notebook name from file path directory structure."""
        if not self.options.preserve_directory_structure:
            return None

        # Use parent directory name as notebook
        parent = path.parent
        if parent.name and parent.name != ".":
            return parent.name

        return None
