---
name: joplin
description: Orchestration guidance for Joplin note, notebook, and tag management tools
user-invocable: true
---

# Joplin MCP — Orchestration Guide

This skill covers non-obvious tool interactions. Tool parameters are already in the tool schemas — don't restate them here.

## Setup

If Joplin MCP tools (e.g., `ping_joplin`) aren't available, the server isn't connected. Follow these steps to configure it automatically:

1. **Ask the user for their Joplin API token.** Tell them where to find it:
   > Open Joplin Desktop → Tools → Options → Web Clipper → copy the **Authorization token**.

2. **Write `.mcp.json`** to the project root with the token. Use the Write tool to create the file:

   ```json
   {
     "mcpServers": {
       "joplin-mcp": {
         "command": "uvx",
         "args": ["--from", "joplin-mcp", "joplin-mcp-server"],
         "env": {
           "JOPLIN_TOKEN": "<paste_token_here>"
         }
       }
     }
   }
   ```

   This file is already covered by `.gitignore` (`.*` rule) so it won't be committed.

3. **Tell the user to restart Claude Code.** The MCP server is loaded at startup, so a restart is required for the tools to appear.

4. **After restart**, call `ping_joplin` to verify the connection.

## Critical: edit_note vs update_note

- **`edit_note`** — find/replace, append, prepend. Use this for partial changes.
- **`update_note(body=...)`** — **replaces the entire body**. Only use when you intend to rewrite the whole note.

If you need to change a paragraph, fix a typo, or append a section: always use `edit_note`.

## Reading long notes

`get_note` returns a **table of contents** (not content) when a note exceeds ~50 lines. To read the actual content:

1. `get_note(note_id)` — see the TOC and line count
2. `get_note(note_id, section="Section Name")` — extract a specific section
3. `get_note(note_id, start_line=1, line_count=50)` — sequential reading by line range
4. `get_note(note_id, force_full=True)` — force full content (large context cost)

## IDs vs names

| Parameter | Accepts |
|-----------|---------|
| `note_id` | 32-char hex ID only |
| `notebook_name` | Human-readable name (e.g., "Work") |
| `tag_name` | Human-readable name (e.g., "important") |
| `parent_id` | 32-char hex ID of parent notebook |

Search results return IDs — use those IDs in subsequent calls.

## Pre-check before bulk tagging

`tag_note` fails if the tag doesn't exist. Before tagging multiple notes:

1. `create_tag("my-tag")` — create it first (idempotent if it already exists)
2. Then loop: `tag_note(note_id, "my-tag")` for each note

## Workflow recipes

### Edit a long note

```
get_note(id)                          # see TOC + line count
get_note(id, section="Target")        # read the section you need
edit_note(id, old_string="...", new_string="...")  # surgical edit
```

### Create a sub-notebook with notes

```
list_notebooks()                      # find parent notebook ID
create_notebook("Sub", parent_id="<parent_hex_id>")
create_note("Title", notebook_name="Sub", body="...")
```

### Bulk-tag notes from search

```
create_tag("project-x")              # ensure tag exists first
find_notes("project x")              # get note IDs
tag_note(id1, "project-x")           # tag each result
tag_note(id2, "project-x")
```

### Move a note to a different notebook

```
list_notebooks()                      # find target notebook ID
update_note(note_id, notebook_id="<target_hex_id>")
```
