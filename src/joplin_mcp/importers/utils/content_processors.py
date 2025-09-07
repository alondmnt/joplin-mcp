"""Content processing utilities for importers."""

import csv
import re
from io import StringIO
from pathlib import Path
from typing import List, Optional

# Define exception locally to avoid circular imports
class ImportProcessingError(Exception):
    """Exception raised during import processing."""
    pass


def extract_title_from_content(content: str, filename_fallback: str) -> str:
    """Extract title from content or use filename fallback.
    
    Args:
        content: File content to analyze
        filename_fallback: Fallback title from filename
        
    Returns:
        Extracted or generated title
    """
    lines = content.strip().split("\n")
    
    # Try first line if it starts with #
    for line in lines:
        line = line.strip()
        if line.startswith("#"):
            # Extract heading text
            title = re.sub(r"^#+\s*", "", line).strip()
            if title:
                return title
    
    # Try first non-empty line as title if it's reasonably short
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            # Use first line as title if it's short and looks like a title
            if len(line) <= 100 and not line.endswith("."):
                # Check if it looks like a title (no paragraph text indicators)
                if not any(
                    phrase in line.lower()
                    for phrase in ["the ", "this ", "here ", "when ", "where ", "and ", "but "]
                ):
                    return line
    
    # Clean up filename fallback
    title = filename_fallback.replace("_", " ").replace("-", " ")
    return " ".join(word.capitalize() for word in title.split()) or "Untitled"


def extract_hashtags(content: str) -> List[str]:
    """Extract hashtags from content.
    
    Args:
        content: Text content to analyze
        
    Returns:
        List of unique hashtags (without # symbol)
    """
    if not content:
        return []
    
    # Find hashtags in the content
    hashtag_pattern = r"#([a-zA-Z0-9_-]+)"
    hashtags = re.findall(hashtag_pattern, content)
    
    # Remove duplicates and return
    return list(set(hashtags))


def html_to_markdown(html_content: str, title: Optional[str] = None) -> str:
    """Convert HTML content to Markdown.
    
    Args:
        html_content: HTML content to convert
        title: Optional title to add if not present
        
    Returns:
        Markdown content
    """
    try:
        import markdownify
        from bs4 import BeautifulSoup
        
        # Parse HTML content
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Remove script and style tags for security
        for tag in soup.find_all(["script", "style"]):
            tag.decompose()
        
        # Convert to Markdown
        markdown = markdownify.markdownify(
            str(soup),
            heading_style="ATX",  # Use # style headers
            bullets="-",  # Use - for bullets
            strip=["script", "style"],  # Strip these elements
        )
        
        # Clean up the markdown
        markdown = clean_markdown(markdown)
        
        # Add title if not already present and title provided
        if title and not markdown.strip().startswith("#"):
            markdown = f"# {title}\n\n{markdown}"
        
        return markdown.strip()
        
    except ImportError:
        # Fallback when markdownify/BeautifulSoup not available
        return _html_to_markdown_fallback(html_content, title)


def _html_to_markdown_fallback(html_content: str, title: Optional[str] = None) -> str:
    """Fallback HTML to Markdown conversion without external dependencies."""
    content = html_content
    
    # Add warning comment
    result = "<!-- Note: HTML converted using fallback method. Install beautifulsoup4 and markdownify for better conversion -->\n\n"
    
    if title:
        result += f"# {title}\n\n"
    
    # Remove script and style content
    content = re.sub(
        r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL | re.IGNORECASE
    )
    content = re.sub(
        r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL | re.IGNORECASE
    )
    
    # Convert headers
    content = re.sub(r"<h1[^>]*>(.*?)</h1>", r"# \1", content, flags=re.IGNORECASE)
    content = re.sub(r"<h2[^>]*>(.*?)</h2>", r"## \1", content, flags=re.IGNORECASE)
    content = re.sub(r"<h3[^>]*>(.*?)</h3>", r"### \1", content, flags=re.IGNORECASE)
    content = re.sub(r"<h4[^>]*>(.*?)</h4>", r"#### \1", content, flags=re.IGNORECASE)
    content = re.sub(r"<h5[^>]*>(.*?)</h5>", r"##### \1", content, flags=re.IGNORECASE)
    content = re.sub(r"<h6[^>]*>(.*?)</h6>", r"###### \1", content, flags=re.IGNORECASE)
    
    # Convert paragraphs
    content = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", content, flags=re.DOTALL | re.IGNORECASE)
    
    # Convert line breaks
    content = re.sub(r"<br[^>]*>", "\n", content, flags=re.IGNORECASE)
    
    # Convert bold and italic
    content = re.sub(r"<(strong|b)[^>]*>(.*?)</\1>", r"**\2**", content, flags=re.IGNORECASE)
    content = re.sub(r"<(em|i)[^>]*>(.*?)</\1>", r"*\2*", content, flags=re.IGNORECASE)
    
    # Convert links
    content = re.sub(
        r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>',
        r"[\2](\1)",
        content,
        flags=re.IGNORECASE,
    )
    
    # Convert lists (basic)
    content = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1", content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r"<[uo]l[^>]*>", "", content, flags=re.IGNORECASE)
    content = re.sub(r"</[uo]l>", "", content, flags=re.IGNORECASE)
    
    # Remove remaining HTML tags
    content = re.sub(r"<[^>]+>", "", content)
    
    # Clean up whitespace
    content = re.sub(r"\n\s*\n\s*\n", "\n\n", content)
    content = re.sub(r"[ \t]+", " ", content)
    
    result += content.strip()
    return result


def csv_to_markdown_table(csv_content: str, title: Optional[str] = None, delimiter: str = ",") -> str:
    """Convert CSV content to Markdown table.
    
    Args:
        csv_content: CSV content as string
        title: Optional title for the table
        delimiter: CSV delimiter
        
    Returns:
        Markdown table content
        
    Raises:
        ImportProcessingError: If CSV parsing fails
    """
    try:
        # Parse CSV data
        reader = csv.reader(StringIO(csv_content), delimiter=delimiter)
        rows = list(reader)
        
        if not rows:
            return f"# {title}\n\nEmpty CSV file." if title else "Empty CSV file."
        
        # Create Markdown table
        markdown_lines = []
        if title:
            markdown_lines.extend([f"# {title}", ""])
        
        markdown_lines.append("CSV Data:")
        markdown_lines.append("")
        
        # Add table headers (first row)
        headers = rows[0] if rows else []
        if headers:
            # Clean and format headers
            clean_headers = [_clean_cell_content(header) for header in headers]
            markdown_lines.append("| " + " | ".join(clean_headers) + " |")
            markdown_lines.append("| " + " | ".join(["---"] * len(clean_headers)) + " |")
            
            # Add data rows
            for row in rows[1:]:
                # Pad row to match header count
                padded_row = row + [""] * (len(headers) - len(row))
                clean_row = [
                    _clean_cell_content(cell) for cell in padded_row[:len(headers)]
                ]
                markdown_lines.append("| " + " | ".join(clean_row) + " |")
        
        return "\n".join(markdown_lines)
        
    except (csv.Error, UnicodeDecodeError) as e:
        # Fallback: return as code block for CSV parsing errors
        fallback = f"```csv\n{csv_content}\n```"
        if title:
            fallback = f"# {title}\n\n{fallback}"
        return fallback


def _clean_cell_content(content: str) -> str:
    """Clean and format cell content for Markdown tables."""
    if not content:
        return ""
    
    # Strip whitespace
    cleaned = content.strip()
    
    # Escape pipe characters for Markdown tables
    cleaned = cleaned.replace("|", "\\|")
    
    # Replace newlines with spaces in table cells
    cleaned = re.sub(r"\s+", " ", cleaned)
    
    return cleaned


def clean_markdown(markdown: str) -> str:
    """Clean up markdown formatting.
    
    Args:
        markdown: Markdown content to clean
        
    Returns:
        Cleaned markdown content
    """
    # Remove excessive whitespace
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    
    # Remove trailing whitespace from lines
    lines = [line.rstrip() for line in markdown.split("\n")]
    markdown = "\n".join(lines)
    
    # Clean up list formatting
    markdown = re.sub(r"\n\s*\n\s*-", "\n-", markdown)
    
    # Remove empty list items
    markdown = re.sub(r"\n-\s*\n", "\n", markdown)
    
    # Fix common conversion issues
    markdown = re.sub(r"\*\*\s+", "**", markdown)  # Fix bold formatting
    markdown = re.sub(r"\s+\*\*", "**", markdown)
    markdown = re.sub(r"\*\s+", "*", markdown)  # Fix italic formatting  
    markdown = re.sub(r"\s+\*", "*", markdown)
    
    # Clean up links
    markdown = re.sub(r"\[\s+", "[", markdown)
    markdown = re.sub(r"\s+\]", "]", markdown)
    
    return markdown.strip()


def convert_plain_text_to_markdown(content: str, title: Optional[str] = None) -> str:
    """Convert plain text to basic Markdown format.
    
    Args:
        content: Plain text content
        title: Optional title to add
        
    Returns:
        Markdown formatted content
    """
    lines = content.split("\n")
    processed_lines = []
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Skip empty lines
        if not stripped:
            processed_lines.append("")
            continue
        
        # Detect potential headers (lines that are short and followed by empty line)
        is_potential_header = (
            len(stripped) <= 80
            and not stripped.endswith(".")
            and (i == len(lines) - 1 or lines[i + 1].strip() == "")
        )
        
        # Convert potential headers to Markdown headers (but not first line if we have a title)
        if is_potential_header and (i > 0 or not title):
            processed_lines.append(f"## {stripped}")
        else:
            processed_lines.append(line)
    
    markdown = "\n".join(processed_lines)
    
    # Add title if provided and not already present
    if title and not markdown.strip().startswith("#"):
        markdown = f"# {title}\n\n{markdown}"
    
    return markdown


def extract_frontmatter_field(content: str, field_name: str) -> Optional[str]:
    """Extract a specific field from YAML frontmatter.
    
    Args:
        content: Content with potential frontmatter
        field_name: Field name to extract
        
    Returns:
        Field value as string or None if not found
    """
    if not content.startswith("---"):
        return None
    
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    
    frontmatter_text = parts[1].strip()
    
    # Try YAML parsing first
    try:
        import yaml
        frontmatter = yaml.safe_load(frontmatter_text)
        if isinstance(frontmatter, dict):
            value = frontmatter.get(field_name)
            return str(value) if value is not None else None
    except ImportError:
        # Fallback to simple parsing
        pass
    except Exception:
        # YAML parsing failed, fallback
        pass
    
    # Simple key: value parsing
    for line in frontmatter_text.split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            if key.strip() == field_name:
                value = value.strip()
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                return value
    
    return None


def extract_frontmatter_tags(content: str) -> List[str]:
    """Extract tags from YAML frontmatter.
    
    Args:
        content: Content with potential frontmatter
        
    Returns:
        List of tags from frontmatter
    """
    if not content.startswith("---"):
        return []
    
    parts = content.split("---", 2)
    if len(parts) < 3:
        return []
    
    frontmatter_text = parts[1].strip()
    tags = []
    
    # Try YAML parsing first
    try:
        import yaml
        frontmatter = yaml.safe_load(frontmatter_text)
        if isinstance(frontmatter, dict):
            # Check various tag field names
            for tag_field in ['tags', 'categories', 'keywords']:
                fm_tags = frontmatter.get(tag_field)
                if fm_tags:
                    if isinstance(fm_tags, list):
                        # Handle list format: tags: [tag1, tag2, tag3]
                        tags.extend([str(tag).strip() for tag in fm_tags if tag])
                    elif isinstance(fm_tags, str):
                        # Handle string format: tags: "tag1, tag2, tag3" or tags: "tag1 tag2 tag3"
                        tag_parts = re.split(r'[,\s]+', fm_tags.strip())
                        tags.extend([tag.strip() for tag in tag_parts if tag.strip()])
            return list(set(tags))  # Remove duplicates
    except ImportError:
        # Fallback when YAML not available
        pass
    except Exception:
        # YAML parsing failed, use fallback
        pass
    
    # Simple fallback parsing for tags
    for line in frontmatter_text.split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            if key in ['tags', 'categories', 'keywords']:
                value = value.strip()
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                elif value.startswith('[') and value.endswith(']'):
                    # Simple list parsing: [tag1, tag2, tag3]
                    value = value[1:-1]
                    tag_parts = [item.strip().strip("\"'") for item in value.split(',')]
                    tags.extend([tag for tag in tag_parts if tag])
                    continue
                
                # Handle comma or space separated tags
                if ',' in value or ' ' in value:
                    tag_parts = re.split(r'[,\s]+', value)
                    tags.extend([tag.strip() for tag in tag_parts if tag.strip()])
                else:
                    # Single tag
                    if value:
                        tags.append(value)
    
    return list(set(tags))  # Remove duplicates


def extract_all_tags(content: str) -> List[str]:
    """Extract all tags from content - both frontmatter tags and hashtags.
    
    Args:
        content: Content to analyze
        
    Returns:
        List of unique tags from both frontmatter and content hashtags
    """
    all_tags = []
    
    # Extract frontmatter tags
    frontmatter_tags = extract_frontmatter_tags(content)
    all_tags.extend(frontmatter_tags)
    
    # Extract hashtags from content
    hashtags = extract_hashtags(content)
    all_tags.extend(hashtags)
    
    # Remove duplicates and empty tags
    return list(set(tag for tag in all_tags if tag and tag.strip()))
