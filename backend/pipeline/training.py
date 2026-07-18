"""Training-mode grading against server-side answer keys."""

from __future__ import annotations

from backend.config import CASES_DIR, KEYS_DIR
from backend.schemas import (
    AnswerKey,
    EvidenceSpan,
    MissedSpan,
    TrainingGradeRequest,
    TrainingGradeResponse,
)
from evals.metrics import planted_for_side


def load_key(case_id: str) -> AnswerKey:
    path = KEYS_DIR / f"{case_id}.key.json"
    if not path.is_file():
        raise FileNotFoundError(f"answer key not found for {case_id}")
    return AnswerKey.model_validate_json(path.read_text(encoding="utf-8"))


def case_exists(case_id: str) -> bool:
    return (CASES_DIR / f"{case_id}.json").is_file()


def grade_submission(case_id: str, req: TrainingGradeRequest) -> TrainingGradeResponse:
    key = load_key(case_id)
    verdict_correct = req.verdict == key.verdict

    targets = planted_for_side(key)
    selected = list(req.selected_spans)

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
