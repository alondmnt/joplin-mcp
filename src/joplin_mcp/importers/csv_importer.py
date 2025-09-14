"""
CSV importer for Joplin MCP.

Handles CSV files by converting structured data to Markdown format,
with each row becoming a separate note or one consolidated note with a table.
"""

import logging
from pathlib import Path
from typing import List

from ..types.import_types import ImportedNote
from .base import BaseImporter
from .utils import csv_to_markdown_table, extract_hashtags


class CSVImporter(BaseImporter):
    """Importer for CSV files."""

    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return ["csv"]

    def can_import(self, file_path: Path) -> bool:
        """Check if file can be imported as CSV."""
        extension = file_path.suffix.lower().lstrip(".")
        return extension in self.get_supported_extensions()

    def supports_directory(self) -> bool:
        """CSV format supports both files and directories containing CSV files."""
        return True

    async def validate(self, source_path: str) -> bool:
        """Validate CSV file or directory can be processed."""
        path = Path(source_path)

        if path.is_file():
            # Use enhanced base class validation
            self.validate_file_comprehensive(path)
        elif path.is_dir():
            # Use enhanced base class validation  
            self.validate_directory_comprehensive(path)
        else:
            from .base import ImportValidationError
            raise ImportValidationError(
                f"Path is neither file nor directory: {source_path}"
            )

        return True

    async def parse(self, source_path: str) -> List[ImportedNote]:
        """Parse CSV file or directory and convert to ImportedNote objects."""
        path = Path(source_path)

        if path.is_file():
            # Parse single CSV file
            notes = await self._parse_csv_file(path)
            return notes
        elif path.is_dir():
            # Parse all CSV files in directory using enhanced base class
            all_notes = []
            csv_files = self.scan_directory_safe(path)

            for csv_file in csv_files:
                try:
                    notes = await self._parse_csv_file(csv_file)
                    all_notes.extend(notes)
                except Exception as e:
                    # Log error but continue with other files
                    logging.getLogger(__name__).warning(
                        "Failed to parse %s: %s", csv_file, str(e)
                    )
                    continue

            return all_notes
        else:
            from .base import ImportProcessingError
            raise ImportProcessingError(
                f"Source is neither file nor directory: {source_path}"
            )

    async def _parse_csv_file(self, file_path: Path) -> List[ImportedNote]:
        """Parse a single CSV file and convert to ImportedNote(s)."""
        # Read CSV content using enhanced base class utilities
        content, used_encoding = self.read_file_safe(file_path)

        # Get import mode from options - default to 'table' (preserving original behavior)
        import_mode = getattr(self.options, "csv_import_mode", "table")

        if import_mode == "rows":
            return await self._create_notes_from_rows(file_path, content, used_encoding)
        else:
            # Default table mode
            return await self._create_table_note(file_path, content, used_encoding)

    async def _create_table_note(self, file_path: Path, content: str, used_encoding: str) -> List[ImportedNote]:
        """Create a single note with CSV data as a Markdown table."""
        # Extract title using enhanced base class utilities
        title = self.extract_title_safe(content, file_path.stem)

        # Convert CSV to Markdown table using shared utility
        markdown_content = csv_to_markdown_table(content, title)

        # Extract hashtags using enhanced base class utilities
        tags = self.extract_hashtags_safe(content)

        # Create note using enhanced base class utilities
        note = self.create_imported_note_safe(
            title=title,
            body=markdown_content,
            file_path=file_path,
            tags=tags,
            additional_metadata={
                "encoding": used_encoding,
                "import_mode": "table",
            },
        )
        return [note]

    async def _create_notes_from_rows(self, file_path: Path, content: str, used_encoding: str) -> List[ImportedNote]:
        """Create separate notes from each CSV row (preserving original functionality)."""
        # Parse CSV content to get rows
        import csv
        from io import StringIO
        
        rows = []
        try:
            # Detect CSV dialect
            sample = content[:1024]
            sniffer = csv.Sniffer()
            try:
                dialect = sniffer.sniff(sample)
            except csv.Error:
                dialect = csv.excel

            reader = csv.reader(StringIO(content), dialect=dialect)
            for row in reader:
                rows.append(row)
        except Exception:
            # Fallback to simple CSV parsing
            rows = [line.split(',') for line in content.strip().split('\n')]

        if not rows:
            return []

        notes = []
        headers = rows[0] if rows else []

        # Create a note for each data row
        for i, row in enumerate(rows[1:], 1):  # Skip header row
            # Create title from first column or row number
            if row and row[0].strip():
                title = self._clean_cell_content(row[0])[:100]  # Limit title length
            else:
                title = f"{file_path.stem} - Row {i}"

            # Create content from row data
            content_lines = [f"# {title}", ""]

            for header, value in zip(headers, row):
                if header.strip() and value.strip():
                    clean_header = self._clean_cell_content(header)
                    clean_value = self._clean_cell_content(value)
                    content_lines.append(f"**{clean_header}**: {clean_value}")

            markdown_content = "\n".join(content_lines)

            # Extract hashtags from row data
            tags = []
            for cell in row:
                tags.extend(self.extract_hashtags_safe(cell))

            # Create note using enhanced base class utilities
            note = self.create_imported_note_safe(
                title=title,
                body=markdown_content,
                file_path=file_path,
                tags=list(set(tags)),  # Remove duplicates
                additional_metadata={
                    "encoding": used_encoding,
                    "import_mode": "rows",
                    "row_number": i,
                    "total_rows": len(rows) - 1,
                },
            )
            notes.append(note)

        return notes

    def _clean_cell_content(self, content: str) -> str:
        """Clean and format cell content for Markdown (preserving original functionality)."""
        if not content:
            return ""

        # Strip whitespace
        cleaned = content.strip()

        # Escape pipe characters for Markdown tables
        cleaned = cleaned.replace("|", "\\|")

        # Replace newlines with spaces in table cells
        import re
        cleaned = re.sub(r"\s+", " ", cleaned)

        return cleaned
