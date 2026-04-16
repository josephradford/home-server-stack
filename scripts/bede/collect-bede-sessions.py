#!/usr/bin/env python3
"""collect-bede-sessions.py <projects_dir> <date YYYY-MM-DD> <claude_bin>

Discovers Claude Code session JSONL files (created by Bede's claude -p calls)
modified on the given date, generates AI summaries, and prints a Markdown report.

Ported from dotfiles/scripts/claude-sessions.py for server-side use.
Called by collect-bede-sessions.sh to produce bede-sessions.md.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

projects_dir = Path(sys.argv[1])
target_date_str = sys.argv[2]
claude_bin = sys.argv[3]
target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()

STRIP_PREFIXES = [
    '-app-',
    '-home-bede-',
]


def readable_project(slug):
    for prefix in STRIP_PREFIXES:
        if slug.startswith(prefix):
            slug = slug[len(prefix):]
            break
    return slug.strip('-').replace('-', '/')


def extract_text(content):
    """Pull plain text out of a message content field (str or list of blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text']
        return ' '.join(parts)
    return ''


def is_noise(text):
    return (not text or len(text) < 15
            or '<local-command-caveat>' in text
            or '<command-name>' in text
            or text.strip().startswith('<'))


def extract_transcript(jsonl_path, max_chars=6000):
    """Build a condensed human-readable transcript for summarisation."""
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
                t = obj.get('type', '')
                if t == 'user':
                    text = extract_text(obj.get('message', {}).get('content', ''))
                    if not is_noise(text):
                        entries.append(('User', text[:600]))
                elif t == 'assistant':
                    blocks = obj.get('message', {}).get('content', [])
                    if not isinstance(blocks, list):
                        continue
                    text_parts = [b.get('text', '') for b in blocks if isinstance(b, dict) and b.get('type') == 'text']
                    tool_names = [b.get('name', '') for b in blocks if isinstance(b, dict) and b.get('type') == 'tool_use' and b.get('name')]
                    text = ' '.join(text_parts).strip()
                    if tool_names and not text:
                        entries.append(('Assistant (tools)', ', '.join(tool_names)))
                    elif text:
                        suffix = f' [also used: {", ".join(tool_names)}]' if tool_names else ''
                        entries.append(('Assistant', text[:500] + suffix))
    except Exception:
        return ''

    if not entries:
        return ''

    if len(entries) > 20:
        middle_count = len(entries) - 20
        selected = entries[:10] + [('...', f'[{middle_count} more turns]')] + entries[-10:]
    else:
        selected = entries

    transcript = ''
    for role, text in selected:
        line = f'[{role}]: {text}\n\n'
        if len(transcript) + len(line) > max_chars:
            transcript += '[transcript truncated]\n'
            break
        transcript += line
    return transcript.strip()


def ai_summarise(project, transcript):
    """Call claude -p to produce a structured session summary."""
    if not transcript or not os.path.isfile(claude_bin):
        return None
    prompt = (
        f'The following is a condensed Bede (Telegram AI assistant) session for the project "{project}".\n\n'
        'Write a short summary (2-4 sentences) of what was discussed or worked on. '
        'Then add two brief bullet-point sections:\n'
        '- **Conclusions:** things that were decided, completed, or answered\n'
        '- **Loose ends:** open questions, next steps, or unresolved issues\n'
        'Use "none" if a section is empty. Be concise.\n\n'
        f'--- TRANSCRIPT ---\n{transcript}\n--- END ---'
    )
    try:
        result = subprocess.run(
            [claude_bin, '-p', prompt, '--output-format', 'text'],
            capture_output=True, text=True, timeout=90
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


# -- Discover sessions --------------------------------------------------------
sessions = []

if not projects_dir.is_dir():
    print(f'# Bede Sessions \u2014 {target_date_str}\n\n_(projects directory not found)_')
    sys.exit(0)

for project_dir in sorted(projects_dir.iterdir()):
    if not project_dir.is_dir():
        continue
    for jsonl_file in sorted(project_dir.glob('*.jsonl')):
        if jsonl_file.parent.name != project_dir.name:
            continue  # skip subagent files

        mtime_date = datetime.fromtimestamp(jsonl_file.stat().st_mtime).date()
        if abs((mtime_date - target_date).days) > 7:
            continue

        project = readable_project(project_dir.name)
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
                    ts_str = obj.get('timestamp', '')
                    if ts_str:
                        try:
                            ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                            if start_ts is None or ts < start_ts:
                                start_ts = ts
                            if end_ts is None or ts > end_ts:
                                end_ts = ts
                        except ValueError:
                            pass
                    if obj.get('type') in ('user', 'assistant'):
                        turns += 1
        except Exception:
            continue

        if start_ts is None:
            continue

        start_local = start_ts.astimezone().date()
        end_local = (end_ts.astimezone().date() if end_ts else start_local)
        if not (start_local <= target_date <= end_local):
            continue

        # Skip sessions created by this script's own summarisation calls
        is_meta_summary = False
        try:
            with open(jsonl_file) as f:
                for raw in f:
                    raw = raw.strip()
                    if not raw:
                        continue
                    obj = json.loads(raw)
                    if obj.get('type') == 'user':
                        text = extract_text(obj.get('message', {}).get('content', ''))
                        if text and len(text) > 15:
                            if 'condensed Bede' in text or 'condensed Claude Code session' in text:
                                is_meta_summary = True
                            break
        except Exception:
            pass
        if is_meta_summary:
            continue

        sessions.append({
            'project': project,
            'jsonl': jsonl_file,
            'start': start_ts,
            'end': end_ts,
            'turns': turns,
        })

sessions.sort(key=lambda s: s['start'])

# -- Build output -------------------------------------------------------------
lines = [f'# Bede Sessions \u2014 {target_date_str}', '']

if not sessions:
    lines.append('_(no sessions)_')
else:
    lines.append(f'_{len(sessions)} session(s)_')
    lines.append('')
    for s in sessions:
        ls = s['start'].astimezone()
        le = s['end'].astimezone() if s['end'] else None
        dur = int((le - ls).total_seconds() / 60) if le else 0
        if le and ls.date() != le.date():
            ts = f"{ls.strftime('%Y-%m-%d %H:%M')}\u2013{le.strftime('%Y-%m-%d %H:%M')} ({dur}m)"
        else:
            ts = f"{ls.strftime('%H:%M')}\u2013{le.strftime('%H:%M') if le else '?'} ({dur}m)"

        lines.append(f"## {s['project']}")
        lines.append(f'- **Time:** {ts} | **Turns:** {s["turns"]}')

        transcript = extract_transcript(s['jsonl'])
        summary = ai_summarise(s['project'], transcript)

        if summary:
            lines.append('')
            for summary_line in summary.splitlines():
                lines.append(summary_line)
        else:
            fallback = ''
            try:
                with open(s['jsonl']) as f:
                    for raw in f:
                        raw = raw.strip()
                        if not raw:
                            continue
                        obj = json.loads(raw)
                        if obj.get('type') == 'user':
                            text = extract_text(obj.get('message', {}).get('content', ''))
                            if not is_noise(text):
                                fallback = text[:200]
                                break
            except Exception:
                pass
            if fallback:
                lines.append(f'- **Started with:** {fallback}')

        lines.append('')

print('\n'.join(lines))
