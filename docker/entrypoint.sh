#!/usr/bin/env sh
set -eu

# If a custom command is provided, run it as-is
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

# If a config file is mounted and env not set, prefer it
if [ -z "${JOPLIN_MCP_CONFIG:-}" ] && [ -f "/config/joplin-mcp.json" ]; then
  export JOPLIN_MCP_CONFIG="/config/joplin-mcp.json"
fi

transport="${MCP_TRANSPORT:-http}"

# Optional flags
CONFIG_OPT=""
if [ -n "${JOPLIN_MCP_CONFIG:-}" ]; then
  CONFIG_OPT="--config ${JOPLIN_MCP_CONFIG}"
fi

LOG_OPT=""
if [ -n "${MCP_LOG_LEVEL:-}" ]; then
  LOG_OPT="--log-level ${MCP_LOG_LEVEL}"
fi

if [ "$transport" = "stdio" ]; then
  # STDIO mode (no host/port/path)
  exec joplin-mcp-server --transport stdio ${LOG_OPT} ${CONFIG_OPT}
else
  host="${MCP_HOST:-0.0.0.0}"
  port="${MCP_PORT:-8000}"
  path="${MCP_PATH:-/mcp}"
  exec joplin-mcp-server --transport "$transport" --host "$host" --port "$port" --path "$path" ${LOG_OPT} ${CONFIG_OPT}
fi

