FROM python:3.12-slim

# System deps: git, curl, supervisor
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI (native installer → copy to system PATH for non-root access)
RUN curl -fsSL https://claude.ai/install.sh | bash && \
    cp /root/.local/bin/claude /usr/local/bin/claude

# Create non-root user
RUN useradd --system --create-home --uid 1000 --shell /bin/bash bede

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x scripts/entrypoint.sh scripts/briefing.sh \
    && chown -R bede:bede /app

USER bede

ENTRYPOINT ["scripts/entrypoint.sh"]
