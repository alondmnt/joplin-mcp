"""
RAW (Joplin Export Directory) importer for Joplin MCP.

Handles RAW format which is Joplin's directory-based export format containing
Markdown files and a resources folder with attachments.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..types.import_types import ImportedNote
from .base import BaseImporter, ImportProcessingError, ImportValidationError


class RAWImporter(BaseImporter):
    """Importer for RAW (Joplin Export Directory) format."""

    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        # RAW format doesn't have extensions - it's directory-based
        return []

    def can_import(self, file_path: Path) -> bool:
        """Check if path can be imported as RAW format."""
        # RAW format is always a directory
        return file_path.is_dir()

    def supports_directory(self) -> bool:
        """RAW format only supports directory imports."""
        return True

    async def validate(self, source_path: str) -> bool:
        """Validate RAW directory can be processed."""
        path = Path(source_path)

        # Check path exists and is directory
        if not path.exists():
            raise ImportValidationError(f"RAW directory not found: {source_path}")

        if not path.is_dir():
            raise ImportValidationError(
                f"RAW format requires a directory: {source_path}"
            )

        # Check for RAW format structure
        has_md_files = any(path.glob("*.md"))
        resources_dir = path / "resources"

        if not has_md_files:
            raise ImportValidationError(
                f"No Markdown files found in RAW directory: {source_path}"
            )

        # Resources directory is optional but common
        if resources_dir.exists() and not resources_dir.is_dir():
            raise ImportValidationError(
                f"Resources path exists but is not a directory: {resources_dir}"
            )

        return True

    async def parse(self, source_path: str) -> List[ImportedNote]:
        """Parse RAW directory and convert to ImportedNote objects."""
        try:
            path = Path(source_path)

            # Find all markdown files
            md_files = list(path.glob("*.md"))

            if not md_files:
                raise ImportProcessingError(
                    f"No Markdown files found in RAW directory: {source_path}"
                )

            notes = []
            resources_dir = path / "resources"

            for md_file in md_files:
                try:
                    note = await self._parse_md_file(md_file, resources_dir)
                    if note:
                        notes.append(note)
                except Exception as e:
                    # Log error but continue with other files
                    print(f"Warning: Failed to parse {md_file}: {str(e)}")
                    continue

            return notes

        except Exception as e:
            if isinstance(e, (ImportValidationError, ImportProcessingError)):
                raise
            raise ImportProcessingError(
                f"Error parsing RAW directory {source_path}: {str(e)}"
            ) from e

    async def _parse_md_file(
        self, md_file: Path, resources_dir: Path
    ) -> Optional[ImportedNote]:
        """Parse a single Markdown file from RAW export."""
        try:
            # Read file content
            with open(md_file, encoding="utf-8") as f:
                content = f.read()

            # Extract metadata from filename or content
            title = self._extract_title(md_file, content)

            # Parse Joplin-specific metadata if present
            metadata, body = self._parse_joplin_metadata(content)

            # Process resource links if resources directory exists
            if resources_dir.exists():
                body = self._process_resource_links(body, resources_dir)

            # Extract timestamps from metadata or file stats
            created_time = self._parse_timestamp(
                metadata.get("created_time")
            ) or datetime.fromtimestamp(md_file.stat().st_ctime)
            updated_time = self._parse_timestamp(
                metadata.get("updated_time")
            ) or datetime.fromtimestamp(md_file.stat().st_mtime)

            # Extract tags
            tags = metadata.get("tags", [])
            if isinstance(tags, str):
                tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

            # Create imported note
            note = ImportedNote(
                title=title,
                body=body,
                created_time=created_time,
                updated_time=updated_time,
                tags=tags,
                notebook=metadata.get("notebook"),
                is_todo=metadata.get("is_todo", False),
                todo_completed=metadata.get("todo_completed", False),
                metadata={
                    "original_format": "raw",
                    "source_file": str(md_file),
                    "import_method": "raw_importer",
                    **metadata,
                },
            )

            return note

        except Exception as e:
            raise ImportProcessingError(
                f"Error parsing RAW file {md_file}: {str(e)}"
            ) from e

    def _extract_title(self, md_file: Path, content: str) -> str:
        """Extract title from filename or content."""
        # Try to find title in content first
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
            elif line and not line.startswith("#") and len(line) <= 100:
                # Use first substantial line as title
                return line

        # Fall back to filename
        return md_file.stem.replace("_", " ").replace("-", " ")

    def _parse_joplin_metadata(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse Joplin metadata from content."""
        metadata: Dict[str, Any] = {}

        # Look for YAML frontmatter
        if content.startswith("---\n"):
            try:
                end_marker = content.find("\n---\n", 4)
                if end_marker != -1:
                    frontmatter = content[4:end_marker]
                    try:
                        import yaml  # type: ignore

                        metadata = yaml.safe_load(frontmatter) or {}
                        content = content[end_marker + 5 :]  # Remove frontmatter
                    except ImportError:
                        pass  # YAML not available, skip frontmatter parsing
            except Exception:
                pass  # Continue without frontmatter parsing

        # Look for Joplin-specific metadata comments
        joplin_patterns = {
            "id": r"<!-- id: ([a-f0-9]+) -->",
            "created_time": r"<!-- created_time: ([0-9T:\-\.Z]+) -->",
            "updated_time": r"<!-- updated_time: ([0-9T:\-\.Z]+) -->",
            "is_todo": r"<!-- is_todo: (true|false) -->",
            "todo_completed": r"<!-- todo_completed: (true|false) -->",
            "notebook": r"<!-- notebook: ([^>]+) -->",
            "tags": r"<!-- tags: ([^>]+) -->",
        }

        for key, pattern in joplin_patterns.items():
            match = re.search(pattern, content)
            if match:
                value = match.group(1)
                if key in ["is_todo", "todo_completed"]:
                    metadata[key] = value.lower() == "true"
                else:
                    metadata[key] = value
                # Remove the comment from content
                content = re.sub(pattern, "", content)

        return metadata, content.strip()

    def _process_resource_links(self, content: str, resources_dir: Path) -> str:
        """Process resource links in content."""
        # Find Joplin resource links: ![](:/resource_id)
        resource_pattern = r"!\[([^\]]*)\]\(:\/([a-f0-9]+)\)"

        def replace_resource(match):
            alt_text = match.group(1)
            resource_id = match.group(2)

            # Find matching resource file
            resource_files = list(resources_dir.glob(f"{resource_id}.*"))
            if resource_files:
                resource_file = resource_files[0]
                # Convert to relative path or keep as reference
                return f"![{alt_text}](resources/{resource_file.name})"
            else:
                # Keep original if resource not found
                return match.group(0)

        return re.sub(resource_pattern, replace_resource, content)

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse timestamp from various formats."""
        if not timestamp_str:
            return None

        try:
            # Try ISO format first
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except Exception:
            try:
                # Try other common formats
                for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                    try:
                        return datetime.strptime(timestamp_str, fmt)
                    except ValueError:
                        continue
            except Exception:
                pass

        return None
