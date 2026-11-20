FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install package and optional HTTP runtime dependency for Streamable HTTP fallback paths.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY docs ./docs

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[http]"

# Localhost-by-default posture for Streamable HTTP; override host/port/path via env/args for container networking.
ENV MCP_TRANSPORT=streamable-http \
    MCP_HTTP_HOST=0.0.0.0 \
    MCP_HTTP_PORT=8000 \
    MCP_HTTP_PATH=/mcp \
    LOG_LEVEL=INFO

EXPOSE 8000

# Default: serve over Streamable HTTP. Place behind TLS/reverse-proxy auth and origin protections in production.
ENTRYPOINT ["medium-mcp-server"]
CMD ["serve", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000", "--path", "/mcp"]
