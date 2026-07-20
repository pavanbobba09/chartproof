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


def test_grade_rejects_oversized_span() -> None:
    """Selecting lines 1-1000000 must be rejected, not scored 1.0."""
    key = AnswerKey.model_validate_json(
        (REPO / "data/keys/sepsis_001.key.json").read_text()
    )
    res = client.post(
        "/training/sepsis_001/grade",
        json={
            "verdict": key.verdict,
            "selected_spans": [
                {"doc_id": "hp", "line_start": 1, "line_end": 1000000}
            ],
        },
    )
    assert res.status_code == 422
    assert "outside the document" in res.json()["detail"]


def test_grade_rejects_unknown_document() -> None:
    res = client.post(
        "/training/sepsis_001/grade",
        json={
            "verdict": "supported",
            "selected_spans": [
                {"doc_id": "made_up_doc", "line_start": 1, "line_end": 1}
            ],
        },
    )
    assert res.status_code == 422
    assert "unknown document" in res.json()["detail"]


def test_grade_rejects_span_longer_than_cap() -> None:
    res = client.post(
        "/training/sepsis_001/grade",
        json={
            "verdict": "supported",
            "selected_spans": [
                {"doc_id": "hp", "line_start": 1, "line_end": 15}
            ],
        },
    )
    assert res.status_code == 422
    assert "too long" in res.json()["detail"]


def test_grade_rejects_excessive_span_count() -> None:
    spans = [
        {"doc_id": "hp", "line_start": 1, "line_end": 1}
        for _ in range(101)
    ]
    res = client.post(
        "/training/sepsis_001/grade",
        json={"verdict": "supported", "selected_spans": spans},
    )
    assert res.status_code == 422
    assert "too many" in res.json()["detail"]


def test_grade_dedupes_duplicate_spans() -> None:
    """Duplicate selections must not inflate or break the score."""
    key = AnswerKey.model_validate_json(
        (REPO / "data/keys/sepsis_001.key.json").read_text()
    )
    plant = key.planted_evidence[0]
    span = {
        "doc_id": plant.doc_id,
        "line_start": plant.line_start,
        "line_end": plant.line_end,
    }
    res = client.post(
        "/training/sepsis_001/grade",
        json={"verdict": key.verdict, "selected_spans": [span, span, span]},
    )
    assert res.status_code == 200
    body = res.json()
    assert 0.0 <= body["evidence_score"] <= 1.0


def test_get_case_no_key_fields() -> None:
    res = client.get("/cases/sepsis_001")
    assert res.status_code == 200
    body = res.json()
    assert body["case_id"] == "sepsis_001"
    assert "documents" in body
    assert "key_rationale" not in body
    assert "planted_evidence" not in body
