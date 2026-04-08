---
tasks:
  - name: Morning Briefing
    schedule: "0 7 * * 1-5"
    prompt: |
      Give me a morning briefing for today. Check my Google Calendar for today's
      events and any deadlines. Keep it concise — bullet points preferred.

  - name: Weekly Review
    schedule: "0 16 * * 5"
    prompt: |
      It's end of week. Summarise any open tasks in /vault/ and remind me to
      do my weekly review.
    enabled: false
---

# Bede Scheduled Tasks

Tasks are defined in the YAML frontmatter above.

## Field reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Display name shown in the Telegram message header |
| `schedule` | yes | Cron expression (5 fields, evaluated in your TIMEZONE) |
| `prompt` | yes | The instruction sent to Claude |
| `enabled` | no | Set `false` to disable without deleting (default: true) |

## Cron quick reference

```
┌─ minute (0-59)
│  ┌─ hour (0-23)
│  │  ┌─ day of month (1-31)
│  │  │  ┌─ month (1-12)
│  │  │  │  ┌─ day of week (0=Sun … 6=Sat)
│  │  │  │  │
0  7  *  *  1-5    →  weekdays at 07:00
0  16 *  *  5      →  Friday at 16:00
30 8  *  *  1      →  Monday at 08:30
```

Bede reloads this file every 5 minutes. Changes take effect without restarting the server.
