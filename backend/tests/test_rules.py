"""Unit tests for criteria loader and deterministic rules engine."""

from __future__ import annotations

from backend.rules.engine import (
    evaluate_case,
    evaluate_structured,
    evaluate_verdict_rule,
)
from backend.rules.loader import load_criteria
from backend.schemas import Case, CriteriaKind, CriteriaNode


def _case(**kwargs) -> Case:
    base = {
        "case_id": "fixture_001",
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
        "labs": [],
        "vitals": [],
    }
    base.update(kwargs)
    return Case.model_validate(base)


def test_load_sepsis_criteria() -> None:
    crit = load_criteria("sepsis")
    assert crit.dx == "sepsis"
    assert crit.verdict_rule == "infection AND organ_dysfunction"
    ids = {c.id for c in crit.criteria}
    assert "infection" in ids
    assert "organ_dysfunction" in ids


def test_structured_gt_lactate() -> None:
    node = CriteriaNode(
        id="lactate_elevated",
        kind=CriteriaKind.STRUCTURED,
        metric="lab.lactate",
        op="gt",
        threshold=2.0,
    )
    high = _case(
        labs=[
            {
                "name": "lactate",
                "value": 3.1,
                "unit": "mmol/L",
                "datetime": "2026-01-03T09:00",
            }
        ]
    )
    low = _case(
        labs=[
            {
                "name": "lactate",
                "value": 1.4,
                "unit": "mmol/L",
                "datetime": "2026-01-03T09:00",
            }
        ]
    )
    assert evaluate_structured(node, high) == "met"
    assert evaluate_structured(node, low) == "not_met"


def test_structured_lt_map() -> None:
    node = CriteriaNode(
        id="hypotension",
        kind=CriteriaKind.STRUCTURED,
        metric="vital.map",
        op="lt",
        threshold=65,
    )
    low = _case(
        vitals=[
            {"name": "map", "value": 58, "unit": "mmHg", "datetime": "2026-01-03T08:00"}
        ]
    )
    high = _case(
        vitals=[
            {"name": "map", "value": 78, "unit": "mmHg", "datetime": "2026-01-03T08:00"}
        ]
    )
    assert evaluate_structured(node, low) == "met"
    assert evaluate_structured(node, high) == "not_met"


def test_structured_rise_gte_creatinine() -> None:
    node = CriteriaNode(
        id="creatinine_rise",
        kind=CriteriaKind.STRUCTURED,
        metric="lab.creatinine",
        op="rise_gte",
        threshold=0.3,
        window_hours=48,
    )
    rising = _case(
        labs=[
            {
                "name": "creatinine",
                "value": 0.9,
                "unit": "mg/dL",
                "datetime": "2026-01-03T08:00",
            },
            {
                "name": "creatinine",
                "value": 1.3,
                "unit": "mg/dL",
                "datetime": "2026-01-04T08:00",
            },
        ]
    )
    flat = _case(
        labs=[
            {
                "name": "creatinine",
                "value": 0.9,
                "unit": "mg/dL",
                "datetime": "2026-01-03T08:00",
            },
            {
                "name": "creatinine",
                "value": 1.0,
                "unit": "mg/dL",
                "datetime": "2026-01-04T08:00",
            },
        ]
    )
    falling = _case(
        labs=[
            {
                "name": "creatinine",
                "value": 1.5,
                "unit": "mg/dL",
                "datetime": "2026-01-03T08:00",
            },
            {
                "name": "creatinine",
                "value": 1.0,
                "unit": "mg/dL",
                "datetime": "2026-01-04T08:00",
            },
        ]
    )
    single = _case(
        labs=[
            {
                "name": "creatinine",
                "value": 1.5,
                "unit": "mg/dL",
                "datetime": "2026-01-03T08:00",
            }
        ]
    )
    assert evaluate_structured(node, rising) == "met"
    assert evaluate_structured(node, flat) == "not_met"
    assert evaluate_structured(node, falling) == "not_met"
    assert evaluate_structured(node, single) == "unclear"


def test_structured_point_op_preserves_earlier_abnormal_value() -> None:
    node = CriteriaNode(
        id="lactate_elevated",
        kind=CriteriaKind.STRUCTURED,
        metric="lab.lactate",
        op="gt",
        threshold=2.0,
    )
    case = _case(
        labs=[
            {
                "name": "lactate",
                "value": 3.2,
                "unit": "mmol/L",
                "datetime": "2026-01-03T08:00",
            },
            {
                "name": "lactate",
                "value": 1.4,
                "unit": "mmol/L",
                "datetime": "2026-01-04T08:00",
            },
        ]
    )
    assert evaluate_structured(node, case) == "met"


def test_structured_missing_metric_unclear() -> None:
    node = CriteriaNode(
        id="platelets",
        kind=CriteriaKind.STRUCTURED,
        metric="lab.platelets",
        op="lt",
        threshold=100,
    )
    assert evaluate_structured(node, _case()) == "unclear"


def test_verdict_rule_and_or_not() -> None:
    assert (
        evaluate_verdict_rule(
            "infection AND organ_dysfunction",
            {"infection": "met", "organ_dysfunction": "met"},
        )
        == "supported"
    )
    assert (
        evaluate_verdict_rule(
            "infection AND organ_dysfunction",
            {"infection": "met", "organ_dysfunction": "not_met"},
        )
        == "not_supported"
    )
    assert (
        evaluate_verdict_rule(
            "infection AND organ_dysfunction",
            {"infection": "met", "organ_dysfunction": "unclear"},
        )
        == "unknown"
    )
    assert (
        evaluate_verdict_rule(
            "a OR b",
            {"a": "not_met", "b": "met"},
        )
        == "supported"
    )
    assert (
        evaluate_verdict_rule(
            "NOT a",
            {"a": "met"},
        )
        == "not_supported"
    )


def test_evaluate_case_supported_sepsis() -> None:
    crit = load_criteria("sepsis")
    case = _case(
        labs=[
            {
                "name": "lactate",
                "value": 3.2,
                "unit": "mmol/L",
                "datetime": "2026-01-03T09:00",
            }
        ],
        vitals=[
            {"name": "map", "value": 80, "unit": "mmHg", "datetime": "2026-01-03T08:00"}
        ],
    )
    result = evaluate_case(
        case,
        crit,
        narrative_answers={"infection": "met", "vasopressors": "not_met", "altered_mentation": "not_met"},
    )
    assert result.verdict == "supported"
    assert result.breakdown["infection"] == "met"
    assert result.breakdown["organ_dysfunction"] == "met"
    assert result.breakdown["lactate_elevated"] == "met"


def test_evaluate_case_not_supported() -> None:
    crit = load_criteria("sepsis")
    case = _case(
        labs=[
            {
                "name": "lactate",
                "value": 1.2,
                "unit": "mmol/L",
                "datetime": "2026-01-03T09:00",
            },
            {
                "name": "platelets",
                "value": 220,
                "unit": "10^9/L",
                "datetime": "2026-01-03T09:00",
            },
            # Two creatinine values so rise_gte resolves (not unclear)
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
        ],
        vitals=[
            {"name": "map", "value": 78, "unit": "mmHg", "datetime": "2026-01-03T08:00"}
        ],
    )
    result = evaluate_case(
        case,
        crit,
        narrative_answers={
            "infection": "met",
            "vasopressors": "not_met",
            "altered_mentation": "not_met",
        },
    )
    assert result.verdict == "not_supported"
    assert result.breakdown["organ_dysfunction"] == "not_met"


def test_evaluate_case_unknown_when_narrative_missing() -> None:
    crit = load_criteria("sepsis")
    case = _case(
        labs=[
            {
                "name": "lactate",
                "value": 1.0,
                "unit": "mmol/L",
                "datetime": "2026-01-03T09:00",
            }
        ],
        vitals=[
            {"name": "map", "value": 80, "unit": "mmHg", "datetime": "2026-01-03T08:00"}
        ],
    )
    # infection not answered, organ_dysfunction not met from structured alone
    # without narrative children, any_of may still be not_met if all structured are not_met
    # and narrative children default to unclear -> organ_dysfunction unclear -> overall unknown
    result = evaluate_case(case, crit, narrative_answers={})
    assert result.breakdown["infection"] == "unclear"
    assert result.verdict == "unknown"
