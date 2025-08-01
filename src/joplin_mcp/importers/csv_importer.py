"""
CSV importer for Joplin MCP.

Handles CSV files by converting structured data to Markdown format,
with each row becoming a separate note or one consolidated note with a table.
"""

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import List

from ..types.import_types import ImportedNote
from .base import BaseImporter, ImportProcessingError, ImportValidationError


class CSVImporter(BaseImporter):
    """Importer for CSV files."""

    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return [".csv"]

    def can_import(self, file_path: Path) -> bool:
        """Check if file can be imported as CSV."""
        return file_path.suffix.lower() in self.get_supported_extensions()

    async def validate(self, file_path: str) -> bool:
        """Validate CSV file can be processed."""
        path = Path(file_path)

        # Check file exists and is readable
        if not path.exists():
            raise ImportValidationError(f"CSV file not found: {file_path}")

        if not path.is_file():
            raise ImportValidationError(f"Path is not a file: {file_path}")

        # Check file extension
        if path.suffix.lower() not in self.get_supported_extensions():
            raise ImportValidationError(
                f"Unsupported CSV file extension: {path.suffix}"
            )

        if path.stat().st_size == 0:
            raise ImportValidationError(f"File is empty: {file_path}")

        # Try to read and parse as CSV
        try:
            with open(file_path, encoding="utf-8") as f:
                # Try to detect CSV format
                sample = f.read(1024)
                f.seek(0)

                # Use csv.Sniffer to detect dialect
                sniffer = csv.Sniffer()
                try:
                    dialect = sniffer.sniff(sample)
                except csv.Error:
                    # Fall back to default dialect
                    dialect = csv.excel

                # Try to read first few rows
                reader = csv.reader(f, dialect=dialect)
                rows = []
                for i, row in enumerate(reader):
                    if i >= 3:  # Read first 3 rows for validation
                        break
                    rows.append(row)

                if not rows:
                    raise ImportValidationError(
                        f"CSV file appears to be empty: {file_path}"
                    )

                # Check if first row looks like headers
                if len(rows) > 1:
                    first_row = rows[0]
                    if not first_row or all(not cell.strip() for cell in first_row):
                        raise ImportValidationError(
                            f"CSV file has empty header row: {file_path}"
                        )

        except UnicodeDecodeError:
            # Try other encodings
            for encoding in ["latin-1", "cp1252", "iso-8859-1"]:
                try:
                    with open(file_path, encoding=encoding) as f:
                        sample = f.read(1024)
                        # Basic validation that it looks like CSV
                        if (
                            "," not in sample
                            and ";" not in sample
                            and "\t" not in sample
                        ):
                            continue
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ImportValidationError(
                    f"Unable to decode CSV file with common encodings: {file_path}"
                )
        except Exception as e:
            raise ImportValidationError(f"Error reading CSV file: {str(e)}") from e

        return True

    async def parse(self, file_path: str) -> List[ImportedNote]:
        """Parse CSV file and convert to ImportedNote objects."""
        try:
            path = Path(file_path)

            # Read CSV content with proper encoding
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
                    f"Could not read CSV file with any supported encoding: {file_path}"
                )

            # Parse CSV data
            rows = []
            with open(file_path, encoding=used_encoding) as f:
                # Detect CSV dialect
                sample = f.read(1024)
                f.seek(0)

                sniffer = csv.Sniffer()
                try:
                    dialect = sniffer.sniff(sample)
                except csv.Error:
                    dialect = csv.excel

                reader = csv.reader(f, dialect=dialect)
                for row in reader:
                    rows.append(row)

            if not rows:
                raise ImportProcessingError(f"CSV file contains no data: {file_path}")

            # Get import mode from options - default to 'table'
            import_mode = getattr(self.options, "csv_import_mode", "table")

            if import_mode == "rows":
                return self._create_notes_from_rows(path, rows, used_encoding or "utf-8")
            else:
                return self._create_table_note(path, rows, used_encoding or "utf-8")

        except Exception as e:
            if isinstance(e, (ImportValidationError, ImportProcessingError)):
                raise
            raise ImportProcessingError(
                f"Error parsing CSV file {file_path}: {str(e)}"
            ) from e

    def _create_table_note(
        self, path: Path, rows: List[List[str]], encoding: str
    ) -> List[ImportedNote]:
        """Create a single note with CSV data as a Markdown table."""
        if not rows:
            return []

        # Extract title from filename
        title = path.stem.replace("_", " ").replace("-", " ").title()

        # Create Markdown table
        markdown_lines = [f"# {title}", "", "CSV Data imported as table:", ""]

        # Add table headers (first row)
        headers = rows[0] if rows else []
        if headers:
            # Clean and format headers
            clean_headers = [self._clean_cell_content(header) for header in headers]
            markdown_lines.append("| " + " | ".join(clean_headers) + " |")
            markdown_lines.append(
                "| " + " | ".join(["---"] * len(clean_headers)) + " |"
            )

            # Add data rows
            for row in rows[1:]:
                # Pad row to match header count
                padded_row = row + [""] * (len(headers) - len(row))
                clean_row = [
                    self._clean_cell_content(cell)
                    for cell in padded_row[: len(headers)]
                ]
                markdown_lines.append("| " + " | ".join(clean_row) + " |")

        markdown_content = "\n".join(markdown_lines)

        # Get file metadata
        stat = path.stat()
        created_time = datetime.fromtimestamp(stat.st_ctime)
        updated_time = datetime.fromtimestamp(stat.st_mtime)

        # Create the imported note
        note = ImportedNote(
            title=title,
            body=markdown_content,
            created_time=created_time,
            updated_time=updated_time,
            tags=[],
            notebook=None,
            metadata={
                "original_format": "csv",
                "source_file": str(path),
                "encoding": encoding,
                "file_size": stat.st_size,
                "import_method": "csv_importer",
                "import_mode": "table",
                "row_count": len(rows),
                "column_count": len(headers) if headers else 0,
            },
        )

        return [note]

    def _create_notes_from_rows(
        self, path: Path, rows: List[List[str]], encoding: str
    ) -> List[ImportedNote]:
        """Create separate notes from each CSV row."""
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
                title = f"{path.stem} - Row {i}"

            # Create content from row data
            content_lines = [f"# {title}", ""]

            for header, value in zip(headers, row):
                if header.strip() and value.strip():
                    clean_header = self._clean_cell_content(header)
                    clean_value = self._clean_cell_content(value)
                    content_lines.append(f"**{clean_header}**: {clean_value}")

            markdown_content = "\n".join(content_lines)

            # Get file metadata
            stat = path.stat()
            created_time = datetime.fromtimestamp(stat.st_ctime)
            updated_time = datetime.fromtimestamp(stat.st_mtime)

            # Extract any hashtags from the row data
            tags = set()
            for cell in row:
                tags.update(self._extract_hashtags(cell))

            # Create the imported note
            note = ImportedNote(
                title=title,
                body=markdown_content,
                created_time=created_time,
                updated_time=updated_time,
                tags=list(tags),
                notebook=None,
                metadata={
                    "original_format": "csv",
                    "source_file": str(path),
                    "encoding": encoding,
                    "file_size": stat.st_size,
                    "import_method": "csv_importer",
                    "import_mode": "rows",
                    "row_number": i,
                    "total_rows": len(rows) - 1,
                },
            )

            notes.append(note)

        return notes

    def _clean_cell_content(self, content: str) -> str:
        """Clean and format cell content for Markdown."""
        if not content:
            return ""

        # Strip whitespace
        cleaned = content.strip()

        # Escape pipe characters for Markdown tables
        cleaned = cleaned.replace("|", "\\|")

        # Replace newlines with spaces in table cells
        cleaned = re.sub(r"\s+", " ", cleaned)

        return cleaned

    def _extract_hashtags(self, content: str) -> List[str]:
        """Extract hashtags from cell content."""
        if not content:
            return []

        # Find hashtags in the content
        hashtag_pattern = r"#([a-zA-Z0-9_-]+)"
        hashtags = re.findall(hashtag_pattern, content)

        return hashtags
