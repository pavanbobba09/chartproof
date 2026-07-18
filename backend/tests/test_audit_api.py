"""API tests for audit endpoints (uses precomputed or live with temp chroma)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.index.build import build_case_collection, build_guidelines_collection, get_client
from backend.pipeline.graph import run_full_pipeline
from backend.schemas import AuditResult, Case

client = TestClient(app)
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def precomputed_sepsis_001(tmp_path_factory: pytest.TempPathFactory):
    """Build tiny index and one precomputed audit result in repo precomputed dir."""
    chroma = tmp_path_factory.mktemp("chroma_api")
    case = Case.model_validate_json((REPO / "data/cases/sepsis_001.json").read_text())
    cli = get_client(chroma)
    build_case_collection(cli, case)
    build_guidelines_collection(cli, REPO / "data/guidelines")
    raw = run_full_pipeline("sepsis_001", persist_trace=False, chroma_dir=chroma)
    result = AuditResult.model_validate(raw["audit_result"])
    # Write to real precomputed path for GET/POST cache tests
    path = REPO / "data" / "precomputed" / "sepsis_001.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = result.model_dump(mode="json")
    payload["source"] = "precomputed"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    yield result
    # keep precomputed for bank (Phase 3 ships these)


def test_list_cases_no_keys() -> None:
    res = client.get("/cases")
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, list)
    assert body
    assert "case_id" in body[0]
    assert "key_rationale" not in body[0]
    assert "planted_evidence" not in body[0]


def test_get_audit_precomputed(precomputed_sepsis_001: AuditResult) -> None:
    res = client.get("/audit/sepsis_001")
    assert res.status_code == 200
    body = res.json()
    assert body["case_id"] == "sepsis_001"
    assert body["source"] == "precomputed"
    assert body["letter_markdown"]
    assert "## Determination" in body["letter_markdown"]
    assert body["dropped_sentences"] == 0
    # no answer key fields
    assert "key_rationale" not in body
    assert "planted_evidence" not in body


def test_post_audit_uses_cache(precomputed_sepsis_001: AuditResult) -> None:
    res = client.post("/audit/sepsis_001")
    assert res.status_code == 200
    assert res.json()["source"] == "precomputed"


def test_post_audit_missing_case() -> None:
    res = client.post("/audit/does_not_exist")
    assert res.status_code == 404


def test_full_pipeline_zero_invalid_citations(precomputed_sepsis_001: AuditResult) -> None:
    assert precomputed_sepsis_001.dropped_sentences == 0
    for e in precomputed_sepsis_001.evidence:
        assert e.evidence_id.startswith("E")
        assert e.span.line_start >= 1
