"""
Bede — Telegram bot wrapping Claude Code CLI.

Each message runs `claude -p` as a subprocess. Multi-turn conversations
reuse the same session via --resume within a configurable timeout window.
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from scheduler import reload as scheduler_reload, setup_scheduler, _parse_tasks, _run_task

load_dotenv()


def _md_to_html(text: str) -> str:
    """Convert CommonMark-style markdown to Telegram HTML."""
    # Escape HTML entities first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Fenced code blocks (``` ... ```)
    text = re.sub(r"```(?:\w+\n)?(.*?)```", r"<pre>\1</pre>", text, flags=re.DOTALL)
    # Inline code
    text = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", text)
    # Bold italic (*** or ___)
    text = re.sub(r"\*\*\*(.*?)\*\*\*", r"<b><i>\1</i></b>", text, flags=re.DOTALL)
    # Bold (** or __)
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    text = re.sub(r"__(.*?)__", r"<b>\1</b>", text, flags=re.DOTALL)
    # Italic (* or _)
    text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text, flags=re.DOTALL)
    text = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"<i>\1</i>", text)
    return text

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_USER_ID = int(os.environ["ALLOWED_USER_ID"])
CLAUDE_WORKDIR = os.environ.get("CLAUDE_WORKDIR", "/app")
SESSION_TIMEOUT_SECS = int(os.environ.get("SESSION_TIMEOUT_MINUTES", "10")) * 60
VAULT_REPO = os.environ.get("VAULT_REPO", "")

_scheduler: AsyncIOScheduler | None = None

# {chat_id: {"session_id": str, "ts": float}}
_sessions: dict[int, dict] = {}

REAUTH_NOTICE = (
    "\u26a0\ufe0f Claude auth has expired.\n\n"
    "Run this from your Mac to re-authenticate:\n"
    "```\n"
    'security find-generic-password -s "Claude Code-credentials" -w | \\\n'
    '  ssh user@SERVER_IP "cat > ~/.claude/.credentials.json"\n'
    "```"
)


def _build_cmd(text: str, session_id: str | None) -> list[str]:
    cmd = [
        "claude", "-p", text,
        "--dangerously-skip-permissions",
        "--output-format", "json",
    ]
    if session_id:
        cmd += ["--resume", session_id]
    return cmd


def _pull_vault():
    """Pull latest vault state before invoking Claude. Fails silently."""
    if not VAULT_REPO or not os.path.isdir("/vault/.git"):
        return
    try:
        subprocess.run(
            ["git", "-C", "/vault", "pull", "--ff-only"],
            capture_output=True,
            timeout=30,
        )
    except Exception:
        pass


def _parse_output(stdout: str) -> tuple[str, str | None]:
    """
    claude --output-format json emits newline-delimited JSON objects.
    The final object with type=result contains the answer and session_id.
    """
    result_text = ""
    session_id = None

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        if obj.get("type") == "result":
            result_text = obj.get("result", "").strip()
            session_id = obj.get("session_id")

    return result_text, session_id


def _run_claude(cmd: list[str], workdir: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        cwd=workdir,
        timeout=120,
    )


async def _keep_typing(bot, chat_id: int):
    """Sends typing action every 4s so it doesn't expire while Claude thinks."""
    while True:
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception:
            pass
        await asyncio.sleep(4)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        log.warning("Rejected message from user %s", update.effective_user.id)
        return

    chat_id = update.effective_chat.id
    text = update.message.text
    now = time.monotonic()

    # Determine session continuity
    session = _sessions.get(chat_id)
    resume_id = None
    if session and (now - session["ts"]) < SESSION_TIMEOUT_SECS:
        resume_id = session["session_id"]

    await asyncio.to_thread(_pull_vault)

    cmd = _build_cmd(text, resume_id)
    log.info("Running: %s", " ".join(cmd[:4]) + " ...")

    typing_task = asyncio.create_task(_keep_typing(context.bot, chat_id))
    try:
        proc = await asyncio.to_thread(_run_claude, cmd, CLAUDE_WORKDIR)
    except subprocess.TimeoutExpired:
        typing_task.cancel()
        await update.message.reply_text("Request timed out after 2 minutes.")
        return
    finally:
        typing_task.cancel()

    # Stale session detection — retry once with a fresh session
    if resume_id and "no conversation found" in proc.stderr.lower():
        log.warning("Stale session %s, retrying fresh.", resume_id)
        _sessions.pop(chat_id, None)
        await update.message.reply_text("_(Session reset — previous context lost)_", parse_mode="Markdown")
        cmd = _build_cmd(text, None)
        typing_task = asyncio.create_task(_keep_typing(context.bot, chat_id))
        try:
            proc = await asyncio.to_thread(_run_claude, cmd, CLAUDE_WORKDIR)
        except subprocess.TimeoutExpired:
            typing_task.cancel()
            await update.message.reply_text("Request timed out after 2 minutes.")
            return
        finally:
            typing_task.cancel()

    # Auth failure detection
    stderr_lower = proc.stderr.lower()
    if proc.returncode != 0 and any(
        kw in stderr_lower for kw in ("unauthorized", "authentication", "auth", "login")
    ):
        log.error("Auth failure detected: %s", proc.stderr[:200])
        await update.message.reply_text(REAUTH_NOTICE, parse_mode="Markdown")
        return

    result_text, new_session_id = _parse_output(proc.stdout)

    if not result_text:
        # Fallback: surface raw output so failures are visible
        result_text = (proc.stdout or proc.stderr or "No response.").strip()[:4096]

    # Update session — if no new session ID came back, the old one was consumed;
    # clear it so the next message starts fresh rather than hitting a stale resume.
    if new_session_id:
        _sessions[chat_id] = {"session_id": new_session_id, "ts": now}
    else:
        if _sessions.pop(chat_id, None):
            await update.message.reply_text("_(Session reset — previous context lost)_", parse_mode="Markdown")

    # Telegram message limit is 4096 chars; convert markdown to HTML, fall back to plain text
    for chunk in [result_text[i:i + 4096] for i in range(0, len(result_text), 4096)]:
        try:
            await update.message.reply_text(_md_to_html(chunk), parse_mode="HTML")
        except Exception:
            await update.message.reply_text(chunk)


async def handle_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    chat_id = update.effective_chat.id
    _sessions.pop(chat_id, None)
    await update.message.reply_text("Session cleared. Next message starts fresh.")


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    await update.message.reply_text(
        "Hi, I'm Bede. Send me a message to get started.\n"
        "/reset — start a new conversation session"
    )


async def handle_runtasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    tasks = _parse_tasks()
    if not tasks:
        await update.message.reply_text("No tasks found in scheduled-tasks.md.")
        return
    names = ", ".join(t.get("name", "?") for t in tasks)
    await update.message.reply_text(f"Running {len(tasks)} task(s): {names}")
    await asyncio.gather(*[_run_task(t) for t in tasks])


async def post_init(app):
    from telegram import BotCommand, BotCommandScopeAllPrivateChats
    commands = [
        BotCommand("start", "Start a conversation"),
        BotCommand("reset", "Clear session and start fresh"),
        BotCommand("runtasks", "Fire all scheduled tasks immediately"),
    ]
    await app.bot.set_my_commands(commands)
    await app.bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())

    global _scheduler
    _scheduler = setup_scheduler(app.bot, ALLOWED_USER_ID)
    _scheduler.start()
    await scheduler_reload(_scheduler)
    log.info("Scheduler started.")


async def post_shutdown(app):
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("Scheduler stopped.")


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("reset", handle_reset))
    app.add_handler(CommandHandler("runtasks", handle_runtasks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("Bede is running.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
