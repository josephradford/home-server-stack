"""HTTP surface: calendars, health, status page, Prometheus metrics, manual run."""
from __future__ import annotations

import asyncio
import html
import re
import time
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from starlette.routing import Route

from oddjobs.core.scheduler import Scheduler
from oddjobs.core.state import State

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def build_routes(scheduler: Scheduler, state: State, out_dir: Path) -> list[Route]:
    async def healthz(_: Request) -> Response:
        return PlainTextResponse("ok")

    async def calendar(request: Request) -> Response:
        name = request.path_params["name"]
        path = out_dir / f"{name}.ics"
        if not _NAME_RE.match(name) or not path.is_file():
            return PlainTextResponse("not found", status_code=404)
        return FileResponse(path, media_type="text/calendar; charset=utf-8")

    async def status(_: Request) -> Response:
        rows = []
        for name in scheduler.jobs:
            rec = state.get(name)
            if rec is None:
                rows.append(f"<tr><td>{html.escape(name)}</td><td colspan=3>not run yet</td></tr>")
                continue
            ran = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(rec.last_run_at))
            rows.append(
                f"<tr><td>{html.escape(name)}</td><td>{'ok' if rec.ok else 'FAILED'}</td>"
                f"<td>{ran}</td><td>{html.escape(rec.detail)}</td></tr>"
            )
        cals = sorted(p.name for p in out_dir.glob("*.ics")) if out_dir.exists() else []
        links = "".join(f'<li><a href="/{html.escape(c)}">{html.escape(c)}</a></li>' for c in cals)
        body = (
            "<!doctype html><title>odd-jobs</title><h1>odd-jobs</h1>"
            "<table border=1 cellpadding=6><tr><th>job</th><th>status</th><th>last run</th><th>detail</th></tr>"
            f"{''.join(rows)}</table><h2>Calendars</h2><ul>{links}</ul>"
        )
        return HTMLResponse(body)

    async def metrics(_: Request) -> Response:
        lines = [
            "# TYPE odd_jobs_last_success_timestamp_seconds gauge",
            "# TYPE odd_jobs_last_run_ok gauge",
        ]
        for name in scheduler.jobs:
            rec = state.get(name)
            success = rec.last_success_at if rec and rec.last_success_at else 0
            ok = 1 if rec and rec.ok else 0
            lines.append(f'odd_jobs_last_success_timestamp_seconds{{job="{name}"}} {success}')
            lines.append(f'odd_jobs_last_run_ok{{job="{name}"}} {ok}')
        return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")

    async def run_now(request: Request) -> Response:
        name = request.path_params["job"]
        if name not in scheduler.jobs:
            return PlainTextResponse("unknown job", status_code=404)
        started = await asyncio.to_thread(scheduler.run_job, name)
        if not started:
            return PlainTextResponse("a job is already running", status_code=409)
        return PlainTextResponse("done", status_code=200)

    return [
        Route("/healthz", healthz),
        Route("/metrics", metrics),
        Route("/run/{job}", run_now, methods=["POST"]),
        Route("/", status),
        Route("/{name}.ics", calendar),
    ]


def build_app(scheduler: Scheduler, state: State, out_dir: Path, lifespan=None) -> Starlette:
    return Starlette(routes=build_routes(scheduler, state, out_dir), lifespan=lifespan)
