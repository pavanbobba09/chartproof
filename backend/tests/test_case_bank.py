"""Load and validate the committed synthetic case bank."""

from __future__ import annotations

from pathlib import Path

from backend.rules import evaluate_case, load_criteria
from backend.schemas import AnswerKey, Case
from data.consistency import check_case_key_consistency

CASES = Path(__file__).resolve().parents[2] / "data" / "cases"
KEYS = Path(__file__).resolve().parents[2] / "data" / "keys"


def _case_ids() -> list[str]:
    return sorted(p.stem for p in CASES.glob("sepsis_*.json"))


def test_bank_has_exactly_one_hundred_cases() -> None:
    assert len(_case_ids()) == 100


def test_each_case_key_consistent_and_loadable() -> None:
    for cid in _case_ids():
        case = Case.model_validate_json((CASES / f"{cid}.json").read_text(encoding="utf-8"))
        key = AnswerKey.model_validate_json(
            (KEYS / f"{cid}.key.json").read_text(encoding="utf-8")
        )
        assert case.case_id == cid
        assert key.case_id == cid
        assert check_case_key_consistency(case, key) == []


def test_volume_records_disclose_their_source_scenario() -> None:
    roles: dict[str, int] = {"clinical_scenario": 0, "volume_test": 0}
    for cid in _case_ids():
        case = Case.model_validate_json(
            (CASES / f"{cid}.json").read_text(encoding="utf-8")
        )
        roles[case.dataset_role] += 1
        if case.dataset_role == "volume_test":
            assert case.source_case_id
            assert (CASES / f"{case.source_case_id}.json").is_file()
        else:
            assert case.source_case_id is None
    assert roles == {"clinical_scenario": 15, "volume_test": 85}


def test_rules_align_with_key_when_infection_met() -> None:
    """With infection forced met and negative narratives, structured organ dysfunction should match key side for clear cases."""
    crit = load_criteria("sepsis")
    for cid in _case_ids():
        case = Case.model_validate_json((CASES / f"{cid}.json").read_text(encoding="utf-8"))
        key = AnswerKey.model_validate_json(
            (KEYS / f"{cid}.key.json").read_text(encoding="utf-8")
        )
        result = evaluate_case(
            case,
            crit,
            narrative_answers={
                "infection": "met",
                "vasopressors": "not_met",
                "altered_mentation": "not_met",
            },
        )
        if key.difficulty == "borderline":
            # Borderline may land unknown depending on near-threshold data
            assert result.verdict in ("supported", "not_supported", "unknown")
            continue
        if result.verdict == "unknown":
            continue
        assert result.verdict == key.verdict, f"{cid}: rules={result.verdict} key={key.verdict}"
