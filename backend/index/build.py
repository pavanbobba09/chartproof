"""Build Chroma collections for cases and guidelines.

Usage:
  python -m backend.index.build --data data --out .chroma
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from backend.config import CHROMA_DIR, DATA_DIR
from backend.index.chunking import (
    chunk_case_documents,
    chunk_guideline_markdown,
    load_guideline_files,
)
from backend.schemas import Case

# Free local embedding model (HF / sentence-transformers via Chroma)
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def get_embedding_function():
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL
    )


def get_client(persist_dir: str | Path | None = None) -> chromadb.PersistentClient:
    path = str(persist_dir or CHROMA_DIR)
    Path(path).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=path)


def _collection_name_for_case(case_id: str) -> str:
    # Chroma collection names: alnum + underscore
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in case_id)
    return f"case_{safe}"


def build_case_collection(
    client: chromadb.PersistentClient,
    case: Case,
    *,
    embed_fn=None,
) -> int:
    """Idempotent rebuild of one case collection. Returns chunk count."""
    name = _collection_name_for_case(case.case_id)
    try:
        client.delete_collection(name)
    except Exception:  # noqa: BLE001 - collection may not exist
        pass
    col = client.create_collection(
        name=name,
        embedding_function=embed_fn or get_embedding_function(),
        metadata={"case_id": case.case_id},
    )
    chunks = chunk_case_documents(case)
    if not chunks:
        return 0
    col.add(
        ids=[c.chunk_id for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[
            {
                "case_id": c.case_id,
                "doc_id": c.doc_id,
                "doc_type": c.doc_type,
                "date": c.date,
                "line_start": c.line_start,
                "line_end": c.line_end,
            }
            for c in chunks
        ],
    )
    return len(chunks)


def build_guidelines_collection(
    client: chromadb.PersistentClient,
    guidelines_dir: Path,
    *,
    embed_fn=None,
) -> int:
    name = "guidelines"
    try:
        client.delete_collection(name)
    except Exception:  # noqa: BLE001
        pass
    col = client.create_collection(
        name=name,
        embedding_function=embed_fn or get_embedding_function(),
        metadata={"kind": "guidelines"},
    )
    all_chunks = []
    for source_id, text in load_guideline_files(guidelines_dir):
        all_chunks.extend(chunk_guideline_markdown(source_id, text))
    if not all_chunks:
        return 0
    col.add(
        ids=[c.chunk_id for c in all_chunks],
        documents=[c.text for c in all_chunks],
        metadatas=[
            {"source_id": c.source_id, "section": c.section} for c in all_chunks
        ],
    )
    return len(all_chunks)


def load_cases(cases_dir: Path) -> list[Case]:
    cases: list[Case] = []
    for path in sorted(cases_dir.glob("*.json")):
        cases.append(Case.model_validate_json(path.read_text(encoding="utf-8")))
    return cases


def build_index(
    data_dir: Path | str | None = None,
    out_dir: Path | str | None = None,
) -> dict[str, int]:
    """Build all collections. Returns stats dict."""
    data = Path(data_dir) if data_dir else DATA_DIR
    out = Path(out_dir) if out_dir else Path(CHROMA_DIR)
    client = get_client(out)
    embed_fn = get_embedding_function()

    cases = load_cases(data / "cases")
    case_chunks = 0
    for case in cases:
        n = build_case_collection(client, case, embed_fn=embed_fn)
        case_chunks += n
        print(f"  indexed {case.case_id}: {n} chunks")

    g_n = build_guidelines_collection(
        client, data / "guidelines", embed_fn=embed_fn
    )
    print(f"  indexed guidelines: {g_n} chunks")

    stats = {
        "cases": len(cases),
        "case_chunks": case_chunks,
        "guideline_chunks": g_n,
        "chroma_dir": str(out.resolve()),
    }
    meta_path = out / "build_meta.json"
    meta_path.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build ChartProof Chroma index")
    parser.add_argument("--data", default=str(DATA_DIR), help="data directory")
    parser.add_argument("--out", default=str(CHROMA_DIR), help="chroma persist dir")
    args = parser.parse_args(argv)
    print(f"building index data={args.data} out={args.out}")
    stats = build_index(args.data, args.out)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
