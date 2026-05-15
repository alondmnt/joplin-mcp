"""Tests for note_view: single-note cache and render_note dispatch.

Drives the four display modes (section, line range, explicit TOC, smart TOC)
plus the default full render through the single ``render_note`` entry point.
``format_note_details`` is patched where assertions need a stable marker; tests
that only assert on the mode-specific wrapper text don't bother patching.
"""

import time
from unittest.mock import MagicMock, patch

from joplin_mcp import note_view


# === Cache ===


class TestNoteCache:
    """The single-slot cache used to span chunked reads of a long note."""

    def setup_method(self):
        note_view.clear_note_cache()

    def test_cache_and_retrieve(self):
        mock_note = MagicMock()
        mock_note.body = "Test content"

        note_view.set_cached_note("note123", mock_note)
        assert note_view.get_cached_note("note123") is mock_note

    def test_cache_miss_returns_none(self):
        assert note_view.get_cached_note("nonexistent") is None

    def test_caching_new_note_replaces_old(self):
        note1, note2 = MagicMock(), MagicMock()

        note_view.set_cached_note("note1", note1)
        note_view.set_cached_note("note2", note2)

        assert note_view.get_cached_note("note1") is None
        assert note_view.get_cached_note("note2") is note2

    def test_clear_cache(self):
        note_view.set_cached_note("note1", MagicMock())
        note_view.clear_note_cache()
        assert note_view.get_cached_note("note1") is None

    def test_cache_expires_after_ttl(self):
        """After TTL, get returns None even though the slot is populated."""
        note_view.set_cached_note("note1", MagicMock())
        # Simulate time advancing past TTL by rewriting the timestamp.
        note_view._cached_at = time.monotonic() - (note_view._CACHE_TTL_SECONDS + 1)
        assert note_view.get_cached_note("note1") is None


# === render_note: shared fixtures ===


def _config(smart_toc_enabled=False, smart_toc_threshold=100_000):
    """Build a minimal config double for render_note."""
    cfg = MagicMock()
    cfg.is_smart_toc_enabled.return_value = smart_toc_enabled
    cfg.get_smart_toc_threshold.return_value = smart_toc_threshold
    return cfg


# === Section extraction mode ===


class TestRenderNoteSection:
    """render_note with ``section`` set."""

    @patch("joplin_mcp.note_view.format_note_details")
    def test_extracts_valid_section(self, mock_format):
        mock_format.return_value = "FORMATTED_OUTPUT"
        note = MagicMock()
        note.body = "# Introduction\nThis is the intro.\n# Conclusion\nThis is the end."
        note.title = "Test Note"

        result = note_view.render_note(
            note, note_id="note123", section="Introduction", config=_config()
        )

        assert "EXTRACTED_SECTION: Introduction" in result
        assert "SECTION_QUERY: Introduction" in result
        assert "FORMATTED_OUTPUT" in result

    def test_section_not_found_lists_available(self):
        note = MagicMock()
        note.body = "# Section A\nContent A\n# Section B\nContent B"
        note.title = "Test Note"

        result = note_view.render_note(
            note, note_id="note123", section="NonExistent", config=_config()
        )

        assert "SECTION_NOT_FOUND: NonExistent" in result
        assert "NOTE_ID: note123" in result
        assert "AVAILABLE_SECTIONS:" in result
        assert "Section A" in result
        assert "Section B" in result
        assert "Section 'NonExistent' not found" in result

    @patch("joplin_mcp.note_view.format_note_details")
    def test_section_ignored_when_include_body_false(self, mock_format):
        """metadata_only path: section is ignored, default render runs."""
        mock_format.return_value = "DEFAULT_OUTPUT"
        note = MagicMock()
        note.body = "# Heading\nContent"
        cfg = _config()

        result = note_view.render_note(
            note,
            note_id="note123",
            section="Heading",
            include_body=False,
            config=cfg,
        )

        assert result == "DEFAULT_OUTPUT"
        mock_format.assert_called_once_with(note, False, "individual_notes", config=cfg)

    @patch("joplin_mcp.note_view.format_note_details")
    def test_section_ignored_when_no_body(self, mock_format):
        """Empty body: section is skipped, default render runs."""
        mock_format.return_value = "DEFAULT_OUTPUT"
        note = MagicMock()
        note.body = ""

        result = note_view.render_note(
            note, note_id="note123", section="Heading", config=_config()
        )

        assert result == "DEFAULT_OUTPUT"


# === Line range mode ===


class TestRenderNoteLineRange:
    """render_note with ``start_line`` set."""

    @patch("joplin_mcp.note_view.format_note_details")
    def test_extracts_default_50_lines(self, mock_format):
        mock_format.return_value = "FORMATTED_OUTPUT"
        note = MagicMock()
        note.body = "\n".join(f"Line {i}" for i in range(1, 101))
        note.title = "Test"

        result = note_view.render_note(
            note, note_id="note123", start_line=1, config=_config()
        )

        assert "EXTRACTED_LINES: 1-50" in result
        assert "50 lines" in result
        assert "TOTAL_LINES: 100" in result
        assert "EXTRACTION_TYPE: sequential_reading" in result
        assert 'NEXT_CHUNK: get_note("note123", start_line=51)' in result

    @patch("joplin_mcp.note_view.format_note_details")
    def test_extracts_specified_line_count(self, mock_format):
        mock_format.return_value = "FORMATTED_OUTPUT"
        note = MagicMock()
        note.body = "\n".join(f"Line {i}" for i in range(1, 21))
        note.title = "Test"

        result = note_view.render_note(
            note, note_id="note123", start_line=5, line_count=3, config=_config()
        )

        assert "EXTRACTED_LINES: 5-7" in result
        assert "3 lines" in result

    @patch("joplin_mcp.note_view.format_note_details")
    def test_end_of_note_status(self, mock_format):
        mock_format.return_value = "FORMATTED_OUTPUT"
        note = MagicMock()
        note.body = "Line 1\nLine 2\nLine 3"
        note.title = "Test"

        result = note_view.render_note(
            note, note_id="note123", start_line=1, line_count=10, config=_config()
        )

        assert "STATUS: End of note reached" in result
        assert "NEXT_CHUNK" not in result

    def test_invalid_start_line_too_low(self):
        note = MagicMock()
        note.body = "Line 1\nLine 2\nLine 3"
        note.title = "Test"

        result = note_view.render_note(
            note, note_id="note123", start_line=0, config=_config()
        )

        assert "LINE_EXTRACTION_ERROR" in result
        assert "Invalid start_line" in result
        assert "must be between 1" in result

    def test_invalid_start_line_too_high(self):
        note = MagicMock()
        note.body = "Line 1\nLine 2\nLine 3"
        note.title = "Test"

        result = note_view.render_note(
            note, note_id="note123", start_line=10, config=_config()
        )

        assert "LINE_EXTRACTION_ERROR" in result
        assert "Invalid start_line" in result
        assert "must be between 1 and 3" in result

    def test_invalid_line_count(self):
        note = MagicMock()
        note.body = "Line 1\nLine 2\nLine 3"
        note.title = "Test"

        result = note_view.render_note(
            note, note_id="note123", start_line=1, line_count=0, config=_config()
        )

        assert "LINE_EXTRACTION_ERROR" in result
        assert "Invalid line_count" in result
        assert "must be >= 1" in result

    @patch("joplin_mcp.note_view.format_note_details")
    def test_line_range_ignored_when_no_body(self, mock_format):
        """Empty body: line extraction is skipped, default render runs."""
        mock_format.return_value = "DEFAULT_OUTPUT"
        note = MagicMock()
        note.body = ""

        result = note_view.render_note(
            note, note_id="note123", start_line=1, config=_config()
        )

        assert result == "DEFAULT_OUTPUT"


# === Explicit TOC mode ===


class TestRenderNoteTocOnly:
    """render_note with ``toc_only=True``."""

    @patch("joplin_mcp.note_view.format_note_details")
    def test_returns_toc_with_metadata(self, mock_format):
        mock_format.return_value = "METADATA_OUTPUT"
        note = MagicMock()
        note.body = "# Heading 1\nContent\n## Heading 2\nMore content"
        note.title = "Test Note"
        note.id = "note123"

        result = note_view.render_note(
            note, note_id="note123", toc_only=True, config=_config()
        )

        assert "METADATA_OUTPUT" in result
        assert "TABLE_OF_CONTENTS:" in result
        assert "Heading 1" in result
        assert "Heading 2" in result
        assert "DISPLAY_MODE: toc_only" in result
        assert "NEXT_STEPS:" in result

    @patch("joplin_mcp.note_view.format_note_details")
    def test_falls_through_when_no_headings(self, mock_format):
        """toc_only on a body with no headings: falls through to default."""
        mock_format.return_value = "DEFAULT_OUTPUT"
        note = MagicMock()
        note.body = "Just regular text without any headings."
        note.title = "Test"

        result = note_view.render_note(
            note, note_id="note123", toc_only=True, config=_config()
        )

        assert result == "DEFAULT_OUTPUT"


# === Smart TOC mode ===


class TestRenderNoteSmartToc:
    """render_note's default-path smart-TOC behaviour for long notes."""

    @patch("joplin_mcp.note_view.format_note_details")
    def test_skipped_when_disabled(self, mock_format):
        mock_format.return_value = "DEFAULT_OUTPUT"
        note = MagicMock()
        note.body = "# Heading\n" + "Content " * 500

        result = note_view.render_note(
            note,
            note_id="note123",
            config=_config(smart_toc_enabled=False),
        )

        assert result == "DEFAULT_OUTPUT"

    @patch("joplin_mcp.note_view.format_note_details")
    def test_skipped_when_short(self, mock_format):
        mock_format.return_value = "DEFAULT_OUTPUT"
        note = MagicMock()
        note.body = "Short note content"

        result = note_view.render_note(
            note,
            note_id="note123",
            config=_config(smart_toc_enabled=True, smart_toc_threshold=2000),
        )

        assert result == "DEFAULT_OUTPUT"

    @patch("joplin_mcp.note_view.format_note_details")
    def test_returns_toc_for_long_note_with_headings(self, mock_format):
        mock_format.return_value = "METADATA_OUTPUT"
        note = MagicMock()
        note.body = "# Heading\n" + "Content " * 100
        note.title = "Test"
        note.id = "note123"

        result = note_view.render_note(
            note,
            note_id="note123",
            config=_config(smart_toc_enabled=True, smart_toc_threshold=100),
        )

        assert "DISPLAY_MODE: smart_toc_auto" in result
        assert "Heading" in result

    @patch("joplin_mcp.note_view.format_note_details")
    def test_truncates_long_note_without_headings(self, mock_format):
        mock_format.return_value = "TRUNCATED_OUTPUT"
        note = MagicMock()
        note.body = "Just regular text " * 100  # long, no headings
        note.title = "Test"

        result = note_view.render_note(
            note,
            note_id="note123",
            config=_config(smart_toc_enabled=True, smart_toc_threshold=100),
        )

        assert "CONTENT_TRUNCATED" in result
        assert "no headings for navigation" in result
        assert "force_full=True" in result

    @patch("joplin_mcp.note_view.format_note_details")
    def test_force_full_bypasses_smart_toc(self, mock_format):
        """``force_full=True`` skips smart TOC even for long notes with headings."""
        mock_format.return_value = "DEFAULT_OUTPUT"
        note = MagicMock()
        note.body = "# Heading\n" + "Content " * 500
        note.title = "Test"

        result = note_view.render_note(
            note,
            note_id="note123",
            force_full=True,
            config=_config(smart_toc_enabled=True, smart_toc_threshold=100),
        )

        assert result == "DEFAULT_OUTPUT"


# === Default full render ===


class TestRenderNoteDefault:
    """When no mode applies, render_note returns the default format."""

    @patch("joplin_mcp.note_view.format_note_details")
    def test_default_render(self, mock_format):
        mock_format.return_value = "FULL_OUTPUT"
        note = MagicMock()
        note.body = "Short body"
        cfg = _config()

        result = note_view.render_note(note, note_id="note123", config=cfg)

        assert result == "FULL_OUTPUT"
        mock_format.assert_called_once_with(note, True, "individual_notes", config=cfg)

    @patch("joplin_mcp.note_view.format_note_details")
    def test_metadata_only(self, mock_format):
        mock_format.return_value = "METADATA_OUTPUT"
        note = MagicMock()
        note.body = "Body"
        cfg = _config()

        result = note_view.render_note(
            note, note_id="note123", include_body=False, config=cfg
        )

        assert result == "METADATA_OUTPUT"
        mock_format.assert_called_once_with(note, False, "individual_notes", config=cfg)
