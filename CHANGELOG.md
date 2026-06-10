# [v0.8.0](https://github.com/alondmnt/joplin-mcp/releases/tag/v0.8.0)
*Released on 2026-05-16T10:27:53Z*

## What's New

- **Notebook allowlist** — pattern-based access control restricting the AI to a chosen set of notebooks. Useful when you want an agent that can touch your work notes but not your personal ones, or any other slice of the tree.
  - gitignore-style patterns: exact names, `*` wildcards, `**` recursive, `!` negation
  - hierarchical access: allowing a parent grants access to all children
  - enforced across every tool that touches notebooks: read, write, search, list, tag
  - generic refusal messages on denials, so the agent doesn't learn which notebooks exist behind the allowlist
  - configurable via JSON (`notebook_allowlist`) or env var (`JOPLIN_NOTEBOOK_ALLOWLIST`)
  - startup validation with logging, and auto-creation of a default notebook when the allowlist resolves to zero accessible notebooks
  - landed across #25, #26, #27 by @rubalo
- **`restore_from_trash`** — recover soft-deleted notes from Joplin's trash. The MCP could already soft-delete via `delete_note` but had no way to undelete, so an accidental delete by an agent meant dropping into the Joplin UI to recover. That gap is now closed (#23 by @MatthewOGoodman).
- **Move notes between notebooks** — `update_note` accepts a `notebook_name` argument that relocates the note in a single call. Previously the only way to move a note from inside the MCP was a delete-and-recreate dance (closes #21).
- **Bulk tag operations** — `tag_note` and `untag_note` accept lists of note IDs and tag names. When either side is a list, the cartesian product runs in one call with a per-pair report, so tagging a batch of notes is one tool invocation instead of N (closes #22).

## Dependency Changes

- **`fastmcp` upgraded to v3** (`>=3,<4`, with `3.3.1` excluded for an upstream import regression). `fastmcp` 3.x moved tool storage off `_tool_manager._tools` onto a provider model and made decorators return the wrapped function instead of a Tool object, so the internal registration path was rewritten against the v3 API. No surface-API change for users beyond the dependency bump itself.

## Fixes

- **Information disclosure in error messages** — tool errors used to forward the Joplin API token via the request URL, the internal TypeScript stack-trace lines from Joplin Desktop, and absolute filesystem paths from the install location (some wrapped in `file://` URLs, some inside JSON response bodies with escaped `\n` between frames). The sanitiser now scrubs all of those before the message reaches the MCP client. The leak was surfaced by an agent smoke test against `get_note` with an all-zeros ID; a follow-up smoke pass surfaced the JSON-escaped / `file://` variants that the first pass missed (#49).
- **`delete_notebook` no longer reports SUCCESS for a non-existent notebook.** Joplin's Data API is idempotent on DELETE — calling it for a missing notebook silently 200s. The tool now does a GET first so the 404 propagates as a sanitised `ValueError` instead of masking a no-op as success. Surfaced by the agent smoke test.
- **`delete_note` no longer reports SUCCESS for a non-existent note** — same root cause as `delete_notebook`. The fix is tidier here because the allowlist branch already had a `client.get_note(...)` for the parent-ID lookup; pulling that GET out of the conditional lets it serve as the existence check too, so there's no extra round trip when the allowlist is on.
- **Stricter `create_notebook` parent ID validation** — malformed parent IDs are caught at the tool boundary now, instead of falling through to joppy with a less useful error (#28 by @iclem).
- **Allowlist edge cases**:
  - empty list now denies all access, instead of being treated as "no restriction" (#46, #47)
  - the allowlist is preserved through `JoplinMCPConfig.copy`, so derived configs don't silently drop the restriction (#45)
  - the notebook-resolver factory rebinds correctly when the client is patched, so tests using monkey-patched clients no longer see stale state (#38)
- **Smart-TOC `NEXT_STEPS` grounded in the note's own headings** — the hint used to show placeholder examples like `section="Introduction"` and `start_line=45` that didn't match the TOC printed directly above. Now both examples pull from the parsed headings: a real heading title and a real line number, so an agent doesn't have to mentally substitute.
- `DELETED` metadata is surfaced on every note-returning path, so trashed notes are always flagged regardless of which tool fetched them.
- The `delete_notebook` recovery hint is corrected.
- The installer's update-tools prompt now offers `restore_from_trash` on upgrade.

## Other Changes

A fair amount of internal restructuring lands alongside the features, mostly aimed at making the codebase easier to navigate and the tests less coupled to import-time state:

- **`NotebookResolver`** owns the notebook cache, path resolution, and invalidation in one place (previously scattered across the server module). Includes a thunk-bound factory so test patches of the joppy client propagate correctly (#38).
- **Config resolver** in `joplin_mcp.config` centralises config reads through a single entry point and drops the module-global `_module_config` shim. Test patches now propagate predictably.
- **Tool gating** deferred to `register_tools` so the runtime config (e.g. `--config-file`) takes effect at server start, rather than being frozen at decoration time (#40).
- **Note rendering** moved into `note_view`; the `get_note` display dispatch collapsed into the same module, keeping formatting out of the tool layer (#39, #43).
- **Search helpers** consolidated next to `find_notes` (#44).
- **Interactive config construction** moved to `ui_integration`, so the installer no longer reaches into server-time code (#48).
- **Delete-tool docstring asymmetry surfaced** — `delete_note` and `delete_notebook` explicitly state they're reversible (unlike `delete_tag`, which is permanent), and `delete_tag`'s description references the other two from its side. All three now document their missing-ID failure modes via a `Raises:` clause.
- **E2E suite for the notebook allowlist** (#27 by @rubalo), plus broader tightening of the existing e2e tests (#32, #33). `delete_note`'s soft-delete behaviour is asserted explicitly now (#34); `JoplinIdType` validation is exercised through the MCP `.run()` path (#37).
- **Opt-in e2e** via `--run-e2e`, so the unit suite stays fast by default and e2e only runs when you have a live Joplin instance to point at (#35).
- **Agent smoke tests** documented in `docs/agent-smoke-tests.md` for hand-driving an MCP-connected agent against the server: a broad first-time-user pass and a targeted allowlist-gating regression. The broad pass is what surfaced #49.

## New Contributors

- @MatthewOGoodman made their first contribution in #23
- @rubalo made their first contribution in #25
- @iclem made their first contribution in #28

**Full Changelog**: https://github.com/alondmnt/joplin-mcp/compare/v0.7.1...v0.8.0

---

# [v0.7.1](https://github.com/alondmnt/joplin-mcp/releases/tag/v0.7.1)
*Released on 2026-03-01T11:37:05Z*

## Fixes

- **Installer permission prompts** — `edit_note` is now correctly toggled by the Update permission, and `import_from_file` by the Write permission during interactive setup
- Remove redundant import tool note from README (already covered in Tool Permissions section)

**Full Changelog**: https://github.com/alondmnt/joplin-mcp/compare/v0.7.0...v0.7.1

---

# [v0.7.0](https://github.com/alondmnt/joplin-mcp/releases/tag/v0.7.0)
*Released on 2026-02-27T03:16:07Z*

## What's New

- **Sorting support for find functions** — `find_notes`, `find_notes_with_tag`, and `find_notes_in_notebook` now accept `order_by` (`title`, `created_time`, `updated_time`) and `order_dir` (`asc`, `desc`) parameters
- **Claude Code plugin** — Joplin orchestration skill for Claude Code with marketplace support

## Other Changes

- Remove dead code from `__init__.py`
- Reorganise README with Supported Clients section

**Full Changelog**: https://github.com/alondmnt/joplin-mcp/compare/v0.6.0...v0.7.0

---

# [v0.6.0](https://github.com/alondmnt/joplin-mcp/releases/tag/v0.6.0)
*Released on 2026-02-10T00:44:21Z*

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
*Released on 2026-01-30T14:16:03Z*

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
