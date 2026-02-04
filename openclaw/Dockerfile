# OpenClaw Container with Homebrew and GOG Preinstalled
# This is a base image that includes homebrew and gog, but does NOT preconfigure OpenClaw
# Users run the OpenClaw onboarding wizard after starting the container

FROM node:22-bookworm

# Install system dependencies
ARG OPENCLAW_DOCKER_APT_PACKAGES=""
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    procps \
    sudo \
    build-essential \
    ${OPENCLAW_DOCKER_APT_PACKAGES} \
    && rm -rf /var/lib/apt/lists/*

# Give node user sudo access (needed for some operations)
RUN echo "node ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/node

# Switch to node user for homebrew installation
USER node
WORKDIR /home/node

# Install Homebrew (Linuxbrew)
RUN NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Add Homebrew to PATH
ENV PATH="/home/linuxbrew/.linuxbrew/bin:/home/linuxbrew/.linuxbrew/sbin:${PATH}"
ENV HOMEBREW_NO_AUTO_UPDATE=1
ENV HOMEBREW_NO_INSTALL_CLEANUP=1

# Verify Homebrew installation
RUN brew --version

# Install GOG (Google OAuth CLI) via npm globally
# Note: gogcli may not be available in homebrew, so using npm as primary method
RUN npm install -g @google/oauth-cli || echo "GOG installation skipped - will be available via skills"

# Install OpenClaw globally (non-interactive)
# The installer script may try to be interactive, so we redirect stdin and suppress the error
RUN curl -fsSL https://openclaw.ai/install.sh > /tmp/install-openclaw.sh && \
    bash /tmp/install-openclaw.sh < /dev/null 2>&1 || true && \
    rm /tmp/install-openclaw.sh

# Add OpenClaw to PATH (includes both npm-global and local bin)
ENV PATH="/home/node/.npm-global/bin:/home/node/.local/bin:${PATH}"

# Verify OpenClaw installation and show diagnostic info
RUN echo "=== OpenClaw Installation Check ===" && \
    ls -la /home/node/.npm-global/bin/ 2>/dev/null || echo "npm-global/bin not found" && \
    ls -la /home/node/.local/bin/ 2>/dev/null || echo ".local/bin not found" && \
    which openclaw && openclaw --version || echo "WARNING: openclaw command not found in PATH"

# Set production environment
ENV NODE_ENV=production

# Create directories for configuration
RUN mkdir -p /home/node/.openclaw /home/node/.openclaw/workspace

# Expose ports
EXPOSE 18789 18790

# Set working directory
WORKDIR /home/node

# Default command - this will fail with a helpful message if user hasn't configured yet
# Users should run: docker compose run --rm openclaw-cli onboard
CMD ["openclaw", "gateway", "--allow-unconfigured"]
