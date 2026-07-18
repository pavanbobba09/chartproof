"""Retrieval wrappers returning spans with verbatim text."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb

from backend.config import CHROMA_DIR
from backend.index.build import (
    _collection_name_for_case,
    get_client,
    get_embedding_function,
)
from backend.schemas import Case, EvidenceSpan


@dataclass
class RetrievedChunk:
    text: str
    span: EvidenceSpan | None
    metadata: dict[str, Any]
    distance: float | None = None
    # for guidelines
    source_id: str | None = None
    section: str | None = None

    @property
    def verbatim(self) -> str:
        """Span text without the doc_type prefix when possible."""
        t = self.text
        if t.startswith("[") and "] " in t:
            return t.split("] ", 1)[1]
        return t


def _query_collection(
    col: Any,
    query: str,
    n_results: int,
) -> list[dict[str, Any]]:
    res = col.query(query_texts=[query], n_results=n_results)
    out: list[dict[str, Any]] = []
    if not res or not res.get("ids") or not res["ids"][0]:
        return out
    ids = res["ids"][0]
    docs = res["documents"][0]
    metas = res["metadatas"][0]
    dists = (res.get("distances") or [[None] * len(ids)])[0]
    for i, _id in enumerate(ids):
        out.append(
            {
                "id": _id,
                "document": docs[i],
                "metadata": metas[i] or {},
                "distance": dists[i],
            }
        )
    return out


def retrieve_case(
    case_id: str,
    query: str,
    *,
    n_results: int = 6,
    client: chromadb.PersistentClient | None = None,
    case: Case | None = None,
) -> list[RetrievedChunk]:
    """Retrieve chart chunks for a case; attach EvidenceSpan and verbatim text."""
    cli = client or get_client(CHROMA_DIR)
    name = _collection_name_for_case(case_id)
    try:
        col = cli.get_collection(
            name=name, embedding_function=get_embedding_function()
        )
    except Exception as e:  # noqa: BLE001
        raise FileNotFoundError(
            f"case collection {name!r} not found; run backend.index.build first"
        ) from e

    rows = _query_collection(col, query, n_results)
    doc_map = {d.doc_id: d for d in case.documents} if case else {}
    results: list[RetrievedChunk] = []
    for row in rows:
        meta = row["metadata"]
        span = EvidenceSpan(
            doc_id=str(meta["doc_id"]),
            line_start=int(meta["line_start"]),
            line_end=int(meta["line_end"]),
        )
        text = row["document"]
        # Prefer exact lines from case if available
        if case and span.doc_id in doc_map:
            doc = doc_map[span.doc_id]
            verbatim = " ".join(doc.lines[span.line_start - 1 : span.line_end])
        else:
            verbatim = text
            if verbatim.startswith("[") and "] " in verbatim:
                verbatim = verbatim.split("] ", 1)[1]
        results.append(
            RetrievedChunk(
                text=verbatim,
                span=span,
                metadata=meta,
                distance=row["distance"],
            )
        )
    return results


def retrieve_guidelines(
    query: str,
    *,
    n_results: int = 4,
    client: chromadb.PersistentClient | None = None,
    persist_dir: str | Path | None = None,
) -> list[RetrievedChunk]:
    cli = client or get_client(persist_dir or CHROMA_DIR)
    try:
        col = cli.get_collection(
            name="guidelines", embedding_function=get_embedding_function()
        )
    except Exception as e:  # noqa: BLE001
        raise FileNotFoundError(
            "guidelines collection not found; run backend.index.build first"
        ) from e
    rows = _query_collection(col, query, n_results)
    out: list[RetrievedChunk] = []
    for row in rows:
        meta = row["metadata"]
        out.append(
            RetrievedChunk(
                text=row["document"],
                span=None,
                metadata=meta,
                distance=row["distance"],
                source_id=str(meta.get("source_id", "")),
                section=str(meta.get("section", "")),
            )
        )
    return out
