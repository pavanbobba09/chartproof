"""Eval metrics against answer keys (PROJECT.md / DATA_SPEC)."""

from __future__ import annotations

from dataclasses import dataclass

from backend.schemas import AnswerKey, AuditResult, PlantedEvidence


@dataclass
class CaseMetrics:
    case_id: str
    determination_correct: bool
    deferred: bool
    evidence_recall: float
    citation_faithfulness: float
    predicted_verdict: str | None
    key_verdict: str
    status: str


def determination_correct(result: AuditResult, key: AnswerKey) -> bool:
    """needs_review counts as wrong for accuracy (tracked separately as deferral)."""
    if result.status == "needs_review":
        return False
    return result.verdict == key.verdict


def planted_for_side(key: AnswerKey) -> list[PlantedEvidence]:
    """Planted spans on the correct side of the key verdict.

    supported → side for; not_supported → side against (for recall of justifying evidence).
    """
    if key.verdict == "supported":
        side = "for"
    else:
        side = "against"
    planted = [p for p in key.planted_evidence if p.side == side]
    # Fallback: any planted if none on preferred side
    return planted or list(key.planted_evidence)


def evidence_recall(result: AuditResult, key: AnswerKey) -> float:
    """Fraction of planted spans (correct side) intersecting at least one cited span."""
    targets = planted_for_side(key)
    if not targets:
        return 1.0
    cited = [e.span for e in result.evidence]
    if not cited:
        return 0.0
    hits = 0
    for plant in targets:
        pspan = plant.as_span()
        if any(pspan.intersects(c) for c in cited):
            hits += 1
    return hits / len(targets)


def citation_faithfulness_deterministic(result: AuditResult) -> float:
    """Pre-check: each evidence item has valid id, non-empty text, valid span.

    Optional LLM judge can refine later; CI uses this deterministic check.
    """
    if not result.evidence:
        # No citations: vacuously faithful but poor recall; score 1.0 on empty set
        # of claims. PROJECT says "for each output claim" — zero claims → 1.0.
        return 1.0
    ok = 0
    for item in result.evidence:
        if not item.evidence_id or not item.evidence_id.startswith("E"):
            continue
        if not (item.text and item.text.strip()):
            continue
        span = item.span
        if span.line_start < 1 or span.line_end < span.line_start:
            continue
        if not span.doc_id:
            continue
        ok += 1
    return ok / len(result.evidence)


def score_case(result: AuditResult, key: AnswerKey) -> CaseMetrics:
    deferred = result.status == "needs_review"
    return CaseMetrics(
        case_id=result.case_id,
        determination_correct=determination_correct(result, key),
        deferred=deferred,
        evidence_recall=evidence_recall(result, key),
        citation_faithfulness=citation_faithfulness_deterministic(result),
        predicted_verdict=result.verdict,
        key_verdict=key.verdict,
        status=result.status,
    )


def aggregate(rows: list[CaseMetrics]) -> dict[str, float]:
    n = len(rows) or 1
    return {
        "determination_accuracy": sum(1 for r in rows if r.determination_correct) / n,
        "evidence_recall": sum(r.evidence_recall for r in rows) / n,
        "citation_faithfulness": sum(r.citation_faithfulness for r in rows) / n,
        "deferral_rate": sum(1 for r in rows if r.deferred) / n,
    }
