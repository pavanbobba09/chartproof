"""QA gate: rules vs draft comparison, confidence, needs_review forcing.

The draft verdict comes from the composer (deterministic evidence-balance
heuristic by default; optionally an LLM when configured). The QA gate compares
it against the independent rules verdict and forces human review on
disagreement, unknowns, dropped citations, or low confidence.
"""

from __future__ import annotations

from typing import Any, Literal

PipelineStatus = Literal["completed", "needs_review"]
Verdict = Literal["supported", "not_supported"]


def compute_confidence(
    *,
    rules_verdict: str | None,
    draft_verdict: str | None,
    dropped_sentences: int,
    unclear_criteria: int,
    evidence_count: int,
) -> float:
    """Heuristic confidence in [0, 1]."""
    score = 0.85
    if rules_verdict != draft_verdict:
        score -= 0.35
    if rules_verdict == "unknown" or draft_verdict is None:
        score -= 0.25
    if dropped_sentences > 0:
        score -= min(0.3, 0.1 * dropped_sentences)
    if unclear_criteria > 0:
        score -= min(0.2, 0.05 * unclear_criteria)
    if evidence_count == 0:
        score -= 0.3
    elif evidence_count < 2:
        score -= 0.1
    return max(0.0, min(1.0, score))


def qa_gate(
    *,
    rules_verdict: str | None,
    draft_verdict: str | None,
    dropped_sentences: int = 0,
    unclear_criteria: int = 0,
    evidence_count: int = 0,
    confidence_threshold: float = 0.6,
) -> dict[str, Any]:
    """Return status, final verdict, confidence, and force reasons."""
    confidence = compute_confidence(
        rules_verdict=rules_verdict,
        draft_verdict=draft_verdict,
        dropped_sentences=dropped_sentences,
        unclear_criteria=unclear_criteria,
        evidence_count=evidence_count,
    )

    reasons: list[str] = []
    status: PipelineStatus = "completed"

    if rules_verdict != draft_verdict:
        reasons.append("rules_draft_disagreement")
        status = "needs_review"
    if rules_verdict == "unknown" or draft_verdict is None:
        reasons.append("unknown_verdict")
        status = "needs_review"
    if dropped_sentences > 0:
        reasons.append("dropped_uncited_sentences")
        status = "needs_review"
    if confidence < confidence_threshold:
        reasons.append("low_confidence")
        status = "needs_review"

    # Final draft verdict shown to auditor
    if status == "needs_review" and rules_verdict != draft_verdict:
        final: Verdict | None = None
    elif draft_verdict in ("supported", "not_supported"):
        final = draft_verdict  # type: ignore[assignment]
    elif rules_verdict in ("supported", "not_supported"):
        final = rules_verdict  # type: ignore[assignment]
    else:
        final = None
        status = "needs_review"
        if "unknown_verdict" not in reasons:
            reasons.append("unknown_verdict")

    return {
        "status": status,
        "verdict": final,
        "confidence": confidence,
        "force_reasons": reasons,
    }
