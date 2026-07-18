"""Eval harness unit tests (precomputed, no live LLM)."""

from __future__ import annotations

from pathlib import Path

from backend.schemas import AnswerKey, AuditResult
from evals.metrics import aggregate, score_case
from evals.run import run_suite

REPO = Path(__file__).resolve().parents[2]


def test_score_precomputed_sepsis_001() -> None:
    result = AuditResult.model_validate_json(
        (REPO / "data/precomputed/sepsis_001.json").read_text()
    )
    key = AnswerKey.model_validate_json(
        (REPO / "data/keys/sepsis_001.key.json").read_text()
    )
    m = score_case(result, key)
    assert m.citation_faithfulness == 1.0
    assert 0.0 <= m.evidence_recall <= 1.0


def test_smoke_suite_enforce() -> None:
    report = run_suite("smoke", live=False, enforce=True)
    assert report["exit_code"] == 0
    assert report["metrics"]["citation_faithfulness"] >= 0.95
    assert len(report["cases"]) == 5


def test_full_suite_writes_report() -> None:
    report = run_suite("full", live=False, enforce=False)
    assert report["exit_code"] == 0
    assert (REPO / "evals/out/results.md").is_file()
    assert report["metrics"]["determination_accuracy"] >= 0.0
    # aggregate helper
    from evals.metrics import CaseMetrics

    rows = [
        CaseMetrics(
            case_id="x",
            determination_correct=True,
            deferred=False,
            evidence_recall=1.0,
            citation_faithfulness=1.0,
            predicted_verdict="supported",
            key_verdict="supported",
            status="completed",
        )
    ]
    assert aggregate(rows)["determination_accuracy"] == 1.0
