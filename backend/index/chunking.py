"""Chunking helpers per DATA_SPEC section 7."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from backend.schemas import Case, Document

# DATA_SPEC: sliding window of 4 lines, overlap 1
CHART_WINDOW = 4
CHART_OVERLAP = 1
GUIDELINE_MAX_CHARS = 1200


@dataclass(frozen=True)
class ChartChunk:
    chunk_id: str
    text: str
    case_id: str
    doc_id: str
    doc_type: str
    date: str
    line_start: int
    line_end: int


@dataclass(frozen=True)
class GuidelineChunk:
    chunk_id: str
    text: str
    source_id: str
    section: str


def chunk_document(case_id: str, doc: Document) -> list[ChartChunk]:
    """Sliding window over document lines with overlap."""
    lines = doc.lines
    if not lines:
        return []
    step = max(1, CHART_WINDOW - CHART_OVERLAP)
    chunks: list[ChartChunk] = []
    start = 0  # 0-based index into lines
    while start < len(lines):
        end = min(start + CHART_WINDOW, len(lines))  # exclusive
        window = lines[start:end]
        line_start = start + 1  # 1-based
        line_end = end  # 1-based inclusive
        body = " ".join(window)
        prefix = f"[{doc.doc_type} {doc.date}] "
        text = prefix + body
        chunk_id = f"{case_id}:{doc.doc_id}:{line_start}-{line_end}"
        chunks.append(
            ChartChunk(
                chunk_id=chunk_id,
                text=text,
                case_id=case_id,
                doc_id=doc.doc_id,
                doc_type=doc.doc_type,
                date=doc.date,
                line_start=line_start,
                line_end=line_end,
            )
        )
        if end >= len(lines):
            break
        start += step
    return chunks


def chunk_case_documents(case: Case) -> list[ChartChunk]:
    out: list[ChartChunk] = []
    for doc in case.documents:
        out.extend(chunk_document(case.case_id, doc))
    return out


_SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def chunk_guideline_markdown(source_id: str, text: str) -> list[GuidelineChunk]:
    """Split on markdown ## headers; cap chunks near GUIDELINE_MAX_CHARS."""
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return _split_long(
            source_id=source_id,
            section="body",
            body=text.strip(),
            base_idx=0,
        )

    chunks: list[GuidelineChunk] = []
    # Optional preamble before first ##
    preamble = text[: matches[0].start()].strip()
    if preamble:
        chunks.extend(_split_long(source_id, "preamble", preamble, 0))

    for i, m in enumerate(matches):
        section = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        chunks.extend(_split_long(source_id, section, body, i))
    return chunks


def _split_long(
    source_id: str, section: str, body: str, base_idx: int
) -> list[GuidelineChunk]:
    if len(body) <= GUIDELINE_MAX_CHARS:
        return [
            GuidelineChunk(
                chunk_id=f"{source_id}:{_slug(section)}:{base_idx}",
                text=f"[{source_id} | {section}] {body}",
                source_id=source_id,
                section=section,
            )
        ]
    out: list[GuidelineChunk] = []
    part = 0
    i = 0
    while i < len(body):
        piece = body[i : i + GUIDELINE_MAX_CHARS]
        out.append(
            GuidelineChunk(
                chunk_id=f"{source_id}:{_slug(section)}:{base_idx}:{part}",
                text=f"[{source_id} | {section}] {piece}",
                source_id=source_id,
                section=section,
            )
        )
        i += GUIDELINE_MAX_CHARS
        part += 1
    return out


def _slug(section: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", section.strip().lower()).strip("_")
    return s or "section"


def load_guideline_files(guidelines_dir: Path) -> list[tuple[str, str]]:
    """Return list of (source_id, markdown_text) from manifest.json."""
    import json

    manifest_path = guidelines_dir / "manifest.json"
    if not manifest_path.is_file():
        return []
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    out: list[tuple[str, str]] = []
    for src in data.get("sources", []):
        source_id = src["source_id"]
        path = guidelines_dir / src["file"]
        if path.is_file():
            out.append((source_id, path.read_text(encoding="utf-8")))
    return out
