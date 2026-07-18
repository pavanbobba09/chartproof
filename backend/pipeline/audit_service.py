"""Run full audit pipeline and map to AuditResult; handle caches."""

from __future__ import annotations

import json
from pathlib import Path

from backend.config import CASES_DIR, CHROMA_DIR, DATA_DIR, REPO_ROOT
from backend.pipeline.graph import run_full_pipeline
from backend.schemas import AuditResult, CaseSummary

PRECOMPUTED_DIR = DATA_DIR / "precomputed"
RUNTIME_CACHE_DIR = REPO_ROOT / "runs" / "cache"


def _precomputed_path(case_id: str) -> Path:
    return PRECOMPUTED_DIR / f"{case_id}.json"


def _runtime_cache_path(case_id: str) -> Path:
    return RUNTIME_CACHE_DIR / f"{case_id}.json"


def load_cached_result(case_id: str, *, fresh: bool = False) -> AuditResult | None:
    if fresh:
        return None
    for path, source in (
        (_precomputed_path(case_id), "precomputed"),
        (_runtime_cache_path(case_id), "cached"),
    ):
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            data["source"] = source
            return AuditResult.model_validate(data)
    return None


def save_runtime_cache(result: AuditResult) -> Path:
    RUNTIME_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _runtime_cache_path(result.case_id)
    payload = result.model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def save_precomputed(result: AuditResult) -> Path:
    PRECOMPUTED_DIR.mkdir(parents=True, exist_ok=True)
    # Store without forcing source; load will set source=precomputed
    payload = result.model_dump(mode="json")
    payload["source"] = "precomputed"
    path = _precomputed_path(result.case_id)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def run_audit(
    case_id: str,
    *,
    fresh: bool = False,
    chroma_dir: str | Path | None = None,
    persist_runtime_cache: bool = True,
) -> AuditResult:
    cached = load_cached_result(case_id, fresh=fresh)
    if cached is not None:
        return cached

    raw = run_full_pipeline(
        case_id,
        persist_trace=True,
        chroma_dir=chroma_dir or CHROMA_DIR,
    )
    result = AuditResult.model_validate(raw["audit_result"])
    result = result.model_copy(update={"source": "live"})
    if persist_runtime_cache:
        save_runtime_cache(result)
    return result


def list_case_summaries() -> list[CaseSummary]:
    out: list[CaseSummary] = []
    for path in sorted(CASES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        case_id = data["case_id"]
        # difficulty lives in key file; do not expose rationale
        difficulty = None
        key_path = DATA_DIR / "keys" / f"{case_id}.key.json"
        if key_path.is_file():
            key = json.loads(key_path.read_text(encoding="utf-8"))
            difficulty = key.get("difficulty")
        out.append(
            CaseSummary(
                case_id=case_id,
                target_dx=data.get("target_dx", "unknown"),
                difficulty=difficulty,
                has_precomputed=_precomputed_path(case_id).is_file(),
            )
        )
    return out


def precompute_all(
    *,
    chroma_dir: str | Path | None = None,
    case_ids: list[str] | None = None,
) -> list[str]:
    ids = case_ids or [p.stem for p in sorted(CASES_DIR.glob("*.json"))]
    saved: list[str] = []
    for case_id in ids:
        result = run_audit(
            case_id,
            fresh=True,
            chroma_dir=chroma_dir,
            persist_runtime_cache=False,
        )
        save_precomputed(result)
        saved.append(case_id)
        print(f"precomputed {case_id}: status={result.status} verdict={result.verdict}")
    return saved
