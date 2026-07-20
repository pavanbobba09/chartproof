"""Unit tests for DATA_SPEC schemas and span intersection."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.schemas import (
    AnswerKey,
    Case,
    EvidenceSpan,
    HealthResponse,
    spans_intersect,
)


def test_span_intersects_same_doc_overlap() -> None:
    a = EvidenceSpan(doc_id="pn_01", line_start=8, line_end=10)
    b = EvidenceSpan(doc_id="pn_01", line_start=10, line_end=12)
    assert a.intersects(b)
    assert b.intersects(a)


def test_span_no_intersect_same_doc_adjacent() -> None:
    a = EvidenceSpan(doc_id="pn_01", line_start=1, line_end=3)
    b = EvidenceSpan(doc_id="pn_01", line_start=4, line_end=6)
    assert not a.intersects(b)


def test_span_no_intersect_different_doc() -> None:
    a = EvidenceSpan(doc_id="hp", line_start=1, line_end=10)
    b = EvidenceSpan(doc_id="pn_01", line_start=1, line_end=10)
    assert not a.intersects(b)


def test_span_full_containment() -> None:
    outer = EvidenceSpan(doc_id="hp", line_start=1, line_end=20)
    inner = EvidenceSpan(doc_id="hp", line_start=5, line_end=7)
    assert outer.intersects(inner)
    assert inner.intersects(outer)


def test_span_invalid_line_order() -> None:
    with pytest.raises(ValidationError):
        EvidenceSpan(doc_id="hp", line_start=5, line_end=2)


def test_spans_intersect_helper_accepts_dicts() -> None:
    assert spans_intersect(
        {"doc_id": "hp", "line_start": 2, "line_end": 4},
        {"doc_id": "hp", "line_start": 4, "line_end": 4},
    )


def test_case_minimal_valid() -> None:
    case = Case.model_validate(
        {
            "case_id": "sepsis_001",
            "target_dx": "sepsis",
            "billed": {"icd10": ["A41.9"], "drg": "871"},
            "patient": {"age": 67, "sex": "F"},
            "documents": [
                {
                    "doc_id": "hp",
                    "doc_type": "history_and_physical",
                    "date": "2026-01-03",
                    "lines": ["Chief complaint: fever."],
                }
            ],
            "labs": [
                {
                    "name": "Lactate",
                    "value": 1.4,
                    "unit": "mmol/L",
                    "datetime": "2026-01-03T09:12",
                }
            ],
            "vitals": [],
        }
    )
    assert case.labs[0].name == "lactate"


def test_case_requires_documents() -> None:
    with pytest.raises(ValidationError):
        Case.model_validate(
            {
                "case_id": "x",
                "target_dx": "sepsis",
                "billed": {"icd10": ["A41.9"], "drg": "871"},
                "patient": {"age": 50, "sex": "M"},
                "documents": [],
            }
        )


def test_volume_case_requires_source_case_id() -> None:
    with pytest.raises(ValidationError):
        Case.model_validate(
            {
                "case_id": "sepsis_016",
                "target_dx": "sepsis",
                "dataset_role": "volume_test",
                "billed": {"icd10": ["A41.9"], "drg": "871"},
                "patient": {"age": 50, "sex": "M"},
                "documents": [
                    {
                        "doc_id": "hp",
                        "doc_type": "history_and_physical",
                        "date": "2026-01-03",
                        "lines": ["Synthetic line."],
                    }
                ],
            }
        )


def test_answer_key_verdict_enum() -> None:
    key = AnswerKey.model_validate(
        {
            "case_id": "sepsis_007",
            "verdict": "not_supported",
            "difficulty": "borderline",
            "planted_evidence": [
                {
                    "doc_id": "pn_01",
                    "line_start": 8,
                    "line_end": 9,
                    "side": "against",
                    "criterion_id": "organ_dysfunction",
                }
            ],
            "key_rationale": "No organ dysfunction.",
        }
    )
    assert key.verdict == "not_supported"
    assert key.planted_evidence[0].as_span().line_start == 8


def test_health_response_defaults() -> None:
    h = HealthResponse()
    assert h.status == "ok"
    assert h.service == "chartproof"
