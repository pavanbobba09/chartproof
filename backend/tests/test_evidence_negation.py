"""Evidence agent negation handling (vasopressors)."""

from __future__ import annotations

from backend.pipeline.evidence import _score_text, gather_evidence_for_criterion
from backend.schemas import Case, CriteriaKind, CriteriaNode


def test_score_not_requiring_vasopressors_is_against() -> None:
    for_kws = ("vasopressors", "on pressors")
    against_kws = ("not requiring vasopressors",)
    text = "The patient is not requiring vasopressors at this time."
    fs, as_ = _score_text(
        text,
        for_kws,
        against_kws,
        apply_vasopressor_negation=True,
    )
    assert as_ > fs


def test_score_active_vasopressors_is_for() -> None:
    for_kws = (
        "vasopressors are being",
        "norepinephrine",
    )
    against_kws = ("not requiring vasopressors",)
    text = "Vasopressors are being titrated to maintain adequate blood pressure."
    fs, as_ = _score_text(
        text,
        for_kws,
        against_kws,
        apply_vasopressor_negation=True,
    )
    assert fs > as_


def test_vasopressor_negation_does_not_leak_into_infection_scoring() -> None:
    text = "Patient is no longer on vasopressors."
    fs, as_ = _score_text(
        text,
        ("infection", "antibiotics"),
        ("no infection", "infection ruled out"),
        apply_vasopressor_negation=False,
    )
    assert fs == 0
    assert as_ == 0


def test_gather_vasopressors_not_met_on_negation_chart() -> None:
    case = Case.model_validate(
        {
            "case_id": "fixture_vaso",
            "target_dx": "sepsis",
            "billed": {"icd10": ["A41.9"], "drg": "871"},
            "patient": {"age": 60, "sex": "F"},
            "documents": [
                {
                    "doc_id": "hp",
                    "doc_type": "history_and_physical",
                    "date": "2026-01-01",
                    "lines": [
                        "UTI treated with ceftriaxone.",
                        "The patient is not requiring vasopressors at this time.",
                        "MAP stable at 80.",
                    ]
                    + [f"pad {i}" for i in range(12)],
                }
            ],
            "labs": [],
            "vitals": [],
        }
    )
    node = CriteriaNode(
        id="vasopressors",
        kind=CriteriaKind.NARRATIVE,
        question="Were vasopressors administered?",
    )
    # client=None falls back to full-chart scan when collection missing
    finding = gather_evidence_for_criterion(case, node, client=None)
    assert finding.result == "not_met"
