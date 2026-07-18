"""Composer: determination draft + rationale letter with citation enforcement.

Hard rule: only numbered evidence IDs may be referenced. Uncited claim sentences
are dropped in code (not prompt-only). Default path is deterministic so tests and
free-tier demos stay offline-friendly; optional Groq can draft prose that is then
filtered through the same citation gate.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from backend.index.retrieve import retrieve_guidelines
from backend.schemas import Case, CriteriaFile, EvidenceItem, EvidenceSpan

Verdict = Literal["supported", "not_supported"]
TriState = Literal["met", "not_met", "unclear"]

_EVIDENCE_ID_RE = re.compile(r"\bE(\d+)\b")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def build_evidence_catalog(
    case: Case,
    evidence_findings: list[dict[str, Any]],
    rules_result: dict[str, Any],
) -> list[EvidenceItem]:
    """Flatten findings + structured rule hits into numbered evidence items."""
    items: list[EvidenceItem] = []
    seen: set[tuple[str, int, int, str]] = set()
    eid = 1

    def _add(side: str, criterion_id: str, span: EvidenceSpan, text: str) -> None:
        nonlocal eid
        key = (span.doc_id, span.line_start, span.line_end, side)
        if key in seen:
            return
        seen.add(key)
        items.append(
            EvidenceItem(
                evidence_id=f"E{eid}",
                side=side,  # type: ignore[arg-type]
                criterion_id=criterion_id,
                span=span,
                text=text.strip() or "(empty span)",
            )
        )
        eid += 1

    # Narrative agent spans
    for finding in evidence_findings:
        cid = finding["criterion_id"]
        for side_item in finding.get("side_items") or []:
            span = EvidenceSpan.model_validate(side_item["span"])
            _add(side_item["side"], cid, span, side_item.get("text") or "")

    # Structured criteria: cite labs/vitals tables as synthetic "spans" on hp line 1 if needed
    # Prefer citing document lines that mention the metric name
    breakdown = rules_result.get("breakdown") or {}
    for crit in rules_result.get("criteria") or []:
        if crit.get("method") != "structured":
            continue
        cid = crit["criterion_id"]
        result = crit["result"]
        if result == "unclear":
            continue
        side = "for" if result == "met" else "against"
        span, text = _find_metric_mention(case, cid)
        _add(side, cid, span, text)

    # Ensure at least one item when organ dysfunction is clear from structured only
    if not items and breakdown:
        for cid, res in breakdown.items():
            if res in ("met", "not_met"):
                span, text = _find_metric_mention(case, cid)
                _add("for" if res == "met" else "against", cid, span, text)
                if len(items) >= 3:
                    break

    return items


def _find_metric_mention(case: Case, criterion_id: str) -> tuple[EvidenceSpan, str]:
    keywords = {
        "lactate_elevated": ("lactate",),
        "hypotension": ("map", "hypotens", "blood pressure"),
        "creatinine_rise": ("creatinine",),
        "thrombocytopenia": ("platelet",),
        "infection": ("infection", "antibiotic", "uti", "pneumonia"),
        "vasopressors": ("vasopressor", "pressor"),
        "organ_dysfunction": ("organ dysfunction", "lactate", "map"),
    }
    kws = keywords.get(criterion_id, (criterion_id.replace("_", " "),))
    for doc in case.documents:
        for i, line in enumerate(doc.lines, start=1):
            low = line.lower()
            if any(k in low for k in kws):
                return EvidenceSpan(doc_id=doc.doc_id, line_start=i, line_end=i), line
    # Fallback: first line of first document
    doc = case.documents[0]
    return (
        EvidenceSpan(doc_id=doc.doc_id, line_start=1, line_end=1),
        doc.lines[0] if doc.lines else "",
    )


def derive_llm_verdict(
    rules_verdict: str | None,
    evidence: list[EvidenceItem],
) -> Verdict | None:
    """Heuristic LLM-side verdict from evidence balance (deterministic demo path)."""
    if rules_verdict in ("supported", "not_supported"):
        # Slightly independent signal: count for vs against on organ-related criteria
        for_n = sum(1 for e in evidence if e.side == "for")
        against_n = sum(1 for e in evidence if e.side == "against")
        if for_n == 0 and against_n == 0:
            return rules_verdict  # type: ignore[return-value]
        if for_n > against_n + 1:
            return "supported"
        if against_n > for_n + 1:
            return "not_supported"
        return rules_verdict  # type: ignore[return-value]
    # unknown rules: lean on evidence
    for_n = sum(1 for e in evidence if e.side == "for" and e.criterion_id != "infection")
    against_n = sum(1 for e in evidence if e.side == "against")
    if for_n > against_n:
        return "supported"
    if against_n > for_n:
        return "not_supported"
    return None


def filter_uncited_sentences(text: str, valid_ids: set[str]) -> tuple[str, int]:
    """Drop claim sentences in ## Determination that lack a valid evidence ID.

    Evidence table rows, coding rationale (guideline source_id cites), headers,
    and reviewer note are not filtered. This enforces citation discipline where
    the draft verdict is stated.
    """
    if not text.strip():
        return text, 0
    lines = text.splitlines()
    kept: list[str] = []
    dropped = 0
    in_determination = False
    claim_markers = (
        "supported",
        "not supported",
        "not_supported",
        "infection",
        "organ",
        "lactate",
        "hypotension",
        "because",
        "therefore",
        "evidence shows",
        "chart shows",
        "deferred",
    )
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_determination = stripped.lower().startswith("## determination")
            kept.append(line)
            continue
        if stripped.startswith("#"):
            in_determination = False
            kept.append(line)
            continue
        if not in_determination:
            kept.append(line)
            continue
        if not stripped:
            kept.append(line)
            continue
        # Determination body: require valid E# on claim-like sentences
        sentences = _SENTENCE_SPLIT.split(stripped)
        kept_sents: list[str] = []
        for sent in sentences:
            s = sent.strip()
            if not s:
                continue
            ids = {f"E{m}" for m in _EVIDENCE_ID_RE.findall(s)}
            looks_like_claim = any(m in s.lower() for m in claim_markers)
            if looks_like_claim and (not ids or not ids.issubset(valid_ids)):
                dropped += 1
                continue
            kept_sents.append(s)
        if kept_sents:
            prefix = line[: len(line) - len(line.lstrip())]
            kept.append(prefix + " ".join(kept_sents))
    return "\n".join(kept), dropped


def compose_letter(
    *,
    case: Case,
    criteria: CriteriaFile,
    status: str,
    verdict: str | None,
    evidence: list[EvidenceItem],
    rules_verdict: str | None,
    guideline_bits: list[tuple[str, str]] | None = None,
) -> tuple[str, int]:
    """Build DATA_SPEC section 9 letter; enforce citations. Returns (markdown, dropped)."""
    display = criteria.display_name
    valid_ids = {e.evidence_id for e in evidence}

    def _excerpt(text: str, n: int = 140) -> str:
        # Single clause only so period-splitting does not create uncited sentences
        first = text.replace("\n", " ").split(".")[0].strip()
        return (first[:n] + ("..." if len(first) > n else "")).replace(":", " -")

    # Strongest reason from top for/against item (must include evidence_id)
    if verdict == "supported":
        top = next((e for e in evidence if e.side == "for"), None)
        reason = (
            f"Draft determination is supported, primarily based on {top.evidence_id} "
            f"({top.criterion_id}): {_excerpt(top.text)}"
            if top
            else "Draft determination is supported with no numbered evidence available (E0 missing)."
        )
    elif verdict == "not_supported":
        top = next((e for e in evidence if e.side == "against"), None)
        reason = (
            f"Draft determination is not_supported, primarily based on {top.evidence_id} "
            f"({top.criterion_id}): {_excerpt(top.text)}"
            if top
            else "Draft determination is not_supported with no numbered evidence available (E0 missing)."
        )
    else:
        reason = (
            "Draft determination is deferred pending auditor review (see evidence table); "
            "criteria evaluation was incomplete or conflicting."
        )
        # Attach an evidence id if any so the deferral sentence is citation-linked
        if evidence:
            reason = (
                f"Draft determination is deferred pending auditor review (see {evidence[0].evidence_id}); "
                f"criteria evaluation was incomplete or conflicting."
            )

    # Evidence table
    doc_lookup = {d.doc_id: d for d in case.documents}
    rows = [
        "| # | For/Against | Source | Lines | Excerpt |",
        "|---|-------------|--------|-------|---------|",
    ]
    for e in evidence:
        doc = doc_lookup.get(e.span.doc_id)
        source = (
            f"{doc.doc_type} {doc.date}" if doc else e.span.doc_id
        )
        excerpt = e.text.replace("|", "/").replace("\n", " ")[:120]
        rows.append(
            f"| {e.evidence_id} | {e.side} | {source} | "
            f"{e.span.line_start}-{e.span.line_end} | {excerpt} |"
        )
    if len(rows) == 2:
        rows.append("| - | - | - | - | No evidence spans collected |")

    # Coding rationale with guideline citations
    g_bits = guideline_bits or [
        ("sepsis3_summary", "Section: Definition"),
        ("icd10cm_coding_summary", "Section: Clinical validation context"),
    ]
    coding = (
        f"Clinical validation of billed {display} should rest on documented infection "
        f"plus organ dysfunction indicators (sepsis3_summary, {g_bits[0][1]}). "
        f"Findings that affect payment grouping must be supported by chart indicators "
        f"({g_bits[1][0]}, {g_bits[1][1]}). "
        f"This draft is for auditor review only and is not a payment decision. "
        f"Key evidence IDs considered: {', '.join(sorted(valid_ids)) or 'none'}."
    )

    letter = f"""# Clinical validation finding: {display}
Case {case.case_id} | Status: {status} | Draft for auditor review

## Determination
{reason}

## Evidence
{chr(10).join(rows)}

## Coding rationale
{coding}

## Reviewer note
Machine-drafted aid generated from synthetic data. A qualified auditor makes the final determination.
"""
    filtered, dropped = filter_uncited_sentences(letter, valid_ids)
    return filtered, dropped


def compose_from_state(
    case: Case,
    criteria: CriteriaFile,
    evidence_findings: list[dict[str, Any]],
    rules_result: dict[str, Any],
    *,
    use_guidelines: bool = True,
    chroma_dir: str | None = None,
) -> dict[str, Any]:
    """Full compose step output for the pipeline."""
    evidence = build_evidence_catalog(case, evidence_findings, rules_result)
    rules_verdict = rules_result.get("verdict")
    llm_verdict = derive_llm_verdict(rules_verdict, evidence)

    guideline_bits: list[tuple[str, str]] = []
    if use_guidelines:
        try:
            from backend.index.build import get_client

            client = get_client(chroma_dir) if chroma_dir else None
            hits = retrieve_guidelines(
                f"{criteria.display_name} clinical validation coding",
                n_results=2,
                client=client,
                persist_dir=chroma_dir,
            )
            for h in hits:
                if h.source_id and h.section:
                    guideline_bits.append((h.source_id, h.section))
        except Exception:  # noqa: BLE001 - offline compose still works
            guideline_bits = []

    # Temporary status for letter header; QA may override
    status = "completed"
    verdict_for_letter: str | None = llm_verdict or (
        rules_verdict if rules_verdict in ("supported", "not_supported") else None
    )
    letter, dropped = compose_letter(
        case=case,
        criteria=criteria,
        status=status,
        verdict=verdict_for_letter,
        evidence=evidence,
        rules_verdict=rules_verdict,
        guideline_bits=guideline_bits or None,
    )

    return {
        "evidence": [e.model_dump(mode="json") for e in evidence],
        "llm_verdict": llm_verdict,
        "letter_markdown": letter,
        "dropped_sentences": dropped,
    }
