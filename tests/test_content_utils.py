"""Tests for content_utils.py - Pure functions for markdown parsing and content manipulation."""

import datetime

import pytest

from joplin_mcp.content_utils import (
    calculate_content_stats,
    create_content_preview,
    create_content_preview_with_search,
    create_matching_lines_preview,
    create_toc_only,
    extract_frontmatter,
    extract_section_content,
    extract_text_terms_from_query,
    format_timestamp,
    parse_markdown_headings,
    _find_matching_lines,
)


# === Tests for parse_markdown_headings ===


class TestParseMarkdownHeadings:
    """Tests for parse_markdown_headings function."""

    def test_empty_body_returns_empty_list(self):
        """Empty body should return empty list."""
        assert parse_markdown_headings("") == []
        assert parse_markdown_headings(None) == []

    def test_no_headings_returns_empty_list(self):
        """Content without headings should return empty list."""
        body = "This is just regular text.\nNo headings here."
        assert parse_markdown_headings(body) == []

    def test_single_heading(self):
        """Single heading should be parsed correctly."""
        body = "# Introduction"
        result = parse_markdown_headings(body)
        assert len(result) == 1
        assert result[0]["level"] == 1
        assert result[0]["title"] == "Introduction"
        assert result[0]["line_idx"] == 0
        assert result[0]["markdown"] == "# Introduction"

    def test_multiple_heading_levels(self):
        """Multiple heading levels should be parsed correctly."""
        body = """# Level 1
## Level 2
### Level 3
#### Level 4
##### Level 5
###### Level 6"""
        result = parse_markdown_headings(body)
        assert len(result) == 6
        for i, heading in enumerate(result):
            assert heading["level"] == i + 1
            assert heading["title"] == f"Level {i + 1}"

    def test_heading_with_extra_whitespace(self):
        """Headings with extra whitespace should be parsed correctly."""
        body = "#   Title with spaces   "
        result = parse_markdown_headings(body)
        assert len(result) == 1
        assert result[0]["title"] == "Title with spaces"

    def test_skips_headings_in_code_blocks(self):
        """Headings inside code blocks should be skipped."""
        body = """# Real Heading
```python
# This is a comment, not a heading
## Also not a heading
```
## Another Real Heading"""
        result = parse_markdown_headings(body)
        assert len(result) == 2
        assert result[0]["title"] == "Real Heading"
        assert result[1]["title"] == "Another Real Heading"

    def test_skips_headings_in_tilde_code_blocks(self):
        """Headings inside ~~~ code blocks should be skipped."""
        body = """# Before
~~~
# Inside code block
~~~
# After"""
        result = parse_markdown_headings(body)
        assert len(result) == 2
        assert result[0]["title"] == "Before"
        assert result[1]["title"] == "After"

    def test_nested_code_blocks(self):
        """Nested code block patterns should be handled correctly."""
        body = """# Start
```
# In first block
```
# Middle
```
# In second block
```
# End"""
        result = parse_markdown_headings(body)
        assert len(result) == 3
        titles = [h["title"] for h in result]
        assert titles == ["Start", "Middle", "End"]

    def test_line_indices_are_correct(self):
        """Line indices should be 0-based and accurate."""
        body = """Some text
# First Heading
More text
## Second Heading"""
        result = parse_markdown_headings(body)
        assert len(result) == 2
        assert result[0]["line_idx"] == 1
        assert result[1]["line_idx"] == 3

    def test_start_line_offset(self):
        """start_line parameter should offset line indices."""
        body = "# Heading"
        result = parse_markdown_headings(body, start_line=10)
        assert result[0]["line_idx"] == 10
        assert result[0]["relative_line_idx"] == 0

    def test_original_line_preserved(self):
        """Original line text should be preserved."""
        body = "  # Indented Heading  "
        result = parse_markdown_headings(body)
        assert len(result) == 1
        assert result[0]["original_line"] == "  # Indented Heading  "

    def test_heading_without_space_not_matched(self):
        """Headings without space after # should not be matched."""
        body = "#NoSpace\n# With Space"
        result = parse_markdown_headings(body)
        assert len(result) == 1
        assert result[0]["title"] == "With Space"


# === Tests for extract_section_content ===


class TestExtractSectionContent:
    """Tests for extract_section_content function."""

    def test_empty_inputs(self):
        """Empty inputs should return empty strings."""
        assert extract_section_content("", "1") == ("", "")
        assert extract_section_content("# Heading", "") == ("", "")
        assert extract_section_content(None, "1") == ("", "")

    def test_no_headings_returns_empty(self):
        """Content without headings should return empty."""
        body = "Just regular text without headings."
        assert extract_section_content(body, "1") == ("", "")

    def test_extract_by_number(self):
        """Should extract section by number (1-based)."""
        body = """# First
Content 1
## Second
Content 2
# Third
Content 3"""
        content, title = extract_section_content(body, "1")
        assert title == "First"
        assert "Content 1" in content
        assert "# First" in content

        content, title = extract_section_content(body, "2")
        assert title == "Second"
        assert "Content 2" in content

    def test_number_out_of_range(self):
        """Out of range section numbers should return empty."""
        body = "# Only Heading"
        assert extract_section_content(body, "0") == ("", "")
        assert extract_section_content(body, "5") == ("", "")
        assert extract_section_content(body, "-1") == ("", "")

    def test_extract_by_exact_text(self):
        """Should extract section by exact text match (case-insensitive)."""
        body = """# Introduction
Intro content
# Configuration
Config content"""
        content, title = extract_section_content(body, "Configuration")
        assert title == "Configuration"
        assert "Config content" in content

        # Case insensitive
        content, title = extract_section_content(body, "CONFIGURATION")
        assert title == "Configuration"

    def test_extract_by_slug(self):
        """Should extract section by slug format."""
        body = """# My Section Title
Content here"""
        content, title = extract_section_content(body, "my-section-title")
        assert title == "My Section Title"

    def test_extract_by_partial_match(self):
        """Should extract section by partial match as fallback."""
        body = """# Configuration Settings
Config content"""
        content, title = extract_section_content(body, "config")
        assert title == "Configuration Settings"

    def test_priority_exact_over_partial(self):
        """Exact match should take priority over partial match."""
        body = """# Config
Exact match
# Configuration Settings
Partial match"""
        content, title = extract_section_content(body, "Config")
        assert title == "Config"
        assert "Exact match" in content

    def test_section_includes_subsections(self):
        """Section should include all subsections until same or higher level."""
        body = """# Parent
Parent content
## Child 1
Child 1 content
### Grandchild
Grandchild content
## Child 2
Child 2 content
# Next Parent
Different section"""
        content, title = extract_section_content(body, "Parent")
        assert title == "Parent"
        assert "Parent content" in content
        assert "Child 1 content" in content
        assert "Grandchild content" in content
        assert "Child 2 content" in content
        assert "Different section" not in content

    def test_section_ends_at_same_level(self):
        """Section should end when same level heading is found."""
        body = """## Section A
Content A
## Section B
Content B"""
        content, title = extract_section_content(body, "Section A")
        assert "Content A" in content
        assert "Content B" not in content

    def test_last_section_goes_to_end(self):
        """Last section should include content to end of document."""
        body = """# First
First content
# Last
Last content
Final line"""
        content, title = extract_section_content(body, "Last")
        assert "Last content" in content
        assert "Final line" in content


# === Tests for extract_frontmatter ===


class TestExtractFrontmatter:
    """Tests for extract_frontmatter function."""

    def test_no_frontmatter(self):
        """Content without frontmatter should return empty."""
        body = "Regular content without frontmatter"
        frontmatter, index = extract_frontmatter(body)
        assert frontmatter == ""
        assert index == 0

    def test_empty_body(self):
        """Empty body should return empty."""
        assert extract_frontmatter("") == ("", 0)
        assert extract_frontmatter(None) == ("", 0)

    def test_valid_frontmatter(self):
        """Valid YAML frontmatter should be extracted."""
        body = """---
title: My Note
tags: [work, important]
---
Content here"""
        frontmatter, index = extract_frontmatter(body)
        assert "title: My Note" in frontmatter
        assert "tags: [work, important]" in frontmatter
        assert frontmatter.startswith("---")
        assert frontmatter.endswith("---")
        assert index == 4

    def test_unclosed_frontmatter(self):
        """Unclosed frontmatter should return empty."""
        body = """---
title: My Note
No closing delimiter"""
        frontmatter, index = extract_frontmatter(body)
        assert frontmatter == ""
        assert index == 0

    def test_frontmatter_truncation(self):
        """Long frontmatter should be truncated at max_lines."""
        lines = ["---"] + [f"field{i}: value{i}" for i in range(30)] + ["---", "Content"]
        body = "\n".join(lines)
        frontmatter, index = extract_frontmatter(body, max_lines=10)
        assert frontmatter.startswith("---")
        assert frontmatter.endswith("---")
        frontmatter_lines = frontmatter.split("\n")
        assert len(frontmatter_lines) <= 10

    def test_content_start_index(self):
        """Content start index should be correct."""
        body = """---
key: value
---
First line of content"""
        _, index = extract_frontmatter(body)
        lines = body.split("\n")
        assert lines[index] == "First line of content"


# === Tests for create_content_preview ===


class TestCreateContentPreview:
    """Tests for create_content_preview function."""

    def test_empty_body(self):
        """Empty body should return empty string."""
        assert create_content_preview("", 100) == ""

    def test_short_content_unchanged(self):
        """Content shorter than max_length should be unchanged."""
        body = "Short content"
        result = create_content_preview(body, 100)
        assert "Short content" in result

    def test_truncation_with_ellipsis(self):
        """Long content should be truncated with ellipsis."""
        body = "A" * 200
        result = create_content_preview(body, 50)
        assert result.endswith("...")
        assert len(result) <= 55  # 50 + "..."

    def test_preserves_frontmatter(self):
        """Frontmatter should be preserved in preview."""
        body = """---
title: Test
---
Content after frontmatter that is quite long and goes on for a while."""
        result = create_content_preview(body, 100)
        assert "title: Test" in result
        assert "---" in result

    def test_ensures_minimum_content_space(self):
        """Should ensure at least 50 chars for content preview."""
        body = """---
very: long
frontmatter: with
many: fields
that: take
up: space
---
Content"""
        result = create_content_preview(body, 100)
        # Should still include some content even with long frontmatter
        assert result  # Non-empty

    def test_no_frontmatter_short_content(self):
        """Content without frontmatter but shorter than limit."""
        body = "Just plain text without any frontmatter"
        result = create_content_preview(body, 100)
        assert "Just plain text" in result

    def test_fallback_when_no_meaningful_content(self):
        """Should fall back to basic truncation when no meaningful content after frontmatter."""
        # Content that has frontmatter but very short remaining content
        body = """---
title: Test
---
x"""
        result = create_content_preview(body, 50)
        # Should still return something
        assert result


# === Tests for create_toc_only ===


class TestCreateTocOnly:
    """Tests for create_toc_only function."""

    def test_empty_body(self):
        """Empty body should return empty string."""
        assert create_toc_only("") == ""
        assert create_toc_only(None) == ""

    def test_no_headings(self):
        """Content without headings should return empty string."""
        assert create_toc_only("Just regular text") == ""

    def test_toc_header_present(self):
        """TOC should start with TABLE_OF_CONTENTS: header."""
        body = "# Heading"
        result = create_toc_only(body)
        assert result.startswith("TABLE_OF_CONTENTS:")

    def test_toc_numbering(self):
        """TOC entries should be numbered sequentially."""
        body = """# First
## Second
# Third"""
        result = create_toc_only(body)
        assert "1. First" in result
        assert "2. Second" in result
        assert "3. Third" in result

    def test_toc_indentation(self):
        """TOC should indent based on heading level."""
        body = """# Level 1
## Level 2
### Level 3"""
        result = create_toc_only(body)
        lines = result.split("\n")
        # Level 1 = no indent, Level 2 = 2 spaces, Level 3 = 4 spaces
        assert "1. Level 1" in lines[1]  # No leading spaces
        assert "  2. Level 2" in lines[2]  # 2 spaces
        assert "    3. Level 3" in lines[3]  # 4 spaces

    def test_toc_includes_line_numbers(self):
        """TOC should include line numbers."""
        body = """Some text
# Heading
More text"""
        result = create_toc_only(body)
        assert "(line 1)" in result  # Heading is on line 1 (0-indexed)


# === Tests for extract_text_terms_from_query ===


class TestExtractTextTermsFromQuery:
    """Tests for extract_text_terms_from_query function."""

    def test_empty_query(self):
        """Empty or wildcard query should return empty list."""
        assert extract_text_terms_from_query("") == []
        assert extract_text_terms_from_query("*") == []
        assert extract_text_terms_from_query("  *  ") == []

    def test_simple_terms(self):
        """Simple search terms should be extracted."""
        result = extract_text_terms_from_query("hello world")
        assert "hello" in result
        assert "world" in result

    def test_removes_tag_operator(self):
        """tag: operator should be removed."""
        result = extract_text_terms_from_query("tag:work meeting notes")
        assert "meeting" in result
        assert "notes" in result
        assert "tag:work" not in result
        assert "work" not in result

    def test_removes_notebook_operator(self):
        """notebook: operator should be removed."""
        result = extract_text_terms_from_query("notebook:projects task")
        assert "task" in result
        assert "notebook:projects" not in result

    def test_removes_type_operator(self):
        """type: operator should be removed."""
        result = extract_text_terms_from_query("type:todo urgent")
        assert "urgent" in result
        assert "type:todo" not in result

    def test_removes_iscompleted_operator(self):
        """iscompleted: operator should be removed."""
        result = extract_text_terms_from_query("iscompleted:0 pending")
        assert "pending" in result
        assert "iscompleted:0" not in result

    def test_removes_multiple_operators(self):
        """Multiple operators should all be removed."""
        result = extract_text_terms_from_query(
            "tag:work notebook:projects type:todo important"
        )
        assert result == ["important"]

    def test_preserves_quoted_phrases(self):
        """Quoted phrases should be preserved as single terms."""
        result = extract_text_terms_from_query('"exact phrase" other')
        assert "exact phrase" in result
        assert "other" in result
        assert len(result) == 2

    def test_mixed_operators_and_phrases(self):
        """Should handle mix of operators, phrases, and terms."""
        result = extract_text_terms_from_query(
            'tag:work "project alpha" meeting notes'
        )
        assert "project alpha" in result
        assert "meeting" in result
        assert "notes" in result
        assert "tag:work" not in result

    def test_case_insensitive_operator_removal(self):
        """Operator removal should be case-insensitive."""
        result = extract_text_terms_from_query("TAG:work NOTEBOOK:projects task")
        assert "task" in result
        assert len(result) == 1


# === Tests for _find_matching_lines ===


class TestFindMatchingLines:
    """Tests for _find_matching_lines internal function."""

    def test_and_matches(self):
        """Lines matching all terms should be AND matches."""
        lines = ["hello world", "hello there", "world peace"]
        and_matches, or_matches = _find_matching_lines(lines, ["hello", "world"], 0)
        assert len(and_matches) == 1
        assert and_matches[0][1] == "hello world"

    def test_or_matches(self):
        """Lines matching any term should be OR matches."""
        lines = ["hello world", "hello there", "goodbye"]
        and_matches, or_matches = _find_matching_lines(lines, ["hello", "world"], 0)
        assert len(or_matches) == 1
        assert or_matches[0][1] == "hello there"

    def test_case_insensitive(self):
        """Matching should be case-insensitive."""
        lines = ["HELLO world", "Hello World", "WORLD"]
        and_matches, or_matches = _find_matching_lines(lines, ["hello", "world"], 0)
        assert len(and_matches) == 2

    def test_line_indices(self):
        """Line indices should account for content_start_index."""
        lines = ["match this"]
        and_matches, _ = _find_matching_lines(lines, ["match"], 10)
        assert and_matches[0][0] == 10


# === Tests for create_matching_lines_preview ===


class TestCreateMatchingLinesPreview:
    """Tests for create_matching_lines_preview function."""

    def test_empty_inputs(self):
        """Empty inputs should return empty results."""
        assert create_matching_lines_preview("", ["term"]) == ("", [], 0, 0)
        assert create_matching_lines_preview("content", []) == ("", [], 0, 0)

    def test_and_matches_prioritized(self):
        """AND matches should appear before OR matches."""
        body = """or match only hello
and match hello world
another or match world"""
        preview, line_nums, and_count, or_count = create_matching_lines_preview(
            body, ["hello", "world"], max_lines=10
        )
        assert and_count == 1
        assert or_count == 2
        # First line in preview should be the AND match
        assert "and match hello world" in preview.split("\n")[0]

    def test_respects_max_lines(self):
        """Should respect max_lines limit."""
        body = "\n".join([f"match {i}" for i in range(20)])
        preview, line_nums, _, _ = create_matching_lines_preview(
            body, ["match"], max_lines=3
        )
        assert len(line_nums) <= 3

    def test_respects_max_length(self):
        """Should respect max_length limit."""
        body = "\n".join([f"match content line {i}" for i in range(20)])
        preview, _, _, _ = create_matching_lines_preview(
            body, ["match"], max_length=100
        )
        assert len(preview) <= 150  # Some tolerance for line markers

    def test_line_numbers_in_output(self):
        """Output should include line numbers."""
        body = "first\nmatch here\nlast"
        preview, line_nums, _, _ = create_matching_lines_preview(body, ["match"])
        assert "[L2]" in preview  # Line 2 (1-indexed)
        assert 2 in line_nums


# === Tests for create_content_preview_with_search ===


class TestCreateContentPreviewWithSearch:
    """Tests for create_content_preview_with_search function."""

    def test_empty_body(self):
        """Empty body should return empty string."""
        assert create_content_preview_with_search("", 100, "query") == ""

    def test_no_query_falls_back(self):
        """Without query, should fall back to regular preview."""
        body = "Some content here"
        result = create_content_preview_with_search(body, 100, "")
        assert "Some content here" in result

    def test_wildcard_query_falls_back(self):
        """Wildcard query should fall back to regular preview."""
        body = "Some content here"
        result = create_content_preview_with_search(body, 100, "*")
        assert "Some content here" in result

    def test_shows_matching_lines_header(self):
        """Should show MATCHING_LINES header when matches found."""
        body = "Line with searchterm here\nAnother line"
        result = create_content_preview_with_search(body, 300, "searchterm")
        assert "MATCHING_LINES:" in result

    def test_shows_search_terms(self):
        """Should show the search terms used."""
        body = "Line with findme here"
        result = create_content_preview_with_search(body, 300, "findme")
        assert '"findme"' in result

    def test_no_matches_falls_back(self):
        """If no matches, should fall back to regular preview."""
        body = "Content without the search term"
        result = create_content_preview_with_search(body, 100, "notfound")
        assert "Content without" in result
        assert "MATCHING_LINES" not in result

    def test_and_matches_quality_info(self):
        """Should show quality info for AND matches (all terms match)."""
        body = "Line with word1 and word2 together"
        result = create_content_preview_with_search(body, 300, "word1 word2")
        assert "MATCHING_LINES:" in result
        # Should have quality info about matching all terms
        assert "match" in result.lower()

    def test_or_matches_only_quality_info(self):
        """Should show quality info when only OR matches found."""
        body = "First line has word1\nSecond line has word2"
        result = create_content_preview_with_search(body, 300, "word1 word2")
        assert "MATCHING_LINES:" in result

    def test_with_frontmatter_preserved(self):
        """Should preserve frontmatter in search preview."""
        body = """---
title: Test Note
---
Content with searchterm here"""
        result = create_content_preview_with_search(body, 300, "searchterm")
        assert "title: Test Note" in result
        assert "MATCHING_LINES:" in result


# === Tests for format_timestamp ===


class TestFormatTimestamp:
    """Tests for format_timestamp function."""

    def test_none_returns_none(self):
        """None timestamp should return None."""
        assert format_timestamp(None) is None

    def test_zero_returns_none(self):
        """Zero timestamp should return None."""
        assert format_timestamp(0) is None

    def test_datetime_formatted(self):
        """datetime object should be formatted correctly."""
        dt = datetime.datetime(2024, 1, 15, 10, 30, 45)
        result = format_timestamp(dt)
        assert result == "2024-01-15 10:30:45"

    def test_millisecond_timestamp(self):
        """Integer millisecond timestamp should be formatted."""
        # 2024-01-15 10:30:45 UTC in milliseconds
        ts = 1705315845000
        result = format_timestamp(ts)
        assert result is not None
        assert "2024" in result

    def test_custom_format(self):
        """Custom format string should be used."""
        dt = datetime.datetime(2024, 1, 15, 10, 30, 45)
        result = format_timestamp(dt, "%Y-%m-%d")
        assert result == "2024-01-15"

    def test_invalid_type_returns_none(self):
        """Invalid type should return None."""
        assert format_timestamp("not a timestamp") is None
        assert format_timestamp([123]) is None

    def test_overflow_timestamp_returns_none(self):
        """Overflow timestamp should be caught and return None."""
        # Very large timestamp that causes overflow
        assert format_timestamp(99999999999999999) is None


# === Tests for calculate_content_stats ===


class TestCalculateContentStats:
    """Tests for calculate_content_stats function."""

    def test_empty_body(self):
        """Empty body should return zero stats."""
        result = calculate_content_stats("")
        assert result == {"characters": 0, "words": 0, "lines": 0}

    def test_character_count(self):
        """Character count should include all characters."""
        result = calculate_content_stats("hello world")
        assert result["characters"] == 11  # Including space

    def test_word_count(self):
        """Word count should count whitespace-separated words."""
        result = calculate_content_stats("one two three four")
        assert result["words"] == 4

    def test_line_count(self):
        """Line count should count newline-separated lines."""
        result = calculate_content_stats("line1\nline2\nline3")
        assert result["lines"] == 3

    def test_complex_content(self):
        """Should handle complex content correctly."""
        body = "# Heading\n\nSome text with **bold** and *italic*.\n\n- Item 1\n- Item 2\n"
        result = calculate_content_stats(body)
        assert result["characters"] > 0
        assert result["words"] > 0
        assert result["lines"] == 7  # 6 content lines + 1 trailing newline

    def test_whitespace_only_content(self):
        """Whitespace-only content should have zero words."""
        result = calculate_content_stats("   \n   \n   ")
        assert result["words"] == 0
        assert result["lines"] == 3
        assert result["characters"] > 0
