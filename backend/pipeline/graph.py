"""LangGraph partial pipeline: intake → evidence → rules.

Phase 2 ends before composer/QA. Full audit API comes in Phase 3.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from backend.config import CASES_DIR, CHROMA_DIR, CRITERIA_DIR
from backend.index.build import get_client
from backend.pipeline.evidence import run_evidence_agents
from backend.pipeline.traces import new_trace_id, save_trace
from backend.rules.engine import RulesResult, evaluate_case
from backend.rules.loader import load_criteria
from backend.schemas import Case, CriteriaFile


class PipelineState(TypedDict, total=False):
    case_id: str
    case: dict[str, Any]
    criteria: dict[str, Any]
    narrative_answers: dict[str, str]
    evidence_findings: list[dict[str, Any]]
    rules_result: dict[str, Any]
    rules_verdict: str | None
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
    # cast to TriState-compatible strings
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
                }
                for c in result.criteria
            ],
        },
    }


def build_partial_graph():
    g = StateGraph(PipelineState)
    g.add_node("intake", node_intake)
    g.add_node("evidence", node_evidence)
    g.add_node("rules", node_rules)
    g.set_entry_point("intake")
    g.add_edge("intake", "evidence")
    g.add_edge("evidence", "rules")
    g.add_edge("rules", END)
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
