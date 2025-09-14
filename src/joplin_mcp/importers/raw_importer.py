"""
RAW (Joplin Export Directory) importer for Joplin MCP.

Handles RAW format which is Joplin's directory-based export format containing
Markdown files and a resources folder with attachments.
"""

import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..types.import_types import ImportedNote
from .base import BaseImporter, ImportProcessingError, ImportValidationError


class RAWImporter(BaseImporter):
    """Importer for RAW (Joplin Export Directory) format."""

    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        # RAW format processes Markdown files within directories
        return ["md"]

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

        # Use enhanced base class validation (will check if directory exists and is readable)
        self.validate_directory_comprehensive(path)

        # Additional RAW-specific validation
        has_md_files = any(path.glob("*.md"))
        if not has_md_files:
            from .base import ImportValidationError
            raise ImportValidationError(
                f"No Markdown files found in RAW directory: {source_path}"
            )

        # Resources directory is optional but common
        resources_dir = path / "resources"
        if resources_dir.exists() and not resources_dir.is_dir():
            from .base import ImportValidationError
            raise ImportValidationError(
                f"Resources path exists but is not a directory: {resources_dir}"
            )

        return True

    async def parse(self, source_path: str) -> List[ImportedNote]:
        """Parse RAW directory and convert to ImportedNote objects."""
        path = Path(source_path)

        # Find all markdown files using utility function directly
        from .utils import scan_directory_for_files
        md_files = scan_directory_for_files(path, ["md"])

        if not md_files:
            from .base import ImportProcessingError
            raise ImportProcessingError(
                f"No Markdown files found in RAW directory: {source_path}"
            )

        # Pre-scan notebooks to map parent_id -> notebook title
        notebooks_by_id: Dict[str, str] = {}
        for md_file in md_files:
            try:
                content, _ = self.read_file_safe(md_file)
                meta_preview, body_preview = self._parse_kv_metadata_block(content)
                type_val = str(meta_preview.get("type_", "")).strip()
                if type_val == "2":  # Notebook item
                    nb_id = str(meta_preview.get("id", "")).strip()
                    if nb_id:
                        # Derive notebook title from first non-empty line
                        title_candidate = self._extract_title(md_file, body_preview)
                        if title_candidate:
                            notebooks_by_id[nb_id] = title_candidate
            except Exception:
                continue

        notes = []
        resources_dir = path / "resources"

        for md_file in md_files:
            try:
                note = await self._parse_md_file(md_file, resources_dir, notebooks_by_id)
                if note:
                    notes.append(note)
            except Exception as e:
                # Log error but continue with other files
                logging.getLogger(__name__).warning(
                    "Failed to parse %s: %s", md_file, str(e)
                )
                continue

        return notes

    async def _parse_md_file(
        self, md_file: Path, resources_dir: Path, notebooks_by_id: Dict[str, str]
    ) -> Optional[ImportedNote]:
        """Parse a single Markdown file from RAW export."""
        try:
            # Read file content using enhanced base class utilities
            content, used_encoding = self.read_file_safe(md_file)

            # Parse Joplin-specific metadata (frontmatter/comments or KV block)
            raw_metadata, body = self._parse_joplin_metadata(content)
            if not raw_metadata:
                # Fallback to key:value block at end (Joplin export style)
                raw_metadata, body = self._parse_kv_metadata_block(content)

            # Skip non-note items (e.g., notebooks type_=2, resources type_=4)
            type_val = str(raw_metadata.get("type_", "")).strip()
            if type_val and type_val != "1":
                return None

            # Extract title from cleaned body or filename
            title = self._extract_title(md_file, body)
            # Remove duplicated title line from body if present
            body = self._remove_title_from_body(body, title)

            # Resource link processing:
            # For 'embed' mode (default), keep Joplin :/resourceId links so the engine can upload and rewrite.
            # Only rewrite to local resources paths in 'link' mode for readability.
            if resources_dir.exists() and getattr(self.options, "attachment_handling", "embed") == "link":
                body = self._process_resource_links(body, resources_dir)

            # Extract timestamps from metadata or file stats using enhanced utilities
            file_metadata = self.get_file_metadata_safe(md_file)
            created_time = (
                self.parse_timestamp_safe(raw_metadata.get("created_time"))
                or file_metadata.get("created_time")
            )
            updated_time = (
                self.parse_timestamp_safe(raw_metadata.get("updated_time"))
                or file_metadata.get("updated_time")
            )

            # Extract tags
            tags = raw_metadata.get("tags", [])
            if isinstance(tags, str):
                tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

            # Resolve notebook from parent_id if available
            notebook = raw_metadata.get("notebook")
            if not notebook:
                parent_id = str(raw_metadata.get("parent_id", "")).strip()
                if parent_id and parent_id in notebooks_by_id:
                    notebook = notebooks_by_id[parent_id]

            # Prepare additional metadata
            additional_metadata = {
                "encoding": used_encoding,
                "original_format": "raw",
                **raw_metadata,
            }

            # Include resources directory for downstream attachment handling
            if resources_dir and resources_dir.exists():
                additional_metadata["raw_resources_dir"] = str(resources_dir.resolve())

            # Create note using enhanced base class utilities
            note = self.create_imported_note_safe(
                title=title,
                body=body,
                file_path=md_file,
                tags=tags,
                notebook=notebook,
                is_todo=bool(int(raw_metadata.get("is_todo", 0))) if isinstance(raw_metadata.get("is_todo", 0), (int, str)) else bool(raw_metadata.get("is_todo", False)),
                todo_completed=bool(int(raw_metadata.get("todo_completed", 0))) if isinstance(raw_metadata.get("todo_completed", 0), (int, str)) else bool(raw_metadata.get("todo_completed", False)),
                created_time=created_time,
                updated_time=updated_time,
                additional_metadata=additional_metadata,
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

    def _parse_kv_metadata_block(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse trailing key: value metadata block used by Joplin RAW/JEX exports.

        Returns a tuple of (metadata_dict, body_without_metadata).
        """
        lines = content.split("\n")
        meta_lines: List[str] = []

        # Walk from end collecting key: value lines
        i = len(lines) - 1
        kv_pattern = re.compile(r"^[a-z_][a-z0-9_]*:\s*(.*)$", re.IGNORECASE)
        while i >= 0:
            line = lines[i].rstrip()
            if not line:
                # allow blank lines in between metadata? stop at first blank after we started collecting
                if meta_lines:
                    break
                i -= 1
                continue
            if kv_pattern.match(line):
                meta_lines.append(line)
                i -= 1
                continue
            # stop once a non kv line encountered after starting
            if meta_lines:
                break
            i -= 1

        metadata: Dict[str, Any] = {}
        if meta_lines:
            # meta_lines are collected bottom-up; reverse to restore order
            meta_lines.reverse()
            for ln in meta_lines:
                m = kv_pattern.match(ln)
                if not m:
                    continue
                key, val = ln.split(":", 1)
                key = key.strip()
                val = val.strip()

                # Coerce some types
                if key in {"is_todo", "todo_completed", "is_conflict", "encryption_applied", "encryption_blob_encrypted", "is_shared"}:
                    if val.lower() in {"true", "false"}:
                        metadata[key] = val.lower() == "true"
                    else:
                        try:
                            metadata[key] = bool(int(val))
                        except Exception:
                            metadata[key] = False
                elif key in {"order", "size", "ocr_status", "type_"}:
                    try:
                        metadata[key] = int(val)
                    except Exception:
                        metadata[key] = val
                else:
                    metadata[key] = val

            # Remove metadata block from body
            body = "\n".join(lines[: i + 1]).rstrip()
            return metadata, body

        return {}, content.strip()

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

    # Note: timestamp parsing delegated to BaseImporter.parse_timestamp_safe

    def _remove_title_from_body(self, body: str, title: str) -> str:
        """RAW/JEX helper: remove a plain first line matching the title.

        Keeps a leading markdown header like '# Title'. Only removes the first
        non-empty line if it equals the title (case and whitespace insensitive)
        and one blank line that follows it.
        """
        if not body or not title:
            return body

        lines = body.split("\n")

        # Find first non-empty line index
        idx = 0
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        if idx >= len(lines):
            return body

        first = lines[idx].rstrip()

        def normalize(s: str) -> str:
            s = s.strip().lower()
            # Remove simple markdown markers characters for comparison
            import re as _re
            s = _re.sub(r"[\s#*_`~]+", " ", s)
            s = " ".join(s.split())
            return s

        normalized_title = normalize(title)

        # Keep if it's a markdown header line
        import re as _re
        m = _re.match(r"^\s*#{1,6}\s*(.*?)\s*#*\s*$", first)
        header_text = m.group(1) if m else None
        if header_text and normalize(header_text) == normalized_title:
            return body

        # Remove if it's a plain line equal to the title
        if normalize(first) == normalized_title:
            del lines[idx]
            if idx < len(lines) and not lines[idx].strip():
                del lines[idx]
            return "\n".join(lines).rstrip()

        return body
