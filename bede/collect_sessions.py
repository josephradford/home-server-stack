"""
Collect and summarise Bede's Claude Code sessions, then POST to data-ingest.

Scans JSONL session files in ~/.claude/projects/, generates AI summaries
via `claude -p`, and sends the results to the data-ingest service for
storage in the bede_sessions SQLite table.

Called nightly by the scheduler as a built-in job.
Can also be run standalone: python collect_sessions.py [YYYY-MM-DD]
"""

import json
import logging
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, date as date_type
from pathlib import Path

log = logging.getLogger(__name__)

PROJECTS_DIR = Path(os.path.expanduser("~/.claude/projects"))
CLAUDE_BIN = "claude"
INGEST_URL = os.environ.get("INGEST_URL", "http://data-ingest:8000/ingest/vault")
INGEST_TOKEN = os.environ.get("INGEST_WRITE_TOKEN", "")

STRIP_PREFIXES = [
    "-app-",
    "-home-bede-",
]


def _readable_project(slug: str) -> str:
    for prefix in STRIP_PREFIXES:
        if slug.startswith(prefix):
            slug = slug[len(prefix):]
            break
    return slug.strip("-").replace("-", "/")


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return " ".join(parts)
    return ""


def _is_noise(text: str) -> bool:
    return (not text or len(text) < 15
            or "<local-command-caveat>" in text
            or "<command-name>" in text
            or text.strip().startswith("<"))


def _extract_transcript(jsonl_path: Path, max_chars: int = 6000) -> str:
    entries = []
    try:
        with open(jsonl_path) as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                t = obj.get("type", "")
                if t == "user":
                    text = _extract_text(obj.get("message", {}).get("content", ""))
                    if not _is_noise(text):
                        entries.append(("User", text[:600]))
                elif t == "assistant":
                    blocks = obj.get("message", {}).get("content", [])
                    if not isinstance(blocks, list):
                        continue
                    text_parts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
                    tool_names = [b.get("name", "") for b in blocks if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name")]
                    text = " ".join(text_parts).strip()
                    if tool_names and not text:
                        entries.append(("Assistant (tools)", ", ".join(tool_names)))
                    elif text:
                        suffix = f' [also used: {", ".join(tool_names)}]' if tool_names else ""
                        entries.append(("Assistant", text[:500] + suffix))
    except Exception:
        return ""

    if not entries:
        return ""

    if len(entries) > 20:
        middle_count = len(entries) - 20
        selected = entries[:10] + [("\u2026", f"[{middle_count} more turns]")] + entries[-10:]
    else:
        selected = entries

    transcript = ""
    for role, text in selected:
        line = f"[{role}]: {text}\n\n"
        if len(transcript) + len(line) > max_chars:
            transcript += "[transcript truncated]\n"
            break
        transcript += line
    return transcript.strip()


def _ai_summarise(project: str, transcript: str) -> str | None:
    if not transcript:
        return None
    prompt = (
        f'The following is a condensed Bede (Telegram AI assistant) session for the project "{project}".\n\n'
        "Write a short summary (2-4 sentences) of what was discussed or worked on. "
        "Then add two brief bullet-point sections:\n"
        "- **Conclusions:** things that were decided, completed, or answered\n"
        "- **Loose ends:** open questions, next steps, or unresolved issues\n"
        "Use \"none\" if a section is empty. Be concise.\n\n"
        f"--- TRANSCRIPT ---\n{transcript}\n--- END ---"
    )
    try:
        result = subprocess.run(
            [CLAUDE_BIN, "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=90,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _is_meta_summary(jsonl_path: Path) -> bool:
    """Check if this session was created by our own summarisation calls."""
    try:
        with open(jsonl_path) as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                obj = json.loads(raw)
                if obj.get("type") == "user":
                    text = _extract_text(obj.get("message", {}).get("content", ""))
                    if text and len(text) > 15:
                        return "condensed Bede" in text or "condensed Claude Code session" in text
    except Exception:
        pass
    return False


def _first_user_message(jsonl_path: Path) -> str:
    """Get the first substantive user message as fallback summary."""
    try:
        with open(jsonl_path) as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                obj = json.loads(raw)
                if obj.get("type") == "user":
                    text = _extract_text(obj.get("message", {}).get("content", ""))
                    if not _is_noise(text):
                        return text[:200]
    except Exception:
        pass
    return ""


def discover_sessions(target_date: date_type) -> list[dict]:
    """Find JSONL session files active on the target date."""
    sessions = []

    if not PROJECTS_DIR.is_dir():
        log.warning("Projects directory not found: %s", PROJECTS_DIR)
        return sessions

    for project_dir in sorted(PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir():
            continue
        for jsonl_file in sorted(project_dir.glob("*.jsonl")):
            if jsonl_file.parent.name != project_dir.name:
                continue

            mtime_date = datetime.fromtimestamp(jsonl_file.stat().st_mtime).date()
            if abs((mtime_date - target_date).days) > 7:
                continue

            project = _readable_project(project_dir.name)
            start_ts = None
            end_ts = None
            turns = 0

            try:
                with open(jsonl_file) as f:
                    for raw in f:
                        raw = raw.strip()
                        if not raw:
                            continue
                        try:
                            obj = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        ts_str = obj.get("timestamp", "")
                        if ts_str:
                            try:
                                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                                if start_ts is None or ts < start_ts:
                                    start_ts = ts
                                if end_ts is None or ts > end_ts:
                                    end_ts = ts
                            except ValueError:
                                pass
                        if obj.get("type") in ("user", "assistant"):
                            turns += 1
            except Exception:
                continue

            if start_ts is None:
                continue

            start_local = start_ts.astimezone().date()
            end_local = (end_ts.astimezone().date() if end_ts else start_local)
            if not (start_local <= target_date <= end_local):
                continue

            if _is_meta_summary(jsonl_file):
                continue

            sessions.append({
                "project": project,
                "jsonl": jsonl_file,
                "start": start_ts,
                "end": end_ts,
                "turns": turns,
            })

    sessions.sort(key=lambda s: s["start"])
    return sessions


def build_markdown(sessions: list[dict], target_date: date_type) -> str:
    """Generate the markdown report for the given sessions."""
    date_str = target_date.isoformat()
    lines = [f"# Bede Sessions \u2014 {date_str}", ""]

    if not sessions:
        lines.append("_(no sessions)_")
        return "\n".join(lines)

    lines.append(f"_{len(sessions)} session(s)_")
    lines.append("")

    for s in sessions:
        ls = s["start"].astimezone()
        le = s["end"].astimezone() if s["end"] else None
        dur = int((le - ls).total_seconds() / 60) if le else 0
        if le and ls.date() != le.date():
            ts = f"{ls.strftime('%Y-%m-%d %H:%M')}\u2013{le.strftime('%Y-%m-%d %H:%M')} ({dur}m)"
        else:
            ts = f"{ls.strftime('%H:%M')}\u2013{le.strftime('%H:%M') if le else '?'} ({dur}m)"

        lines.append(f"## {s['project']}")
        lines.append(f'- **Time:** {ts} | **Turns:** {s["turns"]}')

        transcript = _extract_transcript(s["jsonl"])
        summary = _ai_summarise(s["project"], transcript)

        if summary:
            lines.append("")
            for summary_line in summary.splitlines():
                lines.append(summary_line)
        else:
            fallback = _first_user_message(s["jsonl"])
            if fallback:
                lines.append(f"- **Started with:** {fallback}")

        lines.append("")

    return "\n".join(lines)


def post_to_ingest(date_str: str, content: str) -> bool:
    """POST bede-sessions.md to the data-ingest service."""
    if not INGEST_TOKEN:
        log.warning("INGEST_WRITE_TOKEN not set — cannot POST")
        return False

    payload = json.dumps({
        "date": date_str,
        "files": {"bede-sessions.md": content},
    }).encode()

    req = urllib.request.Request(
        INGEST_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {INGEST_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
            log.info("POST succeeded: %s row(s) inserted", body.get("rows_inserted", "?"))
            return True
    except urllib.error.HTTPError as e:
        log.error("POST failed (HTTP %d): %s", e.code, e.read().decode()[:200])
    except Exception as e:
        log.error("POST failed: %s", e)
    return False


def collect_and_post(target_date: date_type | None = None) -> bool:
    """Main entry point: discover sessions, build markdown, POST to ingest."""
    if target_date is None:
        target_date = datetime.now().astimezone().date()

    log.info("Collecting Bede sessions for %s", target_date)
    sessions = discover_sessions(target_date)

    if not sessions:
        log.info("No Bede sessions found for %s — nothing to POST", target_date)
        return True

    content = build_markdown(sessions, target_date)
    log.info("Generated report: %d session(s), %d lines", len(sessions), content.count("\n"))

    return post_to_ingest(target_date.isoformat(), content)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    target = None
    if len(sys.argv) > 1:
        target = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    collect_and_post(target)
