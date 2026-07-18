"""Load and validate criteria YAML files."""

from __future__ import annotations

from pathlib import Path

import yaml

from backend.schemas import CriteriaFile

DEFAULT_CRITERIA_DIR = Path(__file__).resolve().parents[2] / "data" / "criteria"


def load_criteria(dx: str, criteria_dir: Path | str | None = None) -> CriteriaFile:
    """Load `data/criteria/<dx>.yaml` and validate against CriteriaFile schema."""
    base = Path(criteria_dir) if criteria_dir is not None else DEFAULT_CRITERIA_DIR
    path = base / f"{dx}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"criteria file not found: {path}")
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"criteria file must be a mapping: {path}")
    return CriteriaFile.model_validate(raw)
