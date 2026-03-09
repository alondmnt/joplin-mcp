# Joplin MCP — Project Context

## Architecture

This project is a **Model Context Protocol (MCP) server** that exposes Joplin notes to AI clients
(Ollama, Claude, ClawBot, etc.) via HTTP/SSE.

### Full Docker stack

```
┌──────────────┐        ┌──────────────────┐        ┌──────────────────┐
│   AI Client  │──MCP──▶│   joplin-mcp     │──HTTP──▶│ joplin-data-api  │
│ (port 8000)  │        │   :8000          │        │ :41185 (headless)│
└──────────────┘        └──────────────────┘        └────────┬─────────┘
                                                             │ syncs
                                                    ┌────────▼─────────┐
                                                    │  joplin-server   │
                                                    │  :8082           │
                                                    └────────┬─────────┘
                                                             │ stores
                                                    ┌────────▼─────────┐
                                                    │   postgres :5432 │
                                                    └──────────────────┘
```

- **joplin-data-api** (`rickonono3/joplin-terminal-data-api`) — runs the Joplin CLI headlessly,
  syncs with `joplin-server`, and exposes the Data API on port 41185 with auto-token injection.
- **joplin-mcp** connects to `joplin-data-api:41185` inside the Docker network.
- **AI clients** connect to `http://localhost:8000/mcp`.

## First-run token setup

`joplin-data-api` auto-generates a Joplin API token on first launch. Retrieve it once and add it
to `.env`:

```bash
docker exec joplin-data-api cat /root/joplin/profile/settings.json | grep token
# then set JOPLIN_TOKEN=<value> in .env and restart joplin-mcp:
docker compose restart joplin-mcp
```

## Key environment variables

| Variable | Default | Description |
|---|---|---|
| `JOPLIN_TOKEN` | *(required)* | Joplin Data API token |
| `JOPLIN_HOST` | `joplin-data-api` | Internal Docker service name |
| `JOPLIN_PORT` | `41185` | joplin-data-api port |
| `MCP_PORT` | `8000` | External MCP HTTP port |
| `MCP_TRANSPORT` | `http` | `http`, `sse`, or `stdio` |

## Source layout

- `src/joplin_mcp/` — Python package (FastMCP server)
- `docker/entrypoint.sh` — container startup logic
- `Dockerfile` — image build
- `docker-compose.yml` — full stack (db + joplin-server + joplin-data-api + joplin-mcp)
- `.env.example` — copy to `.env` and fill in secrets

## Connecting an AI client

Point your MCP client at `http://localhost:8000/mcp` (HTTP/SSE transport).
For Claude Code: add to `~/.claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "joplin": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```
