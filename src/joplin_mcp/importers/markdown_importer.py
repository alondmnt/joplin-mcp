"""Markdown file importer for Joplin MCP server."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ..types.import_types import ImportedNote
from .base import BaseImporter, ImportProcessingError, ImportValidationError


class MarkdownImporter(BaseImporter):
    """Importer for Markdown files with optional frontmatter support.

    Supports:
    - Plain Markdown files (.md, .markdown)
    - Frontmatter metadata (YAML header)
    - Directory structure preservation
    - Tag extraction from frontmatter
    - Notebook assignment from directory structure
    """

    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return ["md", "markdown", "mdown", "mkd"]

    async def validate(self, source: str) -> bool:
        """Validate that the source can be imported."""
        self.validate_source_exists(source)
        self.validate_source_readable(source)

        path = Path(source)

        if path.is_file():
            # Validate single file
            if not self.supports_file(source):
                raise ImportValidationError(
                    f"File extension not supported: {path.suffix}"
                )
            self.validate_file_size(
                source, self.options.import_options.get("max_file_size_mb", 100)
            )
            return True

        elif path.is_dir():
            # Validate directory has at least one supported file
            files = await self.get_file_list(source)
            if not files:
                raise ImportValidationError(
                    f"No supported markdown files found in: {source}"
                )

            # Check total size
            total_size = sum(Path(f).stat().st_size for f in files) / (1024 * 1024)
            max_total_size = self.options.import_options.get("max_total_size_mb", 500)
            if total_size > max_total_size:
                raise ImportValidationError(
                    f"Total directory size too large: {total_size:.1f}MB (max: {max_total_size}MB)"
                )

            return True

        raise ImportValidationError(f"Source is neither file nor directory: {source}")

    async def parse(self, source: str) -> List[ImportedNote]:
        """Parse markdown files and return ImportedNote objects."""
        path = Path(source)
        notes = []

        if path.is_file():
            # Parse single file
            note = await self._parse_markdown_file(str(path), str(path.parent))
            if note:
                notes.append(note)

        elif path.is_dir():
            # Parse directory
            files = await self.get_file_list(source)
            for file_path in files:
                try:
                    note = await self._parse_markdown_file(file_path, source)
                    if note:
                        notes.append(note)
                except Exception as e:
                    # Log error but continue processing other files
                    print(f"Warning: Failed to parse {file_path}: {e}")

        return notes

    async def _parse_markdown_file(
        self, file_path: str, base_path: str
    ) -> Optional[ImportedNote]:
        """Parse a single markdown file."""
        try:
            path = Path(file_path)

            # Read file content
            with open(path, encoding=self.options.encoding) as f:
                content = f.read()

            # Extract frontmatter and content
            frontmatter, body = self._extract_frontmatter(content)

            # Generate title
            title = self._extract_title(frontmatter, body, path.stem)

            # Extract notebook from directory structure
            notebook = self.extract_notebook_from_path(file_path, base_path)
            if frontmatter.get("notebook"):
                notebook = frontmatter["notebook"]

            # Extract tags
            tags = self._extract_tags(frontmatter, body)

            # Extract metadata
            is_todo = frontmatter.get("todo", False) or frontmatter.get(
                "is_todo", False
            )
            todo_completed = frontmatter.get("completed", False) or frontmatter.get(
                "todo_completed", False
            )

            # Extract timestamps
            created_time = self._parse_timestamp(
                frontmatter.get("created", frontmatter.get("date"))
            )
            updated_time = self._parse_timestamp(
                frontmatter.get("updated", frontmatter.get("modified"))
            )

            # Use file timestamps as fallback
            if not created_time:
                created_time = datetime.fromtimestamp(path.stat().st_ctime)
            if not updated_time:
                updated_time = datetime.fromtimestamp(path.stat().st_mtime)

            # Create ImportedNote
            note = ImportedNote(
                title=title,
                body=body,
                notebook=notebook,
                tags=tags,
                is_todo=is_todo,
                todo_completed=todo_completed,
                created_time=created_time,
                updated_time=updated_time,
                metadata={
                    "source_file": str(path),
                    "frontmatter": frontmatter,
                    "file_size": path.stat().st_size,
                },
            )

            return note

        except Exception as e:
            raise ImportProcessingError(
                f"Failed to parse markdown file {file_path}: {str(e)}"
            )

    def _extract_frontmatter(self, content: str) -> tuple[Dict[str, Any], str]:
        """Extract YAML frontmatter from markdown content."""
        frontmatter = {}
        body = content

        # Check for YAML frontmatter (--- at start)
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()
                except yaml.YAMLError:
                    # If YAML parsing fails, treat as regular content
                    pass

        return frontmatter, body

    def _extract_title(
        self, frontmatter: Dict[str, Any], body: str, filename_fallback: str
    ) -> str:
        """Extract title from frontmatter, body, or filename."""
        # Try frontmatter first
        title = frontmatter.get("title")
        if title:
            return str(title).strip()

        # Try first heading in body
        lines = body.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("#"):
                # Extract heading text
                title = re.sub(r"^#+\s*", "", line).strip()
                if title:
                    return title

        # Try first non-empty line
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                # Use first 100 characters as title
                return line[:100].strip()

        # Fallback to filename
        return filename_fallback.replace("_", " ").replace("-", " ").title()

    def _extract_tags(self, frontmatter: Dict[str, Any], body: str) -> List[str]:
        """Extract tags from frontmatter and body."""
        tags = []

        # From frontmatter
        fm_tags = frontmatter.get("tags", frontmatter.get("categories", []))
        if isinstance(fm_tags, str):
            # Handle comma-separated tags
            tags.extend([tag.strip() for tag in fm_tags.split(",") if tag.strip()])
        elif isinstance(fm_tags, list):
            tags.extend([str(tag).strip() for tag in fm_tags if tag])

        # From body (hashtags)
        if self.options.import_options.get("extract_hashtags", True):
            hashtag_pattern = r"#([a-zA-Z0-9_-]+)"
            hashtags = re.findall(hashtag_pattern, body)
            tags.extend(hashtags)

        # Remove duplicates and empty tags
        return list(set(tag for tag in tags if tag))

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse timestamp string to datetime object."""
        if not timestamp_str:
            return None

        # Try different timestamp formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y/%m/%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
        ]

        timestamp_str = str(timestamp_str).strip()

        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue

        # If all formats fail, return None
        return None
