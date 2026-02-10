# [v0.6.0](https://github.com/alondmnt/joplin-mcp/releases/tag/v0.6.0)
*Released on 2026-02-10*

- added: `edit_note` tool for precision text editing (find/replace, append, prepend) without full-body replacement
- added: per-tool env var documentation (`JOPLIN_TOOL_<NAME>`)
- improved: `update_note` and `edit_note` docstrings cross-reference each other for clearer tool selection
- changed: deletion tools (`delete_note`, `delete_notebook`, `delete_tag`) disabled by default
- fixed: `verify_ssl` defaulting to `None` instead of `False` in `from_environment()`
- fixed: `find_in_note` missing from `DEFAULT_TOOLS` / `TOOL_CATEGORIES` (could not be disabled via config)
- fixed: `__version__` in `__init__.py` was stale at 0.4.1 since v0.5.0
- fixed: `supported_tools` list in `__init__.py` now derived from config to stay in sync

**Full Changelog**: https://github.com/alondmnt/joplin-mcp/compare/v0.5.0...v0.6.0

---

# [v0.5.0](https://github.com/alondmnt/joplin-mcp/releases/tag/v0.5.0)
*Released on 2026-01-31*

- added: path-based notebook resolution (e.g., `Parent/Child/Notebook`)
- added: notebook suggestions on path resolution errors
- added: `todo_due` parameter to `create_note` and `update_note`
- added: `--version` CLI flag
- added: single-note cache for improved sequential reading performance
- added: security hardening and healthcheck to Dockerfile
- added: docker-compose.yml example for local testing
- fixed: `untag_note` tool using incorrect joppy API method
- fixed: quote notebook/tag names in search queries
- refactored: split fastmcp_server.py into modular tool packages
- refactored: extract formatting, content, and notebook utilities

**Full Changelog**: https://github.com/alondmnt/joplin-mcp/compare/v0.4.1...v0.5.0

---

# [v0.4.1](https://github.com/alondmnt/joplin-mcp/releases/tag/v0.4.1)
*Released on 2025-10-10T00:20:02Z*

- added: GitHub Actions workflow that runs tests, builds, publishes to PyPI, and uploads to the MCP registry via OIDC

**Full Changelog**: https://github.com/alondmnt/joplin-mcp/compare/v0.4.0...v0.4.1

---

# [v0.4.0](https://github.com/alondmnt/joplin-mcp/releases/tag/v0.4.0)
*Released on 2025-09-16T14:10:31Z*

- added: tool `import_from_file` supporting Markdown, HTML, CSV, TXT, JEX, directories and attachments (#6 by @casistack)
- added: Dockerfile (#3)
- added: notebook path to output (#5)
- fixed: Claude setup to follow the tool permissions in the config JSON
- refactored: single entry point `joplin_mcp.server`

**Full Changelog**: https://github.com/alondmnt/joplin-mcp/compare/v0.3.1...v0.4.0

---

# [v0.3.1](https://github.com/alondmnt/joplin-mcp/releases/tag/v0.3.1)
*Released on 2025-08-29T04:19:17Z*



---

# [v0.3.0](https://github.com/alondmnt/joplin-mcp/releases/tag/v0.3.0)
*Released on 2025-07-25T01:54:52Z*

- added: preview matched lines in `find_notes`
- added: smart TOC in `get_note`
- added: section extraction support in `get_note`
- added: sequential reading support in `get_note` with line extraction / pagination
- added: note statistics to note metadata
- improved: extract section slugs from links
- improved: increased maximum preview length to 300 characters

---

# [v0.2.1](https://github.com/alondmnt/joplin-mcp/releases/tag/v0.2.1)
*Released on 2025-07-17T00:30:32Z*

- fixed: backlinks in `get_links` tool

---

# [v0.2.0](https://github.com/alondmnt/joplin-mcp/releases/tag/v0.2.0)
*Released on 2025-07-16T08:38:26Z*

- added: `get_links` tool, for outgoing and backlinks
- added: pagination interface to search tools
- added: front matter metadata support in content preview
- improved: tool output formatting for LLM comprehension
- improved: tool parameter annotation

---

# [v0.1.1](https://github.com/alondmnt/joplin-mcp/releases/tag/v0.1.1)
*Released on 2025-07-09T00:15:30Z*

- added: args `task` and `completed` to find tools
- improved: disable get_all_notes by default
     - to avoid context window overflow

---

# [v0.1.0](https://github.com/alondmnt/joplin-mcp/releases/tag/v0.1.0)
*Released on 2025-07-07T01:12:33Z*

first release, with a near complete toolbox that wraps the Joplin API.

---
