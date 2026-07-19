"""Grounded citation-faithfulness validation."""

from __future__ import annotations

from backend.pipeline.faithfulness import evaluate_citation_faithfulness
from backend.rules.loader import load_criteria
from backend.schemas import AuditResult, Case, EvidenceItem, EvidenceSpan


def _case() -> Case:
    return Case.model_validate(
        {
            "case_id": "faithfulness_001",
            "target_dx": "sepsis",
            "billed": {"icd10": ["A41.9"], "drg": "871"},
            "patient": {"age": 70, "sex": "F"},
            "documents": [
                {
                    "doc_id": "hp",
                    "doc_type": "history_and_physical",
                    "date": "2026-01-01",
                    "lines": [
                        "UTI documented and ceftriaxone started.",
                        "Initial lactate 3.2 mmol/L.",
                    ],
                }
            ],
            "labs": [
                {
                    "name": "lactate",
                    "value": 3.2,
                    "unit": "mmol/L",
                    "datetime": "2026-01-01T08:00",
                }
            ],
            "vitals": [],
        }
    )


def _result() -> AuditResult:
    evidence = [
        EvidenceItem(
            evidence_id="E1",
            side="for",
            criterion_id="infection",
            span=EvidenceSpan(doc_id="hp", line_start=1, line_end=1),
            text="UTI documented and ceftriaxone started.",
        ),
        EvidenceItem(
            evidence_id="E2",
            side="for",
            criterion_id="lactate_elevated",
            span=EvidenceSpan(doc_id="hp", line_start=2, line_end=2),
            text="Initial lactate 3.2 mmol/L.",
        ),
    ]
    letter = """# Clinical validation finding: Sepsis

## Determination
Draft determination is supported based on organ dysfunction documented in E2.

## Evidence
| # | For/Against | Source | Lines | Excerpt |
|---|-------------|--------|-------|---------|
| E1 | for | history_and_physical | 1-1 | UTI documented and ceftriaxone started. |
| E2 | for | history_and_physical | 2-2 | Initial lactate 3.2 mmol/L. |

## Coding rationale
Sepsis requires infection and organ dysfunction (sepsis3_summary, Section: Definition). Clinical validation requires chart support (icd10cm_guidelines_fy2026_summary, Section: Clinical validation context).

## Reviewer note
Draft for auditor review.
"""
    return AuditResult(
        case_id="faithfulness_001",
        status="completed",
        verdict="supported",
        confidence=0.85,
        rules_verdict="supported",
        llm_verdict="supported",
        evidence=evidence,
        letter_markdown=letter,
    )


def _evaluate(result: AuditResult):
    return evaluate_citation_faithfulness(result, _case(), load_criteria("sepsis"))


def test_grounded_citations_pass() -> None:
    report = _evaluate(_result())
    assert report.score == 1.0
    assert report.issues == []


def test_altered_excerpt_fails() -> None:
    result = _result()
    altered = result.evidence[1].model_copy(update={"text": "Lactate was normal."})
    result = result.model_copy(update={"evidence": [result.evidence[0], altered]})
    report = _evaluate(result)
    assert report.score == 0.0
    assert any(issue.code == "text_mismatch" for issue in report.issues)


def test_out_of_bounds_span_fails() -> None:
    result = _result()
    invalid = result.evidence[1].model_copy(
        update={"span": EvidenceSpan(doc_id="hp", line_start=2, line_end=99)}
    )
    result = result.model_copy(update={"evidence": [result.evidence[0], invalid]})
    report = _evaluate(result)
    assert report.score == 0.0
    assert any(issue.code == "span_out_of_bounds" for issue in report.issues)


def test_wrong_evidence_side_fails() -> None:
    result = _result()
    wrong = result.evidence[1].model_copy(update={"side": "against"})
    result = result.model_copy(update={"evidence": [result.evidence[0], wrong]})
    report = _evaluate(result)
    assert report.score == 0.0
    assert any(issue.code == "side_mismatch" for issue in report.issues)


def test_determination_requires_verdict_supporting_citation() -> None:
    result = _result().model_copy(
        update={
            "letter_markdown": _result().letter_markdown.replace(
                "organ dysfunction documented in E2", "infection documented in E1"
            )
        }
    )
    report = _evaluate(result)
    assert report.score == 0.0
    assert any(issue.code == "determination_support" for issue in report.issues)


def test_zero_evidence_is_not_vacuously_faithful() -> None:
    result = _result().model_copy(update={"evidence": []})
    report = _evaluate(result)
    assert report.score == 0.0
    assert any(issue.code == "missing_evidence" for issue in report.issues)


def test_unknown_guideline_section_fails() -> None:
    result = _result().model_copy(
        update={
            "letter_markdown": _result().letter_markdown.replace(
                "Section: Definition", "Section: Invented"
            )
        }
    )
    report = _evaluate(result)
    assert report.score == 0.0
    assert any(issue.code == "invalid_guideline_citation" for issue in report.issues)
