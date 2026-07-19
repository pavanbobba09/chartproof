"""Unit tests for composer citation gate and QA gate (no Chroma)."""

from __future__ import annotations

from backend.pipeline.compose import (
    build_evidence_catalog,
    compose_letter,
    derive_draft_verdict,
    filter_uncited_sentences,
)
from backend.pipeline.graph import node_qa
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
        draft_verdict="not_supported",
        dropped_sentences=0,
        evidence_count=3,
    )
    assert out["status"] == "needs_review"
    assert "rules_draft_disagreement" in out["force_reasons"]


def test_qa_dropped_sentences_needs_review() -> None:
    out = qa_gate(
        rules_verdict="supported",
        draft_verdict="supported",
        dropped_sentences=2,
        evidence_count=3,
    )
    assert out["status"] == "needs_review"
    assert "dropped_uncited_sentences" in out["force_reasons"]


def test_qa_agreement_completed() -> None:
    out = qa_gate(
        rules_verdict="not_supported",
        draft_verdict="not_supported",
        dropped_sentences=0,
        unclear_criteria=0,
        evidence_count=4,
    )
    assert out["status"] == "completed"
    assert out["verdict"] == "not_supported"
    assert out["confidence"] >= 0.6


def test_derive_draft_verdict_follows_rules_when_balanced() -> None:
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
    assert derive_draft_verdict("not_supported", evidence) == "not_supported"


def test_structured_evidence_side_is_based_on_each_observation() -> None:
    payload = _case().model_dump(mode="json")
    payload["documents"] = [
                {
                    "doc_id": "hp",
                    "doc_type": "history_and_physical",
                    "date": "2026-01-01",
                    "lines": [
                        "Initial lactate 3.2 mmol/L.",
                        "Repeat lactate 1.4 mmol/L after fluids.",
                        "Initial MAP 58 mmHg.",
                        "Repeat MAP 78 mmHg after fluids.",
                    ],
                }
            ]
    case = Case.model_validate(payload)
    rules_result = {
        "verdict": "supported",
        "breakdown": {
            "lactate_elevated": "met",
            "hypotension": "met",
        },
        "criteria": [
            {
                "criterion_id": "lactate_elevated",
                "result": "met",
                "method": "structured",
                "metric": "lab.lactate",
                "op": "gt",
                "threshold": 2.0,
            },
            {
                "criterion_id": "hypotension",
                "result": "met",
                "method": "structured",
                "metric": "vital.map",
                "op": "lt",
                "threshold": 65.0,
            },
        ],
    }

    evidence = build_evidence_catalog(case, [], rules_result)
    by_text = {item.text: item.side for item in evidence}

    assert by_text["Initial lactate 3.2 mmol/L."] == "for"
    assert by_text["Repeat lactate 1.4 mmol/L after fluids."] == "against"
    assert by_text["Initial MAP 58 mmHg."] == "for"
    assert by_text["Repeat MAP 78 mmHg after fluids."] == "against"


def test_qa_disagreement_rewrites_letter_as_deferred() -> None:
    evidence = EvidenceItem(
        evidence_id="E1",
        side="for",
        criterion_id="infection",
        span=EvidenceSpan(doc_id="hp", line_start=2, line_end=2),
        text="UTI treated with antibiotics.",
    )
    state = {
        "case_id": "sepsis_001",
        "case": _case().model_dump(mode="json"),
        "criteria": _criteria().model_dump(mode="json"),
        "rules_result": {
            "verdict": "supported",
            "criteria": [
                {
                    "criterion_id": "infection",
                    "result": "met",
                    "method": "narrative",
                }
            ],
        },
        "compose_result": {
            "draft_verdict": "not_supported",
            "evidence": [evidence.model_dump(mode="json")],
            "letter_markdown": (
                "# Clinical validation finding: Sepsis\n"
                "Case sepsis_001 | Status: completed | Draft for auditor review\n\n"
                "## Determination\nDraft determination is not_supported based on E1."
            ),
            "dropped_sentences": 0,
            "guideline_bits": [],
        },
    }

    result = node_qa(state)
    letter = result["audit_result"]["letter_markdown"]

    assert result["audit_result"]["status"] == "needs_review"
    assert result["audit_result"]["verdict"] is None
    assert "deferred pending auditor review" in letter
    assert "Draft determination is not_supported" not in letter


def _findings_for_llm_tests() -> list[dict]:
    return [
        {
            "criterion_id": "infection",
            "result": "met",
            "side_items": [
                {
                    "side": "for",
                    "span": {"doc_id": "hp", "line_start": 2, "line_end": 2},
                    "text": "line 2",
                    "score": 2.0,
                }
            ],
        }
    ]


def test_llm_compose_disabled_by_default(monkeypatch) -> None:
    from backend.pipeline import compose as compose_module

    monkeypatch.delenv("CHARTPROOF_LLM_COMPOSE", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    out = compose_module.compose_from_state(
        _case(),
        _criteria(),
        _findings_for_llm_tests(),
        {"verdict": "supported", "criteria": []},
        use_guidelines=False,
    )
    assert out["composer"] == "deterministic"


def test_llm_compose_uses_llm_verdict_and_prose(monkeypatch) -> None:
    from backend.pipeline import compose as compose_module

    monkeypatch.setenv("CHARTPROOF_LLM_COMPOSE", "1")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(
        compose_module,
        "_llm_compose",
        lambda case, criteria, evidence: (
            "not_supported",
            "Draft determination is not_supported because E1 lacks organ findings.",
        ),
    )
    out = compose_module.compose_from_state(
        _case(),
        _criteria(),
        _findings_for_llm_tests(),
        {"verdict": "supported", "criteria": []},
        use_guidelines=False,
    )
    assert out["composer"] == "llm"
    assert out["draft_verdict"] == "not_supported"
    assert "lacks organ findings" in out["letter_markdown"]


def test_llm_compose_uncited_prose_is_dropped(monkeypatch) -> None:
    """LLM output goes through the same citation gate as everything else."""
    from backend.pipeline import compose as compose_module

    monkeypatch.setenv("CHARTPROOF_LLM_COMPOSE", "1")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(
        compose_module,
        "_llm_compose",
        lambda case, criteria, evidence: (
            "supported",
            "The chart shows overwhelming evidence of sepsis infection.",
        ),
    )
    out = compose_module.compose_from_state(
        _case(),
        _criteria(),
        _findings_for_llm_tests(),
        {"verdict": "supported", "criteria": []},
        use_guidelines=False,
    )
    assert out["composer"] == "llm"
    assert out["dropped_sentences"] >= 1
    assert "overwhelming evidence" not in out["letter_markdown"]


def test_llm_compose_falls_back_on_error(monkeypatch) -> None:
    from backend.pipeline import compose as compose_module

    monkeypatch.setenv("CHARTPROOF_LLM_COMPOSE", "1")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    def _boom(case, criteria, evidence):
        raise RuntimeError("HTTP 429 rate limit")

    monkeypatch.setattr(compose_module, "_llm_compose", _boom)
    out = compose_module.compose_from_state(
        _case(),
        _criteria(),
        _findings_for_llm_tests(),
        {"verdict": "supported", "criteria": []},
        use_guidelines=False,
    )
    assert out["composer"] == "deterministic"
    assert out["letter_markdown"]
