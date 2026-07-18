"""Unit tests for composer citation gate and QA gate (no Chroma)."""

from __future__ import annotations

from backend.pipeline.compose import (
    compose_letter,
    derive_llm_verdict,
    filter_uncited_sentences,
)
from backend.pipeline.qa import qa_gate
from backend.schemas import Case, CriteriaFile, EvidenceItem, EvidenceSpan


def _case() -> Case:
    return Case.model_validate(
        {
            "case_id": "sepsis_001",
            "target_dx": "sepsis",
            "billed": {"icd10": ["A41.9"], "drg": "871"},
            "patient": {"age": 65, "sex": "M"},
            "documents": [
                {
                    "doc_id": "hp",
                    "doc_type": "history_and_physical",
                    "date": "2026-01-01",
                    "lines": [f"line {i}" for i in range(1, 16)],
                }
            ],
        }
    )


def _criteria() -> CriteriaFile:
    return CriteriaFile.model_validate(
        {
            "dx": "sepsis",
            "display_name": "Sepsis",
            "icd10_prefixes": ["A41"],
            "source_note": "demo not for clinical use",
            "verdict_rule": "infection AND organ_dysfunction",
            "criteria": [
                {"id": "infection", "kind": "narrative", "question": "infection?"},
            ],
        }
    )


def test_filter_drops_uncited_claims() -> None:
    text = (
        "## Determination\n"
        "Infection is clearly supported by the chart.\n"
        "Organ dysfunction is present per E1.\n"
        "## Evidence\n"
        "| E1 | for | hp | 1-1 | excerpt |\n"
    )
    filtered, dropped = filter_uncited_sentences(text, {"E1"})
    assert dropped >= 1
    assert "E1" in filtered
    assert "clearly supported by the chart" not in filtered


def test_filter_keeps_cited_claims() -> None:
    text = "Draft determination is supported based on E1 showing infection."
    filtered, dropped = filter_uncited_sentences(text, {"E1"})
    assert dropped == 0
    assert "E1" in filtered


def test_compose_letter_has_required_sections() -> None:
    evidence = [
        EvidenceItem(
            evidence_id="E1",
            side="for",
            criterion_id="infection",
            span=EvidenceSpan(doc_id="hp", line_start=2, line_end=2),
            text="UTI treated with antibiotics.",
        )
    ]
    letter, dropped = compose_letter(
        case=_case(),
        criteria=_criteria(),
        status="completed",
        verdict="supported",
        evidence=evidence,
        rules_verdict="supported",
    )
    assert "# Clinical validation finding: Sepsis" in letter
    assert "## Determination" in letter
    assert "## Evidence" in letter
    assert "## Coding rationale" in letter
    assert "## Reviewer note" in letter
    assert "Machine-drafted aid generated from synthetic data" in letter
    assert "E1" in letter
    assert dropped == 0


def test_qa_disagreement_needs_review() -> None:
    out = qa_gate(
        rules_verdict="supported",
        llm_verdict="not_supported",
        dropped_sentences=0,
        evidence_count=3,
    )
    assert out["status"] == "needs_review"
    assert "rules_llm_disagreement" in out["force_reasons"]


def test_qa_dropped_sentences_needs_review() -> None:
    out = qa_gate(
        rules_verdict="supported",
        llm_verdict="supported",
        dropped_sentences=2,
        evidence_count=3,
    )
    assert out["status"] == "needs_review"
    assert "dropped_uncited_sentences" in out["force_reasons"]


def test_qa_agreement_completed() -> None:
    out = qa_gate(
        rules_verdict="not_supported",
        llm_verdict="not_supported",
        dropped_sentences=0,
        unclear_criteria=0,
        evidence_count=4,
    )
    assert out["status"] == "completed"
    assert out["verdict"] == "not_supported"
    assert out["confidence"] >= 0.6


def test_derive_llm_verdict_follows_rules_when_balanced() -> None:
    evidence = [
        EvidenceItem(
            evidence_id="E1",
            side="for",
            criterion_id="infection",
            span=EvidenceSpan(doc_id="hp", line_start=1, line_end=1),
            text="x",
        ),
        EvidenceItem(
            evidence_id="E2",
            side="against",
            criterion_id="lactate_elevated",
            span=EvidenceSpan(doc_id="hp", line_start=2, line_end=2),
            text="y",
        ),
    ]
    assert derive_llm_verdict("not_supported", evidence) == "not_supported"
