# Bede — Design Document

**Version:** 1.0
**Date:** 2026-04-29
**Author:** Joe Radford + Claude
**Status:** Draft — awaiting review
**Requirements:** [Bede Requirements Document](2026-04-29-bede-requirements.md)

This document describes how Bede will be built to satisfy the requirements. It covers architecture, component design, data flow, and operational concerns. It does not cover implementation sequencing — that belongs in a separate plan.

---

## 1. Design Principles

These principles guided every decision in this document. When a future choice isn't covered here, use these to decide.

1. **Prototype-informed, not prototype-constrained.** The current system taught us what works and what doesn't. This design preserves what works and replaces what doesn't — it is not an incremental patch.
2. **Swappable dependencies.** Claude CLI is the AI engine today. The design abstracts it behind interfaces so the engine can be replaced (subscription API, local model) without restructuring the system.
3. **Code for computation, Claude for conversation.** Pattern detection, trend analysis, and threshold checking are deterministic code. Interpreting patterns, coaching, and conversation are Claude's job. Don't use AI where a `for` loop works.
4. **No silent failures.** Every failure that affects the user must be surfaced. If something breaks at 3am, the user finds out at a reasonable hour — not never.
5. **Configuration through conversation.** The user changes Bede's behaviour by talking to Bede. Config files are the storage mechanism, not the input method.
6. **Vault is curated, not a dumping ground.** Bede writes to SQLite freely. Only content the user would want to find in Obsidian later gets published to the vault.
7. **Lighter AI demands.** Minimise Claude session usage by pre-computing what can be pre-computed. Save Claude for what it's good at.
8. **Extensible by default.** The architecture supports adding new data sources (new Ingest API parsers), new scheduled tasks (new SQLite config rows), new capabilities (new MCP sidecars), and swapping the AI engine — all without rewriting existing functionality.

---

## 2. Container Architecture

Three application containers plus MCP sidecars, orchestrated by Docker Compose.

### 2.1 bede-core

The brain. Manages conversations, schedules, sessions, and memory.

**Processes:**
- **Bot** — Telegram message handler. Receives messages, authenticates the user (single allowed ID), passes messages to the Session Manager, formats responses (Markdown → Telegram HTML, with message chunking for Telegram's 4096-character limit), sends replies. Shows a typing indicator while Claude is processing (periodic, with a safety timeout to prevent indicator loops — the prototype had a bug where the typing indicator got stuck in an infinite loop). Target response time is 30 seconds; the typing indicator covers any delay beyond that. Handles Telegram commands by delegating to the Scheduler. If Claude is unavailable, acknowledges receipt and queues the message for processing when service resumes (see Section 10).
- **Scheduler** — APScheduler with cron triggers. Reads task definitions from SQLite via the Data API. Polls for config changes on a timer. Fires tasks through the Session Manager. Logs every execution to SQLite via the Data API (task name, start time, duration, status, error detail). Manages interactive task handoff (task yields to chat for user corrections). Implements C7 fallback: 3 unanswered attempts → non-interactive delivery.
- **Session Manager** — Abstracts Claude CLI subprocess lifecycle. Exposes a simple interface: `send(message, context) → response`. Manages the daily session (see Section 3). Injects context (memories, date/time, daily scratchpad) before each interaction. Swappable — the rest of the system does not know it's a CLI subprocess. On early interactions when data sources are sparse or memories are few, Claude operates in a degraded-but-functional mode — this progressive learning is intentional, not an error. Claude is instructed to ask natural discovery questions to fill gaps over time.
- **Memory Manager** — Proposes, stores, retrieves, and manages memories. Stores in SQLite via the Data API. Surfaces relevant memories to the Session Manager for context injection. Handles corrections (new correction overrides previous memory on the same topic).

**Does not contain:** Data storage, analytics, MCP servers, web serving.

### 2.2 bede-data

The data layer. Ingests, stores, analyses, and serves all data.

**Processes:**
- **Ingest API** — HTTP server receiving external data pushes. Bearer token authentication. Writes to SQLite using upsert-by-natural-key — idempotent, no data loss on duplicate submissions, late-arriving records insert cleanly. See Section 13 for the complete data inputs inventory.
- **Analytics Engine** — Runs periodically (configurable, e.g., every few hours and on new data arrival). Computes derived signals from raw data and stores structured flags in SQLite. Pure Python, deterministic thresholds, no AI. See Section 5.
- **Data API** — HTTP server serving data to Core, Web UI, and the MCP proxy. Read endpoints: health summaries, screen time, trends/flags, location, weather, task execution history, memories, goals, conversation history (indexes and serves Claude session files), data freshness status, storage usage. Write endpoints: store memories, log task executions, update goals, manage vault publish queue, update configuration. All date handling normalised to user's timezone.
- **SQLite** — Single database file, WAL mode for concurrent reads. Single writer (this container). Schema versioned with proper migrations. Single source of truth for schema definition.

### 2.3 bede-web

The display layer. Read-only web UI for richer content display.

- Static web app served by a lightweight HTTP server (e.g., Caddy, nginx)
- Calls bede-data's API for content
- Accessed at `bede.DOMAIN` via Traefik, secured behind admin-secure middleware (IP whitelist + security headers)
- Read-only by default. The Data API supports write endpoints, and the web UI can be extended to use them when a specific use case earns it.
- Displays: today's briefing, journal entries, goal progress, memory list, task execution history, deal monitoring results, data freshness status, conversation history browser, storage usage

### 2.4 MCP Sidecars

Separate containers, not inside Core. Stay up when Core restarts.

- **bede-workspace-mcp** — Google Workspace (Gmail, Calendar, Tasks). OAuth credentials bind-mounted from host with auto-refresh.
- **bede-browser-mcp** — Playwright headless browser for web browsing (deal monitoring, content curation).
- **bede-data-mcp** — Thin proxy MCP server that forwards tool calls to bede-data's HTTP API. This is how Claude discovers and calls personal data tools. No logic of its own — schema definition and HTTP forwarding only.

### 2.5 Communication

```
External (Mac/iPhone)
    │
    ▼ HTTPS (bearer token, rate-limited)
┌──────────┐
│ bede-data │◄──── HTTP ────── bede-web (read-only)
│          │◄──── HTTP ────── bede-core
│  SQLite  │◄──── HTTP ────── bede-data-mcp (proxy)
└──────────┘
                    
Claude (inside bede-core) ──── MCP ────► bede-data-mcp (personal data tools)
                          ──── MCP ────► bede-workspace-mcp (Gmail, Calendar, Tasks)
                          ──── MCP ────► bede-browser-mcp (Playwright)

All containers on the same Docker network.
Traefik routes:
  - data.DOMAIN → bede-data ingest API (webhook-secure middleware)
  - bede.DOMAIN → bede-web (admin-secure middleware)
  - mcp.DOMAIN  → bede-workspace-mcp OAuth callback (as today)
```

---

## 3. Daily Session Continuity

All interactions within a day (scheduled tasks and user messages) share a single Claude session. This provides genuine conversational continuity — the evening reflection remembers the morning briefing because it was the same conversation.

### Session lifecycle

1. **First interaction of the day** (typically the morning briefing) starts a fresh Claude session. The session ID is stored in SQLite.
2. **Subsequent interactions** (scheduled tasks, user messages) resume the daily session via `--resume <session_id>`.
3. **If resumption fails** (session expired, corrupted, too large), the Session Manager falls back to a fresh session and injects the **daily scratchpad** — a structured summary of all prior interactions that day.
4. **End of day** (midnight in the user's timezone): the daily session expires. Next day's first interaction starts fresh.

### Daily scratchpad

After each interaction (scheduled or conversational), the Session Manager asks Claude to generate a brief structured summary and appends it to the scratchpad in SQLite. This is Claude-generated (not deterministic code) because summarising what was discussed, decided, and emotionally significant requires judgement. The cost is one additional inference call per interaction; the benefit is a high-quality fallback that preserves conversational continuity when session resumption fails.

```
[08:00] Morning Briefing: 2 calendar events, flagged poor sleep (3rd night), 
        user said "I'm fine, just stayed up late". 3 emails triaged.
[12:34] User chat: Asked about weekend camping spots. Suggested Blue Mountains.
[20:00] Evening Data Check: All data sources received. No gaps.
[21:00] Evening Reflection: Journal written. User set new goal: read 2 books in May.
```

The scratchpad is the fallback context. It is not a full transcript — it captures what was discussed, decided, and flagged, in enough detail for Claude to continue coherently.

---

## 4. Memory System

Memories are facts, preferences, corrections, and commitments that persist across days, weeks, and months. They are distinct from the daily scratchpad (which is intra-day context) and from analytics flags (which are computed signals).

### Memory types

| Type | Example | Retention |
|------|---------|-----------|
| Fact | "Training for a half marathon" | Until user deletes or corrects |
| Preference | "Don't nag about meditation" | Until user deletes or corrects |
| Correction | "I said X but it's actually Y" | Overrides previous memory on same topic |
| Commitment | "Finish AWS cert by September" | Stored as a goal (see Section 5) |

### Memory lifecycle

1. **Proposal**: After each conversation, Claude proposes memories: "I'd like to remember that you're training for a half marathon — ok?"
2. **Confirmation**: User confirms, edits, or rejects. Only confirmed memories are stored.
3. **Storage**: Memories stored in SQLite via the Data API. Fields: content, type, created date, last referenced date, source conversation.
4. **Retrieval**: Before each Claude interaction, the Session Manager queries for relevant memories. Relevance scoring is an implementation detail (options include keyword matching, SQLite FTS5 full-text search, or embedding-based similarity) — the requirement is that relevant memories surface and irrelevant ones don't. Injected into Claude's system prompt.
5. **Budget**: Total memory injection is capped per interaction to avoid flooding the context window. Most recent and most relevant memories prioritised.
6. **Review**: Web UI shows all stored memories — searchable and filterable. User can edit or delete. Telegram command to list recent memories.
7. **Correction**: A correction memory overrides the previous memory on the same topic. Bede does not accumulate contradictions.

### Transparency

Memories are fully inspectable. The user can see everything Bede has stored about them, when it was stored, and which conversation it came from. No hidden internal model.

---

## 5. Coaching & Accountability

R1 (mental health coaching) and R2 (goal accountability) share the same architecture: deterministic analysis produces flags, Claude interprets the flags and has the conversation.

### Analytics Engine — flag computation

The Analytics Engine runs periodically and computes structured flags from raw data:

| Signal | Data source | Example flag |
|--------|-------------|-------------|
| Sleep declining | Health data (sleep duration, quality) | `{ signal: "sleep_declining", severity: "concern", window: "3 days", detail: "avg 5.2h vs 7h target" }` |
| Exercise gap | Health data (workouts) | `{ signal: "exercise_gap", severity: "nudge", days_since: 5 }` |
| Medication missed | Health data (adherence) | `{ signal: "medication_missed", severity: "alert", detail: "evening dose skipped" }` |
| Screen time spike | Screen time data | `{ signal: "passive_screen_up", severity: "info", detail: "YouTube +40% this week" }` |
| Goal stale | Goal progress tracking | `{ signal: "goal_stale", severity: "nudge", goal: "AWS cert", days_inactive: 10 }` |
| Goal drifting | Goal progress vs plan | `{ signal: "goal_drifting", severity: "concern", goal: "read 2 books", detail: "0 of 2, 3 weeks remaining" }` |
| Bedtime drift | Health data (sleep times) | `{ signal: "bedtime_drifting", severity: "info", detail: "avg bedtime shifted 45min later" }` |

Severity levels: `info` (logged, available if asked), `nudge` (raised at next check-in), `concern` (raised proactively via Telegram), `alert` (raised immediately, respecting quiet hours).

All thresholds are configurable in SQLite: what counts as "poor sleep", how many days before a goal is "stale", what percentage change triggers a screen time flag. Changed through conversation or directly via the Data API.

### Coaching flow

1. **Scheduled coaching check-in** (daily, configurable time): Session Manager passes active flags + relevant memories to Claude.
2. Claude interprets the flags in context — connects dots across signals (poor sleep + dropped exercise + goal drift = a pattern worth discussing), considers what the user said recently, and has the conversation.
3. **Proactive nudges**: flags at "concern" or "alert" severity trigger an immediate Telegram message (outside the scheduled check-in). Configurable: user can suppress nudges per signal, set quiet hours (default 10pm–7am, stored in SQLite, changeable via conversation). During quiet hours, nudges queue and deliver when quiet hours end. "Alert" severity also respects quiet hours — there is no override level, since this is a personal assistant, not a medical device.
4. **"Back off" support**: user tells Bede to back off on a topic → stored as a memory → coaching respects it. The memory has the same lifecycle as any other — user can reverse it later.
5. **Crisis safety**: if Claude detects signals of serious distress or crisis, it must recommend professional resources (e.g., crisis helplines, GP, psychologist) and not attempt to manage the situation itself. Bede is a coaching tool, not a clinical service. This behaviour is enforced via Claude's system prompt and is non-configurable.

### Goal management

Goals enter the system through conversation:
- User tells Bede about a goal → Bede proposes storing it (same confirm pattern as memories) → stored in SQLite via Data API
- Fields: name, target description, deadline (optional), measurable indicators, current status
- Analytics Engine starts tracking immediately
- Goals are reviewed during coaching check-ins and weekly planning sessions
- User can update goals conversationally: "push the deadline", "drop that goal"
- Web UI shows all active goals and progress (read-only)

---

## 6. Day & Week Planning

### Daily briefing

1. Scheduler fires the morning briefing task (configurable time, default 8am weekdays).
2. Bede sends an opening message via Telegram with what it knows:
   - Calendar events for today (via workspace-mcp)
   - Weather and air quality (via Data API)
   - Active flags from Analytics Engine (poor sleep, goal nudges)
   - Email triage proposals (pre-scanned, categorised as task / event / dismiss)
   - Pending reminders and tasks
3. Bede asks questions: "Anything else on your plate today?" / "Want to adjust these priorities?"
4. User responds, Bede incorporates and delivers the final day view.
5. C7 fallback: if no response after 3 attempts, Bede sends a non-interactive version.

### Email triage

Folded into the daily briefing (replaces the current separate email triage task):
- Bede scans inbox via workspace-mcp before the briefing
- Pre-categorises each actionable email: task, event, or dismiss
- Presents proposals in the briefing with proposed actions
- User confirms or corrects via Telegram reply
- Confirmed actions: Bede creates Google Tasks, creates Calendar events, or marks as handled

### Evening reflection

- Scheduled task (daily, configurable time, e.g., 9pm)
- Gathers the day's data: Claude Code sessions, screen time, vault git history, location timeline, calendar events, workouts, any tasks completed
- Interactive — Bede presents what it observed and asks the user to fill gaps or correct the record
- Produces a journal entry with two distinct parts:
  1. **Daily activity record** — structured summary of what the user worked on, where they went, what they accomplished. Built from data, not just self-report. This is the "what I did" section.
  2. **Reflection** — coaching-informed observations, pattern connections, goal progress notes. This is the "how it's going" section.
- Journal entry is published to the vault (selective publish — one of the items that earns its place in Obsidian)
- C7 fallback: if no response, Bede writes a best-effort journal from data alone (no reflection input from user)
- Same daily session — the reflection has full context from the morning briefing and any conversations during the day

### Weekly planning

- Scheduled task, configurable (e.g., Sunday evening)
- Reviews the week ahead: calendar events, upcoming deadlines, active goals, carryover tasks
- Interactive — asks about priorities and intentions for the week
- Natural moment to review goal progress and add/update goals
- Same daily session model — starts or continues the day's session

---

## 7. Stay Current & Deal Monitoring

### Stay current (R3)

- Scheduled task, configurable cadence per topic (daily, weekly)
- Bede browses configured sources via browser-mcp
- Sources and topics defined in SQLite config
- Curates a summary (signal, not firehose) and delivers via Telegram
- Currently delivered as part of the morning briefing (news digest section)
- Content the user wants to keep can be captured to the vault (selective publish, user confirms)

### Deal monitoring (R9)

- Scheduled task, configurable per category (e.g., weekly)
- Categories and preferences defined in SQLite config
- Bede browses retailer sites via browser-mcp
- **Only reports when something actionable changed** — price drop, restock, new item matching criteria
- Results stored in SQLite (price history, stock status, timestamps)
- Operational memory (dead URLs, price trends) stored in SQLite (replaces current vault-based memory file)
- Alerts delivered via Telegram

Both features follow the same pattern: scheduled task + browser-mcp + conditional delivery.

---

## 8. Knowledge Base & Vault Integration

### Reading from the vault

- Vault is git-cloned onto the server
- Server pulls from git on a configurable schedule (requirement: under 1 minute freshness for captures)
- Claude has filesystem access to the vault for searching and reading notes
- If git pull fails, Bede continues with the last successful pull and surfaces the failure to the user

### Writing to the vault — selective publish

Bede's primary write target is SQLite. The vault receives only content the user would want to find in Obsidian:

**Published to vault:**
- Journal entries (formatted from evening reflection)
- Captured ideas/thoughts (when user explicitly says "save this to my vault")

**Not published to vault:**
- Coaching check-in logs
- Deal scout results
- Task execution records
- Email triage results
- Computed analytics flags
- Raw memories

### Publish mechanism

- A publish queue in SQLite holds items approved for vault publishing
- A background process picks items off the queue, writes Markdown files, git commits and pushes
- If git push fails, items stay in the queue and retry — no data loss
- The vault is not a live dependency — if sync breaks, Bede keeps working

### Search

- Claude searches the vault via filesystem tools (grep, find)
- No vector database or embedding search. If this becomes a limitation, it is a future improvement.

---

## 9. Configuration

### Configuration split

| What | Where | Why |
|------|-------|-----|
| Personality, tone, boundaries | Vault Markdown (`soul.md`) | Prose — human-authored, read by Claude directly as natural language |
| User context | Vault Markdown (`user.md`) | Prose — background context for Claude |
| Schedules, thresholds, cadences | SQLite (managed via conversation) | Structured — easy to query, modify programmatically, and display in web UI |
| Monitored items (deals, sources) | SQLite (managed via conversation) | Structured — same benefits, no YAML parse/write complexity |
| Goals | SQLite (managed via conversation) | Dynamic — created, updated, completed over time |
| Memories | SQLite (managed via conversation) | Dynamic — proposed, confirmed, corrected over time |

SQLite is the single store for all structured configuration. This eliminates YAML parsing, file write-back complexity, and hot-reload file watching. The web UI and Telegram commands provide human-readable access. The user can still change any setting through conversation with Bede. Only prose config (personality, user context) stays in the vault because Claude reads it directly as natural language.

**Deviation from requirements:** The requirements document (Section 5, Configurability) states "Configuration should be stored as human-readable files, not in databases or admin UIs." This design deliberately overrides that requirement. The prototype stored configuration in Markdown files in the Obsidian vault, which revealed several shortcomings: programmatic modification of Markdown is fragile (parsing structured data from prose, rewriting without breaking formatting or comments), the vault sync pipeline (iCloud → Mac → git push → server git pull) adds latency and failure modes between a config change and it taking effect, and hot-reloading requires file-watching infrastructure. SQLite eliminates all three problems while still meeting the spirit of the requirement — configuration is inspectable (via web UI and Telegram commands), editable (via conversation), and portable (single file, easy to back up and restore).

### Configuration through conversation

The user changes Bede's behaviour by talking to Bede:
- "Check for deals on camping gear every week" → Bede updates deal monitoring config in SQLite
- "Move my morning briefing to 7:30" → Bede updates the schedule config in SQLite
- "Be more direct when coaching" → Bede updates soul.md in the vault
- "I'm training for a half marathon" → Bede proposes a goal, stores in SQLite

Bede proposes the change, the user confirms, Bede writes to the appropriate store. Prose changes go to vault files; everything else goes to SQLite.

### Hot-reload

Structured config changes in SQLite are picked up by the Scheduler on a configurable polling timer. Vault prose changes are picked up on the vault sync schedule. No container restart required for any config change.

---

## 10. Observability & Reliability

### Task audit trail

Every scheduled task execution logged to SQLite: task name, start time, duration, status (success/failure/timeout), error detail. Queryable via Data API. Web UI shows execution history. Telegram alert on task failure (configurable per task).

### Data pipeline monitoring

Analytics Engine tracks data freshness per source. If a source goes stale beyond its expected freshness window, a flag is raised and the user is notified:

| Source | Expected freshness |
|--------|-------------------|
| Calendar, email, tasks | 15 minutes |
| Location | Near real-time when queried |
| Weather | Hourly |
| Health, screen time, browsing, media | Daily |
| Knowledge base | Under 1 minute |
| Conversation history | Immediate (within-session); under 1 minute (cross-session via Data API) |
| Goals and schedule | On change |

### Message queuing

If Claude is unavailable (service outage, session failure that cannot be retried), the Bot acknowledges receipt via Telegram ("Got it — Claude is temporarily unavailable, I'll process this when it's back") and queues the message in SQLite. A background retry loop checks availability periodically and processes queued messages in order when service resumes. Scheduled tasks that fail due to Claude unavailability are also queued for retry.

### Error surfacing

No silent failures. Every caught exception that affects user-facing functionality is reported via Telegram. Categories: data pipeline failure, vault sync failure, Claude session failure, MCP server unreachable, OAuth expiry. Quiet hours respected — errors queue and deliver when quiet hours end.

### Health checks

Each container exposes a `/health` endpoint. Docker Compose healthchecks configured — containers restart on failure. Prometheus can scrape for dashboard/alerting (optional, leverages existing monitoring stack).

### Conversation history

Claude CLI automatically creates session files (JSONL) on the server's filesystem when invoked. These are the authoritative conversation history — full transcripts of every interaction, not summaries. The session files directory is bind-mounted as a persistent volume so history survives container restarts. Conversation history is reviewable by reading these files directly or via a Data API endpoint that indexes and serves them. The daily scratchpad (Section 3) is a lightweight summary for context injection, not a replacement for the full transcript.

### Backup & recovery

All state lives in `./data/bede/` — the SQLite database, Claude session files, and any other persistent data. The Claude session files bind-mount must resolve to a path inside `./data/bede/` (e.g., `./data/bede/claude-sessions/`) so that a single directory copy captures everything. Backup = copy the directory. Recovery = restore the directory, `docker compose up`. Vault is separately backed up via git. Recovery process documented in a runbook.

### Storage visibility

A Data API endpoint returns database size and row counts per table. The web UI displays current storage usage by data type, so the user can see what's consuming space and adjust retention settings if needed.

### Data retention

Configurable TTLs per data type in SQLite config. A periodic cleanup job prunes expired data.

| Data type | Default retention |
|-----------|------------------|
| Memories, journal entries | Indefinite (unless user deletes) |
| Goals (including completed) | Indefinite |
| Raw health/screen time/browsing | 90 days |
| Task execution logs | 30 days |
| Analytics flags | Rolling window |
| Daily scratchpads | 7 days |
| Deal monitoring price history | 180 days |

---

## 11. Security

### Authentication & access control

- Telegram: single allowed user ID per message (as today)
- Data ingest API: bearer token authentication, rate-limited via Traefik
- Web UI: Traefik admin-secure middleware (IP whitelist to local/VPN subnets + security headers)
- MCP OAuth callback: exposed for Google Workspace auth flow only
- No public-facing endpoints beyond ingest and OAuth callback

### Data in transit

- All external communication over HTTPS (Traefik with Let's Encrypt wildcard certs)
- Internal container communication over Docker network (not exposed to host)

### Secrets management

- Secrets in `.env` file, never committed to version control
- OAuth credentials bind-mounted from host with auto-refresh
- API keys and tokens passed as environment variables

### Claude session isolation

- Claude CLI runs with `--dangerously-skip-permissions` (required for tool use)
- Mitigated by: CLAUDE.md boundaries, single-user system, no public access to Claude sessions
- Environment variable filtering: sensitive tokens (Telegram bot token, ingest write token) excluded from Claude subprocess environment

---

## 12. Voice (R7) — Future Slot-in

Voice interaction is deferred from this design. The architecture supports adding it later:

- Voice messages received via Telegram → transcribed (STT service) → processed as text by Session Manager
- Responses optionally converted to audio (TTS service) → sent as Telegram voice message
- The Session Manager's `send(message, context) → response` interface does not change — voice is a pre/post-processing layer on the Telegram bot, not a new component.

No voice pipeline, STT/TTS service selection, or latency requirements are designed here. When voice is implemented, it will be a contained addition to the bot process in bede-core.

---

## 13. Data Inputs Inventory

Complete list of data sources the system ingests, how they arrive, and how they are queried. This maps to Section 4 of the requirements document.

### Pushed via Ingest API

These arrive as HTTP POSTs from external collectors (Mac launchd jobs, iPhone apps).

| Data source | What's collected | Natural key | Collector |
|-------------|-----------------|-------------|-----------|
| Sleep | Duration, quality, phases (core/deep/REM/awake), bedtime/wake time | date + source | Health Auto Export (iPhone) |
| Activity | Steps, exercise minutes, stand hours, active energy, move time | date + metric | Health Auto Export (iPhone) |
| Workouts | Type, duration, active energy, avg/max heart rate | date + start_time | Health Auto Export (iPhone) |
| Heart rate | Resting heart rate, heart rate variability | date + metric | Health Auto Export (iPhone) |
| Medications | Adherence tracking per medication | date + medication | Health Auto Export (iPhone) |
| State of mind | Valence, labels, context/associations | date + timestamp | Health Auto Export (iPhone) |
| Mindfulness | Mindfulness minutes | date + metric | Health Auto Export (iPhone) |
| Screen time (Mac) | App usage duration, web domain usage | date + device + app | Mac launchd (knowledgeC.db) |
| Screen time (iPhone) | App usage duration | date + device + app | Mac launchd (Biome SEGB files via iCloud) |
| Safari history | URL, title, visit time, device (Mac/iPhone) | url + visited_at | Mac launchd (History.db via iCloud) |
| YouTube history | URL, title, visit time | url + visited_at | Mac launchd (subset of Safari history) |
| Podcasts | Episode, show, duration, play time | episode + played_at | Mac launchd (MTLibrary.sqlite) |
| Claude Code sessions | Project, start/end time, turns, AI-generated summary | project + start_time | Mac launchd (claude-sessions.py) |
| Bede sessions | Task name, start/end time, summary | task + start_time | Internal (bede-core logs) |
| Music listening | Tracks, artists, play counts, listening time | track + listened_at | Last.fm API (scrobble history) |

### Queried live (not stored)

These are fetched on demand when Claude needs them.

| Data source | What's returned | Provider |
|-------------|----------------|----------|
| Location | GPS clusters → named places, arrived/departed times | OwnTracks Recorder (existing infrastructure — runs as a container in the home-server-stack, receives MQTT from the OwnTracks iPhone app) + Nominatim geocoding |
| Weather | Current conditions, 7-day forecast, temperature, wind, rain, UV | BOM via homepage-api |
| Air quality | Air quality index and alerts | NSW Air Quality API (airquality.nsw.gov.au) |
| Calendar events | Personal calendar events | Google Calendar via workspace-mcp |
| Email | Inbox contents, search, read, send/reply | Gmail via workspace-mcp |
| Tasks/Reminders | Active tasks, completion status, create new | Google Tasks via workspace-mcp |

### Read from vault

| Data source | What's accessed | Access method |
|-------------|----------------|---------------|
| Knowledge base | Notes, journal entries, structured files | Filesystem (grep, find, read) |
| Personality and user context | soul.md, user.md | Filesystem (read) |
| Vault activity | Recent changes to notes and files | Git log on vault repo |

### Read from SQLite (managed via conversation)

| Data source | What's accessed | Access method |
|-------------|----------------|---------------|
| Goals | Current goals, deadlines, progress | Data API |
| Schedules and thresholds | Task schedules, coaching thresholds, cadences | Data API |
| Memories | Stored facts, preferences, corrections | Data API |
| Monitored items | Deal categories, content sources | Data API |

### Derived by Analytics Engine

| Signal | Derived from | Output |
|--------|-------------|--------|
| Sleep trends | Sleep data (rolling window) | Structured flags |
| Activity trends | Activity + workout data | Structured flags |
| Goal staleness | Goal definitions + progress signals | Structured flags |
| Screen time patterns | Screen time data (rolling window) | Structured flags |
| Medication adherence | Medication data | Structured flags |
| Bedtime drift | Sleep data (bedtime timestamps) | Structured flags |

---

## 14. What This Design Does Not Cover

- **Implementation sequencing.** What gets built first, phasing, milestones — belongs in an implementation plan.
- **Migration from prototype.** How to get from the current system to this design — belongs in the implementation plan.
- **Web UI specifics.** What the web UI looks like, which framework, component design — belongs in a separate frontend design if needed.
- **SQLite schema.** Exact table structures for config, analytics, memories — defined during implementation.
- **Claude prompt engineering.** System prompts, tool descriptions, coaching prompt design — defined during implementation.
- **Testing strategy.** Unit, integration, and end-to-end test approach — defined in the implementation plan.
- **Recovery runbook.** Step-by-step recovery procedure for hardware failure — written during implementation alongside backup setup.
