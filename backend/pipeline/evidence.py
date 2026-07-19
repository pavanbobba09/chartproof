"""Evidence agents for narrative criteria (retrieval + lightweight scoring).

No LLM required for Phase 2 golden path. Optional Groq can be added later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from backend.index.retrieve import retrieve_case
from backend.schemas import Case, CriteriaKind, CriteriaNode, EvidenceSpan

TriState = Literal["met", "not_met", "unclear"]
Side = Literal["for", "against"]

# Keyword bags for demo-quality narrative resolution (synthetic charts)
_CRITERION_KEYWORDS: dict[str, dict[str, tuple[str, ...]]] = {
    "infection": {
        "for": (
            "infection",
            "infected",
            "antibiotic",
            "antibiotics",
            "ceftriaxone",
            "vancomycin",
            "piperacillin",
            "culture",
            "uti",
            "pneumonia",
            "bacteremia",
            "sepsis",
            "cellulitis",
            "pyelonephritis",
            "abscess",
            "fever",
            "leukocytosis",
        ),
        "against": (
            "no infection",
            "infection ruled out",
            "cultures negative",
            "not infected",
            "aseptic",
        ),
    },
    "vasopressors": {
        "for": (
            "norepinephrine",
            "levophed",
            "phenylephrine",
            "vasopressin drip",
            "on pressors",
            "started on pressors",
            "started vasopressor",
            "requiring vasopressors",
            "vasopressors are being",
            "treated with broad-spectrum antibiotics and vasopressors",
        ),
        "against": (
            "no vasopressor",
            "no vasopressors",
            "not requiring vasopressor",
            "not requiring vasopressors",
            "without vasopressor",
            "without vasopressors",
            "off vasopressors",
            "not on vasopressors",
            "did not require vasopressor",
            "did not require vasopressors",
            "no longer requiring vasopressor",
            "no longer requiring vasopressors",
            "not requiring pressors",
        ),
    },
    "altered_mentation": {
        "for": (
            "altered mental",
            "confused",
            "confusion",
            "obtunded",
            "delirium",
            "gcs",
            "unresponsive",
            "encephalopath",
            "mental status change",
        ),
        "against": (
            "alert and oriented",
            "mental status clear",
            "normal mental",
            "a&ox3",
            "a and o x3",
            "gcs 15",
            "neurologically intact",
        ),
    },
}


@dataclass
class EvidenceFinding:
    criterion_id: str
    result: TriState
    side_items: list[dict] = field(default_factory=list)
    # each item: {side, span, text, score}


def _score_text(
    text: str,
    for_kws: tuple[str, ...],
    against_kws: tuple[str, ...],
    *,
    apply_vasopressor_negation: bool = False,
) -> tuple[float, float]:
    lower = text.lower()
    for_score = 0.0
    against_score = 0.0
    for kw in for_kws:
        if kw in lower:
            for_score += 1.0
    for kw in against_kws:
        if kw in lower:
            against_score += 2.0  # stronger weight for explicit negation phrases
    # Generic negation around vasopressor/pressor words (catches plural forms)
    if apply_vasopressor_negation and (
        re.search(
            r"\b(no|not|without|never|denies?)\b.{0,40}\b(vasopressors?|pressors?)\b",
            lower,
        )
        or re.search(
            r"\b(vasopressors?|pressors?)\b.{0,40}\b(not required|not indicated|discontinued)\b",
            lower,
        )
    ):
        against_score += 2.5
        # Do not also credit bare "vasopressors" as for when negation present
        if for_score > 0 and against_score > for_score:
            for_score = max(0.0, for_score - 1.0)
    return for_score, against_score


def classify_narrative_evidence_side(
    criterion_id: str,
    text: str,
) -> Side | None:
    """Re-evaluate one narrative excerpt against its criterion-specific signals."""
    bags = _CRITERION_KEYWORDS.get(criterion_id)
    if bags is None:
        return None
    for_score, against_score = _score_text(
        text,
        bags["for"],
        bags["against"],
        apply_vasopressor_negation=criterion_id == "vasopressors",
    )
    if against_score > for_score and against_score > 0:
        return "against"
    if for_score > against_score and for_score > 0:
        return "for"
    return None


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
    bags = _CRITERION_KEYWORDS.get(
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
            fs, as_ = _score_text(
                ch.text,
                for_kws,
                against_kws,
                apply_vasopressor_negation=node.id == "vasopressors",
            )
            if as_ > fs and as_ > 0:
                candidates.append(("against", ch.span, ch.text, as_))
            elif fs > 0:
                candidates.append(("for", ch.span, ch.text, fs))

    # Fallback: scan full chart if retrieval weak
    if len(candidates) < 2:
        for doc in case.documents:
            for i, line in enumerate(doc.lines, start=1):
                fs, as_ = _score_text(
                    line,
                    for_kws,
                    against_kws,
                    apply_vasopressor_negation=node.id == "vasopressors",
                )
                if fs == 0 and as_ == 0:
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
