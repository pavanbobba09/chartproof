"""Guidelines corpus smoke tests (no network)."""

from __future__ import annotations

import json
from pathlib import Path

GUIDELINES = Path(__file__).resolve().parents[2] / "data" / "guidelines"


def test_manifest_and_files_exist() -> None:
    manifest_path = GUIDELINES / "manifest.json"
    assert manifest_path.is_file()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = data["sources"]
    assert len(sources) >= 2
    for src in sources:
        assert "source_id" in src
        path = GUIDELINES / src["file"]
        assert path.is_file(), f"missing {path}"
        text = path.read_text(encoding="utf-8")
        assert "Not for clinical use" in text or "not for clinical use" in text.lower()
        assert "source_id:" in text or src["source_id"] in text
