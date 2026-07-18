"""Deterministic clinical criteria rules engine (no LLM calls)."""

from backend.rules.engine import (
    CriterionEval,
    RulesResult,
    evaluate_case,
    evaluate_structured,
    evaluate_verdict_rule,
)
from backend.rules.loader import load_criteria

__all__ = [
    "CriterionEval",
    "RulesResult",
    "evaluate_case",
    "evaluate_structured",
    "evaluate_verdict_rule",
    "load_criteria",
]
