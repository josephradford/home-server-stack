# UniFi Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export UDR7 metrics to Prometheus with unpoller, provision Grafana dashboards for them, and show a Router tile on Homepage.

**Architecture:** `unpoller` (internal-only container) polls the UDR7's local API with a read-only API key and exposes `/metrics`; Prometheus scrapes it; Grafana loads committed dashboard JSON; `homepage-api` gets a new `/api/network/router` endpoint that queries Prometheus and feeds a `customapi` Homepage tile.

**Tech Stack:** Docker Compose, unpoller v5.5.1, Prometheus v3.15.0, Grafana 13.2.2, Flask (`homepage-api`), pytest, Homepage v2.4.0.

**Spec:** `docs/superpowers/specs/2026-10-12-unifi-observability-design.md`

## Global Constraints

- unpoller image is pinned: `ghcr.io/unpoller/unpoller:v5.5.1` (no `latest`).
- unpoller has no Traefik labels and no published ports; Prometheus reaches it at `unpoller:9130` on the `homeserver` network.
- The API key lives only in `.env` (`UNIFI_API_KEY`); `.env.example` carries a placeholder. The key is never logged, printed, committed or pasted into chat. When checking logs, mask it.
- unpoller environment variables (verified against v5.5.1 on the server): `UP_UNIFI_DEFAULT_URL`, `UP_UNIFI_DEFAULT_API_KEY`, `UP_UNIFI_DEFAULT_VERIFY_SSL=false`, `UP_INFLUXDB_DISABLE=true`. unpoller caches Prometheus output for 1 minute, so the scrape interval is `60s`.
- Grafana dashboards reference the datasource by uid `prometheus` (object form `{"type": "prometheus", "uid": "prometheus"}`), matching `monitoring/grafana/provisioning/datasources/prometheus.yml`.
- No alert rules, no event/log shipping, no InfluxDB/Loki, no change to the router, no second credential for Homepage's built-in UniFi widget (all spec non-goals).
- Nothing is deployed to the server except the named services; AdGuard is never restarted.
- Docker is not installed on the dev Mac, so `make validate` and container checks run on the server (SSH config in `.claude/server-test.local`). Deploying the branch to the server needs the user's go-ahead for that step.
- Commits end with: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. The PR body ends with: `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- Branch: `feature/unifi-observability` (already created; the spec is committed on it).

## Review Focus

Failure modes the spec implies that are most likely to bite, most likely first. Each has a test or verification step in the task that owns it.

1. **unpoller down or router unreachable:** Prometheus returns no series. The endpoint must return 200 with every field `null` (not 500), so the tile degrades quietly. (Task 2 test `test_router_no_data_returns_nulls`.)
2. **Only some metrics present** (e.g. the temperature sensor is missing): that field is `null`, the others still show. (Task 2 test `test_router_partial_data`.)
3. **Prometheus returns `NaN`:** `float('NaN')` would produce invalid JSON in the response. It must become `null`. (Task 2 test `test_router_nan_becomes_null`.)
4. **Several temperature sensors:** the endpoint reports the hottest, not an arbitrary one. (Task 2: the temperature query uses `max(...)`, pinned by `test_router_queries_use_aggregates`.)
5. **API key missing, wrong or revoked:** other services must be unaffected; unpoller logs an auth error and never prints the key. (Task 1 Step 7 and Task 5 Step 4.)

---

### Task 1: unpoller container, config and Prometheus scrape job

**Files:**
- Modify: `.env.example` (monitoring block, after `ROUTER_IP=192.168.1.1`, around line 104)
- Modify: `docker-compose.monitoring.yml` (add service before the top-level `volumes:` key)
- Modify: `monitoring/prometheus/prometheus.yml` (append a scrape job)

**Interfaces:**
- Produces: a container named `unpoller` on network `homeserver` serving metrics at `http://unpoller:9130/metrics`; Prometheus job label `job="unpoller"`; environment variables `UNIFI_URL` and `UNIFI_API_KEY` read from `.env`. Task 2 and Task 3 rely on the metric names `unpoller_device_*` and `unpoller_site_users` being present.

- [ ] **Step 1: Add the env vars to `.env.example`**

Insert directly after the line `ROUTER_IP=192.168.1.1`:

```bash

# -----------------------------------------------------------------------------
# unpoller (UniFi router metrics for Prometheus/Grafana/Homepage)
# UNIFI_API_KEY: create in the UniFi Network app (Integrations / API keys) from a
# view-only local admin. It must be a Network application key, not a Site
# Manager key. Leave empty to disable router metrics (unpoller just logs an
# authentication error).
# UNIFI_URL: the router's local address (self-signed certificate; verification
# is off).
# -----------------------------------------------------------------------------
UNIFI_URL=https://192.168.1.1
UNIFI_API_KEY=
```

- [ ] **Step 2: Add the unpoller service**

In `docker-compose.monitoring.yml`, insert after the `blackbox-exporter` service block and before the top-level `volumes:` key:

```yaml
  unpoller:
    image: ghcr.io/unpoller/unpoller:v5.5.1
    container_name: unpoller
    restart: unless-stopped
    environment:
      # Verified against v5.5.1: these names authenticate with an API key.
      UP_UNIFI_DEFAULT_URL: ${UNIFI_URL:-https://192.168.1.1}
      UP_UNIFI_DEFAULT_API_KEY: ${UNIFI_API_KEY:-}
      UP_UNIFI_DEFAULT_VERIFY_SSL: "false"   # the router's certificate is self-signed
      UP_INFLUXDB_DISABLE: "true"            # Prometheus output only
    networks:
      - homeserver
```

No `ports:` and no Traefik labels: only Prometheus (same network) reaches it.

- [ ] **Step 3: Add the Prometheus scrape job**

Append to `monitoring/prometheus/prometheus.yml` (after the `odd-jobs` job, same indentation as the other jobs):

```yaml

  - job_name: 'unpoller'
    scrape_interval: 60s   # unpoller caches its output for 1 minute
    static_configs:
      - targets: ['unpoller:9130']
```

- [ ] **Step 4: Commit the config (before touching the server)**

```bash
git add .env.example docker-compose.monitoring.yml monitoring/prometheus/prometheus.yml
git commit -m "feat(monitoring): add unpoller and a Prometheus scrape job for the UDR7" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push -u origin feature/unifi-observability
```

- [ ] **Step 5: Get the user's go-ahead to deploy the branch, then check out the branch on the server**

Ask: "OK to check out `feature/unifi-observability` on the server and start unpoller?" Then (read the SSH user/host from `.claude/server-test.local`):

```bash
ssh joe@192.168.1.101 'cd ~/home-server-stack && test -z "$(git status --porcelain --untracked-files=no)" && git fetch -q origin && git checkout -q feature/unifi-observability && git pull -q origin feature/unifi-observability && git log --oneline -1 && make validate 2>&1 | tail -2'
```
Expected: the commit from Step 4, then `✓ Docker Compose configuration is valid`.

- [ ] **Step 6: Start only unpoller**

```bash
ssh joe@192.168.1.101 'cd ~/home-server-stack && F="-f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml -f docker-compose.photos.yml -f docker-compose.location.yml -f docker-compose.immich.yml -f docker-compose.library.yml -f docker-compose.kiosk.yml -f docker-compose.radmap.yml -f docker-compose.netalertx.yml -f docker-compose.jobs.yml" && docker compose $F up -d unpoller 2>&1 | tail -3 && sleep 15 && docker ps --filter name=unpoller --format "{{.Names}} {{.Status}}"'
```
Expected: `unpoller Up ...`. (Confirm the file list still matches `COMPOSE` in the Makefile; if it differs, use the Makefile's list.)

- [ ] **Step 7: Verify unpoller authenticated, with the key masked**

```bash
ssh joe@192.168.1.101 'cd ~/home-server-stack && set -a && . ./.env && set +a && docker logs unpoller 2>&1 | sed "s/$UNIFI_API_KEY/<key>/g" | grep -E "has api-key|Prometheus exported|ERROR|error" | tail -6'
```
Expected: a line containing `has api-key: true` and `Prometheus exported at http://0.0.0.0:9130/`, and no `ERROR` lines. If `has api-key: false`, `UNIFI_API_KEY` is empty or missing from the server's `.env`.

- [ ] **Step 8: Reload Prometheus and check the target is up**

```bash
ssh joe@192.168.1.101 'docker exec prometheus wget -qO- --post-data="" http://localhost:9090/-/reload; sleep 70; docker exec prometheus wget -qO- "http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22unpoller%22%7D"'
```
Expected: JSON whose `result` has one series with value `"1"`. Also run `docker exec prometheus wget -qO- "http://localhost:9090/api/v1/query?query=unpoller_device_uptime_seconds"` and expect one series (the UDR7, `type="udm"`).

Review Focus 5 check: with the key deliberately blank this would only produce an authentication error in unpoller's logs; no other container is affected because nothing depends on unpoller.

---

### Task 2: `/api/network/router` endpoint in homepage-api (TDD)

**Files:**
- Modify: `homepage-api/app.py` (add `import math` near the other imports at lines 9-21; add the endpoint directly after the `network_health` function, before the `# DOCKER DAEMON STATUS` banner)
- Modify: `homepage-api/tests/test_app.py` (append a new class directly after `TestNetworkHealthEndpoint`, before `TestIcloudpdStatusEndpoint`)

**Interfaces:**
- Consumes: `_prometheus_query(query)` (existing, `app.py`), returns the list under `data.result`.
- Produces: `GET /api/network/router` returning JSON `{cpu_pct, memory_pct, temperature_c, uptime_days, wan_down_mbps, wan_up_mbps, clients, vpn_clients, updated}`; every numeric field is a number or `null`. Helper functions `_prometheus_scalar(query) -> float | None` and `_round_or_none(value, digits)`. Task 4's Homepage tile maps exactly these field names.

- [ ] **Step 1: Create a throwaway venv for the tests (outside the repo)**

```bash
VENV=/private/tmp/claude-501/-Users-joeradford-dev-home-server-stack/ad2eb400-9f4c-4cf1-bd51-d81cd62eee10/scratchpad/venv
python3 -m venv "$VENV" && "$VENV/bin/pip" install -q -r homepage-api/requirements.txt
cd homepage-api && "$VENV/bin/python" -m pytest tests/test_app.py -q -k NetworkHealth 2>&1 | tail -3
```
Expected: the existing `TestNetworkHealthEndpoint` tests pass (2 passed). This confirms the environment works before changing anything.

- [ ] **Step 2: Write the failing tests**

Append after `TestNetworkHealthEndpoint` in `homepage-api/tests/test_app.py`:

```python
def _router_fake_get(values):
    """Build a requests.get stand-in answering Prometheus instant queries.

    `values` maps a distinctive substring of the PromQL query to the sample
    value (a string, like Prometheus returns). Queries that match nothing get
    an empty result, the same as a metric Prometheus has no series for.
    """
    def fake_get(url, params=None, timeout=None):
        query = params['query']
        result = []
        for fragment, value in values.items():
            if fragment in query:
                result = [{'metric': {}, 'value': [0, value]}]
                break
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'success', 'data': {'result': result}}
        return mock_response
    return fake_get


_ROUTER_FULL_VALUES = {
    'unpoller_device_cpu_utilization_ratio': '22.4',
    'unpoller_device_memory_utilization_ratio': '55.2',
    'unpoller_device_temperature_celsius': '63',
    'unpoller_device_uptime_seconds': '245584',
    'unpoller_device_wan_receive_rate_bytes': '587937',
    'unpoller_device_wan_transmit_rate_bytes': '571582',
    'subsystem=~"lan|wlan"': '10',
    'subsystem="vpn"': '0',
}


class TestNetworkRouterEndpoint:
    """Tests for /api/network/router (UDR7 stats from unpoller via Prometheus)"""

    @patch('app.requests.get')
    def test_router_success(self, mock_get, client):
        mock_get.side_effect = _router_fake_get(_ROUTER_FULL_VALUES)

        response = client.get('/api/network/router')
        assert response.status_code == 200

        data = response.get_json()
        assert data['cpu_pct'] == 22.4
        assert data['memory_pct'] == 55.2
        assert data['temperature_c'] == 63.0
        assert data['uptime_days'] == 2.8          # 245584 s / 86400
        assert data['wan_down_mbps'] == 4.7        # 587937 B/s * 8 / 1e6
        assert data['wan_up_mbps'] == 4.6          # 571582 B/s * 8 / 1e6
        assert data['clients'] == 10
        assert data['vpn_clients'] == 0
        assert 'updated' in data

    @patch('app.requests.get')
    def test_router_no_data_returns_nulls(self, mock_get, client):
        """unpoller down / router unreachable: no series -> 200 with all nulls."""
        mock_get.side_effect = _router_fake_get({})

        response = client.get('/api/network/router')
        assert response.status_code == 200

        data = response.get_json()
        for field in ('cpu_pct', 'memory_pct', 'temperature_c', 'uptime_days',
                      'wan_down_mbps', 'wan_up_mbps', 'clients', 'vpn_clients'):
            assert data[field] is None, field

    @patch('app.requests.get')
    def test_router_partial_data(self, mock_get, client):
        """A missing metric nulls only that field."""
        values = dict(_ROUTER_FULL_VALUES)
        del values['unpoller_device_temperature_celsius']
        mock_get.side_effect = _router_fake_get(values)

        data = client.get('/api/network/router').get_json()
        assert data['temperature_c'] is None
        assert data['cpu_pct'] == 22.4
        assert data['clients'] == 10

    @patch('app.requests.get')
    def test_router_nan_becomes_null(self, mock_get, client):
        """Prometheus can return 'NaN'; it must not leak into the JSON."""
        values = dict(_ROUTER_FULL_VALUES)
        values['unpoller_device_cpu_utilization_ratio'] = 'NaN'
        mock_get.side_effect = _router_fake_get(values)

        response = client.get('/api/network/router')
        assert response.status_code == 200
        assert b'NaN' not in response.data
        assert response.get_json()['cpu_pct'] is None

    @patch('app.requests.get')
    def test_router_queries_use_aggregates(self, mock_get, client):
        """Several sensors/devices must collapse to one value (hottest temp, summed rates)."""
        seen = []
        inner = _router_fake_get(_ROUTER_FULL_VALUES)

        def recording_get(url, params=None, timeout=None):
            seen.append(params['query'])
            return inner(url, params=params, timeout=timeout)
        mock_get.side_effect = recording_get

        client.get('/api/network/router')

        temperature_query = next(q for q in seen if 'temperature_celsius' in q)
        assert temperature_query.startswith('max(')
        wan_query = next(q for q in seen if 'wan_receive_rate_bytes' in q)
        assert wan_query.startswith('sum(')

    @patch('app.requests.get')
    def test_router_prometheus_error(self, mock_get, client):
        mock_get.side_effect = Exception('connection refused')

        response = client.get('/api/network/router')
        assert response.status_code == 500
        assert 'error' in response.get_json()
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
cd homepage-api && "$VENV/bin/python" -m pytest tests/test_app.py -q -k NetworkRouter 2>&1 | tail -8
```
Expected: 6 failures, all `404 != 200` style (the route does not exist yet).

- [ ] **Step 4: Implement the endpoint**

In `homepage-api/app.py`, add `import math` next to `import os` (line 15). Then insert directly after the `network_health` function (ends with the `except Exception as e: return jsonify({'error': str(e)}), 500` block) and before the `# DOCKER DAEMON STATUS` banner:

```python
# unpoller labels the UDR7 as type "udm". Selecting on it keeps the numbers
# about the router if APs/switches are ever added to the site.
_ROUTER_DEVICE_TYPE = 'udm'


def _prometheus_scalar(query):
    """First sample of an instant query as a float, or None when there is no
    series or the value is not a finite number (Prometheus may return NaN)."""
    results = _prometheus_query(query)
    if not results:
        return None
    value = float(results[0]['value'][1])
    return None if math.isnan(value) or math.isinf(value) else value


def _round_or_none(value, digits):
    return None if value is None else round(value, digits)


@app.route('/api/network/router')
def network_router():
    """
    UDR7 health from unpoller metrics in Prometheus: CPU, memory, temperature,
    uptime, WAN throughput and client counts. Any value Prometheus has no
    data for is null, so the Homepage tile degrades instead of failing.
    """
    try:
        dev = f'type="{_ROUTER_DEVICE_TYPE}"'
        cpu = _prometheus_scalar(f'max(unpoller_device_cpu_utilization_ratio{{{dev}}}) * 100')
        memory = _prometheus_scalar(f'max(unpoller_device_memory_utilization_ratio{{{dev}}}) * 100')
        temperature = _prometheus_scalar(f'max(unpoller_device_temperature_celsius{{{dev}}})')
        uptime_s = _prometheus_scalar(f'max(unpoller_device_uptime_seconds{{{dev}}})')
        wan_down = _prometheus_scalar(f'sum(unpoller_device_wan_receive_rate_bytes{{{dev}}})')
        wan_up = _prometheus_scalar(f'sum(unpoller_device_wan_transmit_rate_bytes{{{dev}}})')
        clients = _prometheus_scalar('sum(unpoller_site_users{subsystem=~"lan|wlan"})')
        vpn_clients = _prometheus_scalar('sum(unpoller_site_users{subsystem="vpn"})')

        return jsonify({
            'cpu_pct': _round_or_none(cpu, 1),
            'memory_pct': _round_or_none(memory, 1),
            'temperature_c': _round_or_none(temperature, 1),
            'uptime_days': _round_or_none(None if uptime_s is None else uptime_s / 86400, 1),
            # unpoller reports bytes/second; the tile shows megabits/second.
            'wan_down_mbps': _round_or_none(None if wan_down is None else wan_down * 8 / 1e6, 1),
            'wan_up_mbps': _round_or_none(None if wan_up is None else wan_up * 8 / 1e6, 1),
            'clients': None if clients is None else int(clients),
            'vpn_clients': None if vpn_clients is None else int(vpn_clients),
            'updated': datetime.now().isoformat()
        })

    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Prometheus API error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

- [ ] **Step 5: Run the new tests, then the whole suite**

```bash
cd homepage-api && "$VENV/bin/python" -m pytest tests/test_app.py -q -k NetworkRouter 2>&1 | tail -4
"$VENV/bin/python" -m pytest -q 2>&1 | tail -3
```
Expected: `6 passed`, then the full suite passes with no new failures.

- [ ] **Step 6: Commit**

```bash
git add homepage-api/app.py homepage-api/tests/test_app.py
git commit -m "feat(homepage-api): add /api/network/router from unpoller metrics" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Grafana dashboards

**Files:**
- Create: `monitoring/grafana/dashboards/unifi-usg-insights.json` (grafana.com 11313, revision 9)
- Create: `monitoring/grafana/dashboards/unifi-client-insights.json` (11315, revision 9)
- Create: `monitoring/grafana/dashboards/unifi-network-sites.json` (11311, revision 5)
- Create: `monitoring/grafana/dashboards/unifi-uap-insights.json` (11314, revision 10; kept only if it shows data in Step 5)

**Interfaces:**
- Consumes: Task 1's live `unpoller` metrics under datasource uid `prometheus`.
- Produces: dashboards with their original uids, in particular USG Insights uid `4Yo8IZ-Wk`, which Task 4's tile links to (`https://grafana.<domain>/d/4Yo8IZ-Wk`).

- [ ] **Step 1: Download the community dashboards and rewrite their datasource references**

Run from the repo root (this adapts the dashboards once; only the resulting JSON is committed):

```bash
python3 - <<'EOF'
import json, urllib.request

DASHBOARDS = [
    (11313, 9, 'unifi-usg-insights'),
    (11315, 9, 'unifi-client-insights'),
    (11311, 5, 'unifi-network-sites'),
    (11314, 10, 'unifi-uap-insights'),
]
PROM = {'type': 'prometheus', 'uid': 'prometheus'}
IMPORT_VARS = ('${DS_PROMETHEUS}', '${DS_UNIFI_POLLER}')  # DS_UNIFI_POLLER only appears on text/row panels


def fix(node):
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if key == 'datasource':
                if value in IMPORT_VARS or (isinstance(value, dict) and value.get('uid') in IMPORT_VARS):
                    node[key] = dict(PROM)
                    continue
            fix(value)
    elif isinstance(node, list):
        for item in node:
            fix(item)


for dash_id, revision, name in DASHBOARDS:
    url = f'https://grafana.com/api/dashboards/{dash_id}/revisions/{revision}/download'
    request = urllib.request.Request(url, headers={'User-Agent': 'home-server-stack-dashboard-import'})
    with urllib.request.urlopen(request, timeout=30) as response:
        dash = json.load(response)
    dash.pop('__inputs', None)
    dash.pop('__requires', None)
    dash['id'] = None
    fix(dash)
    text = json.dumps(dash, indent=2, sort_keys=False)
    assert '${DS_' not in text, f'{name}: unresolved datasource variable'
    with open(f'monitoring/grafana/dashboards/{name}.json', 'w') as handle:
        handle.write(text + '\n')
    print(f'{name}: uid={dash.get("uid")} panels={len(dash.get("panels", []))}')
EOF
```
Expected: four lines, one per dashboard, and USG Insights printing `uid=4Yo8IZ-Wk`. The script fails loudly if any `${DS_...}` reference survives.

- [ ] **Step 2: Sanity-check the JSON**

```bash
for f in monitoring/grafana/dashboards/unifi-*.json; do python3 -c "import json,sys; json.load(open('$f')); print('ok', '$f')"; done
grep -c '"uid": "prometheus"' monitoring/grafana/dashboards/unifi-*.json
```
Expected: four `ok` lines and a non-zero count per file.

- [ ] **Step 3: Commit and push**

```bash
git add monitoring/grafana/dashboards/unifi-*.json
git commit -m "feat(monitoring): provision UniFi dashboards (gateway, clients, sites, AP)" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push
```

- [ ] **Step 4: Pull on the server (Grafana loads new dashboard files within ~10 seconds, no restart)**

```bash
ssh joe@192.168.1.101 'cd ~/home-server-stack && git pull -q origin feature/unifi-observability && ls monitoring/grafana/dashboards | grep unifi'
```
Expected: the four `unifi-*.json` files.

- [ ] **Step 5: Verify the dashboards show data and prune any that do not**

Open `https://grafana.<domain>/dashboards` (use the Claude-in-Chrome tools if available, otherwise ask the user to look) and open each UniFi dashboard with the time range set to "Last 15 minutes". Expected: USG Insights shows the gateway's CPU, memory, temperature and WAN traffic; Client Insights lists the connected clients; Network Sites shows site-level counts. For any dashboard where **every** panel says "No data" (most likely UAP Insights, which filters on access-point devices and the UDR7 is classed as a gateway), remove its file with `git rm`, commit (`chore(monitoring): drop UniFi dashboard with no data on a UDR7`), and push. Keep dashboards where at least the main panels populate; individual empty panels are acceptable.

---

### Task 4: Homepage tile and docs

**Files:**
- Modify: `config/homepage/services-template.yaml` (add a tile directly after the `Network Health` tile, same group and indentation, before the `# External Service Status` comment)
- Modify: `SERVICES.md` (monitoring section after `#### blackbox-exporter`, and the "Router hardware stats" checklist item around line 235)
- Modify: `README.md` (Monitoring line near the top)

**Interfaces:**
- Consumes: `/api/network/router` fields from Task 2 and Grafana dashboard uid `4Yo8IZ-Wk` from Task 3.

- [ ] **Step 1: Add the Router tile**

Insert after the `Network Health` entry (after its `suffix: "%"` line for the last mapping) in `config/homepage/services-template.yaml`:

```yaml
      - Router:
          icon: mdi-router-wireless
          href: https://grafana.{{HOMEPAGE_VAR_DOMAIN}}/d/4Yo8IZ-Wk
          description: UDR7 health (unpoller via Prometheus)
          widget:
            type: customapi
            url: http://homepage-api:5000/api/network/router
            refreshInterval: 60000  # 1 minute (unpoller refreshes every minute)
            mappings:
              - field: cpu_pct
                label: CPU
                suffix: "%"
              - field: temperature_c
                label: Temp
                suffix: "°C"
              - field: uptime_days
                label: Uptime
                suffix: " d"
              - field: clients
                label: Clients
              - field: wan_down_mbps
                label: WAN down
                suffix: " Mbps"
              - field: wan_up_mbps
                label: WAN up
                suffix: " Mbps"
```

- [ ] **Step 2: Update `SERVICES.md`**

Add after the `#### blackbox-exporter` section:

```markdown
#### unpoller
- **Purpose:** Exports UDR7 metrics (gateway CPU/memory/temperature, uptime, WAN throughput, clients, Wi-Fi) to Prometheus. Feeds the UniFi Grafana dashboards and the Homepage "Router" tile (via `homepage-api` `/api/network/router`).
- **Access:** Internal only (`unpoller:9130` on the `homeserver` network; no Traefik route, no published port)
- **Config:** `UNIFI_URL` and `UNIFI_API_KEY` in `.env` (read-only Network application API key; see `.env.example`). Prometheus job `unpoller` in `monitoring/prometheus/prometheus.yml`. Dashboards in `monitoring/grafana/dashboards/unifi-*.json`.
- **Notes:** unpoller caches its output for a minute, so the job scrapes every 60s. If the Router tile shows empty values, check `docker logs unpoller` (authentication errors) and the `unpoller` target on the Prometheus targets page.
```

Replace the existing checklist line beginning `- [ ] **Router hardware stats on Homepage**` with:

```markdown
- [x] **Router hardware stats on Homepage** (CPU, temp, uptime, WAN throughput, clients) - Shipped via unpoller to Prometheus and a Homepage "Router" tile, plus UniFi Grafana dashboards. Devices-on-network and ISP/local latency + packet-loss widgets use AdGuard + blackbox_exporter.
```

In `README.md`, change the Monitoring line to include unpoller: replace `Node Exporter, cAdvisor, blackbox-exporter` with `Node Exporter, cAdvisor, blackbox-exporter, [unpoller](https://github.com/unpoller/unpoller) (UDR7 metrics)`.

- [ ] **Step 3: Check the edits landed and commit**

```bash
grep -n "unpoller" SERVICES.md README.md | cut -c1-110
grep -n "Router:" -A3 config/homepage/services-template.yaml | head -5
git add config/homepage/services-template.yaml SERVICES.md README.md
git commit -m "feat(homepage): add a UDR7 Router tile; document unpoller" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push
```

---

### Task 5: Deploy to the server, verify end to end, open the PR

**Files:** none (deployment and verification; one PR).

**Interfaces:** Consumes everything above.

- [ ] **Step 1: Pull the branch on the server and rebuild only `homepage-api`**

```bash
ssh joe@192.168.1.101 'cd ~/home-server-stack && git pull -q origin feature/unifi-observability && F="-f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml -f docker-compose.photos.yml -f docker-compose.location.yml -f docker-compose.immich.yml -f docker-compose.library.yml -f docker-compose.kiosk.yml -f docker-compose.radmap.yml -f docker-compose.netalertx.yml -f docker-compose.jobs.yml" && docker compose $F up -d --build homepage-api 2>&1 | tail -3 && sleep 10 && docker ps --filter name=homepage-api --format "{{.Names}} {{.Status}}"'
```
Expected: `homepage-api Up ... (healthy)`.

- [ ] **Step 2: Check the new endpoint returns real values**

```bash
ssh joe@192.168.1.101 'docker exec homepage-api curl -s http://localhost:5000/api/network/router'
```
Expected: JSON with numeric `cpu_pct`, `memory_pct`, `temperature_c`, `uptime_days`, `wan_down_mbps`, `wan_up_mbps`, `clients` (about the number of connected devices) and `vpn_clients`. If every field is `null`, check that the unpoller target is `up` (Task 1 Step 8) and wait a minute for the first scrape.

- [ ] **Step 3: Apply the Homepage template and check the tile**

Homepage templates are not auto-applied. Review the differences, then copy the template over the live file:

```bash
ssh joe@192.168.1.101 'cd ~/home-server-stack && diff config/homepage/services-template.yaml data/homepage/config/services.yaml'
```
Expected: only the new Router tile (and nothing the user edited by hand). If there are other differences, show them to the user before overwriting. Then:

```bash
ssh joe@192.168.1.101 'cd ~/home-server-stack && cp data/homepage/config/services.yaml data/homepage/config/services.yaml.bak3 && cp config/homepage/services-template.yaml data/homepage/config/services.yaml'
```
Open `https://homepage.<domain>` and confirm the "Router" tile shows CPU, Temp, Uptime, Clients and the two WAN rates. Clicking it opens the USG Insights dashboard.

- [ ] **Step 4: Confirm the key is not exposed anywhere**

```bash
ssh joe@192.168.1.101 'cd ~/home-server-stack && set -a && . ./.env && set +a && for c in unpoller homepage-api prometheus grafana; do printf "%s: " $c; docker logs $c 2>&1 | grep -c -F "$UNIFI_API_KEY"; done; git status --porcelain | grep -c "^??.*env" || true'
```
Expected: `0` for every container and no untracked env files. (The key is checked by value but never printed.)

- [ ] **Step 5: Re-test with the lower-permission key (if the user created one)**

Ask the user to replace `UNIFI_API_KEY` in the server's `.env` themselves (never paste it into chat), then:

```bash
ssh joe@192.168.1.101 'cd ~/home-server-stack && F="-f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml -f docker-compose.photos.yml -f docker-compose.location.yml -f docker-compose.immich.yml -f docker-compose.library.yml -f docker-compose.kiosk.yml -f docker-compose.radmap.yml -f docker-compose.netalertx.yml -f docker-compose.jobs.yml" && docker compose $F up -d --force-recreate unpoller 2>&1 | tail -2 && sleep 20 && docker exec homepage-api curl -s http://localhost:5000/api/network/router'
```
Expected: the same numeric JSON as Step 2. If values are `null`, the new key lacks the permissions unpoller needs; tell the user and keep the previous key until they adjust it.

- [ ] **Step 6: Open the PR (public-safe description: no domain, IPs, key or host details)**

```bash
gh pr create --base main --head feature/unifi-observability --title "feat(monitoring): UDR7 metrics via unpoller, Grafana dashboards and a Homepage tile" --body "$(cat <<'EOF'
## Summary
- Adds `unpoller` (pinned image, internal network only) to export UDR7 metrics to Prometheus, using a read-only UniFi API key from `.env`.
- Provisions UniFi Grafana dashboards (gateway, clients, sites) as committed JSON using the existing `prometheus` datasource uid.
- Adds `/api/network/router` to `homepage-api` and a Homepage "Router" tile (CPU, temperature, uptime, clients, WAN throughput). Missing data degrades to empty values instead of errors.
- Documents the new service in `SERVICES.md`/`README.md` and ticks the router-stats item.

## Test plan
- [x] `homepage-api` unit tests (success, no data, partial data, NaN, aggregation, Prometheus error)
- [x] Branch deployed on the server: unpoller authenticated, Prometheus target up, dashboards populated, tile shows values
- [x] API key not present in any container log
- [ ] After merge: pull on the server, `docker compose up -d unpoller homepage-api`, copy the Homepage services template
- [ ] Alert rules for the router are a follow-up once normal values are known

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 7: After the user merges, put the server back on `main`**

```bash
ssh joe@192.168.1.101 'cd ~/home-server-stack && git checkout -q main && git pull -q origin main && git branch -d feature/unifi-observability; git log --oneline -1; docker ps --filter name=unpoller --format "{{.Names}} {{.Status}}"'
```
Expected: the merge commit on `main`, `unpoller Up ...`, no running-service changes (the merged code matches what was tested).
