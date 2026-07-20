"""Training-mode grading against server-side answer keys."""

from __future__ import annotations

from backend.config import CASES_DIR, KEYS_DIR
from backend.schemas import (
    AnswerKey,
    Case,
    EvidenceSpan,
    MissedSpan,
    TrainingGradeRequest,
    TrainingGradeResponse,
)
from evals.metrics import planted_for_side

# Guardrails so oversized or fabricated selections cannot buy a free score.
MAX_SELECTED_SPANS = 100
MAX_SPAN_LINES = 10


def load_key(case_id: str) -> AnswerKey:
    path = KEYS_DIR / f"{case_id}.key.json"
    if not path.is_file():
        raise FileNotFoundError(f"answer key not found for {case_id}")
    return AnswerKey.model_validate_json(path.read_text(encoding="utf-8"))


def load_case(case_id: str) -> Case:
    path = CASES_DIR / f"{case_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"case not found: {case_id}")
    return Case.model_validate_json(path.read_text(encoding="utf-8"))


def case_exists(case_id: str) -> bool:
    return (CASES_DIR / f"{case_id}.json").is_file()


def validate_selected_spans(case: Case, spans: list[EvidenceSpan]) -> list[EvidenceSpan]:
    """Reject spans that do not exist in the chart; dedupe exact repeats.

    Raises ValueError with a client-safe message on any invalid span.
    """
    if len(spans) > MAX_SELECTED_SPANS:
        raise ValueError(
            f"too many selected spans ({len(spans)}); maximum is {MAX_SELECTED_SPANS}"
        )
    line_counts = {doc.doc_id: len(doc.lines) for doc in case.documents}
    deduped: list[EvidenceSpan] = []
    seen: set[tuple[str, int, int]] = set()
    for span in spans:
        limit = line_counts.get(span.doc_id)
        if limit is None:
            raise ValueError(f"unknown document in selection: {span.doc_id}")
        if span.line_end > limit:
            raise ValueError(
                f"selection {span.doc_id}:{span.line_start}-{span.line_end} "
                f"is outside the document ({limit} lines)"
            )
        if span.line_end - span.line_start + 1 > MAX_SPAN_LINES:
            raise ValueError(
                f"selection {span.doc_id}:{span.line_start}-{span.line_end} "
                f"is too long; maximum span is {MAX_SPAN_LINES} lines"
            )
        key = (span.doc_id, span.line_start, span.line_end)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(span)
    return deduped


def grade_submission(case_id: str, req: TrainingGradeRequest) -> TrainingGradeResponse:
    key = load_key(case_id)
    case = load_case(case_id)
    verdict_correct = req.verdict == key.verdict

    targets = planted_for_side(key)
    selected = validate_selected_spans(case, list(req.selected_spans))

    hit_plants: list[bool] = []
    for plant in targets:
        pspan = plant.as_span()
        hit_plants.append(any(pspan.intersects(s) for s in selected))

    evidence_score = (sum(hit_plants) / len(targets)) if targets else 1.0

    missed: list[MissedSpan] = []
    for plant, hit in zip(targets, hit_plants, strict=True):
        if not hit:
            missed.append(
                MissedSpan(span=plant.as_span(), criterion_id=plant.criterion_id)
            )

    # Extra: selected spans that intersect no planted span of either side
    all_planted_spans = [p.as_span() for p in key.planted_evidence]
    extra: list[EvidenceSpan] = []
    for s in selected:
        if not any(s.intersects(p) for p in all_planted_spans):
            extra.append(s)

    if verdict_correct and evidence_score >= 0.99:
        feedback = (
            f"Correct verdict ({key.verdict}). You captured the key evidence. "
            f"{key.key_rationale}"
        )
    elif verdict_correct:
        feedback = (
            f"Verdict is correct ({key.verdict}), but some key evidence was missed. "
            f"{key.key_rationale}"
        )
    else:
        feedback = (
            f"Verdict should be {key.verdict}, not {req.verdict}. "
            f"{key.key_rationale}"
        )

    return TrainingGradeResponse(
        verdict_correct=verdict_correct,
        key_verdict=key.verdict,
        evidence_score=evidence_score,
        missed_spans=missed,
        extra_spans=extra,
        feedback=feedback,
    )
