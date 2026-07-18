# Phase 2 complete: retrieval + evidence agents

**Date:** 2026-07-18  
**Status:** Complete (local gate green)  
**Loop focus:** chunk → index → retrieve spans → evidence agents → rules → persist trace  
**Groq key required for this phase:** No (keyword + embedding retrieval; offline golden path)  
**Groq key required for Phase 3:** Yes (composer + LLM verdict)

---

## Goal

Index synthetic charts and guidelines in ChromaDB, retrieve line-level evidence spans, resolve narrative criteria, feed the deterministic rules engine, and persist a full trace under `runs/`.

## Gate

```bash
ruff check backend data
pytest backend/tests -q
python -m backend.index.build --data data --out .chroma
python -c "from backend.pipeline import run_partial_pipeline; print(run_partial_pipeline('sepsis_001')['rules_verdict'])"
```

**Result:** Pass. 39 tests green including Phase 2 integration/golden tests.

## Work completed

### Index (`backend/index/`)

| Item | Path |
|------|------|
| Chunking (4-line window, overlap 1; guideline ## sections) | `backend/index/chunking.py` |
| Build CLI | `backend/index/build.py` |
| Retrieval with verbatim spans | `backend/index/retrieve.py` |

Collections:

- `case_{case_id}` per chart
- `guidelines` for corpus
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2` via Chroma

Full bank build stats (local): 10 cases × 15 chunks = 150 chart chunks + 18 guideline chunks.

### Evidence agents (`backend/pipeline/evidence.py`)

- Collects all `narrative` nodes from the criteria tree
- Retrieves FOR/AGAINST chunks; falls back to full-chart keyword scan
- Keyword bags for `infection`, `vasopressors`, `altered_mentation` (demo-quality, no LLM)
- Returns `met` / `not_met` / `unclear` plus side items with `{doc_id, line_start, line_end, text}`

### LangGraph partial pipeline (`backend/pipeline/graph.py`)

Nodes: **intake → evidence → rules → END**

- Loads case + criteria
- Runs evidence agents against Chroma
- Calls deterministic rules engine with narrative answers
- Writes `runs/run_<case_id>_<timestamp>.json` (`runs/` gitignored)

### Dependencies

Added to `backend/requirements.txt`: `chromadb`, `sentence-transformers`, `langgraph`, `langchain-core`.

### Tests

| File | Coverage |
|------|----------|
| `test_chunking.py` | Window/overlap, guideline sections |
| `test_pipeline_phase2.py` | Index counts, retrieve spans, golden infection evidence, end-to-end graph + trace line numbers |

## Acceptance checklist (TASKS.md)

- [x] `backend/index/build.py` idempotent rebuild
- [x] Retrieval wrapper with metadata + verbatim span text
- [x] Evidence agent for narrative criteria (FOR/AGAINST + yes/no/unclear)
- [x] LangGraph intake → evidence → rules; traces under `runs/`
- [x] Golden test: infection-related planted/related span found on hand-checked case

## Decisions and tradeoffs

- **No LLM in Phase 2 evidence path** keeps the loop free of rate limits and makes CI/golden tests deterministic. Phase 3 composer will introduce Groq.
- Embedding model download is one-time on first build; Docker will bake it in Phase 5.
- Keyword bags are intentionally simple for synthetic sepsis charts; expand if recall fails on later cases.
- Partial pipeline only (no composer/QA/API audit yet) per phase order.

## How to re-verify

```bash
source .venv/bin/activate
uv pip install -r backend/requirements.txt -r backend/requirements-dev.txt
ruff check backend data
pytest backend/tests -q
python -m backend.index.build --data data --out .chroma
```

## Next phase opener (Phase 3)

Composer with citation enforcement, QA gate (rules vs LLM), `POST/GET /audit/{case_id}`, precomputed results.
