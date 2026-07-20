"""Lightweight public API for the free Vercel portfolio deployment.

The full ChartProof pipeline depends on local retrieval/model assets and remains
available through ``backend.app``. This adapter deliberately serves committed,
CI-verified audit drafts and the guarded training workflow so the public demo is
small, deterministic, and honest about its hosting boundary.
"""

from __future__ import annotations

import json
import os
import re

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.config import CASES_DIR, DATA_DIR
from backend.pipeline.training import case_exists, grade_submission
from backend.schemas import (
    AuditResult,
    Case,
    CaseSummary,
    HealthResponse,
    TrainingGradeRequest,
    TrainingGradeResponse,
)

PRECOMPUTED_DIR = DATA_DIR / "precomputed"
_CASE_ID_RE = re.compile(r"^[a-z0-9_-]+$")

app = FastAPI(
    title="ChartProof Portfolio API",
    description=(
        "Read-only public adapter for the synthetic ChartProof portfolio demo. "
        "Audit drafts are precomputed and verified in CI; training submissions "
        "are graded server-side."
    ),
    version="0.1.0",
)

_origins = [
    origin.strip()
    for origin in os.environ.get(
        "ALLOWED_ORIGINS",
        "https://chartproof.vercel.app,http://localhost:3000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _safe_case_id(case_id: str) -> str:
    if not _CASE_ID_RE.fullmatch(case_id):
        raise HTTPException(status_code=404, detail=f"case not found: {case_id}")
    return case_id


def _case_path(case_id: str):
    return CASES_DIR / f"{_safe_case_id(case_id)}.json"


def _precomputed_path(case_id: str):
    return PRECOMPUTED_DIR / f"{_safe_case_id(case_id)}.json"


def _load_precomputed(case_id: str) -> AuditResult:
    path = _precomputed_path(case_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"no audit result for {case_id}")
    result = AuditResult.model_validate_json(path.read_text(encoding="utf-8"))
    return result.model_copy(update={"source": "precomputed"})


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "chartproof",
        "status": "ok",
        "mode": "precomputed-portfolio",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/cases", response_model=list[CaseSummary])
def get_cases() -> list[CaseSummary]:
    summaries: list[CaseSummary] = []
    for path in sorted(CASES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        case_id = str(data["case_id"])
        key_path = DATA_DIR / "keys" / f"{case_id}.key.json"
        difficulty = None
        if key_path.is_file():
            key = json.loads(key_path.read_text(encoding="utf-8"))
            difficulty = key.get("difficulty")
        summaries.append(
            CaseSummary(
                case_id=case_id,
                target_dx=data.get("target_dx", "unknown"),
                dataset_role=data.get("dataset_role", "clinical_scenario"),
                difficulty=difficulty,
                has_precomputed=_precomputed_path(case_id).is_file(),
            )
        )
    return summaries


@app.get("/cases/{case_id}", response_model=Case)
def get_case(case_id: str) -> Case:
    path = _case_path(case_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"case not found: {case_id}")
    return Case.model_validate_json(path.read_text(encoding="utf-8"))


@app.get("/audit/{case_id}", response_model=AuditResult)
def get_audit(case_id: str, response: Response) -> AuditResult:
    response.headers["X-ChartProof-Mode"] = "precomputed-portfolio"
    return _load_precomputed(case_id)


@app.post("/audit/{case_id}", response_model=AuditResult)
def post_audit(
    case_id: str,
    response: Response,
    fresh: bool = Query(False, description="Accepted for UI compatibility"),
) -> AuditResult:
    """Return the immutable CI-verified draft in the public free deployment.

    ``fresh`` is intentionally accepted for compatibility, but this hosting
    profile never claims to run the retrieval/model pipeline.
    """
    del fresh
    if not _case_path(case_id).is_file():
        raise HTTPException(status_code=404, detail=f"case not found: {case_id}")
    response.headers["X-ChartProof-Mode"] = "precomputed-portfolio"
    return _load_precomputed(case_id)


@app.post(
    "/training/{case_id}/grade",
    response_model=TrainingGradeResponse,
)
def post_training_grade(
    case_id: str,
    body: TrainingGradeRequest,
) -> TrainingGradeResponse:
    _safe_case_id(case_id)
    if not case_exists(case_id):
        raise HTTPException(status_code=404, detail=f"case not found: {case_id}")
    try:
        return grade_submission(case_id, body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
