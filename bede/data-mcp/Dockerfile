FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8000

CMD ["uv", "run", "python", "server.py"]
