# Health Auto Export Setup

This document covers setting up `hae-server` and `hae-influxdb` to receive Apple Health
data from the [Health Auto Export](https://apple.co/3iqbU2d) iOS app, and how to
configure the iPhone automations to push data to your server.

## Overview

The health stack (`docker-compose.health.yml`) consists of two services:

- **hae-influxdb** — InfluxDB 2 time-series database that stores all incoming health data
- **hae-server** — [irvinlim/apple-health-ingester](https://github.com/irvinlim/apple-health-ingester)
  receives POSTs from the iOS app and writes them to InfluxDB

---

## Server Setup

### 1. Generate API tokens

Generate a write token for the iOS app and a separate admin token for InfluxDB:

```bash
openssl rand -hex 32   # HAE_WRITE_TOKEN — iOS app uses this to POST data
openssl rand -hex 32   # HAE_INFLUXDB_TOKEN — InfluxDB admin token
openssl rand -hex 32   # HAE_INFLUXDB_PASSWORD — InfluxDB admin password
```

### 2. Add environment variables to `.env`

```bash
# iOS app write token
HAE_WRITE_TOKEN=your-secure-hae-write-token

# InfluxDB credentials
HAE_INFLUXDB_USERNAME=admin
HAE_INFLUXDB_PASSWORD=your-secure-influxdb-password
HAE_INFLUXDB_TOKEN=your-secure-influxdb-admin-token
HAE_INFLUXDB_ORG=health
HAE_INFLUXDB_METRICS_BUCKET=metrics
HAE_INFLUXDB_WORKOUTS_BUCKET=workouts
```

### 3. Build and start

```bash
make hae-start
```

Or it's included in the full stack:

```bash
make start   # starts everything
```

### 4. Verify

```bash
make hae-status     # both containers should show Up
make logs-hae       # hae-server should show it connected to InfluxDB
```

Test the write endpoint:

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer your-write-token" \
  -H "Content-Type: application/json" \
  -d '{"data":[]}' \
  https://hae.YOUR_DOMAIN/api/healthautoexport/v1/influxdb/ingest
# Expected: 200
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
| URL | `https://hae.YOUR_DOMAIN/api/healthautoexport/v1/influxdb/ingest` |
| Header key | `Authorization` |
| Header value | `Bearer <HAE_WRITE_TOKEN value from .env>` |
| Data Type | Health Metrics |
| Export Format | JSON |
| Aggregate Data | On |
| Aggregate Interval | Day |
| Batch Requests | On |
| Date Range | Since Last Sync |

Recommended metrics to enable (maps to what Bede uses in the journal):

| Metric name in app |
|---|
| Sleep Analysis |
| Step Count |
| Heart Rate Variability |
| Resting Heart Rate |
| Active Energy |
| Apple Exercise Time |
| Apple Stand Time |
| Apple Move Time |
| Mindful Minutes |
| State of Mind |

You can enable additional metrics freely — they are stored in InfluxDB and can be
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

## Querying data

Health data is stored in InfluxDB and accessible via:

- **InfluxDB UI**: `https://influxdb.YOUR_DOMAIN` — interactive query builder and dashboards
- **Flux queries**: query via the InfluxDB API using `HAE_INFLUXDB_TOKEN`
- **Bede**: reads directly from InfluxDB using the admin token

---

## Makefile targets

| Target | Description |
|---|---|
| `make hae-build` | Build the hae-server image from source |
| `make hae-start` | Start hae-server and hae-influxdb |
| `make hae-stop` | Stop health services |
| `make hae-restart` | Restart health services |
| `make hae-status` | Show container status |
| `make logs-hae` | Follow logs from both containers |
