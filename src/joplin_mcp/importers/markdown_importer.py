"""Markdown file importer for Joplin MCP server."""

from pathlib import Path
from typing import List, Optional

from ..types.import_types import ImportedNote
from .base import BaseImporter
from .utils import (
    extract_all_tags,
    extract_title_from_content,
    clean_markdown,
    parse_frontmatter_timestamp,
    extract_frontmatter_field,
)


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
        path = Path(source)

        if path.is_file():
            # Use enhanced base class validation
            self.validate_file_comprehensive(path)
        elif path.is_dir():
            # Use enhanced base class validation  
            self.validate_directory_comprehensive(path)
        else:
            from .base import ImportValidationError
            raise ImportValidationError(f"Source is neither file nor directory: {source}")

        return True

    async def parse(self, source: str) -> List[ImportedNote]:
        """Parse markdown files and return ImportedNote objects."""
        path = Path(source)

        if path.is_file():
            # Parse single file
            note = await self._parse_markdown_file(path)
            return [note] if note else []

        elif path.is_dir():
            # Parse all markdown files in directory using enhanced base class
            all_notes = []
            markdown_files = self.scan_directory_safe(path)

            for md_file in markdown_files:
                try:
                    note = await self._parse_markdown_file(md_file)
                    # Preserve directory structure as notebook if not set by frontmatter
                    if note and not note.notebook and self.options.preserve_structure:
                        derived_notebook = self.extract_notebook_from_path(str(md_file), str(path))
                        if derived_notebook:
                            note.notebook = derived_notebook
                    if note:
                        all_notes.append(note)
                except Exception as e:
                    # Log error but continue processing other files
                    print(f"Warning: Failed to parse {md_file}: {e}")

            return all_notes

        return []

    async def _parse_markdown_file(self, file_path: Path) -> Optional[ImportedNote]:
        """Parse a single markdown file."""
        # Read markdown content using enhanced base class utilities
        content, used_encoding = self.read_file_safe(file_path)

        # Clean markdown content using shared utility
        cleaned_content = clean_markdown(content)

        # Extract title using enhanced base class utilities
        title = self.extract_title_safe(cleaned_content, file_path.stem)

        # Extract all tags (frontmatter + hashtags) using enhanced utilities
        # Respect extract_hashtags option from original implementation
        if self.options.import_options.get("extract_hashtags", True):
            tags = extract_all_tags(content)
        else:
            # Only extract frontmatter tags, not hashtags from content
            from .utils import extract_frontmatter_tags
            tags = extract_frontmatter_tags(content)

        # Extract todo flags from frontmatter
        is_todo = bool(extract_frontmatter_field(content, "todo") or 
                      extract_frontmatter_field(content, "is_todo"))
        todo_completed = bool(extract_frontmatter_field(content, "completed") or 
                             extract_frontmatter_field(content, "todo_completed"))

        # Extract notebook from frontmatter (override for directory-based notebook)
        notebook = extract_frontmatter_field(content, "notebook")

        # Extract timestamps from frontmatter using shared utilities
        created_str = extract_frontmatter_field(content, "created") or \
                     extract_frontmatter_field(content, "date")
        updated_str = extract_frontmatter_field(content, "updated") or \
                     extract_frontmatter_field(content, "modified")
        
        created_time = parse_frontmatter_timestamp(created_str) if created_str else None
        updated_time = parse_frontmatter_timestamp(updated_str) if updated_str else None

        # Use file timestamps as fallback (preserving original behavior)
        file_metadata = self.get_file_metadata_safe(file_path)
        if not created_time:
            created_time = file_metadata.get("created_time")
        if not updated_time:
            updated_time = file_metadata.get("updated_time")

        # Note: We don't need complete frontmatter dict since we extract individual fields as needed

        # Create note using enhanced base class utilities
        return self.create_imported_note_safe(
            title=title,
            body=cleaned_content,
            file_path=file_path,
            tags=tags,
            notebook=notebook,
            is_todo=is_todo,
            todo_completed=todo_completed,
            created_time=created_time,
            updated_time=updated_time,
            additional_metadata={
                "encoding": used_encoding,
                "original_format": "markdown",
                "source_file": str(file_path),
                "file_size": file_metadata.get("size", 0),
            },
        )
