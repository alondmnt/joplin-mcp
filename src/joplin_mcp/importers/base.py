"""Base classes for import functionality."""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from ..types.import_types import ImportedNote, ImportOptions


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
                print(f"Warning: Failed to import {file_path}: {str(e)}")
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
        path = Path(directory_path)
        if not path.exists() or not path.is_dir():
            return []

        supported_files = []
        extensions = [
            ext.lstrip(".").lower() for ext in self.get_supported_extensions()
        ]

        # Recursively scan directory
        for file_path in path.rglob("*"):
            if file_path.is_file():
                extension = file_path.suffix.lstrip(".").lower()
                if extension in extensions:
                    supported_files.append(str(file_path))

        return sorted(supported_files)

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
        path = Path(file_path)
        if path.is_file():
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > max_size_mb:
                raise ImportValidationError(
                    f"File too large: {size_mb:.1f}MB (max: {max_size_mb}MB)"
                )

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
