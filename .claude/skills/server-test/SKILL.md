---
name: server-test
description: >
  SSH into the home-server-stack test server, deploy a git branch, and run
  troubleshooting/diagnostic commands. Use this skill whenever the user wants
  to test changes on the server, troubleshoot a running service, check logs,
  inspect docker container health, validate configuration, or deploy a branch
  to the test server. Trigger on phrases like "test on server", "deploy to
  server", "check the server", "what's wrong on the server", "SSH in and...",
  "pull the branch on the server", "troubleshoot the stack", or any request
  that requires running commands on the remote home server.
---

# Server Test Skill

This skill connects to the home-server-stack test server via SSH, deploys the
relevant git branch, and runs diagnostic commands to test or troubleshoot the
stack.

## Step 1 — Load connection config

Read `.claude/server-test.local` in the project root. It must exist before
continuing. If it is missing, tell the user:

```
Config file not found: .claude/server-test.local

Create it from the template:
  cp .claude/server-test.local.example .claude/server-test.local
  # then edit with your SSH username and server IP
```

The file format (shell key=value, no export):
```
SERVER_USER=joe
SERVER_HOST=192.168.1.100
```

Parse it by reading the file. Extract `SERVER_USER` and `SERVER_HOST`.
If either is missing or still set to the placeholder values from the example,
stop and ask the user to fill in the real values.

## Step 2 — Determine the target branch

If the user specified a branch name in their request, use that.
Otherwise, run locally:
```bash
git branch --show-current
```
Use that branch name. Tell the user which branch you are about to deploy.

## Step 3 — Connect and deploy

SSH into the server and run all subsequent commands over that connection.
The stack lives at `~/home-server-stack` on the server.

```bash
ssh ${SERVER_USER}@${SERVER_HOST} "
  set -e
  cd ~/home-server-stack
  git fetch origin
  git checkout <branch>
  git pull origin <branch>
  echo '✓ Branch deployed'
"
```

If the checkout fails because the branch doesn't exist on the remote, tell
the user to push their branch first:
```
git push -u origin <branch>
```

## Step 4 — Run initial diagnostics

After a successful deploy, always run this baseline health check:

```bash
ssh ${SERVER_USER}@${SERVER_HOST} "cd ~/home-server-stack && make validate 2>&1; echo '---'; make status 2>&1"
```

Interpret the output:
- `make validate` — if it fails, the docker-compose config has a syntax error. Show the error.
- `make status` — look for containers that are not `Up` or are `Restarting`. Call them out explicitly.

## Step 5 — Investigate based on what you find

Use your judgment. Run follow-up commands based on what the diagnostics reveal.
Useful commands (run via ssh, cd ~/home-server-stack first):

**Logs:**
```bash
# Last 50 lines for a specific service (non-follow so it completes)
docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml logs --tail=50 <service>
# All services
docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml logs --tail=30
```

**Service state:**
```bash
docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml ps
docker ps -a  # shows exit codes and restart counts
```

**WireGuard (system service, not Docker):**
```bash
systemctl is-active wg-quick@wg0
sudo wg show
```

**SSL certificates:**
```bash
ls -la ~/home-server-stack/data/traefik/certs/
sudo certbot certificates 2>/dev/null | grep -A5 "Certificate Name"
```

**Disk / system:**
```bash
df -h ~
free -h
```

**Restart a specific container:**
```bash
docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml restart <service>
```

**Re-run setup script after config change:**
```bash
make start   # idempotent — safe to re-run
```

## Step 6 — Summarise and suggest next steps

After investigating, give the user:
1. A one-line status: **healthy / degraded / broken**
2. What you found (specific containers, errors, log lines)
3. What you did (if you ran any fix commands)
4. What the user should do next (if anything)

Keep the summary short. Paste relevant log lines rather than paraphrasing them.

## Tips for common failure modes

| Symptom | Likely cause | Check |
|---|---|---|
| Container keeps restarting | Bad env var, missing file, port conflict | `docker ps -a` (exit code) + service logs |
| 502 Bad Gateway in browser | Container not healthy or wrong port | `make status` + traefik logs |
| SSL cert warnings | Certs missing or expired | `data/traefik/certs/` + certbot |
| DNS not resolving | AdGuard not running or misconfigured | `make logs-adguard` (if it exists) or adguard container logs |
| WireGuard not routing | iptables rules missing after reboot | `make wireguard-test` |
| `make validate` fails | .env missing or compose syntax error | Check `.env` exists, then read the error |
