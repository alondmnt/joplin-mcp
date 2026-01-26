"""Content parsing and manipulation utilities.

Pure functions for parsing markdown, extracting sections, creating previews,
and other content-related operations. No external dependencies on Joplin API.
"""

import datetime
import re
from typing import Any, Dict, List, Optional, Union


def parse_markdown_headings(body: str, start_line: int = 0) -> List[Dict[str, Any]]:
    """Parse markdown headings from content, skipping those in code blocks.

    Args:
        body: The markdown content to parse
        start_line: Starting line index (for offset calculations)

    Returns:
        List of heading dictionaries with keys:
        - level: Heading level (1-6)
        - title: Heading text (cleaned)
        - line_idx: Absolute line index in original content
        - relative_line_idx: Line index relative to start_line
        - original_line: Full original line text
        - markdown: Original markdown heading (e.g., "## Title")
    """
    if not body:
        return []

    lines = body.split("\n")
    headings = []

    # Regex patterns
    heading_pattern = r"^(#{1,6})\s+(.+)$"
    code_block_pattern = r"^(```|~~~)"
    in_code_block = False

    for rel_line_idx, line in enumerate(lines):
        line_stripped = line.strip()
        abs_line_idx = start_line + rel_line_idx

        # Check for code block delimiters
        if re.match(code_block_pattern, line_stripped):
            in_code_block = not in_code_block
            continue

        # Only process headings outside code blocks
        if not in_code_block:
            match = re.match(heading_pattern, line_stripped)
            if match:
                hashes = match.group(1)
                title = match.group(2).strip()
                level = len(hashes)

                headings.append(
                    {
                        "level": level,
                        "title": title,
                        "line_idx": abs_line_idx,
                        "relative_line_idx": rel_line_idx,
                        "original_line": line,
                        "markdown": f"{hashes} {title}",
                    }
                )

    return headings


def extract_section_content(body: str, section_identifier: str) -> tuple[str, str]:
    """Extract a specific section from note content.

    Args:
        body: The note content to extract from
        section_identifier: Can be:
            - Section number (1-based): "1", "2", etc. (highest priority)
            - Heading text (case insensitive): "Introduction" (exact match)
            - Slug format: "introduction" or "my-section" (intentional format)
            - Partial text: "config" matches "Configuration" (fuzzy fallback)

    Priority order: Number → Exact → Slug → Partial

    Returns:
        tuple: (extracted_content, section_title) or ("", "") if not found
    """
    if not body or not section_identifier:
        return "", ""

    # Parse headings using helper function
    headings = parse_markdown_headings(body)

    if not headings:
        return "", ""

    # Split body into lines for content extraction
    lines = body.split("\n")

    # Find target section
    target_heading = None

    # Try to parse as section number first
    try:
        section_num = int(section_identifier)
        if 1 <= section_num <= len(headings):
            target_heading = headings[section_num - 1]
        else:
            # Number out of range, fall back to text matching
            target_heading = None
    except ValueError:
        # Not a number, will try text matching below
        target_heading = None

    # If no valid section number found, try text/slug matching
    if target_heading is None:
        identifier_lower = section_identifier.lower().strip()

        # Priority 1: Try exact matches first (case insensitive)
        for heading in headings:
            title_lower = heading["title"].lower()
            if title_lower == identifier_lower:
                target_heading = heading
                break

        # Priority 2: Try slug matches only if no exact match found
        if not target_heading:
            # Convert identifier to slug format
            identifier_slug = re.sub(r"[^\w\s-]", "", identifier_lower)
            identifier_slug = re.sub(r"[-\s_]+", "-", identifier_slug).strip("-")

            for heading in headings:
                title_lower = heading["title"].lower()

                # Convert title to slug and compare
                title_slug = re.sub(
                    r"[^\w\s-]", "", title_lower
                )  # Remove special chars
                title_slug = re.sub(r"[-\s]+", "-", title_slug).strip(
                    "-"
                )  # Normalize spaces/hyphens

                # Only exact slug matches, not partial slug matches
                if title_slug == identifier_slug:
                    target_heading = heading
                    break

        # Priority 3: Try partial matches only if no slug match found
        if not target_heading:
            for heading in headings:
                title_lower = heading["title"].lower()
                if identifier_lower in title_lower:
                    target_heading = heading
                    break

    if not target_heading:
        return "", ""

    # Find content boundaries based on hierarchy
    start_line = target_heading["line_idx"]
    end_line = len(lines)
    target_level = target_heading["level"]

    # Find end of section: next heading at same level or higher
    for heading in headings:
        if heading["line_idx"] > start_line and heading["level"] <= target_level:
            end_line = heading["line_idx"]
            break

    # Extract the section content
    section_lines = lines[start_line:end_line]
    section_content = "\n".join(section_lines).strip()

    return section_content, target_heading["title"]


def extract_frontmatter(body: str, max_lines: int = 20) -> tuple[str, int]:
    """Extract frontmatter from note content if present.

    Args:
        body: The note content to extract frontmatter from
        max_lines: Maximum number of frontmatter lines to include

    Returns:
        tuple: (frontmatter_content, content_start_index)
    """
    if not body or not body.startswith("---"):
        return "", 0

    lines = body.split("\n")

    # Find the closing front matter delimiter
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            front_matter_end = i
            break
    else:
        return "", 0  # No closing delimiter found

    # Get frontmatter lines with limit
    front_matter_lines = lines[: front_matter_end + 1]

    if len(front_matter_lines) > max_lines:
        # Truncate front matter if it exceeds max_lines
        # Keep opening --- + (max_lines-2) lines of content + closing ---
        front_matter_lines = lines[: max_lines - 1]  # Opening --- + content lines
        front_matter_lines.append("---")  # Add back the closing delimiter

    front_matter = "\n".join(front_matter_lines)
    content_start_index = front_matter_end + 1

    return front_matter, content_start_index


def create_content_preview(body: str, max_length: int) -> str:
    """Create a content preview that preserves front matter if present.

    If the content starts with front matter (delimited by ---), includes the entire
    front matter in the preview, followed by regular content preview.

    Args:
        body: The note content to create a preview for
        max_length: Maximum length for the preview (excluding front matter)

    Returns:
        str: The content preview with front matter and content preview
    """
    if not body:
        return ""

    lines = body.split("\n")
    preview_parts = []

    # Extract frontmatter using utility function
    front_matter, content_start_index = extract_frontmatter(body, max_lines=20)

    if front_matter:
        preview_parts.append(front_matter)

    # Get remaining content after front matter
    remaining_lines = lines[content_start_index:]
    remaining_content = "\n".join(remaining_lines)

    # Calculate remaining space for content preview
    used_space = sum(
        len(part) + 1 for part in preview_parts
    )  # +1 for newlines between parts
    remaining_space = max(
        50, max_length - used_space
    )  # Ensure at least 50 chars for content

    # Add content preview with remaining space
    if remaining_content:
        content_preview = remaining_content.strip()
        if len(content_preview) > remaining_space:
            content_preview = content_preview[:remaining_space] + "..."

        # Only add content preview if it's meaningful (more than just "...")
        if len(content_preview.replace("...", "").strip()) > 10:
            preview_parts.append(content_preview)

    # If no meaningful content remains and no front matter, show regular preview
    if not preview_parts:
        preview = body[:max_length]
        if len(body) > max_length:
            preview += "..."
        return preview

    return "\n\n".join(preview_parts)


def create_toc_only(body: str) -> str:
    """Create a table of contents with line numbers from note content.

    Args:
        body: The note content to extract TOC from

    Returns:
        str: Table of contents with heading structure and line numbers, or empty string if no headings
    """
    if not body:
        return ""

    headings = parse_markdown_headings(body)

    if not headings:
        return ""

    # Create TOC entries with line numbers
    toc_entries = []
    for i, heading in enumerate(headings, 1):
        level = heading["level"]
        title = heading["title"]
        line_num = heading["line_idx"]  # 1-based line number

        # Create indentation based on heading level (level 1 = no indent, level 2 = 2 spaces, etc.)
        indent = "  " * (level - 1)
        toc_entries.append(f"{indent}{i}. {title} (line {line_num})")

    toc_header = "TABLE_OF_CONTENTS:"
    toc_content = "\n".join(toc_entries)

    return f"{toc_header}\n{toc_content}"


def extract_text_terms_from_query(query: str) -> List[str]:
    """Extract text search terms from a Joplin search query, removing operators.

    Removes Joplin search operators like tag:, notebook:, type:, iscompleted:, etc.
    and extracts the actual text terms for content matching.

    Args:
        query: The search query that may contain operators and text terms

    Returns:
        List of text terms for content matching
    """
    if not query or query.strip() == "*":
        return []

    # Known Joplin search operators to remove
    operator_patterns = [
        r"tag:\S+",  # tag:work
        r"notebook:\S+",  # notebook:project
        r"type:\S+",  # type:todo
        r"iscompleted:\d+",  # iscompleted:1
        r"created:\S+",  # created:20231201
        r"updated:\S+",  # updated:20231201
        r"latitude:\S+",  # latitude:123.456
        r"longitude:\S+",  # longitude:123.456
        r"altitude:\S+",  # altitude:123.456
        r"resource:\S+",  # resource:image
        r"sourceurl:\S+",  # sourceurl:http
        r"any:\d+",  # any:1
    ]

    # Remove all operators
    cleaned_query = query
    for pattern in operator_patterns:
        cleaned_query = re.sub(pattern, "", cleaned_query, flags=re.IGNORECASE)

    # Handle quoted phrases - extract them as single terms
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, cleaned_query)

    # Remove quoted phrases from the query to avoid double processing
    for phrase in phrases:
        cleaned_query = cleaned_query.replace(f'"{phrase}"', "")

    # Split remaining text into individual words
    individual_words = cleaned_query.split()

    # Combine phrases and individual words, filtering out empty strings
    all_terms = phrases + [word.strip() for word in individual_words if word.strip()]

    return all_terms


def _find_matching_lines(
    content_lines: List[str], search_terms: List[str], content_start_index: int
) -> tuple[List[tuple[int, str]], List[tuple[int, str]]]:
    """Find lines matching search terms, separated by AND vs OR logic."""
    search_terms_lower = [term.lower() for term in search_terms]

    and_matches = []
    or_matches = []
    and_indices = set()

    for i, line in enumerate(content_lines):
        line_index = i + content_start_index
        line_lower = line.lower()

        # Check for AND matches (all terms present)
        if all(term in line_lower for term in search_terms_lower):
            and_matches.append((line_index, line))
            and_indices.add(line_index)
        # Check for OR matches (any terms present), excluding AND matches
        elif any(term in line_lower for term in search_terms_lower):
            or_matches.append((line_index, line))

    return and_matches, or_matches


def create_matching_lines_preview(
    body: str,
    search_terms: List[str],
    max_length: int = 300,
    max_lines: int = 10,
    context_lines: int = 0,
) -> tuple[str, List[int], int, int]:
    """Create a preview showing only lines that match search terms with priority system.

    Priority system:
    1. Lines matching ALL search terms (AND logic) - highest priority
    2. Lines matching any search terms (OR logic) - lower priority
    3. Builds incrementally while respecting max_length limit

    Args:
        body: The note content to search in
        search_terms: List of terms to search for
        max_length: Maximum length for the preview content
        max_lines: Maximum number of matching lines to include
        context_lines: Number of context lines to show around matches

    Returns:
        tuple: (preview_content, list_of_displayed_line_numbers, and_matches_count, or_matches_count)
    """
    if not body or not search_terms:
        return "", [], 0, 0

    lines = body.split("\n")
    _, content_start_index = extract_frontmatter(body)
    content_lines = lines[content_start_index:]

    # Find all matching lines
    and_matches, or_matches = _find_matching_lines(
        content_lines, search_terms, content_start_index
    )
    and_count, or_count = len(and_matches), len(or_matches)

    # Combine matches with priority (AND first, then OR)
    all_matches = and_matches + or_matches
    if not all_matches:
        return "", [], 0, 0

    # Build preview incrementally
    preview_parts = []
    included_line_numbers = []
    used_indices = set()
    current_length = 0

    for line_index, _ in all_matches:
        if len(included_line_numbers) >= max_lines:
            break

        # Calculate what this match would add to the preview
        context_block = []
        block_indices = []

        # Calculate context range
        start_context = max(content_start_index, line_index - context_lines)
        end_context = min(len(lines), line_index + context_lines + 1)

        # Build context block for this match
        for ctx_i in range(start_context, end_context):
            if ctx_i not in used_indices:
                block_indices.append(ctx_i)
                line_num = ctx_i + 1  # 1-based
                line_content = lines[ctx_i]

                # Mark the actual matching line vs context
                if ctx_i == line_index:
                    context_block.append(f"[L{line_num}] {line_content}")
                else:
                    context_block.append(f" L{line_num}  {line_content}")

        if context_block:
            block_content = "\n".join(context_block)
            separator_length = 1 if preview_parts else 0  # Newline separator
            block_length = len(block_content) + separator_length

            # Check length limit
            if current_length + block_length > max_length and preview_parts:
                break

            # Add block with separator
            if preview_parts:
                preview_parts.append("")
            preview_parts.extend(context_block)

            current_length += block_length
            used_indices.update(block_indices)
            included_line_numbers.append(line_index + 1)  # 1-based

    preview_content = "\n".join(preview_parts) if preview_parts else ""
    return preview_content, included_line_numbers, and_count, or_count


def create_content_preview_with_search(
    body: str, max_length: int, search_query: str = ""
) -> str:
    """Create a content preview that shows matching lines for search queries, with fallback.

    Enhancement to create_content_preview that prioritizes showing lines matching
    the search query instead of just the first lines of content.

    Args:
        body: The note content to create a preview for
        max_length: Maximum length for the preview (excluding front matter)
        search_query: The search query to extract terms from

    Returns:
        str: The content preview with matching lines or fallback to regular preview
    """
    if not body:
        return ""

    search_terms = extract_text_terms_from_query(search_query)
    if not search_terms:
        return create_content_preview(body, max_length)

    # Extract frontmatter and calculate available space
    front_matter, _ = extract_frontmatter(body, max_lines=10)
    available_length = max(50, max_length - len(front_matter))

    matching_preview, line_numbers, and_matches, or_matches = (
        create_matching_lines_preview(
            body,
            search_terms,
            max_length=available_length,
            max_lines=8,
            context_lines=0,
        )
    )

    if not matching_preview:
        return create_content_preview(body, max_length)

    # Build preview with metadata
    preview_parts = []

    if front_matter:
        preview_parts.append(front_matter)

    # Build match quality description
    displayed_matches = len(line_numbers)
    total_matches = and_matches + or_matches

    if and_matches > 0 and or_matches > 0:
        quality_info = f"({and_matches} match all terms, {or_matches} match any terms)"
    elif and_matches > 0:
        quality_info = "(all match all search terms)"
    else:
        quality_info = "(all match some search terms)"

    # Build main message with truncation info
    if displayed_matches < total_matches:
        match_info = f"MATCHING_LINES: {total_matches} total lines match search terms {quality_info} - showing first {displayed_matches}"
    else:
        match_info = (
            f"MATCHING_LINES: {total_matches} lines match search terms {quality_info}"
        )

    # Add search terms info
    if search_terms:
        terms_str = ", ".join(f'"{term}"' for term in search_terms[:3])
        if len(search_terms) > 3:
            terms_str += f" (+{len(search_terms)-3} more)"
        match_info += f" [{terms_str}]"

    preview_parts.append(match_info)
    preview_parts.append("")
    preview_parts.append(matching_preview)

    return "\n".join(preview_parts)


def format_timestamp(
    timestamp: Optional[Union[int, datetime.datetime]],
    format_str: str = "%Y-%m-%d %H:%M:%S",
) -> Optional[str]:
    """Format a timestamp safely."""
    if not timestamp:
        return None
    try:
        if isinstance(timestamp, datetime.datetime):
            return timestamp.strftime(format_str)
        elif isinstance(timestamp, int):
            return datetime.datetime.fromtimestamp(timestamp / 1000).strftime(
                format_str
            )
        else:
            return None
    except:
        return None


def calculate_content_stats(body: str) -> Dict[str, int]:
    """Calculate content statistics for a note body.

    Args:
        body: The note content to analyze

    Returns:
        Dict with keys: 'characters', 'words', 'lines'
    """
    if not body:
        return {"characters": 0, "words": 0, "lines": 0}

    # Character count (including whitespace and special characters)
    char_count = len(body)

    # Line count
    line_count = len(body.split("\n"))

    # Word count (split by whitespace and filter empty strings)
    words = [word for word in body.split() if word.strip()]
    word_count = len(words)

    return {"characters": char_count, "words": word_count, "lines": line_count}
