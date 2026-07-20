"""Eval harness unit tests (precomputed, no live LLM)."""

from __future__ import annotations

from pathlib import Path

from backend.rules.loader import load_criteria
from backend.schemas import AnswerKey, AuditResult, Case
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
    case = Case.model_validate_json(
        (REPO / "data/cases/sepsis_001.json").read_text()
    )
    m = score_case(result, key, case, load_criteria(case.target_dx))
    assert m.citation_faithfulness == 1.0
    assert 0.0 <= m.evidence_recall <= 1.0


def test_smoke_suite_enforce(tmp_path: Path) -> None:
    report = run_suite("smoke", live=False, enforce=True, out_dir=tmp_path)
    assert report["exit_code"] == 0
    assert report["metrics"]["citation_faithfulness"] >= 0.95
    assert len(report["cases"]) == 5


def test_full_suite_writes_report(tmp_path: Path) -> None:
    report = run_suite("full", live=False, enforce=False, out_dir=tmp_path)
    assert report["exit_code"] == 0
    assert (tmp_path / "results.md").is_file()
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


def test_deferral_case_defers_and_scores_correct() -> None:
    """sepsis_011 is ambiguous by design: deferral IS the correct output."""
    result = AuditResult.model_validate_json(
        (REPO / "data/precomputed/sepsis_011.json").read_text(encoding="utf-8")
    )
    key = AnswerKey.model_validate_json(
        (REPO / "data/keys/sepsis_011.key.json").read_text(encoding="utf-8")
    )
    assert key.deferral_expected is True
    assert result.status == "needs_review"
    assert result.verdict is None
    assert "unknown_verdict" in result.force_reasons

    case = Case.model_validate_json(
        (REPO / "data/cases/sepsis_011.json").read_text(encoding="utf-8")
    )
    row = score_case(result, key, case, load_criteria("sepsis"))
    assert row.determination_correct is True
    assert row.deferred is True
