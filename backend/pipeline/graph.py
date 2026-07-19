"""LangGraph audit pipeline: intake → evidence → rules → compose → qa_gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from backend.config import CASES_DIR, CHROMA_DIR, CRITERIA_DIR
from backend.index.build import get_client
from backend.pipeline.compose import compose_from_state, compose_letter
from backend.pipeline.evidence import run_evidence_agents
from backend.pipeline.qa import qa_gate
from backend.pipeline.traces import new_trace_id, save_trace
from backend.rules.engine import RulesResult, evaluate_case
from backend.rules.loader import load_criteria
from backend.schemas import (
    AuditResult,
    Case,
    CriteriaFile,
    CriterionResult,
    EvidenceItem,
)


class PipelineState(TypedDict, total=False):
    case_id: str
    case: dict[str, Any]
    criteria: dict[str, Any]
    narrative_answers: dict[str, str]
    evidence_findings: list[dict[str, Any]]
    rules_result: dict[str, Any]
    rules_verdict: str | None
    compose_result: dict[str, Any]
    qa_result: dict[str, Any]
    audit_result: dict[str, Any]
    trace_id: str
    error: str | None
    chroma_dir: str


def _load_case(case_id: str, cases_dir: Path | None = None) -> Case:
    base = cases_dir or CASES_DIR
    path = base / f"{case_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"case not found: {path}")
    return Case.model_validate_json(path.read_text(encoding="utf-8"))


def node_intake(state: PipelineState) -> PipelineState:
    case_id = state["case_id"]
    case = _load_case(case_id)
    criteria = load_criteria(case.target_dx, CRITERIA_DIR)
    return {
        **state,
        "case": case.model_dump(mode="json"),
        "criteria": criteria.model_dump(mode="json"),
        "trace_id": state.get("trace_id") or new_trace_id(case_id),
        "error": None,
    }


def node_evidence(state: PipelineState) -> PipelineState:
    case = Case.model_validate(state["case"])
    criteria = CriteriaFile.model_validate(state["criteria"])
    chroma = state.get("chroma_dir") or CHROMA_DIR
    client = get_client(chroma)
    answers, findings = run_evidence_agents(
        case, criteria.criteria, client=client
    )
    return {
        **state,
        "narrative_answers": dict(answers),
        "evidence_findings": [
            {
                "criterion_id": f.criterion_id,
                "result": f.result,
                "side_items": f.side_items,
            }
            for f in findings
        ],
    }


def node_rules(state: PipelineState) -> PipelineState:
    case = Case.model_validate(state["case"])
    criteria = CriteriaFile.model_validate(state["criteria"])
    answers = state.get("narrative_answers") or {}
    result: RulesResult = evaluate_case(
        case,
        criteria,
        narrative_answers=answers,  # type: ignore[arg-type]
    )
    return {
        **state,
        "rules_verdict": result.verdict,
        "rules_result": {
            "verdict": result.verdict,
            "breakdown": result.breakdown,
            "criteria": [
                {
                    "criterion_id": c.criterion_id,
                    "result": c.result,
                    "method": c.method,
                    "detail": c.detail,
                    "metric": c.metric,
                    "op": c.op,
                    "threshold": c.threshold,
                    "window_hours": c.window_hours,
                }
                for c in result.criteria
            ],
        },
    }


def node_compose(state: PipelineState) -> PipelineState:
    case = Case.model_validate(state["case"])
    criteria = CriteriaFile.model_validate(state["criteria"])
    chroma = state.get("chroma_dir")
    composed = compose_from_state(
        case,
        criteria,
        state.get("evidence_findings") or [],
        state.get("rules_result") or {},
        use_guidelines=True,
        chroma_dir=chroma,
    )
    return {**state, "compose_result": composed}


def node_qa(state: PipelineState) -> PipelineState:
    rules = state.get("rules_result") or {}
    composed = state.get("compose_result") or {}
    unclear = sum(
        1
        for c in rules.get("criteria") or []
        if c.get("result") == "unclear"
    )
    evidence = composed.get("evidence") or []
    qa = qa_gate(
        rules_verdict=rules.get("verdict"),
        draft_verdict=composed.get("draft_verdict"),
        dropped_sentences=int(composed.get("dropped_sentences") or 0),
        unclear_criteria=unclear,
        evidence_count=len(evidence),
    )

    # Map criteria_results with evidence_ids
    evidence_items = [EvidenceItem.model_validate(e) for e in evidence]
    by_crit: dict[str, list[str]] = {}
    for e in evidence_items:
        by_crit.setdefault(e.criterion_id, []).append(e.evidence_id)

    criteria_results: list[CriterionResult] = []
    for c in rules.get("criteria") or []:
        cid = c["criterion_id"]
        criteria_results.append(
            CriterionResult(
                criterion_id=cid,
                result=c["result"],
                method=c.get("method") or "unknown",
                evidence_ids=by_crit.get(cid, []),
            )
        )

    # Keep the letter determination aligned with the final QA outcome.
    letter = composed.get("letter_markdown") or ""
    if qa["status"] == "needs_review" and qa["verdict"] is None:
        case = Case.model_validate(state["case"])
        criteria = CriteriaFile.model_validate(state["criteria"])
        raw_guideline_bits = composed.get("guideline_bits") or []
        guideline_bits = [tuple(bit) for bit in raw_guideline_bits]
        letter, _ = compose_letter(
            case=case,
            criteria=criteria,
            status="needs_review",
            verdict=None,
            evidence=evidence_items,
            rules_verdict=rules.get("verdict"),
            guideline_bits=guideline_bits or None,
        )
    elif qa["status"] == "needs_review" and "Status: completed" in letter:
        letter = letter.replace("Status: completed", "Status: needs_review", 1)

    rules_v = rules.get("verdict")
    draft_v = composed.get("draft_verdict")
    audit = AuditResult(
        case_id=state["case_id"],
        status=qa["status"],
        verdict=qa["verdict"],
        confidence=qa["confidence"],
        rules_verdict=rules_v if rules_v in ("supported", "not_supported") else None,
        draft_verdict=draft_v if draft_v in ("supported", "not_supported") else None,
        criteria_results=criteria_results,
        evidence=evidence_items,
        letter_markdown=letter,
        dropped_sentences=int(composed.get("dropped_sentences") or 0),
        force_reasons=list(qa.get("force_reasons") or []),
        source="live",
        trace_id=state.get("trace_id"),
    )
    return {
        **state,
        "qa_result": qa,
        "audit_result": audit.model_dump(mode="json"),
        "compose_result": {**composed, "letter_markdown": letter},
    }


def build_partial_graph():
    """Phase 2 graph (through rules)."""
    g = StateGraph(PipelineState)
    g.add_node("intake", node_intake)
    g.add_node("evidence", node_evidence)
    g.add_node("rules", node_rules)
    g.set_entry_point("intake")
    g.add_edge("intake", "evidence")
    g.add_edge("evidence", "rules")
    g.add_edge("rules", END)
    return g.compile()


def build_full_graph():
    """Phase 3 full audit graph."""
    g = StateGraph(PipelineState)
    g.add_node("intake", node_intake)
    g.add_node("evidence", node_evidence)
    g.add_node("rules", node_rules)
    g.add_node("compose", node_compose)
    g.add_node("qa_gate", node_qa)
    g.set_entry_point("intake")
    g.add_edge("intake", "evidence")
    g.add_edge("evidence", "rules")
    g.add_edge("rules", "compose")
    g.add_edge("compose", "qa_gate")
    g.add_edge("qa_gate", END)
    return g.compile()


def run_partial_pipeline(
    case_id: str,
    *,
    persist_trace: bool = True,
    chroma_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run intake → evidence → rules and optionally write runs/<trace>.json."""
    graph = build_partial_graph()
    init: PipelineState = {"case_id": case_id}
    if chroma_dir is not None:
        init["chroma_dir"] = str(chroma_dir)
    final: PipelineState = graph.invoke(init)
    payload = {
        "trace_id": final.get("trace_id"),
        "case_id": case_id,
        "pipeline": "intake->evidence->rules",
        "narrative_answers": final.get("narrative_answers"),
        "evidence_findings": final.get("evidence_findings"),
        "rules_result": final.get("rules_result"),
        "rules_verdict": final.get("rules_verdict"),
    }
    if persist_trace:
        path = save_trace(final["trace_id"], payload)
        payload["trace_path"] = str(path)
    return payload


def run_full_pipeline(
    case_id: str,
    *,
    persist_trace: bool = True,
    chroma_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run full audit pipeline through QA gate."""
    graph = build_full_graph()
    init: PipelineState = {"case_id": case_id}
    if chroma_dir is not None:
        init["chroma_dir"] = str(chroma_dir)
    final: PipelineState = graph.invoke(init)
    payload = {
        "trace_id": final.get("trace_id"),
        "case_id": case_id,
        "pipeline": "intake->evidence->rules->compose->qa_gate",
        "narrative_answers": final.get("narrative_answers"),
        "evidence_findings": final.get("evidence_findings"),
        "rules_result": final.get("rules_result"),
        "compose_result": final.get("compose_result"),
        "qa_result": final.get("qa_result"),
        "audit_result": final.get("audit_result"),
    }
    if persist_trace:
        path = save_trace(final["trace_id"], payload)
        payload["trace_path"] = str(path)
    return payload
