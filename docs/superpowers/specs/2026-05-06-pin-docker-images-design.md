# Pin All Docker Images to Specific Versions

**Date:** 2026-05-06
**Issue:** #181

## Problem

Several Docker images use `:latest` or are untagged, making deploys non-deterministic. `make update` can silently pull breaking changes.

## Version Map

| Image | Current | Pin to |
|-------|---------|--------|
| `adguard/adguardhome` | `:latest` | `v0.107.74` |
| `alpine` | `:latest` | `3.22.4` |
| `n8nio/n8n` | `:latest` | `2.20.0` |
| `prom/prometheus` | `:latest` | `v3.11.3` |
| `grafana/grafana` | `:latest` | `12.4.3` |
| `prom/alertmanager` | `:latest` | `v0.32.1` |
| `prom/node-exporter` | `:latest` | `v1.11.1` |
| `gcr.io/cadvisor/cadvisor` | `v0.47.2` | `v0.56.2` |
| `traefik` | `v3.6.2` | `v3.6.16` |
| `crazymax/fail2ban` | `:latest` | `1.1.0` |
| `ghcr.io/gethomepage/homepage` | `:latest` | `v1.12.3` |
| `eclipse-mosquitto` | (no tag) | `2.1.2` |
| `owntracks/recorder` | (no tag) | `1.0.1` |
| `ghcr.io/astral-sh/uv` (bede) | `python3.12-bookworm-slim` | `0.11.10-python3.12-bookworm-slim` |
| `ghcr.io/josephradford/bede-*` | `:latest` | Keep `:latest` |

Conservative choices: Grafana stays on 12.x (skip 13.x major bump), Traefik stays on 3.6.x patch line.

## Files to Change

### home-server-stack

- `docker-compose.yml` — adguard, alpine, n8n
- `docker-compose.network.yml` — traefik, fail2ban
- `docker-compose.monitoring.yml` — prometheus, grafana, alertmanager, node-exporter, cadvisor
- `docker-compose.dashboard.yml` — homepage
- `docker-compose.location.yml` — mosquitto, owntracks

### bede repo

- `bede-data/Dockerfile` — uv base image
- `bede-data-mcp/Dockerfile` — uv base image
- `bede-workspace-mcp/Dockerfile` — uv base image
- `bede-core/Dockerfile` — uv base image

## Validation

1. `make validate` locally
2. Deploy to server and run `make status` + `make test-domain-access`
