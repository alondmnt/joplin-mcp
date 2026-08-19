# CLAUDE.md — joplin-mcp

## Environment

- **Conda env:** `joplin-mcp` (`/Users/alondmnt/miniforge3/envs/joplin-mcp/bin/python`, Python 3.11)
- **Run tests:** `/Users/alondmnt/miniforge3/envs/joplin-mcp/bin/python -m pytest tests/ -v` (skips `tests/e2e/` by default)
- **Run a single test file:** `/Users/alondmnt/miniforge3/envs/joplin-mcp/bin/python -m pytest tests/test_config.py -v`
- **Run e2e tests (opt-in):** `JOPLIN_TOKEN=<token> /Users/alondmnt/miniforge3/envs/joplin-mcp/bin/python -m pytest tests/e2e --run-e2e -v` — mutates real notes/notebooks/tags on the local Joplin instance, so don't run routinely. Run before releases, or when changes touch code paths the unit tests don't exercise (notebook allowlist filtering, search/FTS, joppy client interactions).

## Project

- MCP server for Joplin note-taking app
- Source: `src/joplin_mcp/`
- Tests: `tests/`
- Config: `pyproject.toml`

## Design

- Extend existing interfaces before adding new tools. In an MCP context the LLM evaluates all available tools on every action — more tools = more decision points = more confusion. A separate `bulk_tag_notes` alongside `tag_note` forces the agent to choose between two tools for the same action
- Prefer adding parameters to existing tools over creating new tools (e.g., `notebook_name` on `update_note` instead of `move_note`, `trash=True` on `find_notes` instead of `list_trash`)
- For bulk operations, prefer extending single-item tools to accept lists (`str | List[str]`) over separate bulk tools
- Convention: notebooks referenced by name/path, notes by ID (matches `create_note`)
- All tools go through the Joplin REST API — avoid tools that touch the filesystem directly or run subprocesses
- When discoverability is a concern (e.g., `find_notes(trash=True)`), teach the LLM the pattern via docstrings and return messages from related tools
