"""Consistency checks for generated cases and answer keys (no LLM)."""

from __future__ import annotations

from backend.schemas import AnswerKey, Case


class ConsistencyError(ValueError):
    """Raised when a case/key pair fails structural consistency checks."""


def check_case_key_consistency(case: Case, key: AnswerKey) -> list[str]:
    """Return a list of human-readable issues (empty means OK)."""
    issues: list[str] = []

    if case.case_id != key.case_id:
        issues.append(f"case_id mismatch: case={case.case_id!r} key={key.case_id!r}")

    n_docs = len(case.documents)
    if n_docs < 3 or n_docs > 6:
        issues.append(f"case must have 3 to 6 documents, found {n_docs}")

    for doc in case.documents:
        n_lines = len(doc.lines)
        if n_lines < 15 or n_lines > 60:
            issues.append(
                f"document {doc.doc_id!r} must have 15 to 60 lines, found {n_lines}"
            )

    doc_by_id = {d.doc_id: d for d in case.documents}
    for pe in key.planted_evidence:
        doc = doc_by_id.get(pe.doc_id)
        if doc is None:
            issues.append(f"planted evidence references missing doc_id={pe.doc_id!r}")
            continue
        n = len(doc.lines)
        if pe.line_start < 1 or pe.line_end > n:
            issues.append(
                f"planted span {pe.doc_id}:{pe.line_start}-{pe.line_end} "
                f"out of range (doc has {n} lines)"
            )
        if pe.line_end < pe.line_start:
            issues.append(f"planted span has line_end < line_start: {pe}")

    # Notes should not invent lab names that never appear in the labs table.
    # Soft check: if a note line mentions a known lab keyword with a number pattern,
    # the lab table should include that name. Kept light for generator iterations.
    lab_names = {lab.name for lab in case.labs}
    vital_names = {v.name for v in case.vitals}
    mentioned = _mentioned_metrics(" ".join(line for d in case.documents for line in d.lines))
    for name in mentioned:
        if name in ("lactate", "creatinine", "wbc", "platelets", "bilirubin") and name not in lab_names:
            issues.append(f"notes mention lab {name!r} but labs table has no such entry")
        if name in ("map", "sbp", "temp", "spo2") and name not in vital_names:
            issues.append(f"notes mention vital {name!r} but vitals table has no such entry")

    if key.verdict == "not_supported":
        against = [p for p in key.planted_evidence if p.side == "against"]
        if not against:
            issues.append("not_supported key must plant at least one against span")

    if len(key.planted_evidence) < 2:
        issues.append("answer key must plant at least 2 evidence spans")

    return issues


def assert_consistent(case: Case, key: AnswerKey) -> None:
    issues = check_case_key_consistency(case, key)
    if issues:
        raise ConsistencyError("; ".join(issues))


def _mentioned_metrics(text: str) -> set[str]:
    lower = text.lower()
    names = (
        "lactate",
        "creatinine",
        "wbc",
        "platelets",
        "bilirubin",
        "map",
        "sbp",
        "temp",
        "spo2",
    )
    return {n for n in names if n in lower}
