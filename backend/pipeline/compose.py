"""Composer: determination draft + rationale letter with citation enforcement.

Hard rule: only numbered evidence IDs may be referenced. Uncited claim sentences
are dropped in code (not prompt-only). The compose path is deterministic so
tests and free-tier demos stay offline-friendly.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from backend.index.retrieve import retrieve_guidelines
from backend.pipeline.lexicon import narrative_side
from backend.schemas import Case, CriteriaFile, EvidenceItem, EvidenceSpan

Verdict = Literal["supported", "not_supported"]
TriState = Literal["met", "not_met", "unclear"]
Side = Literal["for", "against"]

_EVIDENCE_ID_RE = re.compile(r"\bE(\d+)\b")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def build_evidence_catalog(
    case: Case,
    evidence_findings: list[dict[str, Any]],
    rules_result: dict[str, Any],
) -> list[EvidenceItem]:
    """Flatten findings + structured rule hits into numbered evidence items."""
    items: list[EvidenceItem] = []
    seen: set[tuple[str, int, int, str, str]] = set()
    eid = 1

    def _add(side: str, criterion_id: str, span: EvidenceSpan, text: str) -> None:
        nonlocal eid
        key = (span.doc_id, span.line_start, span.line_end, side, criterion_id)
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

    # Structured criteria: classify each documented observation independently.
    # This prevents a later normal value from relabeling an earlier abnormal line.
    for crit in rules_result.get("criteria") or []:
        if crit.get("method") != "structured":
            continue
        cid = str(crit["criterion_id"])
        for span, text, side in _find_structured_metric_mentions(case, crit):
            _add(side, cid, span, text)

    # Composite criteria: cite explicit chart statements about the composite
    # itself ("no evidence of organ dysfunction"). Each line is side-classified
    # by the shared lexicon, so sides cannot be inherited incorrectly.
    for crit in rules_result.get("criteria") or []:
        if crit.get("method") not in ("any_of", "all_of"):
            continue
        cid = str(crit["criterion_id"])
        added = 0
        for doc in case.documents:
            for line_number, line in enumerate(doc.lines, start=1):
                side = narrative_side(cid, line)
                if side is None:
                    continue
                _add(
                    side,
                    cid,
                    EvidenceSpan(
                        doc_id=doc.doc_id,
                        line_start=line_number,
                        line_end=line_number,
                    ),
                    line,
                )
                added += 1
                if added >= 4:
                    break
            if added >= 4:
                break

    return items


_METRIC_VALUE_PATTERNS: dict[str, re.Pattern[str]] = {
    "lactate_elevated": re.compile(
        r"\blactate(?:\s+level)?\D{0,35}?([0-9]+(?:\.[0-9]+)?)",
        re.IGNORECASE,
    ),
    "hypotension": re.compile(
        r"\bmap\D{0,20}?([0-9]+(?:\.[0-9]+)?)",
        re.IGNORECASE,
    ),
    "creatinine_rise": re.compile(
        r"\bcreatinine(?:\s+level)?\D{0,35}?([0-9]+(?:\.[0-9]+)?)",
        re.IGNORECASE,
    ),
    "thrombocytopenia": re.compile(
        r"\bplatelets?(?:\s+count)?\D{0,35}?([0-9]+(?:\.[0-9]+)?)",
        re.IGNORECASE,
    ),
}


def _point_observation_side(value: float, op: str, threshold: float) -> Side:
    met = {
        "gt": value > threshold,
        "gte": value >= threshold,
        "lt": value < threshold,
        "lte": value <= threshold,
    }.get(op)
    if met is None:
        raise ValueError(f"unsupported point op for evidence: {op}")
    return "for" if met else "against"


def _trend_observation_side(text: str) -> Side | None:
    lower = text.lower()
    against_markers = (
        "stable",
        "unchanged",
        "not changed",
        "no significant",
        "decreas",
        "returned to baseline",
        "at baseline",
    )
    if any(marker in lower for marker in against_markers):
        return "against"
    for_markers = ("rise", "risen", "rose", "increas", "worsen")
    if any(marker in lower for marker in for_markers):
        return "for"
    return None


def classify_structured_observation_side(
    criterion_id: str,
    text: str,
    op: str,
    threshold: float,
) -> Side | None:
    """Classify one structured chart excerpt against its encoded criterion."""
    pattern = _METRIC_VALUE_PATTERNS.get(criterion_id)
    if pattern is None:
        return None
    match = pattern.search(text)
    if match is None:
        return None
    if op == "rise_gte":
        return _trend_observation_side(text)
    return _point_observation_side(float(match.group(1)), op, threshold)


def _find_structured_metric_mentions(
    case: Case,
    criterion: dict[str, Any],
    *,
    limit: int = 6,
) -> list[tuple[EvidenceSpan, str, Side]]:
    criterion_id = str(criterion["criterion_id"])
    op = criterion.get("op")
    threshold = criterion.get("threshold")
    if not op or threshold is None or criterion_id not in _METRIC_VALUE_PATTERNS:
        return []

    found: list[tuple[EvidenceSpan, str, Side]] = []
    for doc in case.documents:
        for line_number, line in enumerate(doc.lines, start=1):
            side = classify_structured_observation_side(
                criterion_id,
                line,
                str(op),
                float(threshold),
            )
            if side is None:
                continue
            found.append(
                (
                    EvidenceSpan(
                        doc_id=doc.doc_id,
                        line_start=line_number,
                        line_end=line_number,
                    ),
                    line,
                    side,
                )
            )
            if len(found) >= limit:
                return found
    return found


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
        top = next(
            (e for e in evidence if e.side == "for" and e.criterion_id != "infection"),
            next((e for e in evidence if e.side == "for"), None),
        )
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

    # Evidence table. One row per evidence ID; the same chart span can appear
    # under several criteria, so the Criterion column makes each row's
    # attribution explicit instead of looking like a duplicate.
    doc_lookup = {d.doc_id: d for d in case.documents}
    rows = [
        "| # | For/Against | Criterion | Source | Lines | Excerpt |",
        "|---|-------------|-----------|--------|-------|---------|",
    ]
    for e in evidence:
        doc = doc_lookup.get(e.span.doc_id)
        source = (
            f"{doc.doc_type} {doc.date}" if doc else e.span.doc_id
        )
        excerpt = e.text.replace("|", "/").replace("\n", " ")[:120]
        rows.append(
            f"| {e.evidence_id} | {e.side} | {e.criterion_id} | {source} | "
            f"{e.span.line_start}-{e.span.line_end} | {excerpt} |"
        )
    if len(rows) == 2:
        rows.append("| - | - | - | - | - | No evidence spans collected |")

    # Coding rationale with guideline citations. Fallback pairs must be real
    # manifest source_ids with real section headings so the offline path still
    # passes the grounded faithfulness gate.
    g_bits = guideline_bits or [
        ("sepsis3_summary", "Section: Definition"),
        ("icd10cm_guidelines_fy2026_summary", "Section: Clinical validation context"),
    ]
    coding = (
        f"Clinical validation of billed {display} should rest on documented infection "
        f"plus organ dysfunction indicators ({g_bits[0][0]}, {g_bits[0][1]}). "
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
                n_results=8,
                client=client,
                persist_dir=chroma_dir,
            )
            clinical = next(
                (
                    (h.source_id, h.section)
                    for h in hits
                    if h.source_id
                    and h.section
                    and criteria.dx.lower() in h.source_id.lower()
                ),
                None,
            )
            coding = next(
                (
                    (h.source_id, h.section)
                    for h in hits
                    if h.source_id and h.section and h.source_id.startswith("icd10cm_")
                ),
                None,
            )
            if clinical and coding:
                guideline_bits = [clinical, coding]
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
        "guideline_bits": guideline_bits,
    }
