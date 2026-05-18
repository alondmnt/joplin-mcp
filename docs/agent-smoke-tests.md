# Agent smoke tests for joplin-mcp

Two prompts for hand-driving an agent against a running joplin-mcp server. Hand the prompt body to an agent that already has the joplin-mcp tools in its tool list.

## Note on tool availability

The joplin-mcp server exposes ~26 tools, of which ~18 are enabled by default. Each can be toggled per-server via the `tools` block in `joplin-mcp.json`. Off by default (destructive or context-heavy): `get_all_notes`, `delete_note`, `update_notebook`, `delete_notebook`, `update_tag`, `delete_tag`, `import_from_file`. Operators often re-enable some of these once they trust the workflow.

The agent should discover its actual tool list from the MCP capability handshake and skip any step that requires a tool it doesn't have — flag the gap in the report rather than failing the run.

## 1. Broad smoke test

First-time user perspective. Exercises the main tool surfaces and reports anything awkward, confusing, or leaky.

> You have access to the joplin-mcp server's tools. The server exposes a subset of ~26 tools depending on its config (defaults: ~19 enabled). Off by default are mostly destructive ops: `get_all_notes`, `delete_note`, `update_notebook`, `delete_notebook`, `update_tag`, `delete_tag`, `import_from_file`. Check your tool list before each step and skip any whose tool isn't exposed — note "skipped: `tool_name` not enabled" in the report. Your job is to smoke-test the MCP from a first-time user's perspective and report findings. You're not writing code; this is exploratory tool testing.
>
> ### Sandbox
>
> All test artefacts (notes, notebooks, tags) go under a top-level notebook `MCP-test`. **Don't create test artefacts in the operator's real notebooks.** Read-only steps (discovery, reading, search) can observe the real workspace freely; only writes are scoped to the sandbox.
>
> Before starting the write steps, check that `MCP-test` exists. If it doesn't and `create_notebook` is exposed, create it (top-level, no parent). If `create_notebook` is disabled, skip every write step and note the gap in the report.
>
> Leave `MCP-test` in place at the end. The operator decides when to clean it up wholesale.
>
> ### Coverage
>
> Hit each area with a representative call (not exhaustive). If a tool you'd want to call is not in your tool list, skip the step.
>
> 1. **Discovery** — list notebooks; list tags; pick a notebook that has notes; list notes in it.
> 2. **Reading** — get a note's full content; extract a section by heading; get a line range; check pagination on a multi-page `find_notes` result. If `find_in_note` is exposed, try a regex search inside one note.
> 3. **Search** — plain text query; `tag:` filter; `notebook:` filter; a date filter (e.g. updated in the last week); a query you expect to return nothing.
> 4. **Write (notes)** — create a note inside `MCP-test` (title prefixed `MCP-test-` for cleanup); update it (body, then title, then tags). If `edit_note` is exposed, try one fine-grained edit (find/replace or append). **If `delete_note` is exposed**: delete it, verify it's in trash, restore from trash, delete again. **If `delete_note` is NOT exposed**: leave the test note inside `MCP-test` and note the title at the end of your report.
> 5. **Write (notebooks)** — create a notebook (`MCP-test-nb-...`) as a child of `MCP-test`; delete it if `delete_notebook` is exposed (otherwise leave it under `MCP-test` and note the name).
> 6. **Tag ops** — create a tag (`MCP-test-tag`); tag the test note from step 4 with it; untag it; delete the tag if `delete_tag` is exposed.
> 7. **Import** — if `import_from_file` is exposed, probe it lightly (read its schema and report what input shape it expects; don't actually import unless you have a known-safe test file).
> 8. **Error surfaces** — try an invalid note ID (all zeros); try a notebook ID that doesn't exist; try a clearly-malformed input on one or two tools (e.g. `start_line=-1`).
>
> If the server is configured with a notebook allowlist you may hit `Notebook not accessible` errors. Note them as you find them — they're expected. Don't try to bypass.
>
> ### Report
>
> For each tool you call, one line:
> - tool name, one-sentence summary of what you passed, one-sentence summary of what came back, and a tag — `ok` / `surprising` / `confusing` / `leak` (the last if a response or error message revealed data you didn't expect — like notebook titles you shouldn't see, raw IDs in user-facing text, or stack-trace fragments).
>
> Then a closing summary, under 200 words:
> - Tools with good shape (helpful errors, predictable schemas, sensible defaults).
> - Tools that felt awkward (confusing parameters, misleading docs, unexpected outputs).
> - Any `leak` findings, with the exact tool and message.
> - Any tool whose response didn't match its description.
> - **Cleanup state**: list every `MCP-test-*` artefact you left under `MCP-test` (because delete was disabled or because a step skipped). The `MCP-test` parent itself stays.
>
> ### Don't
>
> - Don't pad the report with full note bodies — summarise.
> - Don't try to exhaust every parameter combination.
> - Don't write code or commits.
> - Don't try to break the server beyond step 7's tame inputs.
>
> Aim for breadth over depth. One solid call per tool surface; expect 15–25 tool calls total.

## 2. Targeted: allowlist gating regression

End-to-end regression coverage for the notebook allowlist work landed in the config resolver epic. Exercises the three allowlist states across the tool surface and checks that error messages don't leak denied notebook titles. The operator drives the config swaps; the agent runs the same checklist three times.

### Sandbox structure (used by all three scenarios)

The test runs against a disposable sandbox, not the operator's real notebooks:

- `MCP-test/` (top-level)
  - `MCP-test/allowed/` — one stub note
  - `MCP-test/denied/` — one stub note

The sandbox lives in Joplin's database and persists across the three server restarts.

**Provisioning:** the agent creates the sandbox at the start of scenario A if it doesn't already exist (the agent has `create_notebook` and `create_note` enabled — the prompt below tells it to do this). If `create_notebook` happens to be disabled, the operator provisions the sandbox manually before triggering scenario A.

**Cleanup:** scenario C cannot clean up the sandbox itself — under deny-all, `list_notebooks` returns empty and `delete_notebook` has no IDs to act on. The agent should NOT bypass the allowlist to obtain IDs (that would test a different surface than the gating). Two clean options:

1. After scenario C completes, the operator restores an unrestricted config (`notebook_allowlist: null` or field omitted), restarts the server, and either re-triggers a brief cleanup pass or deletes `MCP-test` manually in the Joplin UI.
2. Move the cleanup step to the end of scenario A or B (whichever runs last in your campaign ordering), where the allowlist still permits the sandbox.

If `delete_notebook` is disabled in any of these states, the agent lists the artefacts and the operator deletes manually.

### Operator: run three times with these configs

Write each config to `joplin-mcp.json` (or whatever path you serve via `--config-file`) and restart the MCP server between scenarios. The agent prompt below stays the same across all three; the agent should be told which scenario it's in.

**Scenario A — no allowlist** (`notebook_allowlist` field omitted, or `null`):

```json
{ "token": "...", "host": "127.0.0.1", "port": 41184 }
```

**Scenario B — restricted allowlist:**

```json
{ "token": "...", "host": "127.0.0.1", "port": 41184,
  "notebook_allowlist": ["MCP-test/allowed", "MCP-test/allowed/**"] }
```

**Scenario C — empty allowlist (deny-all):**

```json
{ "token": "...", "host": "127.0.0.1", "port": 41184,
  "notebook_allowlist": [] }
```

### Agent prompt

> You have access to the joplin-mcp server's tools. The server is currently configured in one of three allowlist modes (the operator will tell you which: **A** = no allowlist, **B** = `["MCP-test/allowed", "MCP-test/allowed/**"]`, **C** = `[]`). Your job is to exercise the same checklist in each mode and report whether the allowlist gating behaves correctly.
>
> ### Sandbox
>
> The test uses a disposable sandbox: top-level notebook `MCP-test` with two children `MCP-test/allowed` and `MCP-test/denied`, each containing one stub note. **Don't touch the operator's real notebooks** — read/write only against the sandbox.
>
> If you're running scenario A and the sandbox doesn't exist yet, you're authorised to create it before starting the checklist:
> - create `MCP-test` (top-level, no parent)
> - create `MCP-test/allowed` (parent: `MCP-test`)
> - create `MCP-test/denied` (parent: `MCP-test`)
> - create one stub note in each of `allowed` and `denied` (any title/body, e.g. title `"seed"`, body `"sandbox stub"`)
>
> If `create_notebook` is not exposed in your tool list, stop and ask the operator to provision the sandbox manually.
>
> If you're running scenario B or C, the sandbox should already exist from scenario A; if it doesn't, stop and tell the operator.
>
> At the end of scenario C, delete `MCP-test` (cascade-deletes children and stub notes). If `delete_notebook` isn't exposed, list the artefacts for manual cleanup.
>
> ### Checklist (run all in every mode)
>
> Before starting, check your tool list. If `delete_note` is not exposed in this config, you cannot clean up notes you create — leave them in place and list them in the report so the operator can delete manually.
>
> 1. **List notebooks** (`list_notebooks` or equivalent). Note which appear; specifically whether `MCP-test/allowed` and `MCP-test/denied` are present.
> 2. **Get a note in `MCP-test/allowed`** (find one with `find_notes_in_notebook`, then `get_note` it).
> 3. **Get a note in `MCP-test/denied`** (same shape).
> 4. **Create a note in `MCP-test/allowed`** (`MCP-test-{scenario}-allowed-create`). If `delete_note` is exposed and the create succeeded, delete it at the end of the run.
> 5. **Create a note in `MCP-test/denied`** (`MCP-test-{scenario}-denied-create`). If `delete_note` is exposed and the create succeeded, delete it at the end.
> 6. **Search**: `find_notes("MCP-test")` — note what appears.
> 7. **Search by tag** if any tags exist on notes in either sandbox notebook.
> 8. **Resolution leak probe** (critical for scenario C): try `create_note(notebook_name="denyed", body="x", title="leak-probe")` — a typo of `denied`. The error message must NOT mention `denied` or any other real notebook title. (This call should fail before any note is actually created, so there's nothing to clean up regardless of `delete_note` availability.)
>
> ### Expected behaviour
>
> | step | A (no allowlist) | B (`["MCP-test/allowed", "MCP-test/allowed/**"]`) | C (`[]` deny-all) |
> |---|---|---|---|
> | 1 list_notebooks | all notebooks (incl. both sandbox children) | only `MCP-test/allowed`. The structural parent `MCP-test` is filtered too: `get_accessible_map` keeps ancestors for internal path resolution, but the user-facing `filter_accessible_notebooks` checks each notebook on its own merits — `MCP-test`'s path doesn't match the allowlist patterns. | empty list |
> | 2 get note in `MCP-test/allowed` | ok | ok | refusal (see step 3) |
> | 3 get note in `MCP-test/denied` | ok | refusal. EITHER `Notebook not accessible` (if caller passed the note's ID directly, hitting `validate_notebook_access`) OR `Notebook 'denied' not found in path 'MCP-test/denied'` (if caller passed the name, hitting `resolve_by_path` first). Both close the door; the latter is more private (doesn't confirm existence). The user's own input may appear in the error message — that's an echo, not a leak. | same refusal pattern as B |
> | 4 create in `MCP-test/allowed` | ok | ok | refusal (see step 5) |
> | 5 create in `MCP-test/denied` | ok | refusal, same shape as step 3 (typically `not found in path` since `create_note` resolves by name) | same refusal pattern as B |
> | 6 find_notes | works across all | works but results filtered to allowlisted notebooks | empty results |
> | 7 find by tag | works | results filtered to allowlisted notebooks | empty results |
> | 8 leak probe (`denyed` typo) | `not found`, with EITHER no suggestion OR a suggestion of `denied` (the resolver's fuzzy-matcher may or may not consider `denyed → denied` close enough; both are valid). Never any other notebook title. | `not found` with suggestions, if any, drawn only from allowlisted names (e.g. `allowed`); `denied` MUST NOT appear | `not found` with **no suggestions** mentioning `denied` or any other notebook title |
>
> ### Report
>
> For each step in each scenario, one line: step number, expected outcome (from the table), actual outcome, and a tag — `match` / `mismatch` / `leak` (the last if a denied notebook title appears in any user-facing message).
>
> Closing summary (under 200 words):
>
> - Any `mismatch` — where actual diverged from expected.
> - Any `leak` — with the exact step, scenario, tool name, and the offending substring of the error message.
> - Whether error messages in scenarios B and C were consistent (same generic `Notebook not accessible` text, not leaking which mode produced them).
> - **Cleanup state**: list every `MCP-test-*` artefact left behind (because `delete_note` was disabled, because a create succeeded in a denied notebook unexpectedly, or because a step was skipped). The operator will sweep them up.
>
> ### Don't
>
> - Don't try to bypass the allowlist by passing notebook IDs instead of names if a name fails — that's a different test surface.
> - Don't create dozens of probes — one of each per scenario is enough.
> - Don't write code.
