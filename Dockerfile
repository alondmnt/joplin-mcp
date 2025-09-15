# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Minimal OS deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy project files (keep layers cache-friendly)
COPY pyproject.toml README.md ./
COPY src ./src

# Install package
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# Defaults for server transport
ENV MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    MCP_PATH=/mcp \
    MCP_LOG_LEVEL=info

# Mount point for config files (optional)
VOLUME ["/config"]

# HTTP/SSE/Streamable-HTTP default port
EXPOSE 8000

# Entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

