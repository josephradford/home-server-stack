FROM python:3.12-slim

RUN pip install --no-cache-dir "workspace-mcp>=1.17"

EXPOSE 8000

# OAuth tokens and config persisted in /data
VOLUME /data

CMD ["workspace-mcp", "--transport", "streamable-http"]
