"""Pure-Python rules engine for structured criteria and verdict_rule expressions.

No LLM calls. Narrative criteria are resolved from caller-supplied answers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from backend.schemas import Case, CriteriaFile, CriteriaKind, CriteriaNode, LabValue, VitalValue

TriState = Literal["met", "not_met", "unclear"]
VerdictTri = Literal["supported", "not_supported", "unknown"]

_TOKEN_RE = re.compile(r"\s+|(AND|OR|NOT|\(|\))|([A-Za-z_][A-Za-z0-9_]*)")


@dataclass
class CriterionEval:
    criterion_id: str
    result: TriState
    method: str
    detail: str = ""
    metric: str | None = None
    op: str | None = None
    threshold: float | None = None
    window_hours: int | None = None


@dataclass
class RulesResult:
    verdict: VerdictTri
    criteria: list[CriterionEval] = field(default_factory=list)
    breakdown: dict[str, TriState] = field(default_factory=dict)


def _parse_datetime(value: str) -> datetime:
    # Accept ISO-ish datetimes with or without seconds / timezone Z
    cleaned = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    raise ValueError(f"unparseable datetime: {value}")


def _values_for_metric(
    case: Case, metric: str
) -> list[tuple[datetime, float]]:
    """Return (datetime, value) pairs for lab.X or vital.X."""
    if metric.startswith("lab."):
        name = metric.removeprefix("lab.")
        items: list[LabValue | VitalValue] = [
            lab for lab in case.labs if lab.name == name
        ]
    elif metric.startswith("vital."):
        name = metric.removeprefix("vital.")
        items = [v for v in case.vitals if v.name == name]
    else:
        raise ValueError(f"metric must start with lab. or vital.: {metric}")
    out: list[tuple[datetime, float]] = []
    for item in items:
        out.append((_parse_datetime(item.datetime), item.value))
    out.sort(key=lambda x: x[0])
    return out


def evaluate_structured(node: CriteriaNode, case: Case) -> TriState:
    """Evaluate a structured criterion node against labs/vitals."""
    if node.kind != CriteriaKind.STRUCTURED:
        raise ValueError(f"expected structured node, got {node.kind}")
    if not node.metric or not node.op or node.threshold is None:
        raise ValueError(f"structured node {node.id} missing metric/op/threshold")

    series = _values_for_metric(case, node.metric)
    if not series:
        return "unclear"

    op = node.op
    thr = node.threshold

    if op == "rise_gte":
        window = node.window_hours if node.window_hours is not None else 48
        if len(series) < 2:
            return "unclear"
        # Largest forward rise among chronologically ordered pairs in the window.
        best_rise = 0.0
        found_pair = False
        for i, (t_i, v_i) in enumerate(series):
            for t_j, v_j in series[i + 1 :]:
                hours = (t_j - t_i).total_seconds() / 3600.0
                if hours <= window:
                    found_pair = True
                    best_rise = max(best_rise, v_j - v_i)
        if not found_pair:
            return "unclear"
        return "met" if best_rise >= thr else "not_met"

    # Point criteria are met when any recorded observation crosses the threshold.
    # A later improvement must not erase earlier organ-dysfunction evidence.
    values = [value for _, value in series]
    if op == "gt":
        return "met" if any(value > thr for value in values) else "not_met"
    if op == "gte":
        return "met" if any(value >= thr for value in values) else "not_met"
    if op == "lt":
        return "met" if any(value < thr for value in values) else "not_met"
    if op == "lte":
        return "met" if any(value <= thr for value in values) else "not_met"
    raise ValueError(f"unsupported op: {op}")


def _combine_any_of(states: list[TriState]) -> TriState:
    if any(s == "met" for s in states):
        return "met"
    if all(s == "not_met" for s in states):
        return "not_met"
    return "unclear"


def _combine_all_of(states: list[TriState]) -> TriState:
    if any(s == "not_met" for s in states):
        return "not_met"
    if all(s == "met" for s in states):
        return "met"
    return "unclear"


def evaluate_node(
    node: CriteriaNode,
    case: Case,
    narrative_answers: dict[str, TriState],
    out: list[CriterionEval],
) -> TriState:
    """Recursively evaluate a criteria node; append leaf/composite evals to out."""
    if node.kind == CriteriaKind.STRUCTURED:
        result = evaluate_structured(node, case)
        out.append(
            CriterionEval(
                criterion_id=node.id,
                result=result,
                method="structured",
                detail=f"{node.metric} {node.op} {node.threshold}",
                metric=node.metric,
                op=node.op,
                threshold=node.threshold,
                window_hours=node.window_hours,
            )
        )
        return result

    if node.kind == CriteriaKind.NARRATIVE:
        result = narrative_answers.get(node.id, "unclear")
        out.append(
            CriterionEval(
                criterion_id=node.id,
                result=result,
                method="narrative",
                detail="from evidence agent" if node.id in narrative_answers else "missing answer",
            )
        )
        return result

    if node.kind in (CriteriaKind.ANY_OF, CriteriaKind.ALL_OF):
        child_states = [
            evaluate_node(child, case, narrative_answers, out) for child in node.children
        ]
        if node.kind == CriteriaKind.ANY_OF:
            result = _combine_any_of(child_states)
            method = "any_of"
        else:
            result = _combine_all_of(child_states)
            method = "all_of"
        out.append(
            CriterionEval(criterion_id=node.id, result=result, method=method)
        )
        return result

    raise ValueError(f"unknown criteria kind: {node.kind}")


def evaluate_verdict_rule(rule: str, values: dict[str, TriState]) -> VerdictTri:
    """Evaluate a boolean expression over criterion ids with 3-valued logic.

    Semantics:
    - met -> True, not_met -> False, unclear -> Unknown
    - AND / OR / NOT with Kleene 3-valued logic
    - True -> supported, False -> not_supported, Unknown -> unknown
    """
    tokens: list[str] = []
    pos = 0
    while pos < len(rule):
        m = _TOKEN_RE.match(rule, pos)
        if not m:
            raise ValueError(f"invalid token in verdict_rule at {pos}: {rule!r}")
        pos = m.end()
        if m.group(0).isspace():
            continue
        if m.group(1):
            tokens.append(m.group(1))
        else:
            tokens.append(m.group(2))

    # Recursive descent parser
    i = 0

    def peek() -> str | None:
        return tokens[i] if i < len(tokens) else None

    def consume(expected: str | None = None) -> str:
        nonlocal i
        if i >= len(tokens):
            raise ValueError("unexpected end of verdict_rule")
        tok = tokens[i]
        if expected is not None and tok != expected:
            raise ValueError(f"expected {expected}, got {tok}")
        i += 1
        return tok

    def parse_primary() -> TriState | bool:
        tok = peek()
        if tok == "(":
            consume("(")
            val = parse_or()
            consume(")")
            return val
        if tok == "NOT":
            consume("NOT")
            inner = parse_primary()
            return _not3(inner)
        if tok is None:
            raise ValueError("unexpected end of verdict_rule")
        # identifier
        name = consume()
        if name not in values:
            raise ValueError(f"unknown criterion id in verdict_rule: {name}")
        return values[name]

    def parse_and() -> TriState | bool:
        left = parse_primary()
        while peek() == "AND":
            consume("AND")
            right = parse_primary()
            left = _and3(left, right)
        return left

    def parse_or() -> TriState | bool:
        left = parse_and()
        while peek() == "OR":
            consume("OR")
            right = parse_and()
            left = _or3(left, right)
        return left

    result = parse_or()
    if i != len(tokens):
        raise ValueError(f"trailing tokens in verdict_rule: {tokens[i:]}")
    return _to_verdict(result)


def _as_tri(x: TriState | bool) -> TriState:
    if isinstance(x, bool):
        return "met" if x else "not_met"
    return x


def _and3(a: TriState | bool, b: TriState | bool) -> TriState:
    a3, b3 = _as_tri(a), _as_tri(b)
    if a3 == "not_met" or b3 == "not_met":
        return "not_met"
    if a3 == "met" and b3 == "met":
        return "met"
    return "unclear"


def _or3(a: TriState | bool, b: TriState | bool) -> TriState:
    a3, b3 = _as_tri(a), _as_tri(b)
    if a3 == "met" or b3 == "met":
        return "met"
    if a3 == "not_met" and b3 == "not_met":
        return "not_met"
    return "unclear"


def _not3(a: TriState | bool) -> TriState:
    a3 = _as_tri(a)
    if a3 == "met":
        return "not_met"
    if a3 == "not_met":
        return "met"
    return "unclear"


def _to_verdict(x: TriState | bool) -> VerdictTri:
    t = _as_tri(x)
    if t == "met":
        return "supported"
    if t == "not_met":
        return "not_supported"
    return "unknown"


def evaluate_case(
    case: Case,
    criteria: CriteriaFile,
    narrative_answers: dict[str, TriState] | None = None,
) -> RulesResult:
    """Evaluate full criteria tree and verdict_rule for a case."""
    answers = narrative_answers or {}
    evals: list[CriterionEval] = []
    top_level: dict[str, TriState] = {}

    for node in criteria.criteria:
        state = evaluate_node(node, case, answers, evals)
        top_level[node.id] = state

    # Also expose nested ids for rules that might reference them (not required for sepsis)
    for ev in evals:
        top_level.setdefault(ev.criterion_id, ev.result)

    verdict = evaluate_verdict_rule(criteria.verdict_rule, top_level)
    return RulesResult(verdict=verdict, criteria=evals, breakdown=top_level)
