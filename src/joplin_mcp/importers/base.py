"""Base classes for import functionality."""

import os
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from ..types.import_types import ImportedNote, ImportOptions
from .utils import (
    read_file_with_encoding,
    validate_file_basic,
    validate_file_size as util_validate_file_size,
    get_file_metadata,
    scan_directory_for_files,
    validate_directory_has_files,
    extract_title_from_content,
    extract_hashtags,
    parse_flexible_timestamp,
)


class ImportError(Exception):
    """Base exception for import-related errors."""

    pass


class ImportValidationError(ImportError):
    """Exception raised when import validation fails."""

    pass


class ImportProcessingError(ImportError):
    """Exception raised during import processing."""

    pass


class BaseImporter(ABC):
    """Abstract base class for all import formats.

    This class defines the interface that all importers must implement
    to provide consistent behavior across different file formats.
    """

    def __init__(self, options: Optional[ImportOptions] = None):
        """Initialize the importer with optional configuration.

        Args:
            options: Import configuration options
        """
        self.options = options or ImportOptions()

    @abstractmethod
    async def parse(self, source: str) -> List[ImportedNote]:
        """Parse the source and return a list of ImportedNote objects.

        Args:
            source: Path to file or directory to import

        Returns:
            List of ImportedNote objects ready for processing

        Raises:
            ImportValidationError: If source validation fails
            ImportProcessingError: If parsing fails
        """
        pass

    @abstractmethod
    async def validate(self, source: str) -> bool:
        """Validate that the source can be imported by this importer.

        Args:
            source: Path to file or directory to validate

        Returns:
            True if source is valid for this importer

        Raises:
            ImportValidationError: If validation fails with specific error
        """
        pass

    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Get list of file extensions supported by this importer.

        Returns:
            List of file extensions (without dots, e.g., ['md', 'txt'])
        """
        pass

    def get_display_name(self) -> str:
        """Get human-readable display name for this importer.

        Returns:
            Display name for the importer
        """
        return self.__class__.__name__.replace("Importer", "")

    def supports_file(self, file_path: str) -> bool:
        """Check if this importer supports the given file.

        Args:
            file_path: Path to the file to check

        Returns:
            True if file is supported by this importer
        """
        path = Path(file_path)
        if not path.exists():
            return False

        extension = path.suffix.lstrip(".").lower()
        return extension in [ext.lstrip(".") for ext in self.get_supported_extensions()]

    async def parse_directory(self, directory_path: str) -> List[ImportedNote]:
        """Parse all supported files in a directory.

        Args:
            directory_path: Path to directory to import

        Returns:
            List of ImportedNote objects from all files in directory
        """
        path = Path(directory_path)
        if not path.exists() or not path.is_dir():
            raise ImportValidationError(f"Directory not found: {directory_path}")

        if not self.supports_directory():
            raise ImportValidationError(
                f"Directory import not supported by {self.__class__.__name__}"
            )

        # Find all supported files
        supported_files = await self.scan_directory(directory_path)

        if not supported_files:
            raise ImportValidationError(
                f"No supported files found in directory: {directory_path}"
            )

        # Parse all files
        all_notes = []
        for file_path in supported_files:
            try:
                # Validate and parse each file
                await self.validate(file_path)
                notes = await self.parse(file_path)
                all_notes.extend(notes)
            except Exception as e:
                # Log error but continue with other files
                logging.getLogger(__name__).warning(
                    "Failed to import %s: %s", file_path, str(e)
                )
                continue

        return all_notes

    def supports_directory(self) -> bool:
        """Check if this importer supports directory imports.

        Returns:
            True if directory imports are supported
        """
        # Default: most importers support directory scanning
        return True

    async def scan_directory(self, directory_path: str) -> List[str]:
        """Scan directory for supported files.

        Args:
            directory_path: Path to directory to scan

        Returns:
            List of file paths that this importer can handle
        """
        # Use enhanced utility method
        path_objects = self.scan_directory_safe(Path(directory_path))
        return [str(p) for p in path_objects]

    def validate_source_exists(self, source: str) -> None:
        """Validate that the source path exists.

        Args:
            source: Path to validate

        Raises:
            ImportValidationError: If source doesn't exist
        """
        path = Path(source)
        if not path.exists():
            raise ImportValidationError(f"Source path does not exist: {source}")

    def validate_source_readable(self, source: str) -> None:
        """Validate that the source is readable.

        Args:
            source: Path to validate

        Raises:
            ImportValidationError: If source is not readable
        """
        path = Path(source)
        if not os.access(path, os.R_OK):
            raise ImportValidationError(f"Source is not readable: {source}")

    def validate_file_size(self, file_path: str, max_size_mb: int = 100) -> None:
        """Validate that file size is within limits.

        Args:
            file_path: Path to file to check
            max_size_mb: Maximum allowed size in MB

        Raises:
            ImportValidationError: If file is too large
        """
        try:
            util_validate_file_size(Path(file_path), max_size_mb)
        except Exception as e:
            raise ImportValidationError(str(e)) from e

    async def get_file_list(self, source: str) -> List[str]:
        """Get list of files to process from source.

        Args:
            source: Source directory or file path

        Returns:
            List of file paths to process
        """
        path = Path(source)

        if path.is_file():
            return [str(path)]

        if path.is_dir():
            files = []
            supported_extensions = self.get_supported_extensions()

            # Use file pattern if specified
            if self.options.file_pattern:
                files.extend(path.glob(self.options.file_pattern))
            else:
                # Find all supported files
                for ext in supported_extensions:
                    files.extend(path.rglob(f"*.{ext}"))

            return [str(f) for f in files if f.is_file()]

        return []

    def extract_notebook_from_path(
        self, file_path: str, base_path: str
    ) -> Optional[str]:
        """Extract notebook name from file path structure.

        Args:
            file_path: Full path to the file
            base_path: Base import directory path

        Returns:
            Notebook name derived from directory structure, or None
        """
        if not self.options.preserve_structure:
            return self.options.target_notebook

        file_path_obj = Path(file_path)
        base_path_obj = Path(base_path)

        try:
            # Get relative path from import base to file
            rel_path = file_path_obj.relative_to(base_path_obj)

            # Use parent directory as notebook name
            if rel_path.parent != Path("."):
                return str(rel_path.parent).replace(os.sep, " / ")

        except ValueError:
            # File is not under base path
            pass

        return self.options.target_notebook

    # Enhanced utility methods using shared utilities
    
    def read_file_safe(self, file_path: Path, encodings: Optional[List[str]] = None) -> Tuple[str, str]:
        """Safely read file content with encoding detection.
        
        Args:
            file_path: Path to the file to read
            encodings: Optional list of encodings to try
            
        Returns:
            Tuple of (content, used_encoding)
            
        Raises:
            ImportProcessingError: If file cannot be read
        """
        try:
            return read_file_with_encoding(file_path, encodings)
        except Exception as e:
            raise ImportProcessingError(f"Cannot read file {file_path}: {str(e)}") from e
    
    def validate_file_comprehensive(self, file_path: Path, allow_empty: bool = False) -> None:
        """Perform comprehensive file validation using shared utilities.
        
        Args:
            file_path: Path to validate
            allow_empty: Whether to allow empty files
            
        Raises:
            ImportValidationError: If validation fails
        """
        try:
            validate_file_basic(file_path, self.get_supported_extensions(), allow_empty)
            
            # Also validate size if specified in options
            max_size = getattr(self.options, 'max_file_size_mb', None)
            if max_size:
                util_validate_file_size(file_path, max_size)
                
        except Exception as e:
            raise ImportValidationError(str(e)) from e
    
    def validate_directory_comprehensive(self, directory_path: Path) -> None:
        """Validate directory contains supported files.
        
        Args:
            directory_path: Directory to validate
            
        Raises:
            ImportValidationError: If validation fails
        """
        try:
            validate_directory_has_files(directory_path, self.get_supported_extensions())
        except Exception as e:
            raise ImportValidationError(str(e)) from e
    
    def scan_directory_safe(self, directory_path: Path, recursive: bool = True) -> List[Path]:
        """Scan directory for supported files using shared utilities.
        
        Args:
            directory_path: Directory to scan
            recursive: Whether to scan recursively
            
        Returns:
            List of supported file paths
        """
        extensions = self.get_supported_extensions()
        
        # Special case: if no extensions specified, scan all files
        # This allows importers like GenericImporter to handle any file type
        if not extensions:
            glob_method = directory_path.rglob if recursive else directory_path.glob
            return [f for f in glob_method("*") if f.is_file()]
        
        return scan_directory_for_files(directory_path, extensions, recursive)
    
    def extract_title_safe(self, content: str, filename_fallback: str) -> str:
        """Extract title from content using shared logic.
        
        Args:
            content: File content to analyze
            filename_fallback: Fallback title from filename
            
        Returns:
            Extracted or generated title
        """
        return extract_title_from_content(content, filename_fallback)
    
    def extract_hashtags_safe(self, content: str) -> List[str]:
        """Extract hashtags from content using shared logic and options.
        
        Respects import option 'extract_hashtags' (default: True).
        """
        try:
            if not getattr(self.options, "import_options", {}).get("extract_hashtags", True):
                return []
        except Exception:
            pass
        return extract_hashtags(content)
    
    def get_file_metadata_safe(self, file_path: Path) -> dict:
        """Get file metadata using shared utilities.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with file metadata
            
        Raises:
            ImportProcessingError: If metadata cannot be extracted
        """
        try:
            return get_file_metadata(file_path)
        except Exception as e:
            raise ImportProcessingError(f"Cannot get metadata for {file_path}: {str(e)}") from e
    
    def parse_timestamp_safe(self, timestamp_value, formats: Optional[List[str]] = None) -> Optional[datetime]:
        """Parse timestamp using flexible parsing.
        
        Args:
            timestamp_value: Timestamp in various formats
            formats: Optional list of formats to try
            
        Returns:
            Parsed datetime or None
        """
        return parse_flexible_timestamp(timestamp_value, formats)
    
    def create_imported_note_safe(
        self, 
        title: str, 
        body: str, 
        file_path: Path,
        tags: Optional[List[str]] = None,
        notebook: Optional[str] = None,
        is_todo: bool = False,
        todo_completed: bool = False,
        created_time: Optional[datetime] = None,
        updated_time: Optional[datetime] = None,
        additional_metadata: Optional[dict] = None
    ) -> ImportedNote:
        """Create ImportedNote with standard metadata population.
        
        Args:
            title: Note title
            body: Note content
            file_path: Source file path
            tags: Optional tags list
            notebook: Optional notebook name
            is_todo: Whether note is a todo
            todo_completed: Whether todo is completed
            created_time: Optional creation time
            updated_time: Optional update time
            additional_metadata: Additional metadata to include
            
        Returns:
            Properly constructed ImportedNote
        """
        # Get file metadata if timestamps not provided
        file_metadata = self.get_file_metadata_safe(file_path)
        
        if not created_time:
            created_time = file_metadata["created_time"]
        if not updated_time:
            updated_time = file_metadata["updated_time"]
        
        # Build metadata
        metadata = {
            "import_method": self.__class__.__name__.lower(),
            "original_format": self.get_display_name().lower(),
            **file_metadata,
        }
        
        if additional_metadata:
            metadata.update(additional_metadata)
        
        return ImportedNote(
            title=title,
            body=body,
            notebook=notebook,
            tags=tags or [],
            is_todo=is_todo,
            todo_completed=todo_completed,
            created_time=created_time,
            updated_time=updated_time,
            metadata=metadata,
        )
