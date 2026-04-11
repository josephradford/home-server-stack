# Health Auto Export Setup

This document covers setting up `hae-server` and `hae-mongo` to receive Apple Health
data from the [Health Auto Export](https://apple.co/3iqbU2d) iOS app, and how to
configure the iPhone automations to push data to your server.

## Overview

The health stack (`docker-compose.health.yml`) consists of two services:

- **hae-mongo** — MongoDB 7 database that stores all incoming health data
- **hae-server** — Node.js REST API that receives POSTs from the iOS app (`/api/data`)
  and exposes read endpoints (`/api/metrics/:name`, `/api/workouts`) for Bede or other
  consumers

The upstream project is [HealthyApps/health-auto-export-server](https://github.com/HealthyApps/health-auto-export-server),
vendored here as a git submodule at `./hae-server`.

---

## Server Setup

### 1. Generate API tokens

Tokens must start with `sk-`. Generate two (one for writing, one for reading):

```bash
echo "sk-$(openssl rand -hex 32)"   # run twice
```

### 2. Add environment variables to `.env`

```bash
HAE_MONGO_USERNAME=admin
HAE_MONGO_PASSWORD=your_secure_mongo_password

# Token the iOS app sends when POSTing data
HAE_WRITE_TOKEN=sk-your-write-token

# Token Bede (or Grafana) uses when reading data
HAE_READ_TOKEN=sk-your-read-token
```

Both token values **must start with `sk-`** — the server's auth middleware enforces
this and will return 401 for any token without the prefix.

### 3. Build and start

The `hae-server` image is built from source (git submodule). Initialise the submodule
if you haven't already:

```bash
git submodule update --init hae-server
make hae-build
make hae-start
```

Or it's included in the full stack:

```bash
make build   # builds all custom images including hae-server
make start   # starts everything
```

### 4. Verify

```bash
make hae-status     # both containers should show Up
make logs-hae       # hae-server should print "Connected successfully to health-auto-export"
```

Test the write endpoint from the server:

```bash
docker exec hae-server wget -q -O- \
  --post-data='{"data":[]}' \
  --header='Content-Type: application/json' \
  --header='api-key: sk-your-write-token' \
  http://localhost:3001/api/data
# Expected: {"metrics":{"success":true,...},"workouts":{"success":true,...}}
```

Test a read endpoint:

```bash
docker exec hae-server wget -q -O- \
  --header='api-key: sk-your-read-token' \
  'http://localhost:3001/api/metrics/step_count'
# Expected: [] (empty until data has been synced from iPhone)
```

---

## iPhone Setup

Install **Health Auto Export** from the App Store. Under the **Automations** tab,
create the following automations. Each taps **Update** to save and **Manual Export**
to trigger a first sync.

### Automation 1 — Health Metrics

| Setting | Value |
|---|---|
| Automation Type | REST API |
| URL | `https://hae.YOUR_DOMAIN/api/data` |
| Header key | `api-key` |
| Header value | `HAE_WRITE_TOKEN` value from `.env` |
| Data Type | Health Metrics |
| Export Format | JSON |
| Aggregate Data | On |
| Aggregate Interval | Day |
| Batch Requests | On |
| Date Range | Since Last Sync |

Recommended metrics to enable (maps to what Bede uses in the journal):

| Metric name in app | Enum value (read API) |
|---|---|
| Sleep Analysis | `sleep_analysis` |
| Step Count | `step_count` |
| Heart Rate Variability | `heart_rate_variability` |
| Resting Heart Rate | `resting_heart_rate` |
| Active Energy | `active_energy` |
| Apple Exercise Time | `apple_exercise_time` |
| Apple Stand Time | `apple_stand_time` |
| Apple Move Time | `apple_move_time` |
| Mindful Minutes | `mindful_minutes` |
| State of Mind | `state_of_mind` |

You can enable additional metrics freely — they are stored in MongoDB and can be
queried later without any server changes.

### Automation 2 — Workouts

Same settings as above, but **Data Type = Workouts**. This captures gym sessions,
runs, and any other recorded workout activity.

### Automation 3 — Medications *(optional)*

Same settings, Data Type = Health Metrics, metrics = Medications only. Only needed
if you log medications in the Health app and want Bede to include them in the journal.

### Manual first sync

After saving each automation, tap **Manual Export**, set the date range to
**Last 7 Days**, and trigger it. This pre-populates the database immediately rather
than waiting for the next scheduled sync.

### Sync frequency note

iOS only allows the app to access Health data while the iPhone is **unlocked**. Set
each automation to run every 1–4 hours — it will catch up whenever the phone is in
use. For the 2am journal job, the previous day's data will have fully synced long
before Bede runs.

---

## Read API Reference

All read endpoints require the header `api-key: sk-your-read-token`.

| Endpoint | Description |
|---|---|
| `GET /api/metrics/:name` | Returns stored data for a named metric (see enum values above) |
| `GET /api/workouts` | Returns stored workout records |
| `POST /api/data` | Write endpoint — used by the iOS app only |

The full list of supported metric names is defined in
[`server/src/models/MetricName.ts`](https://github.com/HealthyApps/health-auto-export-server/blob/main/server/src/models/MetricName.ts)
in the upstream repo.

### Example: query yesterday's step count

```bash
curl -H 'api-key: sk-your-read-token' \
  https://hae.YOUR_DOMAIN/api/metrics/step_count
```

---

## Makefile targets

| Target | Description |
|---|---|
| `make hae-build` | Build the hae-server image from source |
| `make hae-start` | Start hae-server and hae-mongo |
| `make hae-stop` | Stop health services |
| `make hae-restart` | Restart health services |
| `make hae-status` | Show container status |
| `make logs-hae` | Follow logs from both containers |
