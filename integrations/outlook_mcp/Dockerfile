FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY outlook_mcp/requirements.txt /tmp/outlook_mcp-requirements.txt
RUN pip install --no-cache-dir -r /tmp/outlook_mcp-requirements.txt

COPY outlook_mcp/__init__.py outlook_mcp/__init__.py
COPY outlook_mcp/graph_session.py outlook_mcp/graph_session.py
COPY outlook_mcp/server.py outlook_mcp/server.py

ENV MCP_HTTP_PORT=8010
ENV MCP_HTTP_HOST=0.0.0.0
ENV MSAL_TOKEN_CACHE_PATH=/data/msal_token_cache.bin

EXPOSE 8010

CMD ["python", "-m", "outlook_mcp.server"]
