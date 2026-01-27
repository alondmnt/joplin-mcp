"""File handling utilities for importers."""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# Define exceptions locally to avoid circular imports
class ImportValidationError(Exception):
    """Exception raised when import validation fails."""
    pass

class ImportProcessingError(Exception):
    """Exception raised during import processing."""
    pass


def read_file_with_encoding(file_path: Path, encodings: Optional[List[str]] = None) -> Tuple[str, str]:
    """Read file content with automatic encoding detection.
    
    Args:
        file_path: Path to the file to read
        encodings: List of encodings to try (uses default if None)
        
    Returns:
        Tuple of (content, used_encoding)
        
    Raises:
        ImportProcessingError: If file cannot be read with any encoding
    """
    if encodings is None:
        encodings = ["utf-8", "utf-16", "latin-1", "cp1252", "iso-8859-1"]
    
    for encoding in encodings:
        try:
            with open(file_path, encoding=encoding) as f:
                content = f.read()
            return content, encoding
        except UnicodeDecodeError:
            continue
        except (IOError, OSError, PermissionError) as e:
            raise ImportProcessingError(
                f"Cannot read file {file_path}: {str(e)}"
            ) from e
    
    raise ImportProcessingError(
        f"Could not read file with any supported encoding: {file_path}"
    )


def validate_file_basic(file_path: Path, supported_extensions: Optional[List[str]] = None, allow_empty: bool = False) -> None:
    """Perform basic file validation.
    
    Args:
        file_path: Path to validate
        supported_extensions: List of supported extensions (without dots)
        allow_empty: Whether to allow empty files
        
    Raises:
        ImportValidationError: If validation fails
    """
    if not file_path.exists():
        raise ImportValidationError(f"File not found: {file_path}")
    
    if not file_path.is_file():
        raise ImportValidationError(f"Path is not a file: {file_path}")
    
    if supported_extensions:
        extension = file_path.suffix.lstrip(".").lower()
        if extension not in supported_extensions:
            raise ImportValidationError(
                f"Unsupported file extension: {file_path.suffix}. "
                f"Supported: {', '.join(supported_extensions)}"
            )
    
    if not allow_empty and file_path.stat().st_size == 0:
        raise ImportValidationError(f"File is empty: {file_path}")


def validate_file_size(file_path: Path, max_size_mb: int = 100) -> None:
    """Validate file size is within limits.
    
    Args:
        file_path: Path to file to check
        max_size_mb: Maximum allowed size in MB
        
    Raises:
        ImportValidationError: If file is too large or doesn't exist
    """
    if not file_path.exists():
        raise ImportValidationError(f"File not found: {file_path}")
    
    if not file_path.is_file():
        raise ImportValidationError(f"Path is not a file: {file_path}")
    
    size_mb = file_path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ImportValidationError(
            f"File too large: {size_mb:.1f}MB (max: {max_size_mb}MB)"
        )


def get_file_metadata(file_path: Path) -> dict:
    """Extract common file metadata.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with file metadata
        
    Raises:
        ImportProcessingError: If file cannot be accessed
    """
    try:
        stat = file_path.stat()
        
        # Use birth time (creation time) if available (macOS/Windows), otherwise fall back to ctime
        if hasattr(stat, 'st_birthtime') and stat.st_birthtime > 0:
            created_time = datetime.fromtimestamp(stat.st_birthtime)
        else:
            created_time = datetime.fromtimestamp(stat.st_ctime)
            
        return {
            "created_time": created_time,
            "updated_time": datetime.fromtimestamp(stat.st_mtime),
            "modified_time": datetime.fromtimestamp(stat.st_mtime),  # Alias for compatibility
            "file_size": stat.st_size,
            "size": stat.st_size,  # Alias for compatibility
            "source_file": str(file_path),
        }
    except (OSError, FileNotFoundError) as e:
        raise ImportProcessingError(
            f"Cannot access file metadata for {file_path}: {str(e)}"
        ) from e


def scan_directory_for_files(
    directory_path: Path, 
    extensions: List[str], 
    recursive: bool = True
) -> List[Path]:
    """Scan directory for files with specific extensions.
    
    Args:
        directory_path: Directory to scan
        extensions: List of file extensions (without dots)
        recursive: Whether to scan recursively
        
    Returns:
        List of file paths found
    """
    if not directory_path.exists() or not directory_path.is_dir():
        return []
    
    files = []
    glob_method = directory_path.rglob if recursive else directory_path.glob
    
    for extension in extensions:
        pattern = f"*.{extension.lstrip('.')}"
        files.extend(glob_method(pattern))
    
    return [f for f in files if f.is_file()]


def validate_directory_has_files(
    directory_path: Path, 
    extensions: List[str], 
    min_files: int = 1
) -> None:
    """Validate directory contains files with specified extensions.
    
    Args:
        directory_path: Directory to validate
        extensions: Required file extensions (empty list means any files)
        min_files: Minimum number of files required
        
    Raises:
        ImportValidationError: If validation fails
    """
    if not directory_path.exists():
        raise ImportValidationError(f"Directory not found: {directory_path}")
    
    if not directory_path.is_dir():
        raise ImportValidationError(f"Path is not a directory: {directory_path}")
    
    # Handle empty extensions (scan all files)
    if not extensions:
        files = [f for f in directory_path.rglob("*") if f.is_file()]
        ext_str = "any"
    else:
        files = scan_directory_for_files(directory_path, extensions)
        ext_str = ", ".join(f".{ext}" for ext in extensions)
    
    if len(files) < min_files:
        raise ImportValidationError(
            f"Directory contains insufficient files ({len(files)} found, {min_files} required) "
            f"with extensions: {ext_str} in {directory_path}"
        )


def is_readable_text_file(file_path: Path, sample_size: int = 1024) -> bool:
    """Check if file appears to be readable text.
    
    Args:
        file_path: Path to check
        sample_size: Number of bytes to sample
        
    Returns:
        True if file appears to be text
    """
    try:
        with open(file_path, "rb") as f:
            sample = f.read(sample_size)
        
        # Check for null bytes (common in binary files)
        if b"\x00" in sample:
            return False
        
        # Try to decode as text
        try:
            sample.decode("utf-8")
            return True
        except UnicodeDecodeError:
            # Try other common encodings
            for encoding in ["latin-1", "cp1252"]:
                try:
                    sample.decode(encoding)
                    return True
                except UnicodeDecodeError:
                    continue
            return False
    except Exception:
        return False
