"""Unit tests for chart/guideline chunking (no Chroma required)."""

from __future__ import annotations

from backend.index.chunking import chunk_case_documents, chunk_document, chunk_guideline_markdown
from backend.schemas import Case, Document


def test_chart_chunk_window_and_overlap() -> None:
    doc = Document(
        doc_id="hp",
        doc_type="history_and_physical",
        date="2026-01-03",
        lines=[f"line {i}" for i in range(1, 11)],
    )
    chunks = chunk_document("sepsis_001", doc)
    assert chunks
    # first window lines 1-4
    assert chunks[0].line_start == 1
    assert chunks[0].line_end == 4
    assert chunks[0].text.startswith("[history_and_physical 2026-01-03] ")
    # overlap 1 => next starts at line 4
    assert chunks[1].line_start == 4
    assert "case_id" not in chunks[0].text


def test_chunk_case_metadata() -> None:
    case = Case.model_validate(
        {
            "case_id": "sepsis_001",
            "target_dx": "sepsis",
            "billed": {"icd10": ["A41.9"], "drg": "871"},
            "patient": {"age": 60, "sex": "M"},
            "documents": [
                {
                    "doc_id": "hp",
                    "doc_type": "history_and_physical",
                    "date": "2026-01-01",
                    "lines": [f"L{i}" for i in range(15)],
                }
            ],
        }
    )
    chunks = chunk_case_documents(case)
    assert all(c.case_id == "sepsis_001" for c in chunks)
    assert all(c.doc_id == "hp" for c in chunks)


def test_guideline_section_split() -> None:
    md = """# Title

## Section: Infection

Infection means documented source or antibiotics.

## Section: Organ dysfunction

Organ dysfunction needs SOFA-like change.
"""
    chunks = chunk_guideline_markdown("sepsis3_summary", md)
    sections = {c.section for c in chunks}
    assert "Section: Infection" in sections or any("Infection" in s for s in sections)
    assert any("antibiotics" in c.text for c in chunks)
