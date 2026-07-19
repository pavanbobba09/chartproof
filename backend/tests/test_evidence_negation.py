"""Evidence agent negation handling (vasopressors)."""

from __future__ import annotations

from backend.pipeline.evidence import gather_evidence_for_criterion
from backend.pipeline.lexicon import narrative_side, score_text
from backend.schemas import Case, CriteriaKind, CriteriaNode


def test_score_not_requiring_vasopressors_is_against() -> None:
    for_kws = ("vasopressors", "on pressors")
    against_kws = ("not requiring vasopressors",)
    text = "The patient is not requiring vasopressors at this time."
    fs, as_ = score_text(
        text,
        for_kws,
        against_kws,
        apply_vasopressor_rules=True,
    )
    assert as_ > fs


def test_score_active_vasopressors_is_for() -> None:
    for_kws = (
        "vasopressors are being",
        "norepinephrine",
    )
    against_kws = ("not requiring vasopressors",)
    text = "Vasopressors are being titrated to maintain adequate blood pressure."
    fs, as_ = score_text(
        text,
        for_kws,
        against_kws,
        apply_vasopressor_rules=True,
    )
    assert fs > as_


def test_vasopressor_negation_does_not_leak_into_infection_scoring() -> None:
    text = "Patient is no longer on vasopressors."
    fs, as_ = score_text(
        text,
        ("infection", "antibiotics"),
        ("no infection", "infection ruled out"),
        apply_vasopressor_rules=False,
    )
    assert fs == 0
    assert as_ == 0


def test_started_on_vasopressors_is_for() -> None:
    """sepsis_005 regression: affirmative start language must count FOR."""
    assert (
        narrative_side(
            "vasopressors",
            "Patient is being started on vasopressors to support blood pressure.",
        )
        == "for"
    )


def test_vasopressors_have_been_started_is_for() -> None:
    """sepsis_009 regression: reversed word order must also count FOR."""
    assert (
        narrative_side(
            "vasopressors",
            "Vasopressors have been started for persistent hypotension.",
        )
        == "for"
    )


def test_glasgow_coma_scale_is_for_altered_mentation() -> None:
    """sepsis_009 regression: spelled-out GCS must count FOR altered mentation."""
    assert (
        narrative_side(
            "altered_mentation",
            "Patient noted to be lethargic with a Glasgow Coma Scale score of 12.",
        )
        == "for"
    )


def test_normal_glasgow_coma_scale_is_against() -> None:
    assert (
        narrative_side(
            "altered_mentation",
            "Neuro exam normal, Glasgow Coma Scale score of 15.",
        )
        == "against"
    )


def test_sepsis_label_is_not_infection_evidence() -> None:
    """The billed diagnosis label must not count as evidence for itself."""
    assert narrative_side("infection", "Assessment: sepsis.") is None


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
