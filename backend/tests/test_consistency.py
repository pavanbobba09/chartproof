"""Tests for case/key consistency checker."""

from __future__ import annotations

import pytest

from backend.schemas import AnswerKey, Case
from data.consistency import ConsistencyError, assert_consistent, check_case_key_consistency


def _pad_lines(lines: list[str], n: int = 15) -> list[str]:
    out = list(lines)
    i = 0
    while len(out) < n:
        out.append(f"Additional synthetic note line {i + 1} for length compliance.")
        i += 1
    return out


def _valid_pair() -> tuple[Case, AnswerKey]:
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
                    "lines": _pad_lines(
                        [
                            "Chief complaint: fever.",
                            "Lactate 1.4 mmol/L, MAP 78.",
                            "Infection: UTI suspected, antibiotics started.",
                            "No organ dysfunction noted.",
                        ]
                    ),
                },
                {
                    "doc_id": "pn_01",
                    "doc_type": "progress_note",
                    "date": "2026-01-04",
                    "lines": _pad_lines(
                        [
                            "HD2: afebrile, MAP stable.",
                            "Continues antibiotics for UTI.",
                            "No vasopressors.",
                        ]
                    ),
                },
                {
                    "doc_id": "ds",
                    "doc_type": "discharge_summary",
                    "date": "2026-01-06",
                    "lines": _pad_lines(
                        [
                            "Discharge: UTI without organ dysfunction.",
                            "Coding listed sepsis for review.",
                        ]
                    ),
                },
            ],
            "labs": [
                {
                    "name": "lactate",
                    "value": 1.4,
                    "unit": "mmol/L",
                    "datetime": "2026-01-03T09:00",
                }
            ],
            "vitals": [
                {"name": "map", "value": 78, "unit": "mmHg", "datetime": "2026-01-03T08:00"}
            ],
        }
    )
    key = AnswerKey.model_validate(
        {
            "case_id": "sepsis_001",
            "verdict": "not_supported",
            "difficulty": "clear",
            "planted_evidence": [
                {
                    "doc_id": "hp",
                    "line_start": 2,
                    "line_end": 2,
                    "side": "against",
                    "criterion_id": "organ_dysfunction",
                },
                {
                    "doc_id": "hp",
                    "line_start": 3,
                    "line_end": 3,
                    "side": "for",
                    "criterion_id": "infection",
                },
            ],
            "key_rationale": "Infection treated but no organ dysfunction.",
        }
    )
    return case, key


def test_consistent_pair_ok() -> None:
    case, key = _valid_pair()
    assert check_case_key_consistency(case, key) == []
    assert_consistent(case, key)


def test_out_of_range_span() -> None:
    case, key = _valid_pair()
    key.planted_evidence[0].line_end = 99
    issues = check_case_key_consistency(case, key)
    assert any("out of range" in i for i in issues)
    with pytest.raises(ConsistencyError):
        assert_consistent(case, key)


def test_missing_against_for_not_supported() -> None:
    case, key = _valid_pair()
    key.planted_evidence = [
        p for p in key.planted_evidence if p.side == "for"
    ] * 2  # two for, zero against
    issues = check_case_key_consistency(case, key)
    assert any("against" in i for i in issues)


def test_short_document_flagged() -> None:
    case, key = _valid_pair()
    # Shrink first document below DATA_SPEC minimum
    short = case.documents[0].model_copy(update={"lines": ["too short"]})
    case = case.model_copy(update={"documents": [short, *case.documents[1:]]})
    issues = check_case_key_consistency(case, key)
    assert any("15 to 60 lines" in i for i in issues)
