# Bede — Requirements Document

**Version:** 1.0
**Date:** 2026-04-29
**Author:** Joe Radford + Claude
**Status:** Draft — awaiting review

This document defines what Bede must do and the constraints it must operate within. It is deliberately implementation-agnostic — it says nothing about architecture, technology choices, or how the requirements should be met. Design decisions belong in a separate design document.

---

## 1. What is Bede?

Bede is a personal assistant for a single user. It knows about the user's health, activity, location, calendar, email, screen time, goals, and knowledge base. It uses this context to coach, inform, remind, and assist — proactively on a schedule and reactively on demand.

Bede is powered by Claude (Anthropic's large language model) via a subscription. This is a pragmatic constraint — Claude is the reasoning engine, but Bede is not a thin wrapper around it. Bede is the product; Claude is a dependency.

---

## 2. Requirements

Requirements are listed in priority order. Each requirement stands on its own — the system must deliver value for each independently, not only when all are working together.

### R1. Mental health coaching

**I want to be coached to keep my mental health issues of anxiety and depression in check.**

Bede must have access to signals relevant to mental health: sleep quality and duration, physical activity, medication adherence, mood indicators, and behavioural patterns (e.g., social isolation, routine disruption). It must surface concerns proactively and honestly — not wait to be asked. It must track patterns over time, not just react to single data points. It must be direct without being clinical, and supportive without being patronising.

Coaching means ongoing, not reactive. Bede should check in regularly, notice when things are slipping before the user does, and connect dots across days and weeks. A single bad night's sleep is not a concern; three in a row alongside dropping exercise is.

The coaching relationship must be configurable — The user controls the tone, the boundaries, and what topics are in scope. If the user says "back off on this topic," Bede must respect that immediately and durably.

**Success looks like:** The user feels like someone is genuinely watching out for him and will say something honest when patterns emerge — not just echoing data back.

**Measurable indicator:** Bede surfaces a concern about a negative pattern within 48 hours of the pattern emerging (e.g., 3 consecutive poor sleeps flagged by day 4).

### R2. Goal accountability

**I want to be held accountable to my personal and professional goals.**

Bede must know the user's current goals (professional certifications, hobbies like camping/piano/reading, fitness targets, career direction) and track progress toward them. It must notice when effort is drifting — too much mindless device time, skipped practice sessions, stalled projects — and call it out.

Accountability means measuring reality against intention. Bede must know what the user said he would do (goals, weekly schedule) and what he actually did (screen time, media consumption, activity, location, calendar, task completion, vault edits). The gap between those is what matters.

This is closely linked to R1 — poor mental health often causes goal drift, and goal drift often worsens mental health. Bede must understand this connection and not treat them as independent.

**Success looks like:** The user can't quietly let a goal slide for two weeks without Bede noticing and raising it.

**Measurable indicator:** No active goal goes unmentioned for more than 14 days without progress.

### R3. Stay current without effort

**I want to stay current in my professional and personal interests without having to go looking.**

Bede must curate and deliver relevant content from the user's areas of interest — professional (software engineering, AI, cloud) and personal (music, camping, whatever The user defines). The user should not have to seek out this information himself; Bede should bring it to him in a digestible format.

The sources, topics, and delivery cadence must be configurable by the user. Bede must be able to distinguish signal from noise — a curated summary is valuable, a firehose is not.

**Success looks like:** The user learns about things that matter to him without opening a browser to go looking.

**Measurable indicator:** The user receives at least one curated content delivery per configured topic per week.

### R4. Day and week planning

**I want to know what my day and week look like before they start — including emails triaged into tasks, events, or dismissed.**

Bede must prepare a view of the upcoming day (and week, at appropriate cadence) that includes: calendar events, weather, air quality, relevant reminders and tasks, and any actions extracted from email. Email triage follows a strict pattern: each email becomes a task, becomes an event, or is dismissed as requiring no action. Bede proposes the classification; the user confirms or corrects.

This must be delivered proactively before the day/week starts, not on demand. The delivery must be interactive — Bede asks questions, the user provides input, then Bede delivers the final view. The user must be able to correct, reprioritise, or add items during the interaction.

If the user does not respond to the interactive prompt, Bede retries up to three times total. If there is still no response, Bede sends a non-interactive version (best-effort summary without the user's input) so the information is not lost entirely.

**Success looks like:** The user starts each day and week knowing exactly what's ahead, with no unprocessed email creating background anxiety.

**Measurable indicator:** The user receives a day briefing before his day starts on 90%+ of weekdays.

### R5. Personal knowledge base

**I want my personal knowledge base to grow naturally and be easy to search.**

Bede must integrate with the user's personal knowledge base (currently an Obsidian vault organised using the PARA method). It must be able to read from and write to the knowledge base. Writing includes: journal entries, meeting notes, captured ideas, task outcomes, and any other structured or unstructured content the user asks it to record.

"Grow naturally" means low friction — capturing a thought should take seconds, not minutes of formatting and filing. Bede should suggest where to file things and how to organise them, but the user makes the final decision. Bede does not file autonomously.

"Easy to search" means the user can ask Bede a question and get an answer that draws on his own notes, not just the AI's training data. The knowledge base must be the first place Bede looks for personal context.

The knowledge base must be stored as files the user owns and controls (Markdown preferred). It must be accessible from multiple devices (Mac, iPhone) and must not depend on any single vendor's sync service for its integrity.

**Success looks like:** the user's notes are useful because they're findable, and growing because capture is effortless.

**Measurable indicator:** The user can capture a thought in under 10 seconds (voice or text). Bede can answer a question using vault content when relevant notes exist.

### R6. Deal and price monitoring

**I want deals and prices monitored on things I care about.**

Bede must track prices and availability for products and events the user specifies. Categories include clothing, household staples, outdoor gear, event tickets, and whatever the user adds in future. The user defines what to watch, what retailers to check, and what constitutes a deal worth reporting.

Monitoring must run on a configurable schedule. Reports should only surface when something actionable has changed — a price drop, a restock, a new event announced. No-change reports are noise.

Bede must be able to browse the web to check prices and availability, since many retailers don't offer APIs.

**Success looks like:** The user gets timely alerts about deals he cares about without manually checking websites.

**Measurable indicator:** Price alerts are delivered within 24 hours of a price change on a monitored item.

### R7. Conversational assistant

**I want a conversational assistant I can ask anything, with full context on my life.**

Bede must be available for ad-hoc questions and tasks at any time. This is the general-purpose assistant capability — drafting messages, answering questions, brainstorming, looking things up, helping with decisions. The key differentiator from a generic assistant is that Bede has full context: calendar, health, location, goals, knowledge base, conversation history.

Multi-turn conversations must be supported — Bede must remember what was discussed earlier in the same conversation, not treat every message as a fresh start.

This must not be limited to any specific domain. If the user asks about cooking, travel planning, or how to fix a shelf, Bede should help.

**Success looks like:** The user uses Bede instead of a generic chat assistant because the answers are better — they account for his schedule, his health, his goals, and his history.

**Measurable indicator:** Bede incorporates personal context (calendar, health, goals, or vault) in responses where relevant, without the user having to ask for it.

### R8. Voice interaction

**I want to talk to Bede by voice, and have Bede talk back — especially on the go.**

Bede must support voice input and voice output as a secondary interaction mode. The primary use case is hands-free situations: driving, walking, cooking. The user speaks a message, Bede responds with audio. Walkie-talkie style (speak, wait, receive response) is acceptable — real-time phone-call-style conversation is not required.

Voice must support the same capabilities as text — it's an alternative input/output mode, not a separate feature set. If the user can ask it in text, he can ask it by voice.

Creating tasks, capturing thoughts, and asking quick questions are the primary voice use cases.

**Success looks like:** The user can interact with Bede while driving or doing chores, without reaching for his phone to type.

### R9. Memory and continuity

**Bede must remember what matters across conversations and over time.**

Bede must maintain context beyond a single conversation. This includes:

- **Within a conversation:** multi-turn context so Bede doesn't forget what was just discussed.
- **Across conversations:** Bede must remember significant facts, preferences, corrections, and commitments the user has made, even days or weeks later. If the user says "I'm training for a half marathon" in March, Bede should still know that in June.
- **Pattern recognition over time:** R1 (coaching) and R2 (accountability) require Bede to detect trends across days and weeks — sleep patterns, exercise consistency, goal progress. This requires access to historical data, not just today's snapshot.

What Bede remembers must be transparent — The user should be able to see and edit what Bede has stored about them. Bede must not silently build an internal model The user can't inspect.

When Bede gets something wrong based on its memory, The user must be able to correct it, and the correction must stick. Bede must not repeat a corrected mistake.

**Success looks like:** Bede feels like it knows the user — not because it's guessing, but because it genuinely remembers past conversations, corrections, and context. The user never has to re-explain something he's already told Bede.

---

## 3. Constraints

These are non-negotiable boundaries the system must operate within.

### C1. Own hardware

The system must run on hardware the user owns and controls, in his home. No cloud-hosted compute for the assistant itself. The server runs Linux or Windows. Cloud services may be used for specific functions (e.g., AI inference, DNS, email APIs) but the assistant's core logic, data, and state must reside on the user's hardware.

### C2. Data sovereignty

All personal data — health, location, screen time, calendar, email content, conversation history, knowledge base — must be stored on the user's own infrastructure. Data may transit third-party services for processing (e.g., sending a prompt to Claude for inference) but must not be stored by third parties beyond what is necessary for the service to function. The user must be able to delete all his data by deleting files on his own server.

### C3. Claude subscription

The system must use a Claude subscription (flat monthly cost), not per-token API billing. This constrains how the system interacts with Claude — it must use mechanisms covered by the subscription, not the commercial API.

### C4. Minimal-setup interface

The interface must be usable from an iPhone using only apps available from the App Store, with no custom app development or App Store deployment required. Server-side setup should be achievable in under an hour for someone with the user's technical skills.

Text is the primary interaction mode. Voice is secondary (R8).

### C5. File-based knowledge

The knowledge base must be stored as Markdown files that the user owns. It must be editable with standard text editors and must not be locked into any proprietary format. Obsidian is the likely tool but must not be a hard dependency — the files must be usable without it.

### C6. Maintenance budget

The system must run unattended on weeknights without manual intervention. Maintenance and feature work happens on weekends (target: a couple of hours). The system must not require more than one manual intervention per week on average. When things break, failures must be visible — not silent.

### C7. Scheduled interaction style

Scheduled outputs (briefings, coaching check-ins, reflections) must be interactive: Bede initiates, asks the user questions, the user responds, then Bede produces the output. This is the preferred mode — read-only delivery is a fallback, not the default.

If the user does not respond, Bede retries up to three times total. After three unanswered attempts, Bede sends a non-interactive version (best-effort output without the user's input). The information must not be lost simply because the user was unavailable.

---

## 4. Data Inputs

Bede's value depends on having context about the user's life. These are the categories of data the system must be able to access. This section defines what data is needed, not how it is collected or stored.

### Health and wellness
- Sleep: duration, quality, bedtime/wake time
- Physical activity: steps, exercise minutes, stand hours, active energy
- Workouts: type, duration, intensity
- Heart rate: resting heart rate, heart rate variability
- Medications: adherence tracking
- Mood/wellbeing: state of mind entries, mindfulness minutes
- Source: Apple Health (iPhone/Apple Watch)

### Location
- Where the user has been during the day (GPS-based)
- Clustered into meaningful places (home, work, gym, etc.)
- Source: iPhone location tracking

### Screen time and browsing history
- App usage duration by app (Mac and iPhone)
- Web domain usage duration
- Safari browsing history (URLs, not just domains) — useful for R2 (what the user actually reads) and R3 (interest tracking)
- Source: macOS and iOS system data

### Calendar
- Events across personal calendars
- Work calendar is not available (locked down, Bede cannot access it)
- Source: Google Calendar

### Email
- Inbox contents for triage
- Ability to search, read, and (with permission) send/reply
- Source: Gmail

### Reminders and tasks
- Active reminders and tasks, and their completion status
- Bede must be able to create tasks/reminders (e.g., captured via voice while driving)
- Source: Google Tasks or equivalent task system

### Media consumption
- YouTube watch history
- Podcast listening history (episodes, duration)
- Music listening history
- Source: macOS and iOS system data, streaming service history

### Weather and air quality
- Current conditions and forecast for the user's location
- Air quality index and alerts
- Source: Bureau of Meteorology (Australia), NSW government air quality API

### Knowledge base
- All notes, journal entries, and structured files in the personal vault
- Source: Obsidian vault (Markdown files)

### Goals and schedule
- the user's current goals (professional, personal, health)
- the user's intended weekly schedule/routine
- Source: defined by the user (not necessarily in the knowledge base — could be configured separately)

### Browsing
- Ability to obtain information from websites regardless of whether they offer structured APIs (for deal monitoring, interest curation)
- Source: the open web

### Conversation history
- Bede's own prior conversations with the user
- Prior corrections the user has made to Bede's behaviour or interpretations
- Supports R1 (pattern tracking), R2 (accountability continuity), R7 (multi-turn), R9 (memory)
- Source: Bede's own conversation logs

### Data freshness expectations

Not all data needs to arrive in real-time. Approximate expectations:

| Category | Freshness | Rationale |
|----------|-----------|-----------|
| Calendar, email, tasks | Near real-time (minutes) | Day planning needs current state |
| Location | Near real-time when queried | "Where am I?" must be accurate now |
| Weather and air quality | Hourly | Forecasts don't change faster |
| Health (sleep, activity, HR) | Daily | Collected overnight or end-of-day |
| Screen time, browsing history | Daily | Batch collection is sufficient |
| Media consumption | Daily | Batch collection is sufficient |
| Knowledge base | Minutes | Captures should appear quickly |
| Conversation history | Immediate | Must be available within the same session |
| Goals and schedule | On change | Only updates when the user edits them |

---

## 5. Cross-Cutting Requirements

These apply across all functional requirements.

### Privacy and security
- The system must not expose personal data to unauthorized parties.
- External-facing endpoints must be authenticated and access-restricted to the user's network.
- The assistant must not be able to exfiltrate data through tool calls without the user's awareness.
- Secrets and credentials must never be committed to version control.

### Reliability
- Individual component failures must not take down the entire system. If one data source is unavailable, Bede must still function with the data it has.
- Failures must be surfaced to the user, not swallowed silently.
- The system must recover gracefully from restarts without data loss.
- If the underlying language model is unavailable, Bede should queue incoming messages and process them when service resumes rather than dropping them silently.

### Configurability
- The user must be able to change Bede's personality, tone, and boundaries.
- Scheduled tasks, monitored items, interest topics, and goal definitions must all be editable by the user without code changes.
- Configuration should be stored as human-readable files, not in databases or admin UIs.

### Auditability
- The user must be able to see what Bede did, when, and why.
- Scheduled task executions must be logged with enough detail to diagnose failures.
- Conversation history must be reviewable.

### Responsiveness
- Text conversations (R7): Bede should respond within 30 seconds. Longer delays should show a "thinking" indicator.
- Voice interactions (R8): same latency tolerance as text — walkie-talkie style, not real-time.
- Scheduled tasks: no hard latency requirement, but must complete within a reasonable window (minutes, not hours).

### Extensibility
- Adding new data sources, new scheduled tasks, or new capabilities should not require rewriting existing functionality.
- The system should be modular enough that components can be added, removed, or replaced independently.

### Backup and recovery
- The user must be able to back up the entire system (data, configuration, state) and restore it on new hardware.
- The backup process should be simple enough to automate (e.g., a single directory or a script).
- Given that this runs on home hardware, hardware failure is a realistic scenario — recovery must be documented and tested.

### Data retention
- Operational data (logs, raw data exports, task execution records) should have a configurable retention period. It must not grow unboundedly.
- Conversation history and knowledge base content should be retained indefinitely unless the user explicitly deletes it.
- The system should make it easy to see how much storage is being used and by what.

---

## 6. What This Document Does Not Cover

- **Architecture and technology choices.** How the requirements are met is a design decision.
- **Specific schedules or cadences.** When briefings run, how often coaching checks in, etc. are configuration, not requirements.
- **UI/UX design.** How messages are formatted, what buttons exist, etc.
- **Migration plan.** How to get from the current system to the target system.
- **Cost analysis.** Budget for hardware, subscriptions, or services.

These belong in subsequent design and planning documents.

---

## Appendix: Relationship Map

Requirements are not independent — they share data, reinforce each other, and in some cases conflict. Key relationships:

```
R1 (Mental health) ←→ R2 (Goal accountability)
  Poor mental health causes goal drift; goal drift worsens mental health.
  Share data: sleep, activity, screen time, media consumption, location.

R2 (Goal accountability) ← R4 (Day planning)
  Planning sets intentions; accountability measures follow-through.
  Tasks/reminders bridge both: R4 creates them, R2 tracks completion.

R3 (Stay current) → R5 (Knowledge base)
  Curated content should flow into the knowledge base if the user wants to keep it.

R4 (Day planning) ← all data inputs
  Planning requires the broadest view: calendar, email, weather, tasks, health, goals.

R7 (Conversational) ← all data inputs + R5 (Knowledge base)
  The conversational assistant is most valuable when it has full context.

R8 (Voice) → R4 (Day planning), R5 (Knowledge base)
  Voice enables quick task creation and thought capture on the go.
  Voice is an alternative I/O mode for R7 in hands-free situations.

R9 (Memory) ← R1, R2, R5, R7
  Memory is foundational infrastructure. R1 needs pattern history.
  R2 needs goal tracking continuity. R5 needs to be searchable.
  R7 needs multi-turn and cross-conversation context.

Implementation dependency note:
  R1 and R2 are highest *value* priority, but R4 (planning), R5 (knowledge
  base), and R9 (memory) are foundational *infrastructure* that R1 and R2
  depend on. A design must address this — either build infrastructure first,
  or deliver R1/R2 in reduced form initially and enhance as infrastructure
  matures.
```
