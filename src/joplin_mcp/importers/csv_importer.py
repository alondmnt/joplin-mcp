"""
CSV importer for Joplin MCP.

Handles CSV files by converting structured data to Markdown format,
with each row becoming a separate note or one consolidated note with a table.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any

from ..types.import_types import ImportedNote
from .base import BaseImporter
from .utils import csv_to_markdown_table, extract_hashtags, extract_frontmatter_tags


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

        # Get import mode from options - default to 'table'
        csv_opts = getattr(self.options, "import_options", {}) or {}
        import_mode = csv_opts.get(
            "csv_import_mode", getattr(self.options, "csv_import_mode", "table")
        )
        delimiter_opt = csv_opts.get("csv_delimiter")

        if import_mode == "rows":
            return await self._create_notes_from_rows(
                file_path, content, used_encoding, delimiter_opt
            )
        else:
            # Default table mode
            return await self._create_table_note(
                file_path, content, used_encoding, delimiter_opt
            )

    async def _create_table_note(
        self, file_path: Path, content: str, used_encoding: str, delimiter_opt: str = None
    ) -> List[ImportedNote]:
        """Create a single note with CSV data as a Markdown table."""
        # Title from path (prefer filename over CSV content heuristics)
        title = self._title_from_path(file_path)

        # Convert CSV to Markdown table using shared utility
        if delimiter_opt and isinstance(delimiter_opt, str) and len(delimiter_opt) == 1:
            markdown_content = csv_to_markdown_table(content, title, delimiter=delimiter_opt)
        else:
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

    def _title_from_path(self, file_path: Path) -> str:
        """Derive a human-friendly title from a file path.

        Replaces common separators with spaces and collapses whitespace.
        """
        title = file_path.stem
        # Replace separators
        title = title.replace("_", " ").replace("-", " ").replace(".", " ")
        # Collapse spaces
        title = " ".join(title.split())
        return title or file_path.name

    async def _create_notes_from_rows(
        self, file_path: Path, content: str, used_encoding: str, delimiter_opt: str = None
    ) -> List[ImportedNote]:
        """Create separate notes from each CSV row using YAML frontmatter.

        Each note body contains only a YAML frontmatter block constructed from
        the CSV headers and row values. The note title is derived from the
        first column (if present) or a fallback of "<filename> - Row <n>".
        """
        # Parse CSV content to get rows
        import csv
        from io import StringIO
        
        rows = []
        try:
            if delimiter_opt and isinstance(delimiter_opt, str) and len(delimiter_opt) == 1:
                reader = csv.reader(StringIO(content), delimiter=delimiter_opt)
            else:
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

        # Precompute sanitized header keys to keep order stable
        sanitized_headers = [self._sanitize_key(h) for h in headers]

        # Create a note for each data row
        for i, row in enumerate(rows[1:], 1):  # Skip header row
            # Create title from first column or row number
            if row and row[0].strip():
                title = self._clean_cell_content(row[0])[:100]  # Limit title length
            else:
                title = f"{file_path.stem} - Row {i}"

            # Build frontmatter dict from row data
            fm: Dict[str, Any] = {}
            for raw_header, key, value in zip(headers, sanitized_headers, row):
                if not raw_header or not raw_header.strip():
                    continue
                if value is None:
                    continue
                value_str = str(value).strip()
                if value_str == "":
                    continue

                # Special handling for tag-like fields
                if key in {"tags", "keywords", "categories"}:
                    parsed_tags = self._parse_tags_value(value_str)
                    if parsed_tags:
                        fm[key] = parsed_tags
                    continue

                fm[key] = value_str

            # Convert dict to YAML frontmatter
            markdown_content = self._to_yaml_frontmatter(fm)

            # Extract hashtags from row data
            tags = []
            for cell in row:
                tags.extend(self.extract_hashtags_safe(cell))

            # Also include tags from frontmatter if present
            try:
                fm_tags = extract_frontmatter_tags(markdown_content)
                if fm_tags:
                    tags.extend(fm_tags)
            except Exception:
                pass

            # Create note using enhanced base class utilities
            note = self.create_imported_note_safe(
                title=title,
                body=markdown_content,
                file_path=file_path,
                tags=sorted(list(set(tags))),  # Remove duplicates, stable order
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

    def _sanitize_key(self, key: str) -> str:
        """Sanitize CSV header into a YAML-safe key.

        - Lowercase
        - Trim surrounding whitespace
        - Replace spaces and dashes with underscore
        - Remove characters other than letters, numbers and underscore
        - Collapse multiple underscores
        """
        if not key:
            return ""
        import re as _re
        k = key.strip().lower()
        k = k.replace(" ", "_").replace("-", "_")
        k = _re.sub(r"[^a-z0-9_]+", "", k)
        k = _re.sub(r"_+", "_", k)
        return k

    def _parse_tags_value(self, value: str) -> List[str]:
        """Parse a CSV cell value into a list of tags.

        Supports formats like:
        - "tag1, tag2, tag3"
        - "tag1 tag2 tag3"
        - "[tag1, tag2, tag3]"
        - "tag1; tag2; tag3"
        """
        import re as _re
        v = value.strip().strip("[]")
        # Split on commas, semicolons, or whitespace sequences
        parts = [p.strip().strip("\"'") for p in _re.split(r"[,;\s]+", v) if p.strip()]
        # Remove empty and deduplicate while preserving order
        seen = set()
        tags: List[str] = []
        for p in parts:
            if p and p not in seen:
                seen.add(p)
                tags.append(p)
        return tags

    def _to_yaml_frontmatter(self, data: Dict[str, Any]) -> str:
        """Convert dict to a YAML frontmatter block.

        Attempts to use PyYAML if available; otherwise falls back to a simple
        serializer that handles strings and list-of-strings. Keys are assumed
        to be pre-sanitized.
        """
        # First try PyYAML for robust quoting/escaping
        try:
            import yaml  # type: ignore
            dumped = yaml.safe_dump(
                data,
                sort_keys=False,
                allow_unicode=True,
                default_flow_style=False,
            ).strip()
            return f"---\n{dumped}\n---\n"
        except Exception:
            pass

        # Fallback minimal YAML writer
        def _quote_scalar(s: str) -> str:
            # Quote if contains special YAML-significant characters
            import re as _re
            if s == "" or _re.search(r"[:#\-\n\r\t]|^\s|\s$", s):
                esc = s.replace("\"", "\\\"")
                return f'"{esc}"'
            return s

        lines = ["---"]
        for k, v in data.items():
            if isinstance(v, list):
                if not v:
                    lines.append(f"{k}: []")
                else:
                    lines.append(f"{k}:")
                    for item in v:
                        lines.append(f"  - {_quote_scalar(str(item))}")
            else:
                lines.append(f"{k}: {_quote_scalar(str(v))}")
        lines.append("---")
        return "\n".join(lines) + "\n"
