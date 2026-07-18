"""Persist pipeline traces under runs/ for debuggability."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.config import REPO_ROOT

RUNS_DIR = REPO_ROOT / "runs"


def new_trace_id(case_id: str) -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"run_{case_id}_{ts}"


def save_trace(trace_id: str, payload: dict[str, Any]) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{trace_id}.json"
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return path
