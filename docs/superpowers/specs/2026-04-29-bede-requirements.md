# Bede — Requirements Document

**Version:** 1.0
**Date:** 2026-04-29
**Author:** Joe Radford + Claude
**Status:** Draft — awaiting review

This document defines what Bede must do and the constraints it must operate within. It is deliberately implementation-agnostic — it says nothing about architecture, technology choices, or how the requirements should be met. Design decisions belong in a separate design document.

---

## 1. What is Bede?

Bede is a personal assistant for one person: Joe Radford. It knows about Joe's health, activity, location, calendar, email, screen time, goals, and knowledge base. It uses this context to coach, inform, remind, and assist — proactively on a schedule and reactively on demand.

---

## 2. Requirements

Requirements are listed in priority order. Each requirement stands on its own — the system must deliver value for each independently, not only when all are working together.

### R1. Mental health coaching

**I want to be coached to keep my mental health issues of anxiety and depression in check.**

Bede must have access to signals relevant to mental health: sleep quality and duration, physical activity, medication adherence, mood indicators, and behavioural patterns (e.g., social isolation, routine disruption). It must surface concerns proactively and honestly — not wait to be asked. It must track patterns over time, not just react to single data points. It must be direct without being clinical, and supportive without being patronising.

Coaching means ongoing, not reactive. Bede should check in regularly, notice when things are slipping before Joe does, and connect dots across days and weeks. A single bad night's sleep is not a concern; three in a row alongside dropping exercise is.

The coaching relationship must be configurable — Joe controls the tone, the boundaries, and what topics are in scope. If Joe says "back off on this topic," Bede must respect that immediately and durably.

**Success looks like:** Joe feels like someone is genuinely watching out for him and will say something honest when patterns emerge — not just echoing data back.

### R2. Goal accountability

**I want to be held accountable to my personal and professional goals.**

Bede must know Joe's current goals (professional certifications, hobbies like camping/piano/reading, fitness targets, career direction) and track progress toward them. It must notice when effort is drifting — too much mindless device time, skipped practice sessions, stalled projects — and call it out.

Accountability means measuring reality against intention. Bede must know what Joe said he would do (goals, weekly schedule) and what he actually did (screen time, media consumption, activity, location, calendar, task completion, vault edits). The gap between those is what matters.

This is closely linked to R1 — poor mental health often causes goal drift, and goal drift often worsens mental health. Bede must understand this connection and not treat them as independent.

**Success looks like:** Joe can't quietly let a goal slide for two weeks without Bede noticing and raising it.

### R3. Stay current without effort

**I want to stay current in my professional and personal interests without having to go looking.**

Bede must curate and deliver relevant content from Joe's areas of interest — professional (software engineering, AI, cloud) and personal (music, camping, whatever Joe defines). Joe should not have to seek out this information himself; Bede should bring it to him in a digestible format.

The sources, topics, and delivery cadence must be configurable by Joe. Bede must be able to distinguish signal from noise — a curated summary is valuable, a firehose is not.

**Success looks like:** Joe learns about things that matter to him without opening a browser to go looking.

### R4. Day and week planning

**I want to know what my day and week look like before they start — including emails triaged into tasks, events, or dismissed.**

Bede must prepare a view of the upcoming day (and week, at appropriate cadence) that includes: calendar events, weather, relevant reminders, and any actions extracted from email. Email triage follows a strict pattern: each email becomes a task, becomes an event, or is dismissed as requiring no action.

This must be delivered proactively before the day/week starts, not on demand. The delivery must be interactive — Bede asks questions, Joe provides input, then Bede delivers the final view. Joe must be able to correct, reprioritise, or add items during the interaction.

**Success looks like:** Joe starts each day and week knowing exactly what's ahead, with no unprocessed email creating background anxiety.

### R5. Personal knowledge base

**I want my personal knowledge base to grow naturally and be easy to search.**

Bede must integrate with Joe's personal knowledge base (currently an Obsidian vault organised using the PARA method). It must be able to read from and write to the knowledge base. Writing includes: journal entries, meeting notes, captured ideas, task outcomes, and any other structured or unstructured content Joe asks it to record.

"Grow naturally" means low friction — capturing a thought should take seconds, not minutes of formatting and filing. Bede should handle the organisation.

"Easy to search" means Joe can ask Bede a question and get an answer that draws on his own notes, not just the AI's training data. The knowledge base must be the first place Bede looks for personal context.

The knowledge base must be stored as files Joe owns and controls (Markdown preferred). It must be accessible from multiple devices (Mac, iPhone) and must not depend on any single vendor's sync service for its integrity.

**Success looks like:** Joe's notes are useful because they're findable, and growing because capture is effortless.

### R6. Deal and price monitoring

**I want deals and prices monitored on things I care about.**

Bede must track prices and availability for products and events Joe specifies. Categories include clothing, household staples, outdoor gear, event tickets, and whatever Joe adds in future. Joe defines what to watch, what retailers to check, and what constitutes a deal worth reporting.

Monitoring must run on a configurable schedule. Reports should only surface when something actionable has changed — a price drop, a restock, a new event announced. No-change reports are noise.

Bede must be able to browse the web to check prices and availability, since many retailers don't offer APIs.

**Success looks like:** Joe gets timely alerts about deals he cares about without manually checking websites.

### R7. Conversational assistant

**I want a conversational assistant I can ask anything, with full context on my life.**

Bede must be available for ad-hoc questions and tasks at any time. This is the general-purpose assistant capability — drafting messages, answering questions, brainstorming, looking things up, helping with decisions. The key differentiator from a generic assistant is that Bede has full context: calendar, health, location, goals, knowledge base, conversation history.

Multi-turn conversations must be supported — Bede must remember what was discussed earlier in the same conversation, not treat every message as a fresh start.

This must not be limited to any specific domain. If Joe asks about cooking, travel planning, or how to fix a shelf, Bede should help.

**Success looks like:** Joe uses Bede instead of a generic chat assistant because the answers are better — they account for his schedule, his health, his goals, and his history.

### R8. Voice interaction

**I want to talk to Bede by voice, and have Bede talk back — especially on the go.**

Bede must support voice input and voice output as a secondary interaction mode. The primary use case is hands-free situations: driving, walking, cooking. Joe speaks a message, Bede responds with audio. Walkie-talkie style (speak, wait, receive response) is acceptable — real-time phone-call-style conversation is not required.

Voice must support the same capabilities as text — it's an alternative input/output mode, not a separate feature set. If Joe can ask it in text, he can ask it by voice.

Creating tasks, capturing thoughts, and asking quick questions are the primary voice use cases.

**Success looks like:** Joe can interact with Bede while driving or doing chores, without reaching for his phone to type.

---

## 3. Constraints

These are non-negotiable boundaries the system must operate within.

### C1. Own hardware

The system must run on hardware Joe owns and controls, in his home. No cloud-hosted compute for the assistant itself. The server runs Linux or Windows (macOS would be ideal but is not in budget). Cloud services may be used for specific functions (e.g., AI inference, DNS, email APIs) but the assistant's core logic, data, and state must reside on Joe's hardware.

### C2. Data sovereignty

All personal data — health, location, screen time, calendar, email content, conversation history, knowledge base — must be stored on Joe's own infrastructure. Data may transit third-party services for processing (e.g., sending a prompt to Claude for inference) but must not be stored by third parties beyond what is necessary for the service to function. Joe must be able to delete all his data by deleting files on his own server.

### C3. Claude subscription

The system must use a Claude subscription (flat monthly cost), not per-token API billing. This constrains how the system interacts with Claude — it must use mechanisms covered by the subscription, not the commercial API.

### C4. Minimal-setup interface

The interface must be easy to set up on Joe's server hardware and on an iPhone. "Easy" means: no custom app development, no App Store deployment, no complex client-side configuration. The interface should use existing apps or protocols that work on iPhone out of the box.

Text is the primary interaction mode. Voice is secondary (R8).

### C5. File-based knowledge

The knowledge base must be stored as Markdown files that Joe owns. It must be editable with standard text editors and must not be locked into any proprietary format. Obsidian is the likely tool but must not be a hard dependency — the files must be usable without it.

### C6. Maintenance budget

The system must be stable enough to run unattended on weeknights. Maintenance and feature work happens on weekends (target: a couple of hours). The system must not require regular firefighting or manual intervention to keep running. When things break, failures must be visible — not silent.

### C7. Scheduled interaction style

Scheduled outputs (briefings, coaching check-ins, reflections) must be interactive: Bede initiates, asks Joe questions, Joe responds, then Bede produces the output. This is not optional — read-only delivery or "reply if you want" delivery does not meet the requirement.

---

## 4. Data Inputs

Bede's value depends on having context about Joe's life. These are the categories of data the system must be able to access. This section defines what data is needed, not how it is collected or stored.

### Health and wellness
- Sleep: duration, quality, bedtime/wake time
- Physical activity: steps, exercise minutes, stand hours, active energy
- Workouts: type, duration, intensity
- Heart rate: resting heart rate, heart rate variability
- Medications: adherence tracking
- Mood/wellbeing: state of mind entries, mindfulness minutes
- Source: Apple Health (iPhone/Apple Watch)

### Location
- Where Joe has been during the day (GPS-based)
- Clustered into meaningful places (home, work, gym, etc.)
- Source: iPhone location tracking

### Screen time
- App usage duration by app (Mac and iPhone)
- Web domain usage duration
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
- Current conditions and forecast for Joe's location
- Air quality index and alerts
- Source: Bureau of Meteorology (Australia), NSW government air quality API

### Knowledge base
- All notes, journal entries, and structured files in the personal vault
- Source: Obsidian vault (Markdown files)

### Goals and schedule
- Joe's current goals (professional, personal, health)
- Joe's intended weekly schedule/routine
- Source: defined by Joe (not necessarily in the knowledge base — could be configured separately)

### Browsing
- Ability to visit web pages and extract information (for deal monitoring, interest curation)
- Source: the open web

---

## 5. Cross-Cutting Requirements

These apply across all functional requirements.

### Privacy and security
- The system must not expose personal data to unauthorized parties.
- External-facing endpoints must be authenticated and access-restricted to Joe's network.
- The assistant must not be able to exfiltrate data through tool calls without Joe's awareness.
- Secrets and credentials must never be committed to version control.

### Reliability
- Individual component failures must not take down the entire system.
- Failures must be surfaced to Joe, not swallowed silently.
- The system must recover gracefully from restarts without data loss.

### Configurability
- Joe must be able to change Bede's personality, tone, and boundaries.
- Scheduled tasks, monitored items, interest topics, and goal definitions must all be editable by Joe without code changes.
- Configuration should be stored as human-readable files, not in databases or admin UIs.

### Auditability
- Joe must be able to see what Bede did, when, and why.
- Scheduled task executions must be logged with enough detail to diagnose failures.
- Conversation history must be reviewable.

### Extensibility
- Adding new data sources, new scheduled tasks, or new capabilities should not require rewriting existing functionality.
- The system should be modular enough that components can be added, removed, or replaced independently.

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
  Curated content should flow into the knowledge base if Joe wants to keep it.

R4 (Day planning) ← all data inputs
  Planning requires the broadest view: calendar, email, weather, tasks, health, goals.

R7 (Conversational) ← all data inputs + R5 (Knowledge base)
  The conversational assistant is most valuable when it has full context.

R8 (Voice) → R4 (Day planning), R5 (Knowledge base)
  Voice enables quick task creation and thought capture on the go.
  Voice is an alternative I/O mode for R7 in hands-free situations.
```
