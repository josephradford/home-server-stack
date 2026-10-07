# Odd Jobs: Life Admin Service (v1: Sports Calendars)

## Purpose

A small, self-hosted, AI-free service for "odd jobs" of life admin. Bede's dependency on the Claude CLI kept breaking, so this service is deterministic code only.

v1 handles one job: scrape official sports fixtures and publish them as subscribable `.ics` calendars for Apple Calendar. The design keeps the core generic so future odd jobs can be added as new modules without touching the scheduler or server.

## Success criteria

- Three calendars appear in Apple Calendar via subscription URLs, each toggleable independently:
  - Australia men's Tests
  - NSW men's Sheffield Shield
  - Parramatta first grade (NSW Premier Cricket, Belvidere Cup)
- Multi-day matches appear as one event per day ("Day 1", "Day 2", ...).
- Rescheduled fixtures update in place; no duplicate events.
- A broken scrape never empties a calendar, and staleness is alerted on.
- Adding a competition is a config edit; adding a new kind of job is a new module.

## Non-goals (v1)

UI, CalDAV, authentication, notifications beyond Prometheus/Alertmanager, any AI/LLM use, jobs other than sports calendars.

## Architecture

One container, `odd-jobs`, Python.

- **Location:** `services/odd-jobs/` in this repo, built locally via `make build`. No separate repo or GHCR image.
- **Compose:** new `docker-compose.jobs.yml`, added to the Makefile `COMPOSE` list. Bind mount `./data/jobs/`.
- **Routing:** `jobs.${DOMAIN}` via Traefik with the `admin-secure` chain (RFC1918 whitelist). Reachable at home and over WireGuard. Apple Calendar keeps the last fetched events when a refresh fails, so being unreachable away from home only means slightly stale data.
- **Core responsibilities (knows nothing about cricket):** load config, schedule jobs, run them one at a time, record status in SQLite, serve output files, expose `/healthz`, a status page and `/metrics`.
- **Job interface:** a module in `jobs/` declares a name, a schedule, and `run(ctx)`, which writes output files and returns a status. Sports calendars is the first job.
- **State:** SQLite in `data/jobs/` holds last run time, status and error per job. Output `.ics` files live in `data/jobs/out/`.

### Components

| Unit | Does | Depends on |
|------|------|-----------|
| `core/scheduler` | Runs each job daily at its configured time and once at startup; serial execution | config, state |
| `core/state` | SQLite run records | none |
| `core/server` | Serves `/<name>.ics`, `/healthz`, status page, `/metrics`, `POST /run/<job>` | state, output dir |
| `jobs/calendars` | Reads calendar config, calls adapters, builds `.ics` | adapters, `ics_builder` |
| `adapters/cricket_com_au` | Series page to `Fixture` list | httpx |
| `adapters/playhq` | GraphQL team fixture to `Fixture` list | httpx |
| `ics_builder` | `Fixture` list to `.ics` with per-day events | icalendar |

Libraries: `httpx`, `icalendar`, `PyYAML`, stdlib `sqlite3`, a small ASGI/HTTP server (FastAPI or Starlette), `prometheus_client`.

## Config

`data/jobs/calendars.yaml`:

```yaml
timezone: Australia/Sydney
calendars:
  - name: australia-tests
    title: Australia Men's Tests
    source: cricket_com_au
    series: ["CA:4605"]
    team: "Australia Men"
  - name: nsw-shield
    title: NSW Blues, Sheffield Shield
    source: cricket_com_au
    series: ["CA:4689"]
    team: "NSW Men"
  - name: parramatta-first-grade
    title: Parramatta First Grade
    source: playhq
    team_id: bb481fee
    team: "Parramatta First Grade"
```

Each `name` becomes `/<name>.ics`. Series IDs change every season, so the config lists them explicitly rather than discovering them. A new season means updating the IDs; the stale-feed alert signals when to do so.

## Data model

```
Fixture:
  source_id: str          # stable ID from the source
  competition: str
  title: str              # e.g. "Australia v New Zealand: 1st Test"
  home, away: str
  venue: str | None       # name, plus suburb when available
  days: list[Day]         # one per played date; may be non-consecutive
  status: scheduled | postponed | abandoned | completed
  url: str | None

Day:
  date: date
  start: time             # local, Australia/Sydney
```

`days` is a list, not a start/end pair, because grade cricket two-day games are often played a week apart (e.g. 17 and 24 Oct).

## Source adapters

Findings below were verified by live probes on 2026-10-07.

### cricket.com.au (Tests, Sheffield Shield)

- Each series page, `https://www.cricket.com.au/matches/series/<id>/<slug>`, embeds the full fixture list as `window.FIXTURES_DATA = JSON.parse('...')` in the HTML. The adapter extracts and decodes that blob (it is JS-string-escaped JSON).
- Fields used: `id`, `name` ("1st Test"), `startDateTime` and `endDateTime` (UTC), `numberOfDays`, `homeTeam.name`, `awayTeam.name`, `venue.name`, `isCompleted`.
- Times are UTC and are converted to `Australia/Sydney`. Day dates are derived from the converted start date plus `numberOfDays` consecutive days. Tests and Shield are played on consecutive days.
- Filter fixtures to the configured `team` (home or away).
- The site sends `x-ratelimit-limit: 15` per minute. One request per configured series per day is well within it.
- The unauthenticated `apiv2.cricket.com.au` API returns IDs without dates and is not used.
- **Open item:** the Shield series page returned 13 fixtures (5 NSW). Verify during implementation whether this is the full published schedule or a partial/paged view.
- **Risk:** this is HTML-embedded data on a public site, not a documented API. A site change could break it; see Failure handling.

### PlayHQ (Parramatta first grade)

- Endpoint: `POST https://api.playhq.com/graphql` with header `tenant: ca` and a plain identifying `User-Agent`. It works unauthenticated; it is the same endpoint the PlayHQ web app uses for anonymous visitors. It is not the documented keyed REST API.
- Query: `discoverTeamFixture(teamID: "<team_id>")` returns all rounds for the team's grade. Each round lists every game in the grade, so the adapter filters to games where the configured `team` is home or away. Team names need inline fragments on `DiscoverTeam` and `ProvisionalTeam`.
- Fields used: `game.id`, `game.dates`, `status.value`, `allocation.dateTimeList[{date, time}]`, `allocation.court.venue{name, suburb}`, `gameType.name`, round name, `provisionalDates`.
- Times are local Sydney clock times with no timezone (confirmed against the PlayHQ website). The adapter treats them as `Australia/Sydney`.
- Verified result: 16 rounds, 3 Oct 2026 to 6 Mar 2027; one-day and "Two Day+" games; 10:00 starts (09:30 in round 2); venue names such as Old Kings Oval.
- `team_id` is the last URL segment of the team page on playhq.com.
- **Risk:** undocumented use, and PlayHQ may change it or restrict automated access. Mitigations: one request per day, a plain User-Agent, last-good-file behaviour. Fallback is requesting an official API key.

## Event generation

- One event per `Day`. Title: `<title>, Day N` for multi-day fixtures (e.g. "Australia v New Zealand: 1st Test, Day 2"); no suffix for single-day. Grade games read "Parramatta v Northern District, Day 1 of 2".
- Start: source start time in Australia/Sydney. Default duration: 6 hours for Tests and Shield, 7 hours for grade cricket (configurable).
- Location: venue. URL: official match or team page.
- Status: postponed or abandoned adds "[Postponed]" or "[Abandoned]" to the title; events are kept, not deleted.
- UID: `<calendar-name>-<source_id>-d<N>@jobs.<domain>`. Stable across runs so reschedules update in place. If a later refresh has fewer days for a fixture (e.g. a Test ends early), the missing days disappear.
- Calendar-level properties: `X-WR-CALNAME` set to the title, `X-WR-TIMEZONE`, and `REFRESH-INTERVAL` / `X-PUBLISHED-TTL` of 1 day.
- Output is written to a temp file and renamed into place atomically.

## Scheduling

Each job runs once a day at about 04:00 local and once at container start. Jobs run serially. HTTP timeout 30 s with one retry. `POST /run/<job>` triggers a manual run (reachable only through `admin-secure`).

## Failure handling

A run fails if it raises an exception, or if it returns zero fixtures when the previous successful run had some. On failure:

- the previous `.ics` stays in place and keeps being served;
- the error is recorded in SQLite and shown on the status page;
- `odd_jobs_last_success_timestamp_seconds{job}` stops advancing and `odd_jobs_last_run_ok{job}` goes to 0.

An alert rule in `monitoring/prometheus/alert_rules.yml` fires if a job has not succeeded in 3 days.

## Serving

- `GET /<name>.ics`: `Content-Type: text/calendar; charset=utf-8`. Returns 404 if no successful run has produced the file yet.
- `GET /healthz`: 200 when the process is up.
- `GET /`: status page listing each job's last run, status and error.
- `GET /metrics`: Prometheus metrics.

## Integration

- `.env.example`: any new variables (job run time, durations) with descriptions.
- Homepage tile in `config/homepage/services-template.yaml` with `showStats: true`.
- `SERVICES.md` entry.
- Prometheus scrape config for `odd-jobs:<port>/metrics` and the stale-job alert rule.
- Makefile: add the compose file to `COMPOSE`; add `make jobs-probe` (see Testing) and `make logs-odd-jobs` via the existing pattern.
- Follow the Traefik label pattern in CLAUDE.md.

## Testing

- Saved real responses from each source (the series page JSON blob and the GraphQL result) are checked into the repo as test fixtures.
- Unit tests, with no network access, cover: adapter parsing and team filtering, UTC to Sydney conversion, per-day expansion including non-consecutive days, UID stability across runs, postponed handling, zero-fixture failure handling, and `.ics` output validity.
- `make jobs-probe` calls each live source once and reports whether the adapters still parse them, for checking after a suspected source change without running the service.
- Per the repo checklist: `make validate` passes, the service starts healthy, no log errors, `make test-domain-access` covers `jobs.${DOMAIN}`.

## Adding things later

- New competition on an existing platform: a config block.
- New platform: a new adapter returning `Fixture` objects.
- New kind of odd job: a new module in `jobs/` implementing the job interface. No change to core.

## Open items

1. Confirm the Sheffield Shield series page lists the full season (see cricket.com.au adapter).
2. Confirm in Apple Calendar that subscribed `.ics` refreshes work against `jobs.${DOMAIN}` (private DNS and a certificate valid for the wildcard domain).
3. Decide the container port and the internal framework (FastAPI vs Starlette) at plan time.
