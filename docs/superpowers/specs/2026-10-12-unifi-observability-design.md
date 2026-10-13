# UniFi Observability: UDR7 Metrics, Dashboards and Homepage Tile

## Purpose

The router is now a UniFi Dream Router 7 (UDR7). Bring its health and traffic into the existing Prometheus/Grafana stack and surface the key numbers on Homepage. This also unblocks the "Router hardware stats on Homepage" item in `SERVICES.md`.

## Success criteria

- Prometheus scrapes the UDR7 (gateway CPU/memory/temperature, uptime, WAN throughput, client counts, Wi-Fi stats) every scrape interval; the target shows `up`.
- Grafana has dashboards for the gateway, clients and Wi-Fi, provisioned from files in the repo (no manual import).
- Homepage has a "Router" tile showing CPU, temperature, uptime, WAN throughput and number of clients.
- The router credential is a read-only UniFi API key, held only in `.env` on the server.
- Nothing new is exposed outside the `homeserver` Docker network.

## Non-goals

Alert rules (follow-up once normal values are known), UniFi events/log shipping (WebSocket features), InfluxDB/Loki outputs, a second credential for Homepage's built-in UniFi widget, any change to the router itself.

## Architecture

```
UDR7 (192.168.1.1, local API, self-signed cert)
   ^  API key (read-only)
unpoller  --/metrics:9130-->  Prometheus  -->  Grafana (provisioned dashboards)
                                  ^
                          homepage-api (/api/network/router)  -->  Homepage "Router" tile
```

### Components

1. **unpoller** (`docker-compose.monitoring.yml`)
   - Pinned image tag (latest stable at implementation time), `restart: unless-stopped`, on the `homeserver` network.
   - No Traefik labels, no published ports. Prometheus reaches it at `unpoller:9130`.
   - Authenticates to `UNIFI_URL` (default `https://192.168.1.1`) with `UNIFI_API_KEY`; TLS verification is off because the router certificate is self-signed.
   - Prometheus output on; InfluxDB, Loki and event collection off.
   - Config delivery: unpoller documents the API key as a config-file setting (`api_key`, exclusive of user/pass). If the environment-variable name for the key cannot be confirmed against the pinned version, render a config file from `.env` at start, following the existing `scripts/monitoring/configure-alertmanager.sh` pattern (generated file, gitignored, mounted read-only).

2. **Prometheus** (`monitoring/prometheus/prometheus.yml`): one new scrape job `unpoller` targeting `unpoller:9130`.

3. **Grafana** (`monitoring/grafana/dashboards/`): a small set of community unpoller dashboards (gateway, clients, Wi-Fi) committed as JSON, with every datasource reference rewritten to uid `prometheus`. Picked up by the existing file provisioning.

4. **homepage-api**: new `GET /api/network/router`, using the existing `_prometheus_query()` helper. Returns CPU %, temperature, uptime, WAN rx/tx rate and client count, with `null` for any value Prometheus does not have (so a missing metric degrades the tile instead of breaking it). Metric names are confirmed against a live scrape during implementation.

5. **Homepage** (`config/homepage/services-template.yaml`): a "Router" tile using the `customapi` widget against the new endpoint, placed beside "Network Health", with an href to the Grafana gateway dashboard. Follows the "Adding a New Service" steps in `CLAUDE.md`, including `SERVICES.md`.

### Configuration and secrets

| Variable | Purpose |
|---|---|
| `UNIFI_URL` | Router address, default `https://192.168.1.1` |
| `UNIFI_API_KEY` | Network application API key (not a Site Manager key), read-only |

Both go in `.env.example` with placeholders and comments; real values only in the server's `.env`. The key is never logged, printed or committed.

## Error handling

- Router unreachable or key rejected: unpoller logs the error and exposes no router metrics; the Prometheus target goes `down`; the Homepage tile shows empty values rather than failing.
- Missing/renamed metric: the endpoint returns `null` for that field.
- unpoller restarting does not affect any other service (nothing depends on it).

## Testing

- `make validate` for compose/config syntax.
- Unit tests for `/api/network/router` in the style of the existing `homepage-api` endpoint tests (Prometheus responses mocked, including the all-`null` case).
- On the server before merging: unpoller authenticates (logs, no key in output), the `unpoller` Prometheus target is `up`, the dashboards populate, and the Homepage tile shows values.

## Deployment notes

- Only the new/changed containers are brought up (`unpoller`, `homepage-api`, Prometheus reload); AdGuard is not restarted.
- Homepage templates are not auto-applied: copy the updated services template to the live config after deploying.
- Prerequisite (done by the user): API key created in the UniFi Network app and added to the server's `.env` as `UNIFI_API_KEY`.

## Open items to resolve during implementation

- Exact unpoller environment-variable names for API-key auth in the pinned version (fallback: generated config file, above).
- Exact metric names exported for the UDR7 (drives the endpoint queries and dashboard choice).
- Which community dashboards best fit a UDR7 (gateway-class device).
