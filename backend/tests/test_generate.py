"""Unit tests for generator planning and JSON parsing (no live Groq calls)."""

from __future__ import annotations

import json

from backend.schemas import AnswerKey, Case
from data.consistency import assert_consistent
from data.generate import (
    CaseSpec,
    extract_json_object,
    parse_case_and_key,
    plan_specs,
)


def test_plan_specs_balance() -> None:
    specs = plan_specs("sepsis", 6)
    assert len(specs) == 6
    assert specs[0].case_id == "sepsis_001"
    assert specs[0].verdict == "supported"
    assert specs[1].verdict == "not_supported"
    assert specs[4].difficulty == "borderline"
    assert specs[5].difficulty == "borderline"


def test_extract_json_object_plain() -> None:
    data = extract_json_object('{"a": 1, "b": {"c": 2}}')
    assert data["a"] == 1
    assert data["b"]["c"] == 2


def test_extract_json_object_fenced() -> None:
    text = """Here is the case:
```json
{"case": {"case_id": "x"}, "key": {"case_id": "x"}}
```
"""
    data = extract_json_object(text)
    assert data["case"]["case_id"] == "x"


def test_parse_and_consistency_fixture() -> None:
    payload = {
        "case": {
            "case_id": "wrong_id",
            "target_dx": "sepsis",
            "billed": {"icd10": ["A41.9"], "drg": "871"},
            "patient": {"age": 70, "sex": "M"},
            "documents": [
                {
                    "doc_id": "hp",
                    "doc_type": "history_and_physical",
                    "date": "2026-01-03",
                    "lines": [
                        "CC: fever and dysuria.",
                        "Lactate 1.3 mmol/L, MAP 76 mmHg, afebrile after fluids.",
                        "UTI suspected; ceftriaxone started.",
                        "No vasopressors. Mental status clear.",
                        "Assessment: sepsis ruled out clinically; simple UTI.",
                    ],
                },
                {
                    "doc_id": "pn_01",
                    "doc_type": "progress_note",
                    "date": "2026-01-04",
                    "lines": [
                        "HD2: afebrile, MAP stable 70s.",
                        "Creatinine 0.9 then 1.0, no significant rise.",
                        "Platelets 210. Continues antibiotics.",
                    ],
                },
                {
                    "doc_id": "ds",
                    "doc_type": "discharge_summary",
                    "date": "2026-01-06",
                    "lines": [
                        "Discharge diagnosis listed sepsis by coding query.",
                        "Clinical course consistent with UTI without organ dysfunction.",
                    ],
                },
            ],
            "labs": [
                {
                    "name": "lactate",
                    "value": 1.3,
                    "unit": "mmol/L",
                    "datetime": "2026-01-03T09:00",
                },
                {
                    "name": "creatinine",
                    "value": 0.9,
                    "unit": "mg/dL",
                    "datetime": "2026-01-03T09:00",
                },
                {
                    "name": "creatinine",
                    "value": 1.0,
                    "unit": "mg/dL",
                    "datetime": "2026-01-04T09:00",
                },
                {
                    "name": "platelets",
                    "value": 210,
                    "unit": "10^9/L",
                    "datetime": "2026-01-03T09:00",
                },
            ],
            "vitals": [
                {
                    "name": "map",
                    "value": 76,
                    "unit": "mmHg",
                    "datetime": "2026-01-03T08:00",
                },
                {
                    "name": "temp",
                    "value": 38.2,
                    "unit": "C",
                    "datetime": "2026-01-03T08:00",
                },
            ],
        },
        "key": {
            "case_id": "wrong_id",
            "verdict": "supported",
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
            "key_rationale": "Infection treated; no organ dysfunction on objective data.",
        },
    }
    spec = CaseSpec(
        case_id="sepsis_099",
        dx="sepsis",
        verdict="not_supported",
        difficulty="clear",
        seed=1,
    )
    case, key = parse_case_and_key(payload, spec)
    assert case.case_id == "sepsis_099"
    assert key.verdict == "not_supported"
    assert_consistent(case, key)
    # Round-trip JSON dump
    Case.model_validate(json.loads(case.model_dump_json()))
    AnswerKey.model_validate(json.loads(key.model_dump_json()))
