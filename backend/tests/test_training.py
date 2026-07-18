"""Training grade endpoint tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
from backend.schemas import AnswerKey

client = TestClient(app)
REPO = Path(__file__).resolve().parents[2]


def test_grade_correct_verdict_with_planted_span() -> None:
    key = AnswerKey.model_validate_json(
        (REPO / "data/keys/sepsis_001.key.json").read_text()
    )
    plant = key.planted_evidence[0]
    res = client.post(
        "/training/sepsis_001/grade",
        json={
            "verdict": key.verdict,
            "selected_spans": [
                {
                    "doc_id": plant.doc_id,
                    "line_start": plant.line_start,
                    "line_end": plant.line_end,
                }
            ],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["verdict_correct"] is True
    assert body["key_verdict"] == key.verdict
    assert body["evidence_score"] >= 0.0
    assert "feedback" in body


def test_grade_wrong_verdict() -> None:
    key = AnswerKey.model_validate_json(
        (REPO / "data/keys/sepsis_001.key.json").read_text()
    )
    wrong = "not_supported" if key.verdict == "supported" else "supported"
    res = client.post(
        "/training/sepsis_001/grade",
        json={"verdict": wrong, "selected_spans": []},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["verdict_correct"] is False
    assert body["key_verdict"] == key.verdict
    assert body["evidence_score"] == 0.0 or body["missed_spans"]


def test_get_case_no_key_fields() -> None:
    res = client.get("/cases/sepsis_001")
    assert res.status_code == 200
    body = res.json()
    assert body["case_id"] == "sepsis_001"
    assert "documents" in body
    assert "key_rationale" not in body
    assert "planted_evidence" not in body
