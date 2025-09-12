"""
ZIP importer for Joplin MCP.

Handles ZIP files, particularly OneNote Notebook format and other zipped content.
Extracts and processes supported file formats from ZIP archives.
"""

import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..types.import_types import ImportedNote
from .base import BaseImporter, ImportProcessingError, ImportValidationError


class ZIPImporter(BaseImporter):
    """Importer for ZIP archives, including OneNote Notebook format."""

    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return ["zip"]

    def can_import(self, file_path: Path) -> bool:
        """Check if file can be imported as ZIP."""
        extension = file_path.suffix.lower().lstrip(".")
        return extension in self.get_supported_extensions()

    def supports_directory(self) -> bool:
        """ZIP format only supports file imports."""
        return False

    async def validate(self, file_path: str) -> bool:
        """Validate ZIP file can be processed."""
        path = Path(file_path)

        # Use enhanced base class validation for basic checks
        self.validate_file_comprehensive(path)

        # Additional ZIP-specific validation
        try:
            with zipfile.ZipFile(file_path, "r") as zip_file:
                # Check if it's a valid ZIP file
                zip_file.testzip()

                # Get list of files in the archive
                file_list = zip_file.namelist()
                if not file_list:
                    from .base import ImportValidationError
                    raise ImportValidationError(f"ZIP file is empty: {file_path}")

                # Check if it contains any supported file types
                supported_extensions = {".md", ".txt", ".html", ".htm", ".csv", ".enex"}
                has_supported_files = any(
                    Path(filename).suffix.lower() in supported_extensions
                    for filename in file_list
                    if not filename.endswith("/")
                )

                if not has_supported_files:
                    from .base import ImportValidationError
                    raise ImportValidationError(
                        f"ZIP file contains no supported file formats: {file_path}"
                    )

        except zipfile.BadZipFile as e:
            from .base import ImportValidationError
            raise ImportValidationError(f"Invalid ZIP file: {file_path}") from e

        return True

    async def parse(self, file_path: str) -> List[ImportedNote]:
        """Parse ZIP file and convert to ImportedNote objects."""
        try:
            path = Path(file_path)
            notes = []

            with zipfile.ZipFile(file_path, "r") as zip_file:
                # Get list of all files in the archive
                file_list = zip_file.namelist()

                # Detect if this is a OneNote Notebook
                is_onenote = self._detect_onenote_format(file_list)

                # Process each file in the archive
                for zip_path in file_list:
                    # Skip directories
                    if zip_path.endswith("/"):
                        continue

                    zip_file_path = Path(zip_path)
                    extension = zip_file_path.suffix.lower()

                    # Check if this is a supported file type
                    if extension in {".md", ".txt", ".html", ".htm", ".csv", ".enex"}:
                        try:
                            # Extract file content
                            with zip_file.open(zip_path) as extracted_file:
                                content = extracted_file.read()

                            # Create a temporary note from the extracted content
                            note = await self._process_extracted_file(
                                zip_file_path, content, path, is_onenote
                            )

                            if note:
                                notes.append(note)

                        except Exception as e:
                            # Log error but continue with other files
                            print(f"Warning: Failed to process {zip_path}: {str(e)}")
                            continue

            return notes

        except Exception as e:
            if isinstance(e, (ImportValidationError, ImportProcessingError)):
                raise
            raise ImportProcessingError(
                f"Error parsing ZIP file {file_path}: {str(e)}"
            ) from e

    def _detect_onenote_format(self, file_list: List[str]) -> bool:
        """Detect if ZIP contains OneNote Notebook structure."""
        # OneNote notebooks typically have specific folder structures and file types
        onenote_indicators = [
            ".one",  # OneNote section files
            "Open Notebook.onetoc2",  # OneNote table of contents
            ".onetoc2",  # Section group files
        ]

        for filename in file_list:
            if any(indicator in filename for indicator in onenote_indicators):
                return True

        return False

    async def _process_extracted_file(
        self, zip_file_path: Path, content: bytes, zip_source: Path, is_onenote: bool
    ) -> Optional[ImportedNote]:
        """Process an extracted file from the ZIP archive."""
        try:
            # Decode content to text
            text_content = self._decode_content(content)
            if not text_content:
                return None

            # Extract title from filename or content
            title = self._extract_title(zip_file_path, text_content)

            # Delegate file processing to GenericImporter for consistent handling
            body = await self._delegate_to_generic_importer(zip_file_path, text_content)

            # Extract hashtags using enhanced base class utilities
            tags = self.extract_hashtags_safe(text_content)

            # Add OneNote tag if detected
            if is_onenote and "onenote" not in tags:
                tags.append("onenote")

            # Get file metadata using enhanced base class utilities
            file_metadata = self.get_file_metadata_safe(zip_source)
            created_time = file_metadata.get("created_time")
            updated_time = file_metadata.get("updated_time")

            # Prepare additional metadata
            extension = zip_file_path.suffix.lower()
            additional_metadata = {
                "original_format": "zip",
                "zip_path": str(zip_file_path),
                "file_extension": extension,
                "is_onenote": is_onenote,
            }

            # Create note using enhanced base class utilities
            note = self.create_imported_note_safe(
                title=title,
                body=body,
                file_path=zip_source,
                tags=tags,
                created_time=created_time,
                updated_time=updated_time,
                additional_metadata=additional_metadata,
            )

            return note

        except Exception as e:
            raise ImportProcessingError(
                f"Error processing extracted file {zip_file_path}: {str(e)}"
            ) from e

    def _decode_content(self, content: bytes) -> Optional[str]:
        """Decode binary content to text."""
        # Try different encodings
        encodings = ["utf-8", "utf-16", "latin-1", "cp1252", "iso-8859-1"]

        for encoding in encodings:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue

        return None

    def _extract_title(self, file_path: Path, content: str) -> str:
        """Extract title from filename or content."""
        # Try to find title in content first
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
            elif line and len(line) <= 100 and not line.startswith("#"):
                return line

        # Fall back to filename
        return file_path.stem.replace("_", " ").replace("-", " ")


    def _extract_hashtags(self, content: str) -> List[str]:
        """Extract hashtags from content."""
        import re

        # Find hashtags in the content
        hashtag_pattern = r"#([a-zA-Z0-9_-]+)"
        hashtags = re.findall(hashtag_pattern, content)

        return list(set(hashtags))

    async def _delegate_to_generic_importer(self, file_path: Path, content: str) -> str:
        """Delegate file processing to GenericImporter - let it decide what to do with the file."""
        try:
            # Dynamic import to avoid circular dependencies
            from .generic_importer import GenericImporter
            
            # Create a GenericImporter instance with same options
            generic_importer = GenericImporter(self.options)
            
            # Create a temporary file to process
            import tempfile
            import os
            
            # Write content to a temporary file so GenericImporter can process it
            with tempfile.NamedTemporaryFile(mode='w', suffix=file_path.suffix, delete=False, encoding='utf-8') as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            try:
                # Let GenericImporter process the file and return the note
                note = await generic_importer._parse_file(Path(temp_file_path))
                
                # Extract the body content from the note
                if note and note.body:
                    return note.body
                else:
                    # Fallback if GenericImporter couldn't process it
                    title = self._extract_title(file_path, content)
                    return f"# {title}\n\n```\n{content}\n```"
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass
                
        except Exception:
            # Ultimate fallback: wrap in code block with title
            title = self._extract_title(file_path, content)
            return f"# {title}\n\n```\n{content}\n```"
