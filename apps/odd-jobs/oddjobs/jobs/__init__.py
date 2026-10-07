"""Job interface. A job is a module-level object with a name, a daily run time, and run()."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Protocol

import httpx


@dataclass(frozen=True)
class JobContext:
    config_path: Path
    out_dir: Path
    uid_domain: str
    client: httpx.Client


@dataclass(frozen=True)
class JobResult:
    detail: str


class Job(Protocol):
    name: str
    run_at: time

    def run(self, ctx: JobContext) -> JobResult: ...
