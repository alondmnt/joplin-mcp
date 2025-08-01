"""JEX (Joplin Export) file importer for Joplin MCP server."""

import json
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..types.import_types import ImportedNote
from .base import BaseImporter, ImportProcessingError, ImportValidationError


class JEXImporter(BaseImporter):
    """Importer for JEX (Joplin Export) files.

    JEX format is a TAR archive containing:
    - Individual .md files for each note
    - JSON metadata files for notes, notebooks, tags
    - Resources (attachments) as separate files
    - Directory structure representing notebooks

    This is Joplin's native lossless export format.
    """

    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return ["jex"]

    def supports_directory(self) -> bool:
        """JEX format only supports individual files (TAR archives)."""
        return False

    async def validate(self, source: str) -> bool:
        """Validate that the source is a valid JEX file."""
        self.validate_source_exists(source)
        self.validate_source_readable(source)

        path = Path(source)
        if not path.is_file():
            raise ImportValidationError(
                f"JEX format requires a single TAR archive file, not a directory. "
                f"Path '{source}' is not a file. Use RAWImporter for directory exports."
            )

        if not self.supports_file(source):
            raise ImportValidationError(f"File extension not supported: {path.suffix}")

        # Validate file size
        self.validate_file_size(
            source, self.options.import_options.get("max_file_size_mb", 500)
        )

        # Validate it's a valid TAR file
        try:
            with tarfile.open(source, "r") as tar:
                # Check if it looks like a JEX file
                members = tar.getnames()
                if not members:
                    raise ImportValidationError("JEX file appears to be empty")

                # Look for expected JEX structure (should have some .md files or .json metadata)
                has_md_files = any(name.endswith(".md") for name in members)
                has_json_files = any(name.endswith(".json") for name in members)

                if not (has_md_files or has_json_files):
                    raise ImportValidationError(
                        "JEX file does not contain expected .md or .json files"
                    )

        except tarfile.TarError as e:
            raise ImportValidationError(
                f"Invalid JEX file (not a valid TAR archive): {str(e)}"
            )

        return True

    async def parse(self, source: str) -> List[ImportedNote]:
        """Parse JEX file and return ImportedNote objects."""
        notes = []

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract JEX archive
                with tarfile.open(source, "r") as tar:
                    tar.extractall(temp_path)

                # Parse extracted content
                notes = await self._parse_extracted_jex(temp_path)

        except Exception as e:
            raise ImportProcessingError(f"Failed to parse JEX file {source}: {str(e)}")

        return notes

    async def _parse_extracted_jex(self, extract_path: Path) -> List[ImportedNote]:
        """Parse extracted JEX directory structure."""
        notes = []

        # Load metadata files
        notebooks_map = await self._load_notebooks_metadata(extract_path)
        tags_map = await self._load_tags_metadata(extract_path)
        resources_map = await self._load_resources_metadata(extract_path)

        # Find and parse all note files
        for md_file in extract_path.rglob("*.md"):
            try:
                note = await self._parse_jex_note(
                    md_file, extract_path, notebooks_map, tags_map, resources_map
                )
                if note:
                    notes.append(note)
            except Exception as e:
                print(f"Warning: Failed to parse note {md_file}: {e}")

        return notes

    async def _load_notebooks_metadata(
        self, extract_path: Path
    ) -> Dict[str, Dict[str, Any]]:
        """Load notebooks metadata from JSON files."""
        notebooks = {}

        # Look for notebook metadata files
        for json_file in extract_path.rglob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)

                # Check if this is a notebook metadata file
                if (
                    isinstance(data, dict) and data.get("type_") == 2
                ):  # Type 2 = Notebook in Joplin
                    notebooks[data.get("id", "")] = data

            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

        return notebooks

    async def _load_tags_metadata(
        self, extract_path: Path
    ) -> Dict[str, Dict[str, Any]]:
        """Load tags metadata from JSON files."""
        tags = {}

        for json_file in extract_path.rglob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)

                # Check if this is a tag metadata file
                if (
                    isinstance(data, dict) and data.get("type_") == 5
                ):  # Type 5 = Tag in Joplin
                    tags[data.get("id", "")] = data

            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

        return tags

    async def _load_resources_metadata(
        self, extract_path: Path
    ) -> Dict[str, Dict[str, Any]]:
        """Load resources (attachments) metadata from JSON files."""
        resources = {}

        for json_file in extract_path.rglob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)

                # Check if this is a resource metadata file
                if (
                    isinstance(data, dict) and data.get("type_") == 4
                ):  # Type 4 = Resource in Joplin
                    resources[data.get("id", "")] = data

            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

        return resources

    async def _parse_jex_note(
        self,
        md_file: Path,
        extract_path: Path,
        notebooks_map: Dict[str, Dict[str, Any]],
        tags_map: Dict[str, Dict[str, Any]],
        resources_map: Dict[str, Dict[str, Any]],
    ) -> Optional[ImportedNote]:
        """Parse a single note from JEX extraction."""

        # Load note metadata
        json_file = md_file.with_suffix(".json")
        note_metadata = {}

        if json_file.exists():
            try:
                with open(json_file, encoding="utf-8") as f:
                    note_metadata = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        # Read note content
        try:
            with open(md_file, encoding="utf-8") as f:
                body = f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(md_file, encoding="latin-1") as f:
                body = f.read()

        # Extract note information
        title = note_metadata.get("title", md_file.stem)

        # Determine notebook
        notebook = None
        parent_id = note_metadata.get("parent_id")
        if parent_id and parent_id in notebooks_map:
            notebook = notebooks_map[parent_id].get("title")

        # Extract tags (need to find note-tag relationships)
        tags = await self._extract_note_tags(
            note_metadata.get("id", ""), extract_path, tags_map
        )

        # Extract timestamps
        created_time = self._parse_joplin_timestamp(note_metadata.get("created_time"))
        updated_time = self._parse_joplin_timestamp(note_metadata.get("updated_time"))

        # Extract todo information
        is_todo = note_metadata.get("is_todo", 0) == 1
        todo_completed = note_metadata.get("todo_completed", 0) > 0

        # Process attachments/resources
        processed_body = await self._process_note_attachments(
            body, resources_map, extract_path
        )

        # Create ImportedNote
        note = ImportedNote(
            title=title,
            body=processed_body,
            notebook=notebook,
            tags=tags,
            is_todo=is_todo,
            todo_completed=todo_completed,
            created_time=created_time,
            updated_time=updated_time,
            metadata={
                "source_file": str(md_file),
                "joplin_id": note_metadata.get("id", ""),
                "joplin_metadata": note_metadata,
                "original_parent_id": parent_id,
            },
        )

        return note

    async def _extract_note_tags(
        self, note_id: str, extract_path: Path, tags_map: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        """Extract tags for a specific note by finding note-tag relationships."""
        tags = []

        if not note_id:
            return tags

        # Look for note-tag relationship files
        for json_file in extract_path.rglob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)

                # Check if this is a note-tag relationship (type 6 in Joplin)
                if (
                    isinstance(data, dict)
                    and data.get("type_") == 6
                    and data.get("note_id") == note_id
                ):

                    tag_id = data.get("tag_id")
                    if tag_id and tag_id in tags_map:
                        tag_title = tags_map[tag_id].get("title")
                        if tag_title:
                            tags.append(tag_title)

            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

        return tags

    def _parse_joplin_timestamp(self, timestamp: Optional[Any]) -> Optional[datetime]:
        """Parse Joplin timestamp (milliseconds since epoch) to datetime."""
        if not timestamp:
            return None

        try:
            # Joplin stores timestamps as milliseconds since epoch
            timestamp_ms = int(timestamp)
            return datetime.fromtimestamp(timestamp_ms / 1000)
        except (ValueError, TypeError):
            return None

    async def _process_note_attachments(
        self, body: str, resources_map: Dict[str, Dict[str, Any]], extract_path: Path
    ) -> str:
        """Process attachments in note body based on import options."""

        attachment_handling = self.options.attachment_handling

        if attachment_handling == "skip":
            # Remove all attachment references
            import re

            # Remove Joplin resource links: ![](:/resource_id)
            body = re.sub(r"!\[.*?\]\(:/[a-f0-9]+\)", "[Attachment removed]", body)
            return body

        elif attachment_handling == "link":
            # Convert to text references (default behavior)
            import re

            def replace_resource(match):
                resource_id = match.group(1) if match.group(1) else match.group(2)
                if resource_id in resources_map:
                    resource_name = resources_map[resource_id].get(
                        "title", f"attachment_{resource_id}"
                    )
                    return f"[Attachment: {resource_name}]"
                return "[Attachment]"

            # Replace resource references
            body = re.sub(r"!\[.*?\]\(:/([a-f0-9]+)\)", replace_resource, body)
            body = re.sub(r"\[.*?\]\(:/([a-f0-9]+)\)", replace_resource, body)

        # Note: "embed" mode would require copying attachment files,
        # which is complex and may not be supported by target Joplin instance

        return body
