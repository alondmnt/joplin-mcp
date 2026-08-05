# Content Privacy Controls

The Joplin MCP server includes comprehensive content exposure controls to address privacy and security concerns when using AI assistants with your personal notes.

## Overview

By default, the MCP server may expose note content to AI systems, which raises legitimate privacy concerns. The content exposure controls allow you to configure exactly what content is visible in different contexts.

## Content Exposure Levels

| Level | Description | Use Case |
|-------|-------------|----------|
| `none` | No content shown - titles and metadata only | Maximum privacy |
| `preview` | Short preview snippets (configurable length) | Balanced privacy |
| `full` | Full content access | Full functionality |

## Configuration Contexts

You can configure different exposure levels for different contexts:

### `search_results`
Controls content visibility in every search and listing operation:
- `find_notes`
- `find_notes_with_tag`
- `find_notes_in_notebook`
- `get_all_notes`

**Default:** `preview`

### `individual_notes`
Controls content visibility when retrieving specific notes:
- `get_note`

**Default:** `full`

These two are the only contexts. Earlier versions also documented a
`listings` context for `find_notes_in_notebook` and `find_notes_with_tag`,
but no tool ever read it - those tools use `search_results`. The key is
still accepted in existing config files and ignored with a warning.

## Smart TOC Controls

### `smart_toc_threshold`
Character count threshold for automatic TOC display in individual notes.
- Notes shorter than this threshold show full content immediately
- Notes longer than this threshold show TOC + metadata only (prevents context flooding)
- Users can override with `force_full=True` parameter

**Default:** `2000`

### `enable_smart_toc`
Global toggle for smart TOC behavior.
- `true`: Enable smart TOC system for efficient context management
- `false`: Always show full content (legacy behavior)

**Default:** `true`

## Configuration Examples

### 1. Privacy-Focused Configuration
```json
{
  "content_exposure": {
    "search_results": "none",
    "individual_notes": "none",
    "max_preview_length": 0,
    "smart_toc_threshold": 2000,
    "enable_smart_toc": false
  }
}
```

### 2. Balanced Configuration (Default)
```json
{
  "content_exposure": {
    "search_results": "preview",
    "individual_notes": "full",
    "max_preview_length": 300,
    "smart_toc_threshold": 2000,
    "enable_smart_toc": true
  }
}
```

### 3. Full Access Configuration
```json
{
  "content_exposure": {
    "search_results": "full",
    "individual_notes": "full",
    "max_preview_length": 500,
    "smart_toc_threshold": 2000,
    "enable_smart_toc": true
  }
}
```

### 4. Token-Frugal Configuration

```json
{
  "content_exposure": {
    "search_results": "none",
    "individual_notes": "full",
    "smart_toc_threshold": 1000,
    "enable_smart_toc": true
  }
}
```

The two settings work on different responses, so it's worth being precise
about which does what:

- `search_results` governs listing size. Measured on a 20-result
  `find_notes_in_notebook` of 3000-character notes (~3200 tokens at the
  defaults): `"none"` drops previews entirely for ~44% less, and
  `"preview"` with `"max_preview_length": 100` keeps snippets for ~31%
  less. `max_preview_length` is omitted above because `"none"` turns
  previews off, which makes the length irrelevant.
- `smart_toc_threshold` governs individual `get_note` responses only. It
  cannot change listing size. Lowering it to 1000 means mid-length notes
  come back as a table of contents rather than a full body - on a
  10,000-character note that's ~240 tokens instead of ~2580.

The largest single lever is neither: pass a smaller `limit` on
`find_notes`, `find_notes_in_notebook` and `find_notes_with_tag`. The
default is 20; `limit=5` is ~73% less, and combined with
`search_results: "none"` it's ~84% less.

Disabling the tools you don't use helps too, though it works on a
different budget - tool definitions are sent once per session, and cost a
few thousand tokens at the default set.

## Environment Variables

You can also configure content exposure via environment variables:

```bash
export JOPLIN_CONTENT_SEARCH_RESULTS=none
export JOPLIN_CONTENT_INDIVIDUAL_NOTES=preview
export JOPLIN_MAX_PREVIEW_LENGTH=150
export JOPLIN_SMART_TOC_THRESHOLD=2000
export JOPLIN_ENABLE_SMART_TOC=true
```

**Precedence:** the server loads a config file *or* the environment, not
both. If `joplin-mcp.json` (or one of the other discovered paths) exists,
these variables are ignored - put the settings in the file instead.

## Security Best Practices

### For Maximum Privacy
1. Set all content exposure levels to `none`
2. Set `max_preview_length` to `0`
3. Use read-only tools only
4. Review AI chat logs regularly

### For Balanced Privacy
1. Use `preview` for search results
2. Use `full` only for individual notes when needed
3. Set a reasonable `max_preview_length` (100-200 characters)

### For Corporate/Sensitive Data
1. Consider using `none` for all contexts
2. Implement additional access controls at the network level
3. Use dedicated Joplin instances for sensitive data
4. Regular audit of configurations

## Privacy Impact

### Content Exposure: `none`
- ✅ Maximum privacy protection
- ✅ No content visible to AI systems
- ❌ Reduced functionality for content-based operations

### Content Exposure: `preview`
- ✅ Good privacy balance
- ✅ Some functionality preserved
- ⚠️ Limited content exposure (snippets only)

### Content Exposure: `full`
- ✅ Full functionality
- ❌ Complete content exposure
- ❌ Privacy concerns for sensitive data

## Troubleshooting

### Content Not Showing
Check your content exposure settings:
```bash
# View current configuration
python -c "
from joplin_mcp.config import JoplinMCPConfig
config = JoplinMCPConfig.load()
print('Content exposure:', config.content_exposure)
"
```

### Unexpected Content Exposure
Verify your configuration file is being loaded:
```bash
# Check which config file is being used
python -c "
from joplin_mcp.config import JoplinMCPConfig
import os
for path in JoplinMCPConfig.DEFAULT_CONFIG_PATHS:
    if path.exists():
        print(f'Config found: {path}')
        break
"
```

## Migration Guide

If you're upgrading from a version without content exposure controls:

1. **Backup your existing configuration**
2. **Review your privacy requirements**
3. **Add content exposure settings to your config file**
4. **Test with privacy-focused settings first**
5. **Gradually increase exposure as needed**

## Configuration Validation

The system validates content exposure settings:
- Content levels must be `none`, `preview`, or `full`
- `max_preview_length` must be a non-negative integer
- `smart_toc_threshold` must be a positive integer
- `enable_smart_toc` must be a boolean value
- Unknown settings will cause validation errors

Invalid configuration example:
```json
{
  "content_exposure": {
    "search_results": "invalid_level"  // ❌ Will fail validation
  }
}
```

## Related Security Features

- **Tool Controls:** Disable write operations (`create_*`, `update_*`, `delete_*`)
- **Network Security:** Use HTTPS and proper authentication
- **Access Logging:** Monitor which tools are being used
- **Configuration Auditing:** Regular review of enabled features 