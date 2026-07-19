"""Run ChartProof eval suites against precomputed (or live) audit results.

Usage:
  python -m evals.run --suite smoke
  python -m evals.run --suite full --enforce-thresholds
  python -m evals.run --suite smoke --live   # run pipeline (needs chroma)
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from backend.config import CASES_DIR, KEYS_DIR, REPO_ROOT
from backend.pipeline.audit_service import load_cached_result, run_audit
from backend.rules.loader import load_criteria
from backend.schemas import AnswerKey, AuditResult, Case
from evals.metrics import CaseMetrics, aggregate, score_case

THRESHOLDS_PATH = REPO_ROOT / "evals" / "thresholds.yaml"
OUT_DIR = REPO_ROOT / "evals" / "out"


def load_thresholds() -> dict:
    return yaml.safe_load(THRESHOLDS_PATH.read_text(encoding="utf-8"))


def list_all_case_ids() -> list[str]:
    return sorted(p.stem for p in CASES_DIR.glob("*.json"))


def load_key(case_id: str) -> AnswerKey:
    path = KEYS_DIR / f"{case_id}.key.json"
    return AnswerKey.model_validate_json(path.read_text(encoding="utf-8"))


def load_result(case_id: str, *, live: bool) -> AuditResult:
    if live:
        return run_audit(case_id, fresh=True, persist_runtime_cache=False)
    # Prefer precomputed/cached
    cached = load_cached_result(case_id, fresh=False)
    if cached is not None:
        return cached
    # Fallback live
    return run_audit(case_id, fresh=True, persist_runtime_cache=False)


def run_suite(
    suite: str,
    *,
    live: bool = False,
    enforce: bool = False,
    out_dir: Path | None = None,
) -> dict:
    thr = load_thresholds()
    if suite == "smoke":
        case_ids = list(thr["smoke_case_ids"])
        limits = thr["smoke"]
    elif suite == "full":
        case_ids = list_all_case_ids()
        limits = thr["full"]
    else:
        raise ValueError(f"unknown suite: {suite}")

    rows: list[CaseMetrics] = []
    errors: list[str] = []
    for case_id in case_ids:
        try:
            result = load_result(case_id, live=live)
            key = load_key(case_id)
            case = Case.model_validate_json(
                (CASES_DIR / f"{case_id}.json").read_text(encoding="utf-8")
            )
            criteria = load_criteria(case.target_dx)
            rows.append(score_case(result, key, case, criteria))
        except Exception as e:  # noqa: BLE001
            errors.append(f"{case_id}: {e}")

    metrics = aggregate(rows) if rows else {
        "determination_accuracy": 0.0,
        "evidence_recall": 0.0,
        "citation_faithfulness": 0.0,
        "deferral_rate": 0.0,
    }

    passed = True
    failures: list[str] = []
    for name, minimum in limits.items():
        actual = metrics.get(name, 0.0)
        if actual < float(minimum):
            passed = False
            failures.append(f"{name}: {actual:.3f} < {float(minimum):.3f}")

    if errors:
        passed = False

    report = {
        "suite": suite,
        "timestamp": datetime.now(UTC).isoformat(),
        "case_ids": case_ids,
        "metrics": metrics,
        "thresholds": limits,
        "passed": passed and (not enforce or not failures),
        "failures": failures,
        "errors": errors,
        "cases": [
            {
                "case_id": r.case_id,
                "status": r.status,
                "key_verdict": r.key_verdict,
                "predicted_verdict": r.predicted_verdict,
                "determination_correct": r.determination_correct,
                "deferred": r.deferred,
                "evidence_recall": r.evidence_recall,
                "citation_faithfulness": r.citation_faithfulness,
                "faithfulness_issues": r.faithfulness_issues,
            }
            for r in rows
        ],
    }

    destination = out_dir or OUT_DIR
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / f"{suite}_results.json"
    md_path = destination / "results.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(_render_markdown(report))
    print(f"wrote {json_path} and {md_path}")

    if enforce and (failures or errors):
        return {**report, "exit_code": 1}
    return {**report, "exit_code": 0}


def _render_markdown(report: dict) -> str:
    m = report["metrics"]
    lines = [
        f"# ChartProof eval report ({report['suite']})",
        "",
        f"Generated: {report['timestamp']}",
        "",
        "## Aggregate metrics",
        "",
        "| Metric | Value | Threshold |",
        "|--------|------:|----------:|",
    ]
    thr = report["thresholds"]
    for key, label in (
        ("determination_accuracy", "Determination accuracy"),
        ("evidence_recall", "Evidence recall"),
        ("citation_faithfulness", "Citation faithfulness"),
        ("deferral_rate", "Deferral rate"),
    ):
        t = thr.get(key)
        tcell = f"{float(t):.2f}" if t is not None else "—"
        # avoid em dash for CLAUDE rule — use n/a
        if t is None:
            tcell = "n/a"
        lines.append(f"| {label} | {m.get(key, 0):.3f} | {tcell} |")

    lines += [
        "",
        f"**Suite passed thresholds:** {report['passed']}",
        "",
        "## Per-case",
        "",
        "| Case | Status | Key | Pred | Correct | Recall | Faithful |",
        "|------|--------|-----|------|---------|-------:|---------:|",
    ]
    for c in report["cases"]:
        lines.append(
            f"| {c['case_id']} | {c['status']} | {c['key_verdict']} | "
            f"{c['predicted_verdict']} | {c['determination_correct']} | "
            f"{c['evidence_recall']:.2f} | {c['citation_faithfulness']:.2f} |"
        )
    faithfulness_failures = [
        (case["case_id"], issue)
        for case in report["cases"]
        for issue in case.get("faithfulness_issues", [])
    ]
    if faithfulness_failures:
        lines += ["", "## Citation faithfulness issues", ""]
        lines.extend(f"- {case_id}: {issue}" for case_id, issue in faithfulness_failures)
    if report.get("failures"):
        lines += ["", "## Threshold failures", ""]
        lines.extend(f"- {f}" for f in report["failures"])
    if report.get("errors"):
        lines += ["", "## Errors", ""]
        lines.extend(f"- {e}" for e in report["errors"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ChartProof eval harness")
    parser.add_argument("--suite", choices=("smoke", "full"), default="smoke")
    parser.add_argument(
        "--enforce-thresholds",
        action="store_true",
        help="exit non-zero if metrics below thresholds",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="run live pipeline instead of precomputed cache",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DIR,
        help="directory for JSON and Markdown reports",
    )
    args = parser.parse_args(argv)
    report = run_suite(
        args.suite,
        live=args.live,
        enforce=args.enforce_thresholds,
        out_dir=args.out_dir,
    )
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
