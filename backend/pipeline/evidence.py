"""Evidence agents for narrative criteria (retrieval + lightweight scoring).

No LLM required for Phase 2 golden path. Optional Groq can be added later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from backend.index.retrieve import retrieve_case
from backend.pipeline.lexicon import (
    NARRATIVE_KEYWORDS,
    Side,
    narrative_side,
    score_text,
)
from backend.schemas import Case, CriteriaKind, CriteriaNode, EvidenceSpan

TriState = Literal["met", "not_met", "unclear"]


@dataclass
class EvidenceFinding:
    criterion_id: str
    result: TriState
    side_items: list[dict] = field(default_factory=list)
    # each item: {side, span, text, score}


def classify_narrative_evidence_side(
    criterion_id: str,
    text: str,
) -> Side | None:
    """Re-evaluate one narrative excerpt against its criterion-specific signals."""
    return narrative_side(criterion_id, text)


def _collect_narrative_nodes(nodes: list[CriteriaNode]) -> list[CriteriaNode]:
    out: list[CriteriaNode] = []
    for n in nodes:
        if n.kind == CriteriaKind.NARRATIVE:
            out.append(n)
        if n.children:
            out.extend(_collect_narrative_nodes(n.children))
    return out


def gather_evidence_for_criterion(
    case: Case,
    node: CriteriaNode,
    *,
    n_results: int = 8,
    client=None,
) -> EvidenceFinding:
    """Retrieve FOR/AGAINST evidence and resolve yes/no/unclear."""
    question = node.question or node.id
    bags = NARRATIVE_KEYWORDS.get(
        node.id,
        {
            "for": tuple(re.findall(r"[a-zA-Z]{4,}", (node.question or node.id).lower())[:8]),
            "against": ("no " + node.id, "not " + node.id),
        },
    )
    for_kws = bags["for"]
    against_kws = bags["against"]

    # Two retrieval queries improve coverage
    queries = [
        question,
        " ".join(for_kws[:6]),
        f"{node.id} not present denied ruled out",
    ]
    seen_spans: set[tuple[str, int, int]] = set()
    candidates: list[tuple[Side, EvidenceSpan, str, float]] = []

    for q in queries:
        try:
            chunks = retrieve_case(
                case.case_id, q, n_results=n_results, client=client, case=case
            )
        except FileNotFoundError:
            chunks = []
        for ch in chunks:
            if ch.span is None:
                continue
            key = (ch.span.doc_id, ch.span.line_start, ch.span.line_end)
            if key in seen_spans:
                continue
            seen_spans.add(key)
            fs, as_ = score_text(
                ch.text,
                for_kws,
                against_kws,
                apply_vasopressor_rules=node.id == "vasopressors",
            )
            # Ties are ambiguous excerpts (signals on both sides); cite neither.
            if as_ > fs and as_ > 0:
                candidates.append(("against", ch.span, ch.text, as_))
            elif fs > as_:
                candidates.append(("for", ch.span, ch.text, fs))

    # Always sweep the full chart as well: retrieval is recall-limited and a
    # keyword sweep over demo-size charts is cheap. Catches signal lines the
    # retriever ranked below the cutoff.
    for doc in case.documents:
        for i, line in enumerate(doc.lines, start=1):
            fs, as_ = score_text(
                line,
                for_kws,
                against_kws,
                apply_vasopressor_rules=node.id == "vasopressors",
            )
            if fs == as_:
                # No signal, or ambiguous signals on both sides: cite neither.
                continue
            span = EvidenceSpan(doc_id=doc.doc_id, line_start=i, line_end=i)
            key = (span.doc_id, span.line_start, span.line_end)
            if key in seen_spans:
                continue
            seen_spans.add(key)
            if as_ > fs:
                candidates.append(("against", span, line, as_))
            else:
                candidates.append(("for", span, line, fs))

    candidates.sort(key=lambda x: x[3], reverse=True)
    # Keep top items per side
    for_items = [c for c in candidates if c[0] == "for"][:4]
    against_items = [c for c in candidates if c[0] == "against"][:4]

    for_total = sum(c[3] for c in for_items)
    against_total = sum(c[3] for c in against_items)

    # Special-case vasopressors: explicit "not requiring" should win
    if node.id == "vasopressors" and against_total > 0 and for_total > 0:
        # If against phrases exist, prefer not_met unless strong active pressor language without negation
        only_negation = against_total >= for_total
        if only_negation:
            result: TriState = "not_met"
        else:
            result = "met"
    elif for_total == 0 and against_total == 0:
        # No textual signal: infection stays unclear; absence of vaso/AMS → not_met
        if node.id in ("vasopressors", "altered_mentation"):
            result = "not_met"
        else:
            result = "unclear"
    elif for_total > against_total:
        result = "met"
    elif against_total > for_total:
        result = "not_met"
    else:
        result = "unclear"

    side_items = [
        {
            "side": side,
            "span": span.model_dump(),
            "text": text,
            "score": score,
        }
        for side, span, text, score in (for_items + against_items)
    ]
    return EvidenceFinding(
        criterion_id=node.id, result=result, side_items=side_items
    )


def run_evidence_agents(
    case: Case,
    criteria_nodes: list[CriteriaNode],
    *,
    client=None,
) -> tuple[dict[str, TriState], list[EvidenceFinding]]:
    """Evaluate all narrative criteria; return answers map + findings list."""
    narrative = _collect_narrative_nodes(criteria_nodes)
    findings: list[EvidenceFinding] = []
    answers: dict[str, TriState] = {}
    for node in narrative:
        finding = gather_evidence_for_criterion(case, node, client=client)
        findings.append(finding)
        answers[node.id] = finding.result
    return answers, findings
