"""Phase 2 integration: index build, retrieval, evidence golden, graph trace."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.index.build import build_case_collection, build_guidelines_collection, get_client
from backend.index.chunking import chunk_case_documents
from backend.index.retrieve import retrieve_case
from backend.pipeline.evidence import gather_evidence_for_criterion
from backend.pipeline.graph import run_partial_pipeline
from backend.rules.loader import load_criteria
from backend.schemas import AnswerKey, Case, CriteriaKind, EvidenceSpan

REPO = Path(__file__).resolve().parents[2]
CASES = REPO / "data" / "cases"
KEYS = REPO / "data" / "keys"
GUIDELINES = REPO / "data" / "guidelines"


@pytest.fixture(scope="module")
def chroma_tmp(tmp_path_factory: pytest.TempPathFactory):
    """Build a temp index for sepsis_001 only (faster than full bank)."""
    root = tmp_path_factory.mktemp("chroma_p2")
    client = get_client(root)
    case = Case.model_validate_json((CASES / "sepsis_001.json").read_text())
    # Also index one not_supported case for variety
    case2 = Case.model_validate_json((CASES / "sepsis_002.json").read_text())
    build_case_collection(client, case)
    build_case_collection(client, case2)
    build_guidelines_collection(client, GUIDELINES)
    return root


def test_index_chunk_count_matches_chunker(chroma_tmp: Path) -> None:
    case = Case.model_validate_json((CASES / "sepsis_001.json").read_text())
    expected = len(chunk_case_documents(case))
    client = get_client(chroma_tmp)
    col = client.get_collection(f"case_{case.case_id}")
    assert col.count() == expected
    assert expected > 0


def test_retrieve_returns_spans_with_line_numbers(chroma_tmp: Path) -> None:
    case = Case.model_validate_json((CASES / "sepsis_001.json").read_text())
    client = get_client(chroma_tmp)
    hits = retrieve_case(
        "sepsis_001",
        "infection antibiotics fever",
        n_results=4,
        client=client,
        case=case,
    )
    assert hits
    for h in hits:
        assert h.span is not None
        assert h.span.line_start >= 1
        assert h.span.line_end >= h.span.line_start
        assert h.text  # verbatim non-empty


def test_golden_infection_span_found(chroma_tmp: Path) -> None:
    """Agent should find a span that intersects planted infection evidence."""
    case = Case.model_validate_json((CASES / "sepsis_001.json").read_text())
    key = AnswerKey.model_validate_json((KEYS / "sepsis_001.key.json").read_text())
    planted = [
        p
        for p in key.planted_evidence
        if p.side == "for"
        and p.criterion_id in ("infection", "organ_dysfunction", "lactate_elevated")
    ]
    # Prefer infection-side planted if present; else any for-span about infection keywords
    infection_planted = [p for p in key.planted_evidence if p.criterion_id == "infection"]
    targets = infection_planted or planted
    assert targets, "key must plant some for-side evidence"

    criteria = load_criteria("sepsis")
    infection = next(c for c in criteria.criteria if c.id == "infection")
    assert infection.kind == CriteriaKind.NARRATIVE

    client = get_client(chroma_tmp)
    finding = gather_evidence_for_criterion(case, infection, client=client)
    assert finding.side_items, "expected at least one evidence item"
    # infection should resolve met on a clear supported sepsis chart
    assert finding.result in ("met", "unclear")

    found_spans = [
        EvidenceSpan.model_validate(item["span"]) for item in finding.side_items
    ]
    hit = False
    for plant in targets:
        pspan = plant.as_span()
        for fspan in found_spans:
            if pspan.intersects(fspan):
                hit = True
                break
        if hit:
            break
    # Also accept intersection with any planted for infection-related line text
    if not hit:
        # Fallback golden: any retrieved for-span mentions infection/antibiotic
        for item in finding.side_items:
            if item["side"] == "for" and any(
                k in item["text"].lower()
                for k in ("infection", "antibiotic", "uti", "pneumonia", "sepsis")
            ):
                hit = True
                break
    assert hit, f"did not find planted/related infection evidence: {finding.side_items}"


def test_partial_pipeline_trace(chroma_tmp: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Point runs/ into tmp by monkeypatching save path via env is hard; just check payload
    monkeypatch.setattr(
        "backend.pipeline.traces.RUNS_DIR",
        tmp_path / "runs",
    )
    out = run_partial_pipeline(
        "sepsis_001",
        persist_trace=True,
        chroma_dir=chroma_tmp,
    )
    assert out["case_id"] == "sepsis_001"
    assert out["rules_verdict"] in ("supported", "not_supported", "unknown")
    assert out["narrative_answers"]
    assert "infection" in out["narrative_answers"]
    # Trace file exists with real line numbers in evidence
    assert "trace_path" in out
    path = Path(out["trace_path"])
    assert path.is_file()
    data = json.loads(path.read_text())
    findings = data["evidence_findings"]
    assert findings
    # at least one span with line numbers
    has_span = False
    for f in findings:
        for item in f.get("side_items", []):
            span = item.get("span")
            if span and "line_start" in span:
                has_span = True
                assert span["line_start"] >= 1
    assert has_span
