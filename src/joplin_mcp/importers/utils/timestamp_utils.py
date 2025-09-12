"""Timestamp parsing utilities for importers."""

from datetime import datetime
from typing import List, Optional, Union


def parse_flexible_timestamp(
    timestamp_input: Union[str, int, float, None],
    formats: Optional[List[str]] = None
) -> Optional[datetime]:
    """Parse timestamp from various formats.
    
    Args:
        timestamp_input: Timestamp in various formats (string, int, float)
        formats: List of datetime format strings to try
        
    Returns:
        Parsed datetime object or None if parsing fails
    """
    if not timestamp_input:
        return None
    
    # Handle numeric timestamps (Joplin format - milliseconds since epoch)
    if isinstance(timestamp_input, (int, float)):
        try:
            return timestamp_to_datetime(timestamp_input)
        except (ValueError, TypeError):
            return None
    
    # Handle string timestamps
    if isinstance(timestamp_input, str):
        timestamp_str = timestamp_input.strip()
        if not timestamp_str:
            return None
        
        # Try default formats if none provided
        if formats is None:
            formats = get_default_timestamp_formats()
        
        # Try each format
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
        
        # Try ISO format parsing as fallback
        try:
            # Handle ISO format with timezone
            iso_str = timestamp_str
            if iso_str.endswith("Z"):
                iso_str = iso_str[:-1] + "+00:00"
            return datetime.fromisoformat(iso_str)
        except ValueError:
            pass
        
        # Try Evernote format (YYYYMMDDTHHMMSSZ)
        if "T" in timestamp_str:
            try:
                clean_timestamp = timestamp_str.replace("T", "").replace("Z", "")
                if len(clean_timestamp) >= 14:
                    return datetime.strptime(clean_timestamp[:14], "%Y%m%d%H%M%S")
            except ValueError:
                pass
    
    return None


def timestamp_to_datetime(timestamp_ms: Union[int, float]) -> datetime:
    """Convert millisecond timestamp to datetime.
    
    Args:
        timestamp_ms: Timestamp in milliseconds since epoch
        
    Returns:
        Datetime object
        
    Raises:
        ValueError: If timestamp is invalid
    """
    try:
        # Convert milliseconds to seconds
        timestamp_seconds = float(timestamp_ms) / 1000
        return datetime.fromtimestamp(timestamp_seconds)
    except (ValueError, TypeError, OSError) as e:
        raise ValueError(f"Invalid timestamp: {timestamp_ms}") from e


def get_default_timestamp_formats() -> List[str]:
    """Get list of common timestamp formats to try.
    
    Returns:
        List of format strings for datetime.strptime
    """
    return [
        # ISO formats
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ", 
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        
        # Standard formats
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        
        # Alternative separators
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
        
        # Different order formats
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M", 
        "%m/%d/%Y",
        
        # Dot separators
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        
        # Human readable formats
        "%B %d, %Y %H:%M:%S",
        "%B %d, %Y %H:%M",
        "%B %d, %Y",
        "%b %d, %Y %H:%M:%S",
        "%b %d, %Y %H:%M",
        "%b %d, %Y",
        "%d %B %Y %H:%M:%S",
        "%d %B %Y %H:%M", 
        "%d %B %Y",
        "%d %b %Y %H:%M:%S",
        "%d %b %Y %H:%M",
        "%d %b %Y",
        
        # Evernote/Joplin formats
        "%Y%m%d%H%M%S",
        "%Y%m%d",
    ]


def parse_frontmatter_timestamp(timestamp_value: Union[str, int, float, datetime, None]) -> Optional[datetime]:
    """Parse timestamp from frontmatter which can be in various formats.
    
    Args:
        timestamp_value: Timestamp value from frontmatter
        
    Returns:
        Parsed datetime or None
    """
    if isinstance(timestamp_value, datetime):
        return timestamp_value
    
    return parse_flexible_timestamp(timestamp_value)


def parse_html_meta_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse timestamp from HTML meta tags.
    
    Args:
        timestamp_str: Timestamp string from HTML meta
        
    Returns:
        Parsed datetime or None
    """
    # HTML meta tags often use specific formats
    html_formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S", 
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%d/%m/%Y",
        "%m/%d/%Y", 
        "%d.%m.%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]
    
    return parse_flexible_timestamp(timestamp_str, html_formats)


def parse_joplin_timestamp(timestamp_ms: Union[str, int, float, None]) -> Optional[datetime]:
    """Parse Joplin-specific timestamp format.
    
    Args:
        timestamp_ms: Joplin timestamp (milliseconds since epoch)
        
    Returns:
        Parsed datetime or None
    """
    if not timestamp_ms:
        return None
    
    try:
        # Joplin stores timestamps as milliseconds since epoch
        if isinstance(timestamp_ms, str):
            timestamp_ms = int(timestamp_ms)
        return timestamp_to_datetime(timestamp_ms)
    except (ValueError, TypeError):
        return None


def parse_evernote_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse Evernote ENEX timestamp format.
    
    Args:
        timestamp_str: Evernote timestamp string
        
    Returns:
        Parsed datetime or None
    """
    if not timestamp_str:
        return None
    
    try:
        # Evernote timestamps are often in format: YYYYMMDDTHHMMSSZ
        if "T" in timestamp_str:
            clean_timestamp = timestamp_str.replace("T", "").replace("Z", "")
            if len(clean_timestamp) >= 14:
                return datetime.strptime(clean_timestamp[:14], "%Y%m%d%H%M%S")
        
        # Try other formats
        evernote_formats = [
            "%Y%m%d%H%M%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ]
        
        return parse_flexible_timestamp(timestamp_str, evernote_formats)
        
    except Exception:
        return None
