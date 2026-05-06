# bede-browser-mcp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a browser-mcp sidecar container to the Bede stack, giving bede-core headless Chromium browser access via the `@anthropic-ai/mcp-remote` proxy to `@playwright/mcp`.

**Architecture:** Lightweight Node.js container running `@playwright/mcp` in `--headless` mode on port 8004, exposed as a streamable-http MCP server. bede-core connects to it via `mcp.json` like the other MCP sidecars. No Traefik routing needed — internal-only on the Docker network.

**Tech Stack:** Node.js 22, `@playwright/mcp`, Playwright Chromium, Docker

**Repos:**
- **bede** (`/Users/joeradford/dev/bede`) — bede-browser-mcp source code, Dockerfile, CI workflow, mcp.json update
- **home-server-stack** (`/Users/joeradford/dev/home-server-stack`) — compose wiring, Makefile, homepage, SERVICES.md

**Pattern:** Follows bede-workspace-mcp sidecar pattern (port 8003) — browser-mcp is port 8004.

---

## File Structure

### bede repo (`/Users/joeradford/dev/bede`)

```
bede-browser-mcp/
├── Dockerfile              # node:22-slim + playwright chromium install
├── package.json            # @playwright/mcp dependency
├── package-lock.json       # lockfile (generated)
└── server.js               # thin wrapper: start @playwright/mcp on configured port

bede-core/
└── mcp.json                # Modified: add browser MCP server entry

.github/workflows/
└── bede-browser-mcp-ci.yml # build → push GHCR image
```

### home-server-stack repo (`/Users/joeradford/dev/home-server-stack`)

```
docker-compose.ai.yml                   # Add bede-browser-mcp service
config/homepage/services-template.yaml  # Add bede-browser-mcp entry
SERVICES.md                             # Document bede-browser-mcp
Makefile                                # Add to bede-pull target
```

---

### Task 1: Project Scaffold (bede repo)

**Files:**
- Create: `/Users/joeradford/dev/bede/bede-browser-mcp/package.json`
- Create: `/Users/joeradford/dev/bede/bede-browser-mcp/server.js`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "bede-browser-mcp",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "dependencies": {
    "@playwright/mcp": "^0.1.0"
  },
  "scripts": {
    "start": "node server.js"
  }
}
```

Note: Check the latest `@playwright/mcp` version on npm before pinning. The package provides the MCP server binary and Playwright browser automation.

- [ ] **Step 2: Create server.js**

Thin wrapper that starts `@playwright/mcp` as a streamable-http server on the configured port:

```js
import { createServer } from "@playwright/mcp";

const port = parseInt(process.env.BROWSER_MCP_PORT || "8004", 10);

const server = createServer({
  headless: true,
  transport: "streamable-http",
});

server.listen(port, () => {
  console.log(`browser-mcp listening on port ${port}`);
});
```

Note: The exact API of `@playwright/mcp` should be verified at implementation time — the package may expose a CLI binary (`npx @playwright/mcp --port 8004`) instead of a programmatic API. Check the README and adapt: if CLI-only, use that in the Dockerfile CMD instead.

- [ ] **Step 3: Install dependencies and generate lockfile**

Run: `cd /Users/joeradford/dev/bede/bede-browser-mcp && npm install`
Expected: `node_modules/` created, `package-lock.json` generated.

- [ ] **Step 4: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-browser-mcp/package.json bede-browser-mcp/package-lock.json bede-browser-mcp/server.js
git commit -m "feat(bede-browser-mcp): project scaffold with @playwright/mcp"
```

---

### Task 2: Dockerfile (bede repo)

**Files:**
- Create: `/Users/joeradford/dev/bede/bede-browser-mcp/Dockerfile`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM node:22-slim

RUN apt-get update && \
    npx playwright install --with-deps chromium && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY server.js ./

RUN useradd --create-home --uid 1000 bede
USER bede

EXPOSE 8004

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD node -e "const http = require('http'); const r = http.get('http://127.0.0.1:8004/mcp', res => { process.exit(res.statusCode < 500 ? 0 : 1) }); r.on('error', () => process.exit(1))"

CMD ["node", "server.js"]
```

Note: Playwright needs Chromium system dependencies — `npx playwright install --with-deps chromium` handles this on Debian-based images. The `node:22-slim` base (Debian bookworm) is required; Alpine won't work with Playwright's Chromium. If `@playwright/mcp` provides a CLI entry point, replace CMD with: `CMD ["npx", "@playwright/mcp", "--headless", "--port", "8004", "--transport", "streamable-http"]`

- [ ] **Step 2: Build and verify locally**

Run: `cd /Users/joeradford/dev/bede && docker build -t bede-browser-mcp:test bede-browser-mcp/`
Expected: Image builds successfully. Will be larger than other sidecars (~500MB+) due to Chromium.

Run: `docker run --rm -p 8004:8004 bede-browser-mcp:test &` then check the health endpoint.
Expected: Server starts on port 8004. Then kill the container.

- [ ] **Step 3: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-browser-mcp/Dockerfile
git commit -m "feat(bede-browser-mcp): Dockerfile with Playwright Chromium"
```

---

### Task 3: CI/CD Workflow (bede repo)

**Files:**
- Create: `/Users/joeradford/dev/bede/.github/workflows/bede-browser-mcp-ci.yml`

- [ ] **Step 1: Create the workflow file**

Follow the bede-workspace-mcp-ci.yml pattern:

```yaml
name: bede-browser-mcp CI

on:
  workflow_dispatch:
  pull_request:
    paths:
      - "bede-browser-mcp/**"
  push:
    branches: [main]
    paths:
      - "bede-browser-mcp/**"

defaults:
  run:
    working-directory: bede-browser-mcp

jobs:
  build-push:
    if: (github.event_name == 'push' || github.event_name == 'workflow_dispatch') && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/setup-buildx-action@v3

      - uses: docker/build-push-action@v6
        with:
          context: ./bede-browser-mcp
          push: true
          platforms: linux/amd64
          tags: |
            ghcr.io/josephradford/bede-browser-mcp:latest
            ghcr.io/josephradford/bede-browser-mcp:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

- [ ] **Step 2: Commit**

```bash
cd /Users/joeradford/dev/bede
git add .github/workflows/bede-browser-mcp-ci.yml
git commit -m "ci(bede-browser-mcp): add build and push workflow"
```

---

### Task 4: Update bede-core mcp.json (bede repo)

**Files:**
- Modify: `/Users/joeradford/dev/bede/bede-core/mcp.json`

- [ ] **Step 1: Add browser MCP server entry**

Add after the `google-workspace` entry:

```json
{
  "mcpServers": {
    "personal-data": {
      "type": "http",
      "url": "http://bede-data-mcp:8002/mcp"
    },
    "google-workspace": {
      "type": "http",
      "url": "http://bede-workspace-mcp:8003/mcp"
    },
    "browser": {
      "type": "http",
      "url": "http://bede-browser-mcp:8004/mcp"
    }
  }
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-core/mcp.json
git commit -m "feat(bede-core): add browser MCP server to mcp.json"
```

---

### Task 5: Create PR in bede repo

**Files:** None (git operations only)

- [ ] **Step 1: Push and create PR**

```bash
cd /Users/joeradford/dev/bede
git push -u origin HEAD
gh pr create --title "feat: add bede-browser-mcp sidecar" --body "$(cat <<'EOF'
## Summary
- Add bede-browser-mcp: headless Chromium browser access via @playwright/mcp
- Node.js container running on port 8004, exposed as streamable-http MCP server
- bede-core connects via mcp.json (same pattern as data-mcp and workspace-mcp)
- GitHub Actions CI: build and push GHCR image on merge

## Test plan
- [ ] Docker image builds: `docker build -t test bede-browser-mcp/`
- [ ] Container starts and healthcheck passes
- [ ] CI builds successfully on this PR
- [ ] After merge: GHCR image published, set visibility to public
- [ ] After deploy: bede-core can use browser tools

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2: Merge the PR**

Wait for CI to pass, then merge. Wait for the GHCR image build to complete before deploying.

- [ ] **Step 3: Set GHCR package visibility to public**

Navigate to: `https://github.com/users/josephradford/packages/container/bede-browser-mcp/settings`
→ Danger Zone → Change visibility → Public

---

### Task 6: Docker Compose Wiring (home-server-stack repo)

**Files:**
- Modify: `/Users/joeradford/dev/home-server-stack/docker-compose.ai.yml`

- [ ] **Step 1: Add bede-browser-mcp service**

Add after `bede-workspace-mcp` and before `bede-core`:

```yaml
  bede-browser-mcp:
    image: ghcr.io/josephradford/bede-browser-mcp:latest
    container_name: bede-browser-mcp
    restart: unless-stopped
    environment:
      - BROWSER_MCP_PORT=8004
    networks:
      - homeserver
    healthcheck:
      test: ["CMD", "node", "-e", "const http = require('http'); const r = http.get('http://127.0.0.1:8004/mcp', res => { process.exit(res.statusCode < 500 ? 0 : 1) }); r.on('error', () => process.exit(1))"]
      interval: 30s
      timeout: 5s
      retries: 3
```

No Traefik labels — this is internal-only, accessed by bede-core over the Docker network.

- [ ] **Step 2: Add to bede-core depends_on**

Add `bede-browser-mcp` to bede-core's `depends_on`:

```yaml
  bede-core:
    depends_on:
      bede-data:
        condition: service_healthy
      bede-data-mcp:
        condition: service_healthy
      bede-workspace-mcp:
        condition: service_healthy
      bede-browser-mcp:
        condition: service_healthy
```

- [ ] **Step 3: Validate compose config**

Run: `cd /Users/joeradford/dev/home-server-stack && make validate`
Expected: PASS — config is valid.

- [ ] **Step 4: Commit**

```bash
cd /Users/joeradford/dev/home-server-stack
git add docker-compose.ai.yml
git commit -m "feat: add bede-browser-mcp to docker compose"
```

---

### Task 7: Makefile — Add to bede-pull (home-server-stack repo)

**Files:**
- Modify: `/Users/joeradford/dev/home-server-stack/Makefile`

- [ ] **Step 1: Add bede-browser-mcp image to bede-pull target**

Add after the `bede-web` pull line:

```makefile
	@docker pull ghcr.io/josephradford/bede-browser-mcp:latest
```

The full target should read:

```makefile
bede-pull: env-check
	@echo "Pulling Bede images..."
	@docker pull ghcr.io/josephradford/bede:latest
	@docker pull ghcr.io/josephradford/bede-data:latest
	@docker pull ghcr.io/josephradford/bede-data-mcp:latest
	@docker pull ghcr.io/josephradford/bede-core:latest
	@docker pull ghcr.io/josephradford/bede-workspace-mcp:latest
	@docker pull ghcr.io/josephradford/bede-web:latest
	@docker pull ghcr.io/josephradford/bede-browser-mcp:latest
	@echo "✓ Bede images pulled"
```

- [ ] **Step 2: Commit**

```bash
cd /Users/joeradford/dev/home-server-stack
git add Makefile
git commit -m "chore: add bede-browser-mcp to bede-pull target"
```

---

### Task 8: Homepage Dashboard (home-server-stack repo)

**Files:**
- Modify: `/Users/joeradford/dev/home-server-stack/config/homepage/services-template.yaml`

- [ ] **Step 1: Add bede-browser-mcp to AI Services section**

Add after the Bede Web entry:

```yaml
      - Bede Browser MCP:
          icon: mdi-web
          href: ""
          description: Headless browser access for Bede (internal MCP)
          container: bede-browser-mcp
          server: my-docker
          showStats: true
```

- [ ] **Step 2: Commit**

```bash
cd /Users/joeradford/dev/home-server-stack
git add config/homepage/services-template.yaml
git commit -m "feat: add bede-browser-mcp to homepage dashboard"
```

---

### Task 9: Update SERVICES.md (home-server-stack repo)

**Files:**
- Modify: `/Users/joeradford/dev/home-server-stack/SERVICES.md`

- [ ] **Step 1: Add bede-browser-mcp service documentation**

Add after the `bede-web` entry in the AI Services section:

```markdown
#### bede-browser-mcp
- **Purpose:** Headless Chromium browser access for bede-core via MCP — enables web browsing, screenshot capture, and page interaction
- **Access:** Internal only (no Traefik routing) — bede-core connects via `http://bede-browser-mcp:8004/mcp`
- **Image:** `ghcr.io/josephradford/bede-browser-mcp:latest`
- **Port:** 8004
- **Depends on:** None (standalone sidecar)
```

- [ ] **Step 2: Commit**

```bash
cd /Users/joeradford/dev/home-server-stack
git add SERVICES.md
git commit -m "docs: add bede-browser-mcp to SERVICES.md"
```

---

### Task 10: Validate and Create PR (home-server-stack repo)

**Files:** None (validation and git operations only)

- [ ] **Step 1: Run full validation**

Run: `cd /Users/joeradford/dev/home-server-stack && make validate`
Expected: PASS.

- [ ] **Step 2: Push and create PR**

```bash
cd /Users/joeradford/dev/home-server-stack
git push -u origin HEAD
gh pr create --title "feat: wire bede-browser-mcp into docker compose" --body "$(cat <<'EOF'
## Summary
- Add bede-browser-mcp service to docker-compose.ai.yml (internal-only, no Traefik routing)
- Add bede-browser-mcp as dependency of bede-core
- Add to bede-pull Makefile target
- Add to homepage dashboard
- Document in SERVICES.md

## Context
Companion to josephradford/bede PR adding bede-browser-mcp. The container runs @playwright/mcp with headless Chromium on port 8004, giving bede-core web browsing capabilities via MCP tools. After both PRs are merged and the GHCR image is built, deploy with `make bede-pull && make bede-restart`.

## Test plan
- [ ] `make validate` passes
- [ ] After deploy: `make bede-status` shows bede-browser-mcp healthy
- [ ] bede-core can reach browser MCP tools
- [ ] Homepage shows bede-browser-mcp container status

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Post-Deployment Verification

After both PRs are merged, the GHCR image is built, and the server is updated (`make bede-pull && make bede-restart`):

1. **Container health:** `make bede-status` — bede-browser-mcp should show healthy.
2. **MCP connectivity:** bede-core should list browser tools when queried.
3. **Browser tools work:** Ask Bede to navigate to a URL and take a screenshot as a smoke test.
4. **Image size:** Expect ~500MB+ due to Chromium — monitor disk usage on the server.
5. **GHCR visibility:** If `docker pull` fails with 403, set the package to public at `https://github.com/users/josephradford/packages/container/bede-browser-mcp/settings`.

## Sidecar Port Registry

| Container | Port | Protocol |
|-----------|------|----------|
| bede-data | 8001 | HTTP REST |
| bede-data-mcp | 8002 | MCP (streamable-http) |
| bede-workspace-mcp | 8003 | MCP (streamable-http) |
| bede-browser-mcp | 8004 | MCP (streamable-http) |
