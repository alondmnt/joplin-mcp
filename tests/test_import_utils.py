"""Tests for import utilities - file handling, content processing, timestamps, and detectors."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# === Tests for file_utils.py ===


class TestReadFileWithEncoding:
    """Tests for read_file_with_encoding function."""

    def test_reads_utf8_file(self, tmp_path):
        """Should read UTF-8 encoded file successfully."""
        from joplin_mcp.imports.importers.utils.file_utils import read_file_with_encoding

        test_content = "Hello, World! 你好世界"
        test_file = tmp_path / "test.txt"
        test_file.write_text(test_content, encoding="utf-8")

        content, encoding = read_file_with_encoding(test_file)

        assert content == test_content
        assert encoding == "utf-8"

    def test_reads_latin1_file(self, tmp_path):
        """Should read Latin-1 encoded file when UTF-8 fails."""
        from joplin_mcp.imports.importers.utils.file_utils import read_file_with_encoding

        test_content = "Café résumé"
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(test_content.encode("latin-1"))

        content, encoding = read_file_with_encoding(test_file)

        assert "Caf" in content  # Partial match since encoding might vary
        assert encoding in ["utf-8", "latin-1", "cp1252"]

    def test_reads_with_custom_encodings(self, tmp_path):
        """Should try custom encodings list."""
        from joplin_mcp.imports.importers.utils.file_utils import read_file_with_encoding

        test_content = "Test content"
        test_file = tmp_path / "test.txt"
        test_file.write_text(test_content, encoding="utf-8")

        content, encoding = read_file_with_encoding(test_file, encodings=["ascii", "utf-8"])

        assert content == test_content

    def test_raises_error_for_nonexistent_file(self, tmp_path):
        """Should raise error for nonexistent file."""
        from joplin_mcp.imports.importers.utils.file_utils import read_file_with_encoding

        nonexistent = tmp_path / "nonexistent.txt"

        with pytest.raises(Exception):
            read_file_with_encoding(nonexistent)


class TestValidateFileBasic:
    """Tests for validate_file_basic function."""

    def test_validates_existing_file(self, tmp_path):
        """Should pass for valid file with correct extension."""
        from joplin_mcp.imports.importers.utils.file_utils import validate_file_basic

        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        # Should not raise
        validate_file_basic(test_file, ["md", "txt"])

    def test_raises_for_wrong_extension(self, tmp_path):
        """Should raise for unsupported extension."""
        from joplin_mcp.imports.importers.utils.file_utils import validate_file_basic, ImportValidationError

        test_file = tmp_path / "test.pdf"
        test_file.write_text("content")

        with pytest.raises(ImportValidationError, match="Unsupported file extension"):
            validate_file_basic(test_file, ["md", "txt"])

    def test_raises_for_nonexistent_file(self, tmp_path):
        """Should raise for nonexistent file."""
        from joplin_mcp.imports.importers.utils.file_utils import validate_file_basic, ImportValidationError

        nonexistent = tmp_path / "nonexistent.md"

        with pytest.raises(ImportValidationError, match="not found"):
            validate_file_basic(nonexistent, ["md"])

    def test_raises_for_empty_file_by_default(self, tmp_path):
        """Should raise for empty file by default."""
        from joplin_mcp.imports.importers.utils.file_utils import validate_file_basic, ImportValidationError

        test_file = tmp_path / "empty.md"
        test_file.write_text("")

        with pytest.raises(ImportValidationError, match="empty"):
            validate_file_basic(test_file, ["md"])

    def test_allows_empty_when_specified(self, tmp_path):
        """Should allow empty file when allow_empty=True."""
        from joplin_mcp.imports.importers.utils.file_utils import validate_file_basic

        test_file = tmp_path / "empty.md"
        test_file.write_text("")

        # Should not raise
        validate_file_basic(test_file, ["md"], allow_empty=True)


class TestValidateFileSize:
    """Tests for validate_file_size function."""

    def test_passes_for_small_file(self, tmp_path):
        """Should pass for file under size limit."""
        from joplin_mcp.imports.importers.utils.file_utils import validate_file_size

        test_file = tmp_path / "small.txt"
        test_file.write_text("Small content")

        # Should not raise
        validate_file_size(test_file, max_size_mb=1)

    def test_raises_for_large_file(self, tmp_path):
        """Should raise for file over size limit."""
        from joplin_mcp.imports.importers.utils.file_utils import validate_file_size, ImportValidationError

        test_file = tmp_path / "large.txt"
        # Create a 2MB file
        test_file.write_bytes(b"x" * (2 * 1024 * 1024))

        with pytest.raises(ImportValidationError, match="too large"):
            validate_file_size(test_file, max_size_mb=1)


class TestGetFileMetadata:
    """Tests for get_file_metadata function."""

    def test_returns_metadata_dict(self, tmp_path):
        """Should return dictionary with file metadata."""
        from joplin_mcp.imports.importers.utils.file_utils import get_file_metadata

        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        metadata = get_file_metadata(test_file)

        assert "source_file" in metadata
        assert "file_size" in metadata
        assert "created_time" in metadata
        assert "updated_time" in metadata
        assert isinstance(metadata["created_time"], datetime)
        assert isinstance(metadata["updated_time"], datetime)

    def test_includes_file_path(self, tmp_path):
        """Should include source file path in metadata."""
        from joplin_mcp.imports.importers.utils.file_utils import get_file_metadata

        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        metadata = get_file_metadata(test_file)

        assert str(test_file) in metadata["source_file"]


class TestScanDirectoryForFiles:
    """Tests for scan_directory_for_files function."""

    def test_finds_files_with_extensions(self, tmp_path):
        """Should find all files with specified extensions."""
        from joplin_mcp.imports.importers.utils.file_utils import scan_directory_for_files

        (tmp_path / "note1.md").write_text("# Note 1")
        (tmp_path / "note2.md").write_text("# Note 2")
        (tmp_path / "other.txt").write_text("Other")
        (tmp_path / "skip.pdf").write_text("PDF")

        files = scan_directory_for_files(tmp_path, ["md"])

        assert len(files) == 2
        assert all(f.suffix == ".md" for f in files)

    def test_scans_recursively(self, tmp_path):
        """Should scan subdirectories recursively."""
        from joplin_mcp.imports.importers.utils.file_utils import scan_directory_for_files

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.md").write_text("# Root")
        (subdir / "nested.md").write_text("# Nested")

        files = scan_directory_for_files(tmp_path, ["md"], recursive=True)

        assert len(files) == 2

    def test_non_recursive_scan(self, tmp_path):
        """Should only scan top level when recursive=False."""
        from joplin_mcp.imports.importers.utils.file_utils import scan_directory_for_files

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.md").write_text("# Root")
        (subdir / "nested.md").write_text("# Nested")

        files = scan_directory_for_files(tmp_path, ["md"], recursive=False)

        assert len(files) == 1
        assert files[0].name == "root.md"


class TestValidateDirectoryHasFiles:
    """Tests for validate_directory_has_files function."""

    def test_passes_for_directory_with_files(self, tmp_path):
        """Should pass when directory has supported files."""
        from joplin_mcp.imports.importers.utils.file_utils import validate_directory_has_files

        (tmp_path / "note.md").write_text("# Note")

        # Should not raise
        validate_directory_has_files(tmp_path, ["md"])

    def test_raises_for_empty_directory(self, tmp_path):
        """Should raise when directory has no supported files."""
        from joplin_mcp.imports.importers.utils.file_utils import validate_directory_has_files, ImportValidationError

        # Empty directory
        with pytest.raises(ImportValidationError, match="insufficient files"):
            validate_directory_has_files(tmp_path, ["md"])

    def test_raises_for_wrong_extensions(self, tmp_path):
        """Should raise when directory has no files with correct extension."""
        from joplin_mcp.imports.importers.utils.file_utils import validate_directory_has_files, ImportValidationError

        (tmp_path / "other.txt").write_text("Text")

        with pytest.raises(ImportValidationError, match="insufficient files"):
            validate_directory_has_files(tmp_path, ["md"])


# === Tests for content_processors.py ===


class TestExtractTitleFromContent:
    """Tests for extract_title_from_content function."""

    def test_extracts_h1_heading(self):
        """Should extract title from H1 heading."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_title_from_content

        content = "# My Title\n\nContent here"
        title = extract_title_from_content(content, "fallback")

        assert title == "My Title"

    def test_extracts_first_line_as_title(self):
        """Should use first line when no heading present."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_title_from_content

        content = "First line title\n\nMore content"
        title = extract_title_from_content(content, "fallback")

        assert title == "First line title"

    def test_uses_fallback_when_empty(self):
        """Should use fallback when content is empty."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_title_from_content

        title = extract_title_from_content("", "My Fallback")

        assert title == "My Fallback"

    def test_strips_whitespace(self):
        """Should strip whitespace from title."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_title_from_content

        content = "#   Spaced Title   \n\nContent"
        title = extract_title_from_content(content, "fallback")

        assert title == "Spaced Title"


class TestExtractHashtags:
    """Tests for extract_hashtags function."""

    def test_extracts_simple_hashtags(self):
        """Should extract simple hashtags."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_hashtags

        content = "Note with #tag1 and #tag2 tags"
        tags = extract_hashtags(content)

        assert "tag1" in tags
        assert "tag2" in tags

    def test_ignores_headings(self):
        """Should not extract markdown headings as tags."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_hashtags

        content = "# Heading\n\nContent with #realtag"
        tags = extract_hashtags(content)

        assert "Heading" not in tags
        assert "realtag" in tags

    def test_handles_no_hashtags(self):
        """Should return empty list when no hashtags."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_hashtags

        content = "Just plain text without tags"
        tags = extract_hashtags(content)

        assert tags == []

    def test_extracts_hyphenated_tags(self):
        """Should extract hyphenated hashtags."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_hashtags

        content = "Content with #my-tag here"
        tags = extract_hashtags(content)

        assert "my-tag" in tags


class TestExtractHtmlTitle:
    """Tests for extract_html_title function."""

    def test_extracts_title_tag(self):
        """Should extract title from <title> tag."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_html_title

        html = "<html><head><title>Page Title</title></head><body></body></html>"
        title = extract_html_title(html, "fallback.html")

        assert title == "Page Title"

    def test_extracts_h1_tag(self):
        """Should extract title from <h1> when no title tag."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_html_title

        html = "<html><body><h1>H1 Title</h1></body></html>"
        title = extract_html_title(html, "fallback.html")

        assert title == "H1 Title"

    def test_extracts_from_content_when_no_title(self):
        """Should extract from first content when no title tag or h1."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_html_title

        html = "<html><body><p>Just content</p></body></html>"
        title = extract_html_title(html, "fallback.html")

        # Falls back to first content text
        assert title == "Just content"

    def test_uses_filename_fallback_for_empty_content(self):
        """Should use filename fallback for empty HTML."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_html_title

        html = "<html><body></body></html>"
        title = extract_html_title(html, "my-file.html")

        # Falls back to filename converted to title case
        assert title == "My File.html"


class TestHtmlToMarkdown:
    """Tests for html_to_markdown function."""

    def test_converts_basic_html(self):
        """Should convert basic HTML to markdown."""
        from joplin_mcp.imports.importers.utils.content_processors import html_to_markdown

        html = "<h1>Title</h1><p>Paragraph text</p>"
        markdown = html_to_markdown(html)

        assert "Title" in markdown or "# Title" in markdown
        assert "Paragraph text" in markdown

    def test_converts_links(self):
        """Should convert HTML links to markdown."""
        from joplin_mcp.imports.importers.utils.content_processors import html_to_markdown

        html = '<a href="https://example.com">Link Text</a>'
        markdown = html_to_markdown(html)

        assert "Link Text" in markdown
        assert "example.com" in markdown or "[Link Text]" in markdown

    def test_handles_empty_html(self):
        """Should handle empty HTML gracefully."""
        from joplin_mcp.imports.importers.utils.content_processors import html_to_markdown

        markdown = html_to_markdown("")

        assert markdown == ""


class TestCsvToMarkdownTable:
    """Tests for csv_to_markdown_table function."""

    def test_converts_simple_csv(self):
        """Should convert simple CSV to markdown table."""
        from joplin_mcp.imports.importers.utils.content_processors import csv_to_markdown_table

        csv_content = "Name,Age\nAlice,30\nBob,25"
        table = csv_to_markdown_table(csv_content)

        assert "Name" in table
        assert "Age" in table
        assert "Alice" in table
        assert "|" in table

    def test_handles_single_row(self):
        """Should handle CSV with single header row."""
        from joplin_mcp.imports.importers.utils.content_processors import csv_to_markdown_table

        csv_content = "Col1,Col2,Col3"
        table = csv_to_markdown_table(csv_content)

        assert "Col1" in table
        assert "|" in table


class TestCleanMarkdown:
    """Tests for clean_markdown function."""

    def test_removes_extra_blank_lines(self):
        """Should collapse multiple blank lines."""
        from joplin_mcp.imports.importers.utils.content_processors import clean_markdown

        content = "Line 1\n\n\n\n\nLine 2"
        cleaned = clean_markdown(content)

        assert "\n\n\n\n\n" not in cleaned
        assert "Line 1" in cleaned
        assert "Line 2" in cleaned

    def test_strips_trailing_whitespace(self):
        """Should strip trailing whitespace from lines."""
        from joplin_mcp.imports.importers.utils.content_processors import clean_markdown

        content = "Line with trailing spaces   \nNext line"
        cleaned = clean_markdown(content)

        # Should not have trailing spaces
        assert "spaces   \n" not in cleaned


class TestExtractFrontmatterField:
    """Tests for extract_frontmatter_field function."""

    def test_extracts_string_field(self):
        """Should extract string field from frontmatter."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_frontmatter_field

        content = "---\ntitle: My Title\nauthor: John\n---\n\nContent"
        title = extract_frontmatter_field(content, "title")

        assert title == "My Title"

    def test_returns_none_for_missing_field(self):
        """Should return None when field not found."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_frontmatter_field

        content = "---\ntitle: Test\n---\n\nContent"
        author = extract_frontmatter_field(content, "author")

        assert author is None

    def test_returns_none_without_frontmatter(self):
        """Should return None when no frontmatter present."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_frontmatter_field

        content = "Just content without frontmatter"
        title = extract_frontmatter_field(content, "title")

        assert title is None


class TestExtractFrontmatterTags:
    """Tests for extract_frontmatter_tags function."""

    def test_extracts_yaml_list_tags(self):
        """Should extract tags from YAML list format."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_frontmatter_tags

        content = "---\ntags:\n  - tag1\n  - tag2\n---\n\nContent"
        tags = extract_frontmatter_tags(content)

        assert "tag1" in tags
        assert "tag2" in tags

    def test_extracts_inline_tags(self):
        """Should extract tags from inline format."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_frontmatter_tags

        content = "---\ntags: [tag1, tag2, tag3]\n---\n\nContent"
        tags = extract_frontmatter_tags(content)

        assert len(tags) >= 2

    def test_returns_empty_without_tags(self):
        """Should return empty list when no tags."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_frontmatter_tags

        content = "---\ntitle: Test\n---\n\nContent"
        tags = extract_frontmatter_tags(content)

        assert tags == []


class TestExtractAllTags:
    """Tests for extract_all_tags function."""

    def test_combines_frontmatter_and_hashtags(self):
        """Should combine frontmatter tags and hashtags."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_all_tags

        content = "---\ntags: [yaml-tag]\n---\n\nContent with #hashtag"
        tags = extract_all_tags(content)

        assert "yaml-tag" in tags
        assert "hashtag" in tags

    def test_deduplicates_tags(self):
        """Should deduplicate tags."""
        from joplin_mcp.imports.importers.utils.content_processors import extract_all_tags

        content = "---\ntags: [duplicate]\n---\n\nContent with #duplicate"
        tags = extract_all_tags(content)

        # Should only have one instance
        assert tags.count("duplicate") == 1


# === Tests for timestamp_utils.py ===


class TestParseFlexibleTimestamp:
    """Tests for parse_flexible_timestamp function."""

    def test_parses_iso_format(self):
        """Should parse ISO format timestamp."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import parse_flexible_timestamp

        result = parse_flexible_timestamp("2023-12-25T10:30:00")

        assert result is not None
        assert result.year == 2023
        assert result.month == 12
        assert result.day == 25

    def test_parses_date_only(self):
        """Should parse date-only format."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import parse_flexible_timestamp

        result = parse_flexible_timestamp("2023-12-25")

        assert result is not None
        assert result.year == 2023
        assert result.month == 12
        assert result.day == 25

    def test_parses_numeric_timestamp(self):
        """Should parse numeric millisecond timestamp."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import parse_flexible_timestamp

        # Jan 1, 2023 00:00:00 UTC in milliseconds
        timestamp_ms = 1672531200000
        result = parse_flexible_timestamp(timestamp_ms)

        assert result is not None
        assert result.year == 2023

    def test_returns_none_for_invalid(self):
        """Should return None for invalid timestamp."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import parse_flexible_timestamp

        result = parse_flexible_timestamp("not a timestamp")

        assert result is None

    def test_returns_none_for_empty(self):
        """Should return None for empty input."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import parse_flexible_timestamp

        assert parse_flexible_timestamp("") is None
        assert parse_flexible_timestamp(None) is None

    def test_parses_with_timezone_z(self):
        """Should parse timestamp with Z suffix."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import parse_flexible_timestamp

        result = parse_flexible_timestamp("2023-12-25T10:30:00Z")

        assert result is not None
        assert result.year == 2023


class TestTimestampToDatetime:
    """Tests for timestamp_to_datetime function."""

    def test_converts_milliseconds(self):
        """Should convert milliseconds to datetime."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import timestamp_to_datetime

        timestamp_ms = 1672531200000  # Jan 1, 2023
        result = timestamp_to_datetime(timestamp_ms)

        assert result.year == 2023

    def test_raises_for_invalid(self):
        """Should raise ValueError for invalid timestamp."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import timestamp_to_datetime

        with pytest.raises(ValueError, match="Invalid timestamp"):
            timestamp_to_datetime("not a number")


class TestGetDefaultTimestampFormats:
    """Tests for get_default_timestamp_formats function."""

    def test_returns_list_of_formats(self):
        """Should return list of format strings."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import get_default_timestamp_formats

        formats = get_default_timestamp_formats()

        assert isinstance(formats, list)
        assert len(formats) > 0
        assert all(isinstance(f, str) for f in formats)

    def test_includes_common_formats(self):
        """Should include common date formats."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import get_default_timestamp_formats

        formats = get_default_timestamp_formats()

        # Should include ISO format
        assert "%Y-%m-%d" in formats or "%Y-%m-%dT%H:%M:%S" in formats


class TestParseFrontmatterTimestamp:
    """Tests for parse_frontmatter_timestamp function."""

    def test_passes_through_datetime(self):
        """Should pass through datetime objects."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import parse_frontmatter_timestamp

        dt = datetime(2023, 12, 25, 10, 30)
        result = parse_frontmatter_timestamp(dt)

        assert result == dt

    def test_parses_string_value(self):
        """Should parse string timestamp."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import parse_frontmatter_timestamp

        result = parse_frontmatter_timestamp("2023-12-25")

        assert result is not None
        assert result.year == 2023


class TestParseHtmlMetaTimestamp:
    """Tests for parse_html_meta_timestamp function."""

    def test_parses_html_date_format(self):
        """Should parse common HTML meta date formats."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import parse_html_meta_timestamp

        result = parse_html_meta_timestamp("2023-12-25")

        assert result is not None
        assert result.year == 2023


class TestParseJoplinTimestamp:
    """Tests for parse_joplin_timestamp function."""

    def test_parses_joplin_milliseconds(self):
        """Should parse Joplin millisecond timestamp."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import parse_joplin_timestamp

        result = parse_joplin_timestamp(1672531200000)

        assert result is not None
        assert result.year == 2023

    def test_parses_string_milliseconds(self):
        """Should parse string representation of milliseconds."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import parse_joplin_timestamp

        result = parse_joplin_timestamp("1672531200000")

        assert result is not None
        assert result.year == 2023

    def test_returns_none_for_invalid(self):
        """Should return None for invalid input."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import parse_joplin_timestamp

        assert parse_joplin_timestamp(None) is None
        assert parse_joplin_timestamp("invalid") is None


class TestParseEvernoteTimestamp:
    """Tests for parse_evernote_timestamp function."""

    def test_parses_evernote_format(self):
        """Should parse Evernote ENEX timestamp format."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import parse_evernote_timestamp

        # Evernote format: YYYYMMDDTHHMMSSZ
        result = parse_evernote_timestamp("20231225T103000Z")

        assert result is not None
        assert result.year == 2023
        assert result.month == 12
        assert result.day == 25

    def test_returns_none_for_empty(self):
        """Should return None for empty input."""
        from joplin_mcp.imports.importers.utils.timestamp_utils import parse_evernote_timestamp

        assert parse_evernote_timestamp("") is None
        assert parse_evernote_timestamp(None) is None


# === Tests for detectors.py ===


class TestLooksLikeRawExport:
    """Tests for looks_like_raw_export function."""

    def test_detects_raw_with_resources_dir(self, tmp_path):
        """Should detect RAW export with resources directory."""
        from joplin_mcp.imports.importers.utils.detectors import looks_like_raw_export

        # Create resources directory and a markdown file
        (tmp_path / "resources").mkdir()
        (tmp_path / "note.md").write_text("# Note content")

        result = looks_like_raw_export(tmp_path)

        assert result is True

    def test_detects_raw_with_metadata_blocks(self, tmp_path):
        """Should detect RAW export via Joplin KV metadata blocks."""
        from joplin_mcp.imports.importers.utils.detectors import looks_like_raw_export

        # Create markdown files with Joplin metadata
        joplin_note = """# Note Title

Content here

id: a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4
parent_id:
created_time: 2023-12-25T10:00:00.000Z
updated_time: 2023-12-25T10:00:00.000Z
is_conflict: 0
latitude: 0.00000000
longitude: 0.00000000
altitude: 0.0000
author:
source_url:
is_todo: 0
todo_due: 0
todo_completed: 0
source: joplin-desktop
source_application: net.cozic.joplin-desktop
application_data:
order: 0
user_created_time: 2023-12-25T10:00:00.000Z
user_updated_time: 2023-12-25T10:00:00.000Z
encryption_cipher_text:
encryption_applied: 0
markup_language: 1
is_shared: 0
share_id:
conflict_original_id:
master_key_id:
user_data:
type_: 1"""

        (tmp_path / "note1.md").write_text(joplin_note)
        (tmp_path / "note2.md").write_text(joplin_note.replace("a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4", "b1c2d3e4f5a6b1c2d3e4f5a6b1c2d3e4"))

        result = looks_like_raw_export(tmp_path)

        assert result is True

    def test_returns_false_for_regular_directory(self, tmp_path):
        """Should return False for regular markdown directory."""
        from joplin_mcp.imports.importers.utils.detectors import looks_like_raw_export

        # Create regular markdown without Joplin metadata
        (tmp_path / "note.md").write_text("# Regular Note\n\nJust content")

        result = looks_like_raw_export(tmp_path)

        assert result is False

    def test_returns_false_for_empty_directory(self, tmp_path):
        """Should return False for empty directory."""
        from joplin_mcp.imports.importers.utils.detectors import looks_like_raw_export

        result = looks_like_raw_export(tmp_path)

        assert result is False

    def test_handles_nonexistent_path(self, tmp_path):
        """Should handle nonexistent path gracefully."""
        from joplin_mcp.imports.importers.utils.detectors import looks_like_raw_export

        nonexistent = tmp_path / "nonexistent"
        result = looks_like_raw_export(nonexistent)

        assert result is False
