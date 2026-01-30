# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Minimal OS deps (curl for healthcheck)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files (keep layers cache-friendly)
COPY pyproject.toml README.md ./
COPY src ./src

# Install package
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

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

# Healthcheck using the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${MCP_PORT}/health || exit 1

# Entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Switch to non-root user
USER appuser

ENTRYPOINT ["/entrypoint.sh"]
