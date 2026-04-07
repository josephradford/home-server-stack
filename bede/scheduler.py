"""
Scheduled task runner for Bede.

Reads task definitions from YAML frontmatter in a markdown file inside the
Obsidian vault (BEDE_TASKS_PATH, relative to /vault). Reloads every 5 minutes
to pick up edits made in Obsidian without restarting the container.

Task file format (YAML frontmatter):

    ---
    tasks:
      - name: Morning Briefing
        schedule: "0 7 * * 1-5"   # standard 5-field cron, evaluated in TIMEZONE
        prompt: |
          Give me a morning briefing: today's calendar events and the weather.
      - name: Weekly Review
        schedule: "0 16 * * 5"
        prompt: "Remind me to do my weekly review."
        enabled: false             # set false to skip without deleting
    ---
"""

import asyncio
import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)

VAULT_PATH = "/vault"
TASKS_REL_PATH = os.environ.get("BEDE_TASKS_PATH", "Bede/scheduled-tasks.md")
TIMEZONE = os.environ.get("TIMEZONE", "UTC")
CLAUDE_WORKDIR = os.environ.get("CLAUDE_WORKDIR", "/app")
RELOAD_INTERVAL_MINUTES = 5

_bot = None
_chat_id: int = 0


def _pull_vault():
    """Pull latest vault state. Fails silently."""
    if not os.path.isdir(os.path.join(VAULT_PATH, ".git")):
        return
    try:
        subprocess.run(
            ["git", "-C", VAULT_PATH, "pull", "--ff-only"],
            capture_output=True,
            timeout=30,
        )
    except Exception:
        pass


def _parse_tasks() -> list[dict]:
    """Read and parse a ```yaml code block from the tasks file in the vault."""
    full_path = os.path.join(VAULT_PATH, TASKS_REL_PATH)
    if not os.path.isfile(full_path):
        log.debug("Tasks file not found at %s — no scheduled tasks.", full_path)
        return []

    with open(full_path) as f:
        content = f.read()

    # Extract content between first ```yaml ... ``` block
    import re
    match = re.search(r"```yaml\s*\n(.*?)```", content, re.DOTALL)
    if not match:
        log.warning("Tasks file has no ```yaml code block: %s", full_path)
        return []

    try:
        data = yaml.safe_load(match.group(1)) or {}
        tasks = data.get("tasks", [])
        enabled = [t for t in tasks if t.get("enabled", True)]
        log.info("Loaded %d scheduled task(s) from vault.", len(enabled))
        return enabled
    except yaml.YAMLError as e:
        log.error("Failed to parse tasks YAML: %s", e)
        return []


async def _send(text: str):
    """Send a message to the user's Telegram chat."""
    try:
        await _bot.send_message(chat_id=_chat_id, text=text, parse_mode="Markdown")
    except Exception as e:
        log.error("Failed to send scheduled message: %s", e)


async def _run_task(task: dict):
    """Run a single scheduled task and send the result via Telegram."""
    name = task.get("name", "Scheduled Task")
    prompt = task.get("prompt", "")

    log.info("Running scheduled task: %s", name)

    tz = ZoneInfo(TIMEZONE)
    now_str = datetime.now(tz).strftime("%H:%M")
    header = f"📅 *{name}* ({now_str})\n---\n"

    cmd = [
        "claude", "-p", prompt,
        "--dangerously-skip-permissions",
        "--output-format", "json",
    ]

    try:
        proc = await asyncio.to_thread(
            subprocess.run, cmd,
            capture_output=True, text=True,
            stdin=subprocess.DEVNULL, cwd=CLAUDE_WORKDIR,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        await _send(f"📅 *{name}*\n⚠️ Timed out after 2 minutes.")
        return
    except Exception as e:
        await _send(f"📅 *{name}*\n⚠️ Error: {e}")
        return

    result_text = ""
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if obj.get("type") == "result":
                result_text = obj.get("result", "").strip()
        except json.JSONDecodeError:
            continue

    if not result_text:
        if proc.returncode != 0:
            result_text = f"⚠️ Task failed (exit {proc.returncode}):\n{(proc.stderr or proc.stdout or 'No output.')[:500]}"
        else:
            result_text = (proc.stdout or proc.stderr or "No response.").strip()

    full = header + result_text
    for chunk in [full[i:i + 4096] for i in range(0, len(full), 4096)]:
        await _send(chunk)


async def reload(scheduler: AsyncIOScheduler):
    """Pull vault, re-parse tasks, and rebuild scheduled jobs."""
    await asyncio.to_thread(_pull_vault)
    tasks = _parse_tasks()

    # Remove all task jobs, keep the reload watcher itself
    for job in scheduler.get_jobs():
        if job.id != "reload_watcher":
            job.remove()

    tz = ZoneInfo(TIMEZONE)
    for task in tasks:
        cron = task.get("schedule", "")
        name = task.get("name", "task")
        if not cron:
            log.warning("Task '%s' has no schedule — skipping.", name)
            continue
        try:
            scheduler.add_job(
                _run_task,
                CronTrigger.from_crontab(cron, timezone=tz),
                args=[task],
                id=f"task_{name}",
                name=name,
                replace_existing=True,
            )
            log.info("Scheduled '%s' with cron '%s' (%s)", name, cron, TIMEZONE)
        except Exception as e:
            log.error("Invalid schedule for '%s': %s", name, e)


def setup_scheduler(bot, chat_id: int) -> AsyncIOScheduler:
    """Create and configure the scheduler. Call start() and await reload() after."""
    global _bot, _chat_id
    _bot = bot
    _chat_id = chat_id

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        reload,
        "interval",
        minutes=RELOAD_INTERVAL_MINUTES,
        args=[scheduler],
        id="reload_watcher",
        name="Task reload watcher",
    )
    return scheduler
