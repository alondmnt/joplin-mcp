"""
Generic importer for Joplin MCP.

Handles unknown file formats and "Other applications..." imports.
Acts as a fallback importer for unsupported formats with intelligent delegation to specialized importers.
"""

import mimetypes
from pathlib import Path
from typing import List, Optional

from ..types.import_types import ImportedNote
from .base import BaseImporter, ImportProcessingError, ImportValidationError
from .utils import csv_to_markdown_table


class GenericImporter(BaseImporter):
    """Generic importer that delegates to specialized importers or handles unknown formats."""

    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions (generic handles any file)."""
        # GenericImporter handles all files regardless of extension
        # Return empty list to trigger scan_directory_safe's "all files" mode
        return []

    def can_import(self, file_path: Path) -> bool:
        """Check if file can be imported (generic can handle any file)."""
        return True

    def supports_directory(self) -> bool:
        """Generic format supports both files and directories."""
        return True

    async def validate(self, source_path: str) -> bool:
        """Validate source can be processed by generic importer."""
        path = Path(source_path)

        if path.is_file():
            # Use enhanced base class validation for files
            self.validate_file_comprehensive(path, allow_empty=True)
        elif path.is_dir():
            # Use enhanced base class validation for directories
            self.validate_directory_comprehensive(path)
        else:
            raise ImportValidationError(
                f"Path is not a file or directory: {source_path}"
            )

        return True

    async def parse(self, source_path: str) -> List[ImportedNote]:
        """Parse source and convert to ImportedNote objects."""
        path = Path(source_path)

        if path.is_dir():
            # Use standard directory processing from BaseImporter
            return await super().parse_directory(source_path)
        else:
            # Process single file
            note = await self._parse_file(path)
            return [note] if note else []

    async def _parse_file(self, file_path: Path) -> Optional[ImportedNote]:
        """Parse a single file by delegating to specialized importers or handling unknown formats."""
        try:
            extension = file_path.suffix.lower().lstrip(".")
            
            # Delegate to specialized importers for known formats
            if extension in ["md", "markdown"]:
                return await self._delegate_to_importer("markdown_importer", "MarkdownImporter", file_path)
            
            elif extension in ["html", "htm"]:
                return await self._delegate_to_importer("html_importer", "HTMLImporter", file_path)
            
            elif extension in ["csv"]:
                return await self._delegate_to_importer("csv_importer", "CSVImporter", file_path)
            
            elif extension in ["tsv"]:
                # Handle TSV files (Tab-separated values) - similar to CSV but different delimiter
                return await self._handle_tsv_format(file_path)
            
            elif extension in ["txt", "text"]:
                return await self._delegate_to_importer("txt_importer", "TxtImporter", file_path)
            
            elif extension in ["enex"]:
                return await self._delegate_to_importer("enex_importer", "ENEXImporter", file_path)
            
            elif extension in ["jex"]:
                return await self._delegate_to_importer("jex_importer", "JEXImporter", file_path)
            
            elif extension in ["zip"]:
                return await self._delegate_to_importer("zip_importer", "ZIPImporter", file_path)
            
            # Handle special formats that need custom processing
            elif extension in ["json"]:
                return await self._handle_json_format(file_path)
            
            elif extension in ["xml"]:
                return await self._handle_xml_format(file_path)
            
            elif extension in ["py", "js", "java", "cpp", "c", "h", "css", "sql"]:
                return await self._handle_code_format(file_path)
            
            elif extension in ["log"]:
                return await self._handle_log_format(file_path)
            
            # Handle truly unknown formats
            else:
                return await self._handle_unknown_format(file_path)

        except Exception as e:
            raise ImportProcessingError(
                f"Error processing file {file_path}: {str(e)}"
            ) from e

    async def _delegate_to_importer(self, module_name: str, class_name: str, file_path: Path) -> Optional[ImportedNote]:
        """Delegate file processing to a specialized importer."""
        try:
            # Dynamic import to avoid circular dependencies
            module = __import__(f"joplin_mcp.importers.{module_name}", fromlist=[class_name])
            importer_class = getattr(module, class_name)
            
            # Create importer instance with same options
            importer = importer_class(self.options)
            
            # Parse the file
            notes = await importer.parse(str(file_path))
            
            # Return first note (specialized importers typically return one note per file)
            if notes:
                note = notes[0]
                # Add generic-import tag to indicate it came through GenericImporter
                if note.tags is None:
                    note.tags = []
                if "generic-import" not in note.tags:
                    note.tags.append("generic-import")
                return note
            
            return None
            
        except Exception as e:
            # If delegation fails, fall back to unknown format handling
            print(f"Warning: Delegation to {class_name} failed for {file_path}: {str(e)}")
            return await self._handle_unknown_format(file_path)

    async def _handle_unknown_format(self, file_path: Path) -> Optional[ImportedNote]:
        """Handle files with truly unknown or unsupported formats."""
        # Detect file characteristics
        is_binary = self._is_binary_file(file_path)
        mime_type = self._detect_mime_type(file_path)
        file_metadata = self.get_file_metadata_safe(file_path)

        # Extract title from filename
        title = self._extract_title_from_path(file_path)

        if is_binary:
            # Create metadata note for binary files
            body = self._create_binary_file_note(file_path, mime_type, file_metadata.get("size", 0))
            tags = ["binary", "attachment", "generic-import"]
        else:
            # Try to read as text
            try:
                content, used_encoding = self.read_file_safe(file_path)
                if not content.strip():
                    # Handle empty files
                    body = f"# {title}\n\n*This file was empty when imported.*"
                    tags = ["empty-file", "generic-import"]
                else:
                    # Format as code block with basic processing
                    body = self._format_unknown_text_content(content, file_path, mime_type)
                    tags = self.extract_hashtags_safe(content) + ["generic-import"]
            except Exception:
                # If reading fails, treat as binary
                body = self._create_binary_file_note(file_path, mime_type, file_metadata.get("size", 0))
                tags = ["binary", "read-error", "generic-import"]

            # Add file type tags
            extension = file_path.suffix.lower()
            if extension:
                tags.append(f"ext{extension.replace('.', '-')}")

            if mime_type:
                main_type = mime_type.split("/")[0]
                tags.append(f"type-{main_type}")

        # Create note using enhanced base class utilities
        return self.create_imported_note_safe(
            title=title,
            body=body,
            file_path=file_path,
            tags=list(set(tags)),  # Remove duplicates
            additional_metadata={
                "original_format": "generic",
                "file_extension": extension,
                "mime_type": mime_type,
                "is_binary": is_binary,
            },
        )

    def _format_unknown_text_content(self, content: str, file_path: Path, mime_type: Optional[str]) -> str:
        """Format unknown text content with basic processing."""
        extension = file_path.suffix.lower()
        
        # For code-like files, use syntax highlighting
        if extension in {".py", ".js", ".java", ".cpp", ".c", ".h", ".css", ".sql", ".json", ".xml"}:
            language = extension.lstrip(".")
            if language == "py":
                language = "python"
            elif language == "js":
                language = "javascript"
            
            return f"# {self._extract_title_from_path(file_path)}\n\n```{language}\n{content}\n```"
        
        # For log files, preserve formatting
        elif extension in {".log"}:
            return f"# {self._extract_title_from_path(file_path)}\n\n```\n{content}\n```"
        
        # For other text files, add basic formatting
        else:
            lines = content.split('\n')
            if len(lines) > 1 and len(lines[0]) < 100:
                # First line might be a title
                title = lines[0].strip()
                body = '\n'.join(lines[1:]).strip()
                if title and body:
                    return f"# {title}\n\n{body}"
            
            return f"# {self._extract_title_from_path(file_path)}\n\n{content}"

    def _is_binary_file(self, file_path: Path) -> bool:
        """Check if file is binary."""
        try:
            # Read first 8192 bytes to check for binary content
            with open(file_path, "rb") as f:
                chunk = f.read(8192)
                if not chunk:
                    return False

            # Check for null bytes (common in binary files)
            if b'\x00' in chunk:
                return True

            # Check for high percentage of non-text characters
            text_chars = sum(1 for byte in chunk if 32 <= byte <= 126 or byte in (9, 10, 13))
            return (text_chars / len(chunk)) < 0.75

        except Exception:
            return False

    def _detect_mime_type(self, file_path: Path) -> Optional[str]:
        """Detect MIME type of file."""
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return mime_type

    def _extract_title_from_path(self, file_path: Path) -> str:
        """Extract title from file path."""
        # Use filename without extension as base title
        title = file_path.stem

        # Replace common separators with spaces
        title = title.replace("_", " ").replace("-", " ").replace(".", " ")
        
        # Remove extra whitespace
        title = " ".join(title.split())

        # Capitalize first letter of each word
        title = " ".join(word.capitalize() for word in title.split())

        return title or "Untitled"

    def _create_binary_file_note(self, file_path: Path, mime_type: Optional[str], file_size: int) -> str:
        """Create note content for binary files."""
        size_mb = file_size / (1024 * 1024)

        content = f"# {self._extract_title_from_path(file_path)}\n\n"
        content += "**Binary File Information**\n\n"
        content += f"- **File**: `{file_path.name}`\n"
        content += f"- **Size**: {file_size:,} bytes ({size_mb:.2f} MB)\n"
        content += f"- **Type**: {mime_type or 'Unknown'}\n"
        content += f"- **Extension**: {file_path.suffix}\n"
        content += f"- **Location**: `{file_path.parent}`\n\n"
        content += "This is a binary file that cannot be displayed as text. "
        content += "The original file should be accessed directly from its location.\n\n"
        content += f"**Original Path**: `{file_path}`\n"

        return content


    def _format_json_content(self, content: str, title: str) -> str:
        """Format JSON content."""
        try:
            import json

            # Try to parse and pretty-print JSON
            parsed = json.loads(content)
            formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
            return f"# {title}\n\n```json\n{formatted}\n```"
            
        except json.JSONDecodeError:
            # If not valid JSON, return as-is in code block
            return f"# {title}\n\n```json\n{content}\n```"

    def _format_xml_content(self, content: str, title: str) -> str:
        """Format XML content."""
        try:
            import xml.dom.minidom
            
            # Try to pretty-print XML
            dom = xml.dom.minidom.parseString(content)
            formatted = dom.toprettyxml(indent="  ")
            # Remove empty lines
            lines = [line for line in formatted.split('\n') if line.strip()]
            formatted = '\n'.join(lines)
            return f"# {title}\n\n```xml\n{formatted}\n```"

        except Exception:
            # If parsing fails, return as-is in code block
            return f"# {title}\n\n```xml\n{content}\n```"

    def _format_code_content(self, content: str, extension: str, title: str) -> str:
        """Format code content with syntax highlighting."""
        # Map extensions to language names for syntax highlighting
        language_map = {
            "py": "python",
            "js": "javascript",
            "java": "java",
            "cpp": "cpp",
            "c": "c",
            "h": "c",
            "css": "css",
            "sql": "sql"
        }
        
        language = language_map.get(extension, extension)
        return f"# {title}\n\n```{language}\n{content}\n```"

    def _format_log_content(self, content: str, title: str) -> str:
        """Format log file content."""
        # Split into lines and add some basic formatting
        lines = content.strip().split("\n")

        # Limit to last 1000 lines for very large logs
        if len(lines) > 1000:
            content = "\n".join(lines[-1000:])
            header = f"# {title}\n\n**Log File** (showing last 1000 of {len(lines)} lines)\n\n"
        else:
            header = f"# {title}\n\n**Log File Content**\n\n"

        return header + f"```log\n{content}\n```"

    async def _handle_tsv_format(self, file_path: Path) -> Optional[ImportedNote]:
        """Handle TSV (Tab-separated values) files."""
        try:
            content, used_encoding = self.read_file_safe(file_path)
            title = self._extract_title_from_path(file_path)
            
            # Convert TSV to Markdown table using shared utility
            body = csv_to_markdown_table(content, title, delimiter="\t")
            tags = self.extract_hashtags_safe(content) + ["tsv", "tabular", "generic-import"]
            
            return self.create_imported_note_safe(
                title=title,
                body=body,
                file_path=file_path,
                tags=tags,
                additional_metadata={
                    "original_format": "tsv",
                    "encoding": used_encoding,
                },
            )
        except Exception as e:
            print(f"Warning: TSV processing failed for {file_path}: {str(e)}")
            return await self._handle_unknown_format(file_path)

    async def _handle_json_format(self, file_path: Path) -> Optional[ImportedNote]:
        """Handle JSON files."""
        try:
            content, used_encoding = self.read_file_safe(file_path)
            title = self._extract_title_from_path(file_path)
            
            # Format JSON content
            body = self._format_json_content(content, title)
            tags = self.extract_hashtags_safe(content) + ["json", "data", "generic-import"]
            
            return self.create_imported_note_safe(
                title=title,
                body=body,
                file_path=file_path,
                tags=tags,
                additional_metadata={
                    "original_format": "json",
                    "encoding": used_encoding,
                },
            )
        except Exception as e:
            print(f"Warning: JSON processing failed for {file_path}: {str(e)}")
            return await self._handle_unknown_format(file_path)

    async def _handle_xml_format(self, file_path: Path) -> Optional[ImportedNote]:
        """Handle XML files."""
        try:
            content, used_encoding = self.read_file_safe(file_path)
            title = self._extract_title_from_path(file_path)
            
            # Format XML content
            body = self._format_xml_content(content, title)
            tags = self.extract_hashtags_safe(content) + ["xml", "markup", "generic-import"]
            
            return self.create_imported_note_safe(
                title=title,
                body=body,
                file_path=file_path,
                tags=tags,
                additional_metadata={
                    "original_format": "xml",
                    "encoding": used_encoding,
                },
            )
        except Exception as e:
            print(f"Warning: XML processing failed for {file_path}: {str(e)}")
            return await self._handle_unknown_format(file_path)

    async def _handle_code_format(self, file_path: Path) -> Optional[ImportedNote]:
        """Handle code files."""
        try:
            content, used_encoding = self.read_file_safe(file_path)
            title = self._extract_title_from_path(file_path)
            extension = file_path.suffix.lower().lstrip(".")
            
            # Format code content
            body = self._format_code_content(content, extension, title)
            tags = self.extract_hashtags_safe(content) + [extension, "code", "generic-import"]
            
            return self.create_imported_note_safe(
                title=title,
                body=body,
                file_path=file_path,
                tags=tags,
                additional_metadata={
                    "original_format": extension,
                    "encoding": used_encoding,
                },
            )
        except Exception as e:
            print(f"Warning: Code processing failed for {file_path}: {str(e)}")
            return await self._handle_unknown_format(file_path)

    async def _handle_log_format(self, file_path: Path) -> Optional[ImportedNote]:
        """Handle log files."""
        try:
            content, used_encoding = self.read_file_safe(file_path)
            title = self._extract_title_from_path(file_path)
            
            # Format log content
            body = self._format_log_content(content, title)
            tags = self.extract_hashtags_safe(content) + ["log", "text", "generic-import"]
            
            return self.create_imported_note_safe(
                title=title,
                body=body,
                file_path=file_path,
                tags=tags,
                additional_metadata={
                    "original_format": "log",
                    "encoding": used_encoding,
                },
            )
        except Exception as e:
            print(f"Warning: Log processing failed for {file_path}: {str(e)}")
            return await self._handle_unknown_format(file_path)
