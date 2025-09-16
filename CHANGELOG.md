# [v0.4.0](https://github.com/alondmnt/joplin-mcp/releases/tag/v0.4.0)
*Released on 2025-09-16T14:10:31Z*

- add: tool `import_from_file` supporting Markdown, HTML, CSV, TXT, JEX, directories and attachments (#6 by @casistack)
- add: Dockerfile (#3)
- add: notebook path to output (#5)
- fix: Claude setup to follow the tool permissions in the config JSON
- refactor: single entry point `joplin_mcp.server`

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
