# Test Files for Joplin MCP Import System

This directory contains sample files for testing the import functionality:

## Files Included

- **`sample.md`** - Markdown with headers, lists, code blocks
- **`sample.html`** - HTML with structure to test conversion
- **`sample.csv`** - CSV data for table import testing  
- **`sample.txt`** - Plain text file
- **`frontmatter.md`** - Markdown with YAML frontmatter metadata

## Usage

Use these files to test the `import_from_file` tool via your MCP client:

```python
# Import individual files
import_from_file(file_path="test_files/sample.md")
import_from_file(file_path="test_files/sample.html") 
import_from_file(file_path="test_files/sample.csv")

# Import entire directory
import_from_file(file_path="test_files/")
```

## Expected Results

Each file should import successfully with:
- ✅ Proper format conversion
- ✅ Structure preservation  
- ✅ Auto-tagging by file extension
- ✅ Metadata extraction (frontmatter.md)
