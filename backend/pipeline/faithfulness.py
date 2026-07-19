"""Grounded citation-faithfulness checks for audit drafts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from backend.config import GUIDELINES_DIR
from backend.pipeline.lexicon import narrative_side
from backend.schemas import (
    AuditResult,
    Case,
    CriteriaFile,
    CriteriaKind,
    CriteriaNode,
    EvidenceItem,
)

_EVIDENCE_ID_RE = re.compile(r"\bE\d+\b")
_EVIDENCE_ROW_RE = re.compile(r"^\|\s*(E\d+)\s*\|", re.MULTILINE)
_GUIDELINE_CITATION_RE = re.compile(
    r"\((?P<source>[A-Za-z0-9_]+),\s*"
    r"(?P<section>[^()]*(?:\([^()]*\)[^()]*)*)\)"
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

_STRUCTURED_VALUE_PATTERNS: dict[str, re.Pattern[str]] = {
    "lactate_elevated": re.compile(
        r"\blactate(?:\s+level)?\D{0,35}?([0-9]+(?:\.[0-9]+)?)",
        re.IGNORECASE,
    ),
    "hypotension": re.compile(
        r"\b(?:map|mean arterial pressure)\D{0,20}?([0-9]+(?:\.[0-9]+)?)",
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

@dataclass(frozen=True)
class FaithfulnessIssue:
    code: str
    message: str
    evidence_id: str | None = None


@dataclass(frozen=True)
class FaithfulnessReport:
    score: float
    issues: list[FaithfulnessIssue] = field(default_factory=list)


def _section(markdown: str, heading: str) -> str:
    marker = f"## {heading}"
    if marker not in markdown:
        return ""
    body = markdown.split(marker, 1)[1]
    return body.split("\n## ", 1)[0].strip()


def _criterion_map(criteria: CriteriaFile) -> dict[str, CriteriaNode]:
    out: dict[str, CriteriaNode] = {}

    def visit(node: CriteriaNode) -> None:
        out[node.id] = node
        for child in node.children:
            visit(child)

    for node in criteria.criteria:
        visit(node)
    return out


def _grounded_text(item: EvidenceItem, case: Case) -> tuple[str | None, str | None]:
    document = next((doc for doc in case.documents if doc.doc_id == item.span.doc_id), None)
    if document is None:
        return None, "unknown_document"
    if item.span.line_end > len(document.lines):
        return None, "span_out_of_bounds"
    text = " ".join(document.lines[item.span.line_start - 1 : item.span.line_end])
    return text, None


def _narrative_side(criterion_id: str, text: str) -> str | None:
    # Canonical lexicon shared with the evidence agents (see lexicon.py for the
    # independence tradeoff). This check verifies stored side labels against
    # what the cited text actually supports under that lexicon.
    return narrative_side(criterion_id, text)


def _structured_side(item: EvidenceItem, node: CriteriaNode) -> str | None:
    if not node.op or node.threshold is None:
        return None
    pattern = _STRUCTURED_VALUE_PATTERNS.get(item.criterion_id)
    if pattern is None:
        return None
    match = pattern.search(item.text)
    if match is None:
        return None
    if node.op == "rise_gte":
        lower = item.text.lower()
        if any(
            marker in lower
            for marker in (
                "stable",
                "unchanged",
                "not changed",
                "no significant",
                "decreas",
                "returned to baseline",
                "at baseline",
            )
        ):
            return "against"
        if any(marker in lower for marker in ("rise", "risen", "rose", "increas", "worsen")):
            return "for"
        return None

    value = float(match.group(1))
    met = {
        "gt": value > node.threshold,
        "gte": value >= node.threshold,
        "lt": value < node.threshold,
        "lte": value <= node.threshold,
    }.get(node.op)
    if met is None:
        return None
    return "for" if met else "against"


def _expected_side(item: EvidenceItem, node: CriteriaNode) -> str | None:
    if node.kind == CriteriaKind.NARRATIVE:
        return _narrative_side(item.criterion_id, item.text)
    if node.kind == CriteriaKind.STRUCTURED:
        return _structured_side(item, node)
    # Composite criteria: explicit textual statements about the composite
    # itself are side-checked with the same shared lexicon.
    return _narrative_side(item.criterion_id, item.text)


def _guideline_sections(guidelines_dir: Path) -> set[tuple[str, str]]:
    manifest_path = guidelines_dir / "manifest.json"
    if not manifest_path.is_file():
        return set()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sections: set[tuple[str, str]] = set()
    for source in manifest.get("sources", []):
        source_id = source.get("source_id")
        filename = source.get("file")
        if not source_id or not filename:
            continue
        path = guidelines_dir / filename
        if not path.is_file():
            continue
        for heading in re.findall(r"^##\s+(.+)$", path.read_text(encoding="utf-8"), re.MULTILINE):
            sections.add((str(source_id), heading.strip()))
    return sections


def _validate_determination(
    result: AuditResult,
    evidence_by_id: dict[str, EvidenceItem],
    criteria: CriteriaFile,
) -> list[FaithfulnessIssue]:
    issues: list[FaithfulnessIssue] = []
    determination = _section(result.letter_markdown, "Determination")
    if not determination:
        return [FaithfulnessIssue("missing_determination", "Letter has no determination section")]

    claim_sentences = [
        sentence.strip()
        for sentence in _SENTENCE_SPLIT_RE.split(determination)
        if sentence.strip()
    ]
    if not claim_sentences:
        return [FaithfulnessIssue("missing_determination", "Determination contains no claim")]

    has_organ_rule = any(node.id == "organ_dysfunction" for node in criteria.criteria)
    for sentence in claim_sentences:
        cited_ids = _EVIDENCE_ID_RE.findall(sentence)
        if not cited_ids:
            issues.append(
                FaithfulnessIssue(
                    "uncited_determination",
                    f"Determination sentence has no evidence ID: {sentence}",
                )
            )
            continue
        cited = [evidence_by_id[eid] for eid in cited_ids if eid in evidence_by_id]
        unknown = [eid for eid in cited_ids if eid not in evidence_by_id]
        for evidence_id in unknown:
            issues.append(
                FaithfulnessIssue(
                    "unknown_determination_citation",
                    f"Determination cites unknown evidence ID {evidence_id}",
                    evidence_id,
                )
            )
        if not cited:
            continue

        if result.verdict == "supported":
            supports = any(
                item.side == "for"
                and (not has_organ_rule or item.criterion_id != "infection")
                for item in cited
            )
        elif result.verdict == "not_supported":
            supports = any(item.side == "against" for item in cited)
        else:
            supports = True
        if not supports:
            issues.append(
                FaithfulnessIssue(
                    "determination_support",
                    "Cited evidence does not support the stated determination",
                )
            )
    return issues


def _validate_guidelines(
    result: AuditResult,
    guidelines_dir: Path,
) -> list[FaithfulnessIssue]:
    coding = _section(result.letter_markdown, "Coding rationale")
    if not coding:
        return [FaithfulnessIssue("missing_coding_rationale", "Letter has no coding rationale")]
    citations = [
        (match.group("source"), match.group("section").strip())
        for match in _GUIDELINE_CITATION_RE.finditer(coding)
    ]
    if not citations:
        return [FaithfulnessIssue("missing_guideline_citation", "Coding rationale has no guideline citation")]
    valid_sections = _guideline_sections(guidelines_dir)
    return [
        FaithfulnessIssue(
            "invalid_guideline_citation",
            f"Unknown guideline source/section: {source}, {section}",
        )
        for source, section in citations
        if (source, section) not in valid_sections
    ]


def evaluate_citation_faithfulness(
    result: AuditResult,
    case: Case,
    criteria: CriteriaFile,
    *,
    guidelines_dir: Path = GUIDELINES_DIR,
) -> FaithfulnessReport:
    """Strictly validate that every audit citation is grounded and supports its claim.

    A case scores 1 only when every check passes. Any grounding, semantic-side,
    determination-support, evidence-table, or guideline-citation issue scores 0.
    """
    issues: list[FaithfulnessIssue] = []
    if not result.evidence:
        issues.append(FaithfulnessIssue("missing_evidence", "Audit has no evidence items"))

    criterion_by_id = _criterion_map(criteria)
    evidence_by_id: dict[str, EvidenceItem] = {}
    for item in result.evidence:
        if not re.fullmatch(r"E\d+", item.evidence_id):
            issues.append(
                FaithfulnessIssue(
                    "invalid_evidence_id",
                    f"Invalid evidence ID {item.evidence_id!r}",
                    item.evidence_id,
                )
            )
        if item.evidence_id in evidence_by_id:
            issues.append(
                FaithfulnessIssue(
                    "duplicate_evidence_id",
                    f"Duplicate evidence ID {item.evidence_id}",
                    item.evidence_id,
                )
            )
        evidence_by_id[item.evidence_id] = item

        grounded, span_error = _grounded_text(item, case)
        if span_error:
            issues.append(
                FaithfulnessIssue(
                    span_error,
                    f"Evidence span is not valid for case {case.case_id}",
                    item.evidence_id,
                )
            )
        elif grounded != item.text:
            issues.append(
                FaithfulnessIssue(
                    "text_mismatch",
                    "Evidence text does not exactly match the cited chart span",
                    item.evidence_id,
                )
            )

        node = criterion_by_id.get(item.criterion_id)
        if node is None:
            issues.append(
                FaithfulnessIssue(
                    "unknown_criterion",
                    f"Unknown criterion {item.criterion_id}",
                    item.evidence_id,
                )
            )
            continue
        expected_side = _expected_side(item, node)
        if expected_side is None:
            issues.append(
                FaithfulnessIssue(
                    "unverifiable_side",
                    "Evidence excerpt has no criterion-specific support signal",
                    item.evidence_id,
                )
            )
        elif expected_side != item.side:
            issues.append(
                FaithfulnessIssue(
                    "side_mismatch",
                    f"Evidence is labeled {item.side}, but the excerpt supports {expected_side}",
                    item.evidence_id,
                )
            )

    table_ids = set(_EVIDENCE_ROW_RE.findall(_section(result.letter_markdown, "Evidence")))
    item_ids = set(evidence_by_id)
    for evidence_id in sorted(item_ids - table_ids):
        issues.append(
            FaithfulnessIssue(
                "missing_evidence_row",
                f"Evidence table omits {evidence_id}",
                evidence_id,
            )
        )
    for evidence_id in sorted(table_ids - item_ids):
        issues.append(
            FaithfulnessIssue(
                "unknown_evidence_row",
                f"Evidence table contains unknown ID {evidence_id}",
                evidence_id,
            )
        )

    issues.extend(_validate_determination(result, evidence_by_id, criteria))
    issues.extend(_validate_guidelines(result, guidelines_dir))
    return FaithfulnessReport(score=0.0 if issues else 1.0, issues=issues)
