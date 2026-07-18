"""ChartProof FastAPI application."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.config import CASES_DIR
from backend.pipeline.audit_service import list_case_summaries, run_audit
from backend.pipeline.training import case_exists, grade_submission
from backend.schemas import (
    AuditResult,
    Case,
    CaseSummary,
    HealthResponse,
    TrainingGradeRequest,
    TrainingGradeResponse,
)

app = FastAPI(
    title="ChartProof API",
    description=(
        "Auditor-assist clinical chart validation demo. "
        "Synthetic data only. Drafts for human review, never payment decisions."
    ),
    version="0.1.0",
)

_origins = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/cases", response_model=list[CaseSummary])
def get_cases() -> list[CaseSummary]:
    """List cases without answer keys."""
    return list_case_summaries()


@app.get("/cases/{case_id}", response_model=Case)
def get_case(case_id: str) -> Case:
    """Return full synthetic chart (never includes answer key)."""
    path = CASES_DIR / f"{case_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"case not found: {case_id}")
    return Case.model_validate_json(path.read_text(encoding="utf-8"))


@app.get("/audit/{case_id}", response_model=AuditResult)
def get_audit(case_id: str) -> AuditResult:
    """Return cached/precomputed audit if present; 404 if never run."""
    from backend.pipeline.audit_service import load_cached_result

    result = load_cached_result(case_id, fresh=False)
    if result is None:
        raise HTTPException(status_code=404, detail=f"no audit result for {case_id}")
    return result


@app.post("/audit/{case_id}", response_model=AuditResult)
def post_audit(
    case_id: str,
    fresh: bool = Query(False, description="Skip caches and run live pipeline"),
) -> AuditResult:
    """Run audit pipeline (or serve precomputed/cached result)."""
    case_path = Path(__file__).resolve().parents[1] / "data" / "cases" / f"{case_id}.json"
    if not case_path.is_file():
        raise HTTPException(status_code=404, detail=f"case not found: {case_id}")
    try:
        return run_audit(case_id, fresh=fresh)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"audit failed: {e}") from e


@app.post("/training/{case_id}/grade", response_model=TrainingGradeResponse)
def post_training_grade(case_id: str, body: TrainingGradeRequest) -> TrainingGradeResponse:
    """Grade trainee verdict + selected evidence against the hidden answer key.

    This is the only endpoint allowed to reveal answer-key content, after submit.
    """
    if not case_exists(case_id):
        raise HTTPException(status_code=404, detail=f"case not found: {case_id}")
    try:
        return grade_submission(case_id, body)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
