# bede-core Prototype Parity Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the feature gaps between the bede-core implementation and the working prototype — interactive sessions, multi-step tasks, task cancellation, and UX polish.

**Architecture:** These are additive changes to bede-core's existing modules (SessionManager, TaskRunner, bot handlers) plus a small schema extension in bede-data. No new modules except `reflection.py`. All features are proven patterns from the production prototype — this plan ports them to the clean architecture.

**Tech Stack:** Python 3.12, python-telegram-bot 21.x, APScheduler 3.10, httpx, pytest, pytest-asyncio

**Repositories:**
- `josephradford/bede` — bede-core code under `bede-core/`, bede-data code under `bede-data/`
- `josephradford/home-server-stack` — this plan document

**Key references:**
- Prototype bot: `/Users/joeradford/dev/bede/bot.py`
- Prototype scheduler: `/Users/joeradford/dev/bede/scheduler.py`
- Design doc: `docs/superpowers/specs/2026-04-29-bede-design.md` (Sections 2.1, 3, 6)
- Requirements doc: `docs/superpowers/specs/2026-04-29-bede-requirements.md` (C7)

---

## Scope

**In scope (this plan):**
- Interactive session tracking — model override, idle/max-age timeouts (Design §2.1, Requirements C7)
- Interactive task handoff — scheduler registers interactive session after `interactive: true` tasks
- Reflection memory — user corrections during interactive sessions appended to vault file
- Cancel running tasks on `/reset` — kill subprocesses, report cancelled tasks
- Typing indicator during scheduled task execution
- Bot `disable_web_page_preview` in reply handler
- Multi-step task schema extension (bede-data: `task_config` JSON column)
- Multi-step + parallel task execution in TaskRunner

**Out of scope:**
- C7 fallback retry (3 unanswered attempts → non-interactive delivery) — future plan
- New scheduled task definitions — task config is created via bede-data API, not this plan

---

## File Structure

```
bede-core/src/bede_core/
├── session_manager.py   # Modified: interactive state tracking, model override
├── scheduler.py         # Modified: interactive handoff, typing, cancel tracking, multi-step execution
├── bot.py               # Modified: interactive awareness, cancel on reset, disable_web_page_preview
├── reflection.py        # New: append corrections to vault reflection-memory.md
├── config.py            # Modified: vault_repo env var
└── main.py              # Modified: pass typing_fn and runner to bot handlers

bede-core/tests/
├── test_session_manager.py  # Modified: interactive session tests
├── test_scheduler.py        # Modified: interactive handoff, cancel, multi-step tests
├── test_bot.py              # Modified: cancel, interactive tests
└── test_reflection.py       # New: reflection memory tests

bede-data/src/bede_data/
├── db/schema.py         # Modified: task_config column on schedules table
├── db/connection.py     # Modified: migration for version 4
└── api/config_api.py    # Modified: task_config in schedule CRUD
```

### Module dependency changes

```
main.py
├── bot.py
│   ├── session_manager.py (now exposes is_interactive, interactive_model)
│   ├── scheduler.py (now exposes cancel_all)
│   └── reflection.py (NEW — append corrections to vault)
├── scheduler.py
│   ├── session_manager.py (now calls register_interactive)
│   └── typing_fn callback (passed from main.py)
└── config.py (adds vault_repo)
```

---

### Task 1: Interactive Session Tracking

**Files:**
- Modify: `bede-core/src/bede_core/session_manager.py`
- Modify: `bede-core/src/bede_core/config.py`
- Modify: `bede-core/tests/test_session_manager.py`

When a scheduled task is `interactive: true`, the session manager must override the model for subsequent user messages and track idle/max-age timeouts. The daily session ID is already shared — interactive mode just changes which model is used and marks the session as interactive.

- [ ] **Step 1: Write the interactive session tests**

Add to `bede-core/tests/test_session_manager.py`:

```python
import time


class TestInteractiveSession:
    async def test_register_interactive_overrides_model(
        self, sm, data_client, claude_cli
    ):
        data_client.get.return_value = {"date": "2026-05-01", "session_id": "sess-1"}
        claude_cli.run.return_value = ClaudeResult(
            text="Reply!", session_id="sess-1"
        )

        sm.register_interactive("claude-sonnet-4-5-20250514")
        await sm.send("Hello")

        call_kwargs = claude_cli.run.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-5-20250514"

    async def test_interactive_refreshes_idle_on_send(
        self, sm, data_client, claude_cli
    ):
        data_client.get.return_value = {"date": "2026-05-01", "session_id": "sess-1"}
        claude_cli.run.return_value = ClaudeResult(
            text="Reply!", session_id="sess-1"
        )

        sm.register_interactive("claude-sonnet-4-5-20250514")
        await sm.send("Message 1")
        await sm.send("Message 2")

        assert claude_cli.run.call_count == 2
        for call in claude_cli.run.call_args_list:
            assert call.kwargs["model"] == "claude-sonnet-4-5-20250514"

    async def test_interactive_expires_after_idle_timeout(
        self, data_client, claude_cli, memory_manager
    ):
        sm = SessionManager(
            data_client=data_client,
            claude_cli=claude_cli,
            memory_manager=memory_manager,
            timezone="Australia/Sydney",
            model="claude-haiku-4-5-20251001",
            vault_path="/vault",
            interactive_idle_timeout=0.01,
            interactive_max_age=3600,
        )
        data_client.get.return_value = {"date": "2026-05-01", "session_id": "sess-1"}
        claude_cli.run.return_value = ClaudeResult(
            text="Reply!", session_id="sess-1"
        )

        sm.register_interactive("claude-sonnet-4-5-20250514")
        time.sleep(0.02)
        await sm.send("Hello")

        call_kwargs = claude_cli.run.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"

    async def test_interactive_expires_after_max_age(
        self, data_client, claude_cli, memory_manager
    ):
        sm = SessionManager(
            data_client=data_client,
            claude_cli=claude_cli,
            memory_manager=memory_manager,
            timezone="Australia/Sydney",
            model="claude-haiku-4-5-20251001",
            vault_path="/vault",
            interactive_idle_timeout=3600,
            interactive_max_age=0.01,
        )
        data_client.get.return_value = {"date": "2026-05-01", "session_id": "sess-1"}
        claude_cli.run.return_value = ClaudeResult(
            text="Reply!", session_id="sess-1"
        )

        sm.register_interactive("claude-sonnet-4-5-20250514")
        time.sleep(0.02)
        await sm.send("Hello")

        call_kwargs = claude_cli.run.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"

    async def test_clear_interactive(self, sm, data_client, claude_cli):
        data_client.get.return_value = {"date": "2026-05-01", "session_id": "sess-1"}
        claude_cli.run.return_value = ClaudeResult(
            text="Reply!", session_id="sess-1"
        )

        sm.register_interactive("claude-sonnet-4-5-20250514")
        sm.clear_interactive()
        await sm.send("Hello")

        call_kwargs = claude_cli.run.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-5-20250514"

    def test_is_interactive(self, sm):
        assert sm.is_interactive is False
        sm.register_interactive("claude-sonnet-4-5-20250514")
        assert sm.is_interactive is True
        sm.clear_interactive()
        assert sm.is_interactive is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/joeradford/dev/bede/bede-core && uv run pytest tests/test_session_manager.py::TestInteractiveSession -v`
Expected: FAIL — `register_interactive` does not exist.

- [ ] **Step 3: Add interactive state to SessionManager**

Modify `bede-core/src/bede_core/session_manager.py`:

```python
import logging
import subprocess
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from bede_core.claude_cli import ClaudeCli, ClaudeResult
from bede_core.data_client import DataClient
from bede_core.memory_manager import MemoryManager

log = logging.getLogger(__name__)


class SessionManager:
    def __init__(
        self,
        data_client: DataClient,
        claude_cli: ClaudeCli,
        memory_manager: MemoryManager,
        timezone: str,
        model: str,
        vault_path: str,
        interactive_idle_timeout: float = 1800,
        interactive_max_age: float = 7200,
    ):
        self._data = data_client
        self._cli = claude_cli
        self._memory = memory_manager
        self._tz = ZoneInfo(timezone)
        self._model = model
        self._vault_path = vault_path
        self._session_cleared = False
        self._idle_timeout = interactive_idle_timeout
        self._max_age = interactive_max_age
        self._interactive: dict | None = None

    def register_interactive(self, model: str):
        now = time.monotonic()
        self._interactive = {"model": model, "idle_ts": now, "created_ts": now}
        log.info("Interactive session registered (model: %s)", model)

    def clear_interactive(self):
        self._interactive = None

    @property
    def is_interactive(self) -> bool:
        return self._get_interactive_model() is not None

    @property
    def interactive_model(self) -> str | None:
        return self._get_interactive_model()

    def _get_interactive_model(self) -> str | None:
        if self._interactive is None:
            return None
        now = time.monotonic()
        idle_ok = (now - self._interactive["idle_ts"]) < self._idle_timeout
        age_ok = (now - self._interactive["created_ts"]) < self._max_age
        if idle_ok and age_ok:
            return self._interactive["model"]
        log.info("Interactive session expired (idle_ok=%s, age_ok=%s).", idle_ok, age_ok)
        self._interactive = None
        return None

    # ... existing _today, _now_str, _get_daily_session_id, _store_daily_session,
    # _get_scratchpad, _append_scratchpad, _build_context, _pull_vault unchanged ...

    async def send(
        self,
        message: str,
        model: str | None = None,
        timeout: int | None = None,
    ) -> ClaudeResult:
        import asyncio

        await asyncio.to_thread(self._pull_vault)

        interactive_model = self._get_interactive_model()
        if interactive_model:
            effective_model = model or interactive_model
        else:
            effective_model = model or self._model

        session_id = await self._get_daily_session_id()
        is_new_session = session_id is None

        if is_new_session:
            prompt = await self._build_context(message, is_new_session=True)
        else:
            prompt = await self._build_context(message, is_new_session=False)

        result = await self._cli.run(
            prompt=prompt,
            model=effective_model,
            session_id=session_id,
            timeout=timeout,
        )

        if result.stale_session and session_id:
            log.warning("Stale session %s, retrying fresh.", session_id)
            prompt = await self._build_context(message, is_new_session=True)
            result = await self._cli.run(
                prompt=prompt,
                model=effective_model,
                session_id=None,
                timeout=timeout,
            )
            result.stale_session = False

        if result.session_id and result.session_id != session_id:
            await self._store_daily_session(result.session_id)

        if result.text and not result.timed_out and not result.auth_failure:
            summary = f"User: {message[:100]}\nBede: {result.text[:200]}"
            await self._append_scratchpad(summary)

        if self._interactive and not result.timed_out and not result.auth_failure:
            self._interactive["idle_ts"] = time.monotonic()

        return result

    # ... existing send_task, clear_daily_session, append_scratchpad_entry unchanged ...
```

- [ ] **Step 4: Update SessionManager constructor in main.py**

Modify the SessionManager instantiation in `bede-core/src/bede_core/main.py`:

```python
    session_manager = SessionManager(
        data_client=data_client,
        claude_cli=claude_cli,
        memory_manager=memory_manager,
        timezone=settings.timezone,
        model=settings.claude_model,
        vault_path=settings.vault_path,
        interactive_idle_timeout=settings.interactive_idle_timeout_minutes * 60,
        interactive_max_age=settings.interactive_max_age_hours * 3600,
    )
```

- [ ] **Step 5: Update the `sm` fixture in tests to match new signature**

The existing `sm` fixture in `test_session_manager.py` must accept the new kwargs without breaking. The defaults handle this — no fixture change needed since the new params have defaults. Verify:

Run: `cd /Users/joeradford/dev/bede/bede-core && uv run pytest tests/test_session_manager.py -v`
Expected: All tests pass (existing + new interactive tests).

- [ ] **Step 6: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-core/src/bede_core/session_manager.py bede-core/src/bede_core/main.py bede-core/tests/test_session_manager.py
git commit -m "feat(bede-core): interactive session tracking with model override and timeouts"
```

---

### Task 2: Interactive Task Handoff

**Files:**
- Modify: `bede-core/src/bede_core/scheduler.py`
- Modify: `bede-core/tests/test_scheduler.py`

After a task with `interactive: true` runs successfully, the TaskRunner registers the interactive session in the SessionManager so subsequent user messages use the task's model.

- [ ] **Step 1: Write the interactive handoff test**

Add to `bede-core/tests/test_scheduler.py`:

```python
class TestInteractiveHandoff:
    async def test_interactive_task_registers_session(
        self, runner, data_client, session_manager, send_fn
    ):
        task = {
            "task_name": "Evening Reflection",
            "cron_expression": "0 21 * * *",
            "prompt": "Write the evening reflection",
            "model": "claude-sonnet-4-5-20250514",
            "timeout_seconds": 300,
            "interactive": True,
        }
        data_client.post.return_value = {"id": 1, "status": "running"}
        data_client.put.return_value = {"id": 1, "status": "success"}

        await runner.run_task(task)

        session_manager.register_interactive.assert_called_once_with(
            "claude-sonnet-4-5-20250514"
        )

    async def test_non_interactive_task_does_not_register(
        self, runner, data_client, session_manager, send_fn
    ):
        task = {
            "task_name": "Morning Briefing",
            "cron_expression": "0 8 * * 1-5",
            "prompt": "Give me a briefing",
            "model": None,
            "timeout_seconds": 300,
            "interactive": False,
        }
        data_client.post.return_value = {"id": 1, "status": "running"}
        data_client.put.return_value = {"id": 1, "status": "success"}

        await runner.run_task(task)

        session_manager.register_interactive.assert_not_called()

    async def test_interactive_not_registered_on_timeout(
        self, runner, data_client, session_manager, send_fn
    ):
        task = {
            "task_name": "Evening Reflection",
            "cron_expression": "0 21 * * *",
            "prompt": "Write the evening reflection",
            "model": "claude-sonnet-4-5-20250514",
            "timeout_seconds": 60,
            "interactive": True,
        }
        session_manager.send_task.return_value = ClaudeResult(timed_out=True)
        data_client.post.return_value = {"id": 1, "status": "running"}
        data_client.put.return_value = {"id": 1, "status": "timeout"}

        await runner.run_task(task)

        session_manager.register_interactive.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/joeradford/dev/bede/bede-core && uv run pytest tests/test_scheduler.py::TestInteractiveHandoff -v`
Expected: FAIL — `register_interactive` never called.

- [ ] **Step 3: Add interactive handoff to `_run_task_inner`**

Modify `bede-core/src/bede_core/scheduler.py`, in `_run_task_inner`, after the successful output handling (after the quiet hours check block):

```python
    async def _run_task_inner(self, task: dict):
        name = task["task_name"]
        prompt = task["prompt"]
        model = task.get("model")
        timeout = task.get("timeout_seconds", 300)
        interactive = task.get("interactive", False)

        now = datetime.now(self._tz)
        now_str = now.strftime("%H:%M")
        now_date_str = now.strftime("%A, %d %B %Y")
        prompt = f"Today is {now_date_str}.\n\n{prompt}"

        cron = task.get("cron_expression", "")
        next_str = _next_run_str(cron, self._tz, now)

        log.info("Running task: %s (timeout: %ds)", name, timeout)

        result = await self._session.send_task(prompt, model=model, timeout=timeout)

        if result.timed_out:
            mins = timeout // 60
            await self._send(f"📅 *{name}*\n⚠️ Timed out after {mins} minutes.")
            return

        text = result.text or "No response."

        if result.stop_reason == "max_tokens":
            text += "\n\n⚠️ _Response was truncated (output token limit reached)._"

        header = f"📅 *{name}* ({now_str})"
        if next_str:
            header += f"\n↻ Next: {next_str}"
        header += "\n---\n"

        output = header + text
        now_check = datetime.now(self._tz)
        if is_quiet_hours(now_check, self._quiet_start, self._quiet_end):
            await self._data.post(
                "/api/message-queue",
                body={
                    "message": output,
                    "source": f"scheduler:{name}",
                },
            )
            log.info("Task '%s' output queued (quiet hours).", name)
        else:
            await self._send(output)

        if interactive and model and not result.timed_out:
            self._session.register_interactive(model)
```

- [ ] **Step 4: Run all scheduler tests**

Run: `cd /Users/joeradford/dev/bede/bede-core && uv run pytest tests/test_scheduler.py -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-core/src/bede_core/scheduler.py bede-core/tests/test_scheduler.py
git commit -m "feat(bede-core): interactive task handoff from scheduler to session manager"
```

---

### Task 3: Reflection Memory

**Files:**
- Create: `bede-core/src/bede_core/reflection.py`
- Create: `bede-core/tests/test_reflection.py`
- Modify: `bede-core/src/bede_core/bot.py`
- Modify: `bede-core/src/bede_core/config.py`
- Modify: `bede-core/src/bede_core/main.py`
- Modify: `bede-core/tests/test_bot.py`

During interactive sessions, the user's messages are corrections/feedback to the scheduled task output (e.g., Evening Reflection). These corrections are appended to `Bede/reflection-memory.md` in the vault and committed+pushed so they're available on the next run.

- [ ] **Step 1: Write the reflection module tests**

Create `bede-core/tests/test_reflection.py`:

```python
import os
import pytest
from unittest.mock import patch

from bede_core.reflection import append_correction


class TestReflection:
    def test_creates_file_if_missing(self, tmp_path):
        bede_dir = tmp_path / "Bede"
        bede_dir.mkdir()
        path = str(bede_dir / "reflection-memory.md")

        with patch("bede_core.reflection._git_commit_push"):
            append_correction("Fix the tone", str(tmp_path), "Australia/Sydney")

        assert os.path.isfile(path)
        content = open(path).read()
        assert "Fix the tone" in content
        assert "# Reflection Memory" in content

    def test_appends_to_existing_file(self, tmp_path):
        bede_dir = tmp_path / "Bede"
        bede_dir.mkdir()
        path = bede_dir / "reflection-memory.md"
        path.write_text("# Reflection Memory\n\n## Corrections\n\n- [2026-04-30 21:00] Old correction\n")

        with patch("bede_core.reflection._git_commit_push"):
            append_correction("New correction", str(tmp_path), "Australia/Sydney")

        content = path.read_text()
        assert "Old correction" in content
        assert "New correction" in content

    def test_includes_timestamp(self, tmp_path):
        bede_dir = tmp_path / "Bede"
        bede_dir.mkdir()

        with patch("bede_core.reflection._git_commit_push"):
            append_correction("Something", str(tmp_path), "Australia/Sydney")

        content = (bede_dir / "reflection-memory.md").read_text()
        assert "2026-" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/joeradford/dev/bede/bede-core && uv run pytest tests/test_reflection.py -v`
Expected: FAIL — `bede_core.reflection` does not exist.

- [ ] **Step 3: Implement the reflection module**

Create `bede-core/src/bede_core/reflection.py`:

```python
import logging
import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

REFLECTION_REL_PATH = os.path.join("Bede", "reflection-memory.md")

_HEADER = (
    "# Reflection Memory\n\n"
    "Corrections and preferences Joe has provided about Evening Reflections.\n"
    "Bede reads this at the start of each reflection to avoid repeating mistakes.\n\n"
    "## Corrections\n\n"
)


def _git_commit_push(vault_path: str, file_path: str):
    try:
        subprocess.run(
            ["git", "-C", vault_path, "add", file_path],
            capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "-C", vault_path, "commit", "-m", "reflection: save correction"],
            capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "-C", vault_path, "push"],
            capture_output=True, timeout=30,
        )
    except Exception as e:
        log.warning("Failed to commit reflection correction: %s", e)


def append_correction(text: str, vault_path: str, timezone: str):
    full_path = os.path.join(vault_path, REFLECTION_REL_PATH)
    now = datetime.now(ZoneInfo(timezone))
    timestamp = now.strftime("%Y-%m-%d %H:%M")

    if not os.path.isfile(full_path):
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(_HEADER)

    with open(full_path, "a") as f:
        f.write(f"- [{timestamp}] {text}\n")

    _git_commit_push(vault_path, full_path)
```

- [ ] **Step 4: Run reflection tests**

Run: `cd /Users/joeradford/dev/bede/bede-core && uv run pytest tests/test_reflection.py -v`
Expected: All pass.

- [ ] **Step 5: Write bot interactive correction test**

Add to `bede-core/tests/test_bot.py`:

```python
class TestInteractiveCorrections:
    async def test_appends_correction_during_interactive(self, session_manager):
        from bede_core.bot import create_message_handler

        session_manager.send.return_value = ClaudeResult(
            text="Noted!", session_id="s1"
        )
        session_manager.is_interactive = True

        correction_calls = []

        def fake_append(text, vault, tz):
            correction_calls.append(text)

        handler = create_message_handler(
            session_manager,
            allowed_user_id=12345,
            timezone="Australia/Sydney",
            append_correction_fn=fake_append,
        )

        update = FakeUpdate("Actually the tone was wrong", user_id=12345)
        context = FakeContext()
        await handler(update, context)

        assert len(correction_calls) == 1
        assert "tone was wrong" in correction_calls[0]

    async def test_no_correction_when_not_interactive(self, session_manager):
        from bede_core.bot import create_message_handler

        session_manager.send.return_value = ClaudeResult(
            text="Hello!", session_id="s1"
        )
        session_manager.is_interactive = False

        correction_calls = []

        def fake_append(text, vault, tz):
            correction_calls.append(text)

        handler = create_message_handler(
            session_manager,
            allowed_user_id=12345,
            timezone="Australia/Sydney",
            append_correction_fn=fake_append,
        )

        update = FakeUpdate("Hello", user_id=12345)
        context = FakeContext()
        await handler(update, context)

        assert len(correction_calls) == 0
```

- [ ] **Step 6: Add correction call to bot message handler**

Modify `bede-core/src/bede_core/bot.py`. Update `create_message_handler` to accept an `append_correction_fn` parameter, and call it during interactive sessions:

```python
def create_message_handler(
    session_manager: SessionManager,
    allowed_user_id: int,
    timezone: str,
    data_client=None,
    append_correction_fn=None,
):
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != allowed_user_id:
            log.warning("Rejected message from user %s", update.effective_user.id)
            return

        chat_id = update.effective_chat.id
        text = update.message.text

        typing_task = asyncio.create_task(_keep_typing(context.bot, chat_id))
        try:
            result = await session_manager.send(text)
        except Exception as e:
            log.error("Unexpected error handling message: %s", e)
            await update.message.reply_text("Something went wrong. Please try again.")
            return
        finally:
            typing_task.cancel()

        if result.timed_out:
            if data_client:
                await data_client.post(
                    "/api/message-queue", body={"message": text, "source": "telegram"}
                )
                await update.message.reply_text(
                    "Request timed out. I've queued your message and will process it when I'm available."
                )
            else:
                await update.message.reply_text("Request timed out.")
            return

        if result.auth_failure:
            if data_client:
                await data_client.post(
                    "/api/message-queue", body={"message": text, "source": "telegram"}
                )
            await update.message.reply_text(REAUTH_NOTICE, parse_mode="Markdown")
            return

        response_text = result.text or "No response."

        if result.stop_reason == "max_tokens":
            response_text += (
                "\n\n⚠️ _Response was truncated (output token limit reached)._"
            )

        if session_manager.is_interactive and append_correction_fn:
            await asyncio.to_thread(append_correction_fn, text)

        await _send_response(update.message, response_text)

    return handle_message
```

- [ ] **Step 7: Wire correction function in main.py**

Modify the message handler creation in `bede-core/src/bede_core/main.py`:

```python
    from bede_core.reflection import append_correction
    from functools import partial

    correction_fn = partial(
        append_correction,
        vault_path=settings.vault_path,
        timezone=settings.timezone,
    )
```

Then update the `create_message_handler` call:

```python
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            create_message_handler(
                session_manager,
                settings.allowed_user_id,
                settings.timezone,
                data_client=data_client,
                append_correction_fn=correction_fn,
            ),
        )
    )
```

- [ ] **Step 8: Add `vault_repo` to config (needed by entrypoint, already exists as env var)**

Verify `VAULT_REPO` is already available in `docker-compose.ai.yml` for bede-core. It is — line 109 has `VAULT_REPO=${VAULT_REPO}`. No config.py change needed since `reflection.py` takes `vault_path` directly.

- [ ] **Step 9: Run all tests**

Run: `cd /Users/joeradford/dev/bede/bede-core && uv run pytest tests/ -v`
Expected: All pass.

- [ ] **Step 10: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-core/src/bede_core/reflection.py bede-core/tests/test_reflection.py bede-core/src/bede_core/bot.py bede-core/tests/test_bot.py bede-core/src/bede_core/main.py
git commit -m "feat(bede-core): reflection memory — append corrections during interactive sessions"
```

---

### Task 4: Cancel Running Tasks on /reset

**Files:**
- Modify: `bede-core/src/bede_core/scheduler.py`
- Modify: `bede-core/src/bede_core/bot.py`
- Modify: `bede-core/src/bede_core/main.py`
- Modify: `bede-core/tests/test_scheduler.py`
- Modify: `bede-core/tests/test_bot.py`

When the user sends `/reset`, all running scheduled tasks should be cancelled and their subprocesses killed. The user should see which tasks were cancelled.

- [ ] **Step 1: Write the cancel tests**

Add to `bede-core/tests/test_scheduler.py`:

```python
class TestCancelTasks:
    def test_cancel_all_returns_running_names(self, runner):
        runner._running.add("Morning Briefing")
        runner._running.add("Deal Scout")

        cancelled = runner.cancel_all()

        assert set(cancelled) == {"Morning Briefing", "Deal Scout"}
        assert len(runner._running) == 0

    def test_cancel_all_empty_when_nothing_running(self, runner):
        cancelled = runner.cancel_all()
        assert cancelled == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/joeradford/dev/bede/bede-core && uv run pytest tests/test_scheduler.py::TestCancelTasks -v`
Expected: FAIL — `cancel_all` does not exist.

- [ ] **Step 3: Add `cancel_all` to TaskRunner**

Add to `bede-core/src/bede_core/scheduler.py`, in the `TaskRunner` class:

```python
    def cancel_all(self) -> list[str]:
        cancelled = list(self._running)
        self._running.clear()
        return cancelled
```

- [ ] **Step 4: Write bot reset cancel test**

Add to `bede-core/tests/test_bot.py`:

```python
class TestResetCancellation:
    async def test_reset_cancels_running_tasks(self, session_manager):
        from bede_core.bot import create_reset_handler

        runner = MagicMock()
        runner.cancel_all.return_value = ["Morning Briefing", "Deal Scout"]

        handler = create_reset_handler(
            session_manager, allowed_user_id=12345, runner=runner
        )

        update = FakeUpdate("/reset", user_id=12345)
        context = FakeContext()
        await handler(update, context)

        runner.cancel_all.assert_called_once()
        session_manager.clear_interactive.assert_called_once()
        reply_text = update.message.reply_text.call_args.args[0]
        assert "Morning Briefing" in reply_text
        assert "Deal Scout" in reply_text

    async def test_reset_no_tasks_running(self, session_manager):
        from bede_core.bot import create_reset_handler

        runner = MagicMock()
        runner.cancel_all.return_value = []

        handler = create_reset_handler(
            session_manager, allowed_user_id=12345, runner=runner
        )

        update = FakeUpdate("/reset", user_id=12345)
        context = FakeContext()
        await handler(update, context)

        reply_text = update.message.reply_text.call_args.args[0]
        assert "cleared" in reply_text.lower()
```

- [ ] **Step 5: Update `create_reset_handler` to accept runner**

Modify `bede-core/src/bede_core/bot.py`:

```python
def create_reset_handler(session_manager: SessionManager, allowed_user_id: int, runner=None):
    async def handle_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != allowed_user_id:
            return
        await session_manager.clear_daily_session()
        session_manager.clear_interactive()
        cancelled = runner.cancel_all() if runner else []
        if cancelled:
            names = ", ".join(cancelled)
            await update.message.reply_text(f"Session cleared. Cancelled running tasks: {names}")
        else:
            await update.message.reply_text("Session cleared. Next message starts fresh.")

    return handle_reset
```

- [ ] **Step 6: Pass runner to reset handler in main.py**

Modify `bede-core/src/bede_core/main.py`:

```python
    app.add_handler(
        CommandHandler(
            "reset", create_reset_handler(session_manager, settings.allowed_user_id, runner=runner)
        )
    )
```

- [ ] **Step 7: Run all tests**

Run: `cd /Users/joeradford/dev/bede/bede-core && uv run pytest tests/ -v`
Expected: All pass.

- [ ] **Step 8: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-core/src/bede_core/scheduler.py bede-core/src/bede_core/bot.py bede-core/src/bede_core/main.py bede-core/tests/test_scheduler.py bede-core/tests/test_bot.py
git commit -m "feat(bede-core): cancel running tasks and clear interactive session on /reset"
```

---

### Task 5: Typing Indicator During Scheduled Tasks + Bot UX

**Files:**
- Modify: `bede-core/src/bede_core/scheduler.py`
- Modify: `bede-core/src/bede_core/bot.py`
- Modify: `bede-core/src/bede_core/main.py`
- Modify: `bede-core/tests/test_scheduler.py`

The prototype shows a typing indicator in Telegram while scheduled tasks are running. The bot reply handler should also set `disable_web_page_preview=True`.

- [ ] **Step 1: Write typing indicator test**

Add to `bede-core/tests/test_scheduler.py`:

```python
class TestTypingIndicator:
    async def test_typing_called_during_task(
        self, data_client, session_manager, send_fn
    ):
        typing_fn = AsyncMock()
        runner = TaskRunner(
            data_client=data_client,
            session_manager=session_manager,
            send_fn=send_fn,
            timezone="Australia/Sydney",
            quiet_hours_start=0,
            quiet_hours_end=0,
            typing_fn=typing_fn,
        )
        task = {
            "task_name": "Test Task",
            "cron_expression": "0 8 * * *",
            "prompt": "Do something",
            "model": None,
            "timeout_seconds": 300,
            "interactive": False,
        }
        data_client.post.return_value = {"id": 1, "status": "running"}
        data_client.put.return_value = {"id": 1, "status": "success"}

        await runner.run_task(task)

        typing_fn.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/joeradford/dev/bede/bede-core && uv run pytest tests/test_scheduler.py::TestTypingIndicator -v`
Expected: FAIL — `typing_fn` not accepted.

- [ ] **Step 3: Add typing support to TaskRunner**

Modify `bede-core/src/bede_core/scheduler.py`. Add `typing_fn` to `__init__` and call it in `run_task`:

```python
class TaskRunner:
    def __init__(
        self,
        data_client: DataClient,
        session_manager: SessionManager,
        send_fn,
        timezone: str,
        quiet_hours_start: int = 22,
        quiet_hours_end: int = 7,
        typing_fn=None,
    ):
        self._data = data_client
        self._session = session_manager
        self._send = send_fn
        self._tz = ZoneInfo(timezone)
        self._running: set[str] = set()
        self._quiet_start = quiet_hours_start
        self._quiet_end = quiet_hours_end
        self._typing_fn = typing_fn
```

Modify `run_task` to start typing before task execution:

```python
    async def run_task(self, task: dict):
        name = task["task_name"]

        if name in self._running:
            log.warning("Task '%s' already running — skipping.", name)
            return

        self._running.add(name)
        start = time.monotonic()
        exec_id = await self._log_start(name)

        typing_task = None
        if self._typing_fn:
            typing_task = asyncio.create_task(self._typing_fn())

        try:
            await self._run_task_inner(task)
            duration = time.monotonic() - start
            await self._log_end(exec_id, "success", duration)
        except Exception as e:
            duration = time.monotonic() - start
            log.error("Task '%s' failed: %s", name, e)
            await self._log_end(exec_id, "failure", duration, error=str(e))
            await self._send(f"⚠️ *{name}* failed: {e}")
        finally:
            if typing_task:
                typing_task.cancel()
            self._running.discard(name)
```

Add `import asyncio` at the top of the file if not already present.

- [ ] **Step 4: Create typing function in main.py**

Add to `bede-core/src/bede_core/main.py`, before the `runner` creation:

```python
    async def keep_typing():
        deadline = time.monotonic() + 3600
        while time.monotonic() < deadline:
            try:
                await app.bot.send_chat_action(
                    chat_id=settings.allowed_user_id, action="typing"
                )
            except Exception:
                pass
            await asyncio.sleep(4)
```

Add `import asyncio, time` at the top. Pass `typing_fn=keep_typing` to the `TaskRunner`:

```python
    runner = TaskRunner(
        data_client=data_client,
        session_manager=session_manager,
        send_fn=send_telegram,
        timezone=settings.timezone,
        quiet_hours_start=settings.quiet_hours_start,
        quiet_hours_end=settings.quiet_hours_end,
        typing_fn=keep_typing,
    )
```

- [ ] **Step 5: Add `disable_web_page_preview` to bot reply handler**

Modify `bede-core/src/bede_core/bot.py`, in `_send_response`:

```python
async def _send_response(message, text: str):
    for c in chunk_text(text):
        try:
            await message.reply_text(
                md_to_html(c), parse_mode="HTML", disable_web_page_preview=True
            )
        except Exception:
            await message.reply_text(c, disable_web_page_preview=True)
```

- [ ] **Step 6: Run all tests**

Run: `cd /Users/joeradford/dev/bede/bede-core && uv run pytest tests/ -v`
Expected: All pass.

- [ ] **Step 7: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-core/src/bede_core/scheduler.py bede-core/src/bede_core/bot.py bede-core/src/bede_core/main.py bede-core/tests/test_scheduler.py
git commit -m "feat(bede-core): typing indicator during scheduled tasks, disable link previews in bot"
```

---

### Task 6: Multi-Step Task Schema (bede-data)

**Files:**
- Modify: `bede-data/src/bede_data/db/schema.py`
- Modify: `bede-data/src/bede_data/db/connection.py`
- Modify: `bede-data/src/bede_data/api/config_api.py`
- Modify: `bede-data/tests/test_api_config.py`

Add a `task_config` TEXT column (JSON, nullable) to the `schedules` table. This holds multi-step task definitions. When null, the task is a single-step task using the `prompt` field.

- [ ] **Step 1: Write the API test for task_config**

Add to `bede-data/tests/test_api_config.py`:

```python
import json


class TestScheduleTaskConfig:
    def test_create_schedule_with_task_config(self, client):
        config = {
            "steps": [
                {"name": "Category 1", "prompt": "Check category 1"},
                {"name": "Category 2", "prompt": "Check category 2"},
                {"name": "Update Memory", "prompt": "Update...", "silent": True},
            ],
            "parallel": True,
        }
        resp = client.post("/api/config/schedules", json={
            "task_name": "Multi Step Task",
            "cron_expression": "0 14 * * 0",
            "prompt": "Preamble for all steps",
            "model": "claude-sonnet-4-5-20250514",
            "task_config": json.dumps(config),
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["task_name"] == "Multi Step Task"
        parsed = json.loads(data["task_config"])
        assert len(parsed["steps"]) == 3
        assert parsed["parallel"] is True

    def test_create_schedule_without_task_config(self, client):
        resp = client.post("/api/config/schedules", json={
            "task_name": "Simple Task",
            "cron_expression": "0 8 * * *",
            "prompt": "Do the thing",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["task_config"] is None

    def test_list_schedules_includes_task_config(self, client):
        config = json.dumps({"steps": [{"name": "S1", "prompt": "P1"}]})
        client.post("/api/config/schedules", json={
            "task_name": "Config Task",
            "cron_expression": "0 8 * * *",
            "prompt": "test",
            "task_config": config,
        })
        resp = client.get("/api/config/schedules")
        schedules = resp.json()["schedules"]
        found = [s for s in schedules if s["task_name"] == "Config Task"]
        assert len(found) == 1
        assert found[0]["task_config"] == config
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/joeradford/dev/bede/bede-data && uv run pytest tests/test_api_config.py::TestScheduleTaskConfig -v`
Expected: FAIL — `task_config` not accepted or not returned.

- [ ] **Step 3: Update schema**

Modify `bede-data/src/bede_data/db/schema.py`:

Change `SCHEMA_VERSION` from `3` to `4`.

In `SCHEMA_SQL`, update the `schedules` table to add `task_config` after `interactive`:

```sql
CREATE TABLE IF NOT EXISTS schedules (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name        TEXT NOT NULL UNIQUE,
    cron_expression  TEXT NOT NULL,
    prompt           TEXT NOT NULL,
    model            TEXT,
    timeout_seconds  INTEGER DEFAULT 300,
    interactive      INTEGER NOT NULL DEFAULT 0,
    task_config      TEXT,
    enabled          INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 4: Add migration in connection.py**

Modify `bede-data/src/bede_data/db/connection.py`, in `init_db`, add migration before `conn.executescript(SCHEMA_SQL)`:

```python
        if existing is not None and existing < 4:
            try:
                conn.execute("ALTER TABLE schedules ADD COLUMN task_config TEXT")
                conn.commit()
            except sqlite3.OperationalError:
                pass
```

This goes after the existing `if existing is not None and existing < 3:` block and before `conn.executescript(SCHEMA_SQL)`.

- [ ] **Step 5: Update API models and endpoints**

Modify `bede-data/src/bede_data/api/config_api.py`:

Add `task_config` to `ScheduleCreate`:

```python
class ScheduleCreate(BaseModel):
    task_name: str
    cron_expression: str
    prompt: str
    model: str | None = None
    timeout_seconds: int = 300
    interactive: bool = False
    task_config: str | None = None
    enabled: bool = True
```

Add `task_config` to `ScheduleUpdate`:

```python
class ScheduleUpdate(BaseModel):
    cron_expression: str | None = None
    prompt: str | None = None
    model: str | None = None
    timeout_seconds: int | None = None
    interactive: bool | None = None
    task_config: str | None = None
    enabled: bool | None = None
```

Update `create_schedule` INSERT:

```python
@router.post("/schedules", status_code=201)
def create_schedule(body: ScheduleCreate, conn: sqlite3.Connection = Depends(get_db)):
    now = _now()
    cursor = conn.execute(
        """INSERT INTO schedules (task_name, cron_expression, prompt, model, timeout_seconds, interactive, task_config, enabled, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            body.task_name,
            body.cron_expression,
            body.prompt,
            body.model,
            body.timeout_seconds,
            int(body.interactive),
            body.task_config,
            int(body.enabled),
            now,
            now,
        ),
    )
    conn.commit()
    return _get_schedule(conn, cursor.lastrowid)
```

Update all SELECT queries in `list_schedules`, `_get_schedule`, and `update_schedule` to include `task_config`:

```python
"SELECT id, task_name, cron_expression, prompt, model, timeout_seconds, interactive, task_config, enabled, created_at, updated_at FROM schedules ..."
```

Add `task_config` to the update logic in `update_schedule`:

```python
    for field in ("cron_expression", "prompt", "model", "timeout_seconds", "task_config"):
        val = getattr(body, field)
        if val is not None:
            updates[field] = val
```

- [ ] **Step 6: Run all bede-data tests**

Run: `cd /Users/joeradford/dev/bede/bede-data && uv run pytest tests/ -v`
Expected: All pass.

- [ ] **Step 7: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data/src/bede_data/db/schema.py bede-data/src/bede_data/db/connection.py bede-data/src/bede_data/api/config_api.py bede-data/tests/test_api_config.py
git commit -m "feat(bede-data): add task_config column to schedules for multi-step tasks"
```

---

### Task 7: Multi-Step Task Execution

**Files:**
- Modify: `bede-core/src/bede_core/scheduler.py`
- Modify: `bede-core/tests/test_scheduler.py`

When a task has `task_config` with `steps`, TaskRunner runs each step as a separate Claude invocation. Steps can run sequentially (default) or in parallel (`parallel: true`). Silent steps execute but don't send output to Telegram. The main `prompt` field serves as preamble context for all steps.

- [ ] **Step 1: Write multi-step tests**

Add to `bede-core/tests/test_scheduler.py`:

```python
import json


class TestMultiStepTasks:
    def _make_task(self, steps, parallel=False, preamble="Context for all steps"):
        config = {"steps": steps}
        if parallel:
            config["parallel"] = True
        return {
            "task_name": "Multi Step",
            "cron_expression": "0 14 * * 0",
            "prompt": preamble,
            "model": "claude-sonnet-4-5-20250514",
            "timeout_seconds": 600,
            "interactive": False,
            "task_config": json.dumps(config),
        }

    async def test_sequential_steps(self, data_client, session_manager, send_fn):
        runner = TaskRunner(
            data_client=data_client,
            session_manager=session_manager,
            send_fn=send_fn,
            timezone="Australia/Sydney",
            quiet_hours_start=0,
            quiet_hours_end=0,
        )
        session_manager.send_task.side_effect = [
            ClaudeResult(text="Step 1 result", session_id="s1"),
            ClaudeResult(text="Step 2 result", session_id="s2"),
        ]
        data_client.post.return_value = {"id": 1, "status": "running"}
        data_client.put.return_value = {"id": 1, "status": "success"}

        task = self._make_task([
            {"name": "Step 1", "prompt": "Do step 1"},
            {"name": "Step 2", "prompt": "Do step 2"},
        ])

        await runner.run_task(task)

        assert session_manager.send_task.call_count == 2
        calls = [c.kwargs.get("prompt", c.args[0] if c.args else "")
                 for c in session_manager.send_task.call_args_list]
        assert any("step 1" in c.lower() for c in calls)
        assert any("step 2" in c.lower() for c in calls)

    async def test_parallel_steps(self, data_client, session_manager, send_fn):
        runner = TaskRunner(
            data_client=data_client,
            session_manager=session_manager,
            send_fn=send_fn,
            timezone="Australia/Sydney",
            quiet_hours_start=0,
            quiet_hours_end=0,
        )
        session_manager.send_task.return_value = ClaudeResult(
            text="Result", session_id="s1"
        )
        data_client.post.return_value = {"id": 1, "status": "running"}
        data_client.put.return_value = {"id": 1, "status": "success"}

        task = self._make_task(
            [
                {"name": "Cat 1", "prompt": "Check cat 1"},
                {"name": "Cat 2", "prompt": "Check cat 2"},
            ],
            parallel=True,
        )

        await runner.run_task(task)

        assert session_manager.send_task.call_count == 2

    async def test_silent_step_not_sent_to_telegram(
        self, data_client, session_manager, send_fn
    ):
        runner = TaskRunner(
            data_client=data_client,
            session_manager=session_manager,
            send_fn=send_fn,
            timezone="Australia/Sydney",
            quiet_hours_start=0,
            quiet_hours_end=0,
        )
        session_manager.send_task.side_effect = [
            ClaudeResult(text="Visible result", session_id="s1"),
            ClaudeResult(text="Silent result", session_id="s2"),
        ]
        data_client.post.return_value = {"id": 1, "status": "running"}
        data_client.put.return_value = {"id": 1, "status": "success"}

        task = self._make_task([
            {"name": "Visible", "prompt": "Show this"},
            {"name": "Silent", "prompt": "Hide this", "silent": True},
        ])

        await runner.run_task(task)

        sent_texts = " ".join(str(c) for c in send_fn.call_args_list)
        assert "Visible result" in sent_texts
        assert "Silent result" not in sent_texts

    async def test_preamble_injected_into_steps(
        self, data_client, session_manager, send_fn
    ):
        runner = TaskRunner(
            data_client=data_client,
            session_manager=session_manager,
            send_fn=send_fn,
            timezone="Australia/Sydney",
            quiet_hours_start=0,
            quiet_hours_end=0,
        )
        session_manager.send_task.return_value = ClaudeResult(
            text="Done", session_id="s1"
        )
        data_client.post.return_value = {"id": 1, "status": "running"}
        data_client.put.return_value = {"id": 1, "status": "success"}

        task = self._make_task(
            [{"name": "S1", "prompt": "Do the thing"}],
            preamble="You are a deal scout",
        )

        await runner.run_task(task)

        prompt = session_manager.send_task.call_args.kwargs.get(
            "prompt", session_manager.send_task.call_args.args[0]
        )
        assert "deal scout" in prompt.lower()

    async def test_no_task_config_runs_single_step(
        self, runner, data_client, session_manager, send_fn
    ):
        """Tasks without task_config still work as single-step (backward compat)."""
        task = {
            "task_name": "Simple Task",
            "cron_expression": "0 8 * * *",
            "prompt": "Do something",
            "model": None,
            "timeout_seconds": 300,
            "interactive": False,
        }
        data_client.post.return_value = {"id": 1, "status": "running"}
        data_client.put.return_value = {"id": 1, "status": "success"}

        await runner.run_task(task)

        session_manager.send_task.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/joeradford/dev/bede/bede-core && uv run pytest tests/test_scheduler.py::TestMultiStepTasks -v`
Expected: FAIL — multi-step logic not implemented.

- [ ] **Step 3: Implement multi-step execution**

Modify `bede-core/src/bede_core/scheduler.py`. Add a `json` import. Modify `_run_task_inner` to check for `task_config`:

```python
import json

# ... existing imports ...

    async def _run_task_inner(self, task: dict):
        name = task["task_name"]
        task_config_raw = task.get("task_config")

        if task_config_raw:
            try:
                config = json.loads(task_config_raw) if isinstance(task_config_raw, str) else task_config_raw
            except (json.JSONDecodeError, TypeError):
                config = {}
            steps = config.get("steps")
            if steps:
                await self._run_multistep(task, config)
                return

        await self._run_single_step(task)

    async def _run_single_step(self, task: dict):
        name = task["task_name"]
        prompt = task["prompt"]
        model = task.get("model")
        timeout = task.get("timeout_seconds", 300)
        interactive = task.get("interactive", False)

        now = datetime.now(self._tz)
        now_str = now.strftime("%H:%M")
        now_date_str = now.strftime("%A, %d %B %Y")
        prompt = f"Today is {now_date_str}.\n\n{prompt}"

        cron = task.get("cron_expression", "")
        next_str = _next_run_str(cron, self._tz, now)

        log.info("Running task: %s (timeout: %ds)", name, timeout)

        result = await self._session.send_task(prompt, model=model, timeout=timeout)

        if result.timed_out:
            mins = timeout // 60
            await self._send(f"📅 *{name}*\n⚠️ Timed out after {mins} minutes.")
            return

        text = result.text or "No response."

        if result.stop_reason == "max_tokens":
            text += "\n\n⚠️ _Response was truncated (output token limit reached)._"

        header = f"📅 *{name}* ({now_str})"
        if next_str:
            header += f"\n↻ Next: {next_str}"
        header += "\n---\n"

        output = header + text
        now_check = datetime.now(self._tz)
        if is_quiet_hours(now_check, self._quiet_start, self._quiet_end):
            await self._data.post(
                "/api/message-queue",
                body={"message": output, "source": f"scheduler:{name}"},
            )
            log.info("Task '%s' output queued (quiet hours).", name)
        else:
            await self._send(output)

        if interactive and model and not result.timed_out:
            self._session.register_interactive(model)

    async def _run_multistep(self, task: dict, config: dict):
        name = task["task_name"]
        preamble = task.get("prompt", "")
        model = task.get("model")
        timeout = task.get("timeout_seconds", 300)
        steps = config["steps"]
        parallel = config.get("parallel", False)

        now = datetime.now(self._tz)
        now_str = now.strftime("%H:%M")
        now_date_str = now.strftime("%A, %d %B %Y")
        cron = task.get("cron_expression", "")
        next_str = _next_run_str(cron, self._tz, now)

        step_names = [s["name"] for s in steps if not s.get("silent")]
        header = f"📅 *{name}* ({now_str})"
        if next_str:
            header += f"\n↻ Next: {next_str}"
        header += f"\n{len(step_names)} sections: {', '.join(step_names)}"
        if parallel:
            header += " ⚡"
        await self._send(header)

        date_prefix = f"Today is {now_date_str}.\n\n"

        async def run_one_step(step: dict) -> tuple[str, str, bool]:
            step_name = step.get("name", "Step")
            step_prompt = step.get("prompt", "")
            silent = step.get("silent", False)
            step_model = step.get("model") or model

            full_prompt = date_prefix
            if preamble:
                full_prompt += preamble + "\n\n"
            full_prompt += step_prompt

            step_timeout = step.get("timeout_seconds", timeout)

            log.info("Running step '%s' for task '%s'", step_name, name)
            result = await self._session.send_task(
                full_prompt, model=step_model, timeout=step_timeout
            )

            if result.timed_out:
                return step_name, f"⚠️ *{step_name}* — timed out", silent
            text = result.text or "No output."
            if result.stop_reason == "max_tokens":
                text += "\n\n⚠️ _Response was truncated._"
            return step_name, text, silent

        if parallel:
            non_silent = [s for s in steps if not s.get("silent")]
            silent_steps = [s for s in steps if s.get("silent")]

            results = await asyncio.gather(
                *(run_one_step(s) for s in non_silent),
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, Exception):
                    log.error("Parallel step failed: %s", r)
                else:
                    step_name, text, _ = r
                    await self._send(text)

            for s in silent_steps:
                step_name, text, _ = await run_one_step(s)
                log.info("Silent step '%s' completed.", step_name)
        else:
            for step in steps:
                step_name, text, silent = await run_one_step(step)
                if not silent and text:
                    await self._send(text)
                elif silent:
                    log.info("Silent step '%s' completed.", step_name)

        await self._send(f"✅ *{name}* complete.")
```

- [ ] **Step 4: Run all tests**

Run: `cd /Users/joeradford/dev/bede/bede-core && uv run pytest tests/ -v`
Expected: All pass.

- [ ] **Step 5: Lint and format**

Run: `cd /Users/joeradford/dev/bede/bede-core && uv run ruff check src/ tests/ --fix && uv run ruff format src/ tests/`
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-core/src/bede_core/scheduler.py bede-core/tests/test_scheduler.py
git commit -m "feat(bede-core): multi-step task execution with parallel and silent support"
```
