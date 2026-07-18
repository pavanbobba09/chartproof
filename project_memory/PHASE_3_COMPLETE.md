# Phase 3 complete: composer + QA gate + audit API

**Date:** 2026-07-18  
**Status:** Complete (local gate green)  
**Loop focus:** evidence catalog → compose letter → citation filter → QA gate → cache → API  
**Groq key required for this phase:** No for default deterministic compose path  
**Groq key required for Phase 4 evals (LLM judge):** Yes  

---

## Goal

Produce citation-safe rationale letters, force `needs_review` when rules and draft verdict disagree or confidence is low, expose `POST/GET /audit/{case_id}` with precomputed/cache/live lookup, and ship precomputed results for the 10-case bank.

## Gate

```bash
ruff check backend data
pytest backend/tests -q
python -m backend.index.build --data data --out .chroma
python -m data.precompute
```

**Result:** Pass. 51 tests. 10/10 precomputed with `dropped_sentences == 0`. Multiple cases `needs_review`.

## Work completed

### Composer (`backend/pipeline/compose.py`)

- Builds numbered evidence catalog (E1, E2, ...) from narrative findings + structured hits
- Renders DATA_SPEC letter sections (Determination, Evidence table, Coding rationale, Reviewer note)
- **Citation enforcement in code:** drops claim sentences in `## Determination` that lack a valid evidence ID
- Deterministic draft path (offline-friendly); guideline snippets from Chroma when available

### QA gate (`backend/pipeline/qa.py`)

Forces `needs_review` when:

- rules verdict ≠ llm/draft verdict
- unknown / null verdict
- dropped uncited sentences > 0
- confidence below threshold (default 0.6)

### Full LangGraph pipeline

`intake → evidence → rules → compose → qa_gate`

- `run_full_pipeline(case_id)` and `run_partial_pipeline(case_id)` both available
- Traces under `runs/`

### Audit service + API

| Endpoint | Behavior |
|----------|----------|
| `GET /health` | ok |
| `GET /cases` | summaries only (no answer keys) |
| `GET /audit/{case_id}` | precomputed or runtime cache |
| `POST /audit/{case_id}` | cache order: precomputed → runtime → live; `?fresh=true` skips caches |

Cache paths: `data/precomputed/`, `runs/cache/`

### Precompute

```bash
python -m data.precompute
```

Writes `data/precomputed/sepsis_001.json` … `sepsis_010.json` (committed for instant demos).

### Tests

| File | Coverage |
|------|----------|
| `test_compose_qa.py` | citation filter, letter sections, QA triggers |
| `test_audit_api.py` | `/cases`, `/audit` cache, zero invalid citations |

## Acceptance checklist (TASKS.md)

- [x] Composer with evidence-ID constraint enforced in code
- [x] Rationale letter template + disclaimer
- [x] QA gate: rules vs draft, confidence, needs_review, unit tests
- [x] `POST /audit/{case_id}` and `GET /audit/{case_id}` with disk cache
- [x] Precomputed results for all bundled cases

## Known gaps / notes

- Draft verdict heuristic can disagree with answer keys on some not_supported charts (evidence/vaso narrative noise). QA correctly routes several to `needs_review`. Phase 4 evals will quantify accuracy.
- Default composer is deterministic (no Groq call) for free-tier reliability; structure is ready for optional LLM prose later.
- Answer keys never appear in audit API responses.

## How to re-verify

```bash
source .venv/bin/activate
ruff check backend data && pytest backend/tests -q
uvicorn backend.app:app --reload --port 8000
# curl http://localhost:8000/cases
# curl http://localhost:8000/audit/sepsis_001
# curl -X POST 'http://localhost:8000/audit/sepsis_001?fresh=true'
```

## Next phase opener (Phase 4)

Eval harness + smoke thresholds in CI; Next.js audit/training UI; expand case bank toward 30.
