# MCP Server Design Patterns

Two architectural approaches to building MCP servers, from most constrained to most open.

## Overview

| Dimension | A: Granular tools | B: Code execution |
|---|---|---|
| **Analogy** | REST API, CLI, ORM | Stored procedures, REPL, raw SQL |
| **MCP design** | Many focused tools with typed schemas | One `execute_script` tool with embedded API |
| **Control flow** | Client/model orchestrates | Server-side execution environment |
| **Trust model** | Server constrains what's possible | Server trusts the caller |
| **Auditability** | Each call individually visible | Opaque; requires reading generated code |
| **Permissions** | Per-tool enable/disable | All-or-nothing |
| **Token efficiency** | O(N) inference passes | O(1) per workflow |
| **Latency** | Round-trip per call | Single round-trip |
| **Model requirements** | Menu selection; works with weak models | Must generate correct code |
| **Error handling** | Per-call; easy to retry | Script-level; harder to isolate failures |
| **Evolvability** | Add a tool, all clients benefit | Change the API, all scripts may break |
| **Flexibility** | Limited by tool catalogue; novel workflows require server changes | Arbitrary code; novel workflows work immediately |
| **Design cost** | Low per tool; grows with catalogue size | Low to build; high to secure |

As usage patterns emerge, A servers can add **batch tools** (e.g., `tag_notes(note_ids[], tag_name)`) to close the token/latency gap for common multi-item workflows. This preserves all of A's safety properties -typed schemas, per-tool permissions, per-item error reporting -while achieving O(1) inference passes for supported patterns. The tradeoff: you must anticipate which patterns to batch, and unsupported workflows still pay O(N).

## When to choose

**A:** Safety matters. Destructive or irreversible actions. Variable trust levels. Variable model capability. Predictable, well-defined workflows. Add batch tools when specific multi-item patterns are common enough to justify the maintenance cost of a growing tool catalogue.

**B:** Dynamic, unpredictable workflows. Long tail of operations too large to enumerate as tools. Rapid iteration -new workflows ship without server changes. Trusted callers. Strong code-generation models.

Neither is universally better. A optimises for safety at the cost of throughput and agility. B optimises for flexibility and speed at the cost of guardrails and auditability. Batch tools narrow the gap but can't close it -there will always be workflows only B can handle in a single pass. Equally, B can't match A's per-operation safety guarantees no matter how good the sandbox.

They're also complementary. A code-execution client needs well-designed granular functions to call -if MCP clients adopt code-execution natively, A's tools become the API that B consumes. And without the infrastructure security properties (credential isolation, API surface restriction), B offers little over a skill/prompt that teaches the agent the REST API directly. The MCP server layer is what justifies B's existence.

## Security

Both approaches share infrastructure-level advantages over direct agent-side code execution (i.e., a skill/prompt that teaches the agent to call the REST API directly):

- **Credential isolation**: API token stays server-side, never enters agent context
- **API surface restriction**: only curated endpoints are exposed, not the full REST API
- **Network segmentation**: agent doesn't need direct access to the service port

The delta between "no MCP" and "any MCP" is larger than the delta between A and B. Having a server at all is the biggest security win.

At the application level, A adds **per-tool permissions** and **typed input validation** on top. B accepts arbitrary code and must defend against it -prototype pollution, resource exhaustion, unintended method combinations. This is a real cost, but it's a different layer of defence than the infrastructure properties above.

## References

- [Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) -Anthropic Engineering
- [Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use) -Anthropic Engineering
- [belsar-ai/joplin-mcp](https://github.com/belsar-ai/joplin-mcp/) -example of approach B
- [alondmnt/joplin-mcp](https://github.com/alondmnt/joplin-mcp/) -example of approach A
