# Phase 0 complete: scaffold

**Date:** 2026-07-18  
**Status:** Complete (local gate green)  
**Owner focus:** Loop engineering substrate  
**Groq key required for this phase:** No  
**Groq key required to start next LLM work (Phase 1 generate):** Yes (for `data/generate.py` only; rules already done offline)

---

## Goal

Establish the repo, schemas, health API, and CI so every later change can run a tight **build → test → fix** loop.

## Gate

```bash
ruff check backend
pytest backend/tests -q
```

**Result:** Pass (schemas + health tests; Phase 0 scope only).

## Work completed

### Project memory / process

- Documented architecture and tasks already present (`PROJECT.md`, `DATA_SPEC.md`, `TASKS.md`, `DEPLOYMENT.md`, `CLAUDE.md`)
- Added [LOOP_PLAN.md](./LOOP_PLAN.md): phase gates, metrics, product loop
- Added [PHASE_LOGS.md](./PHASE_LOGS.md): convention for post-phase writeups + Groq key matrix

### Repo substrate

| Item | Path |
|------|------|
| Git ignore | `.gitignore` |
| Env template | `.env.example` (`GROQ_API_KEY`, `GROQ_MODEL`, `CHROMA_DIR`, `ALLOWED_ORIGINS`, `NEXT_PUBLIC_API_BASE_URL`, `HF_TOKEN`) |
| Ruff / pytest config | `pyproject.toml` |
| Backend deps | `backend/requirements.txt` |
| Dev deps | `backend/requirements-dev.txt` |
| CI (test job only) | `.github/workflows/ci.yml` |
| Root README | `README.md` |

### Application code

| Item | Path | Notes |
|------|------|--------|
| Package root | `backend/__init__.py` | |
| Pydantic schemas | `backend/schemas.py` | Cases, keys, spans, audit/training API shapes, criteria tree per DATA_SPEC |
| FastAPI app | `backend/app.py` | `GET /health`, CORS from `ALLOWED_ORIGINS` |
| Placeholder packages | `backend/pipeline/`, `backend/rules/`, `backend/index/` | Layout for later phases |
| Data dirs | `data/criteria/`, `cases/`, `keys/`, `guidelines/`, `raw/` | |

### Tests (Phase 0)

| File | Coverage |
|------|----------|
| `backend/tests/test_schemas.py` | Span intersection, case/key validation |
| `backend/tests/test_health.py` | `/health` returns ok |

## Decisions and tradeoffs

- Python **3.11** via `uv` (system macOS Python was 3.9).
- Kept Phase 0 deps minimal (FastAPI, pydantic, pyyaml, dotenv). No LangGraph/Chroma/Groq until later phases.
- `CriteriaKind` uses `enum.StrEnum` (ruff UP042).
- Em dashes avoided in docs/UI copy per CLAUDE.md hard rules.

## Acceptance checklist (from TASKS.md)

- [x] Repo structure + `.gitignore`
- [x] requirements + requirements-dev
- [x] `schemas.py` + span intersection tests
- [x] `.env.example`
- [x] FastAPI `GET /health`
- [x] CI `test` job (lint + pytest)
- [x] Ruff in `pyproject.toml`

## Known gaps (intentionally deferred)

- No git remote / push verification of CI in this session
- No frontend yet
- No LLM, index, or pipeline
- Phase 0 does not need a live demo link

## How to re-verify

```bash
cd /path/to/ChartProof
source .venv/bin/activate   # or: uv venv .venv --python 3.11 && uv pip install -r backend/requirements.txt -r backend/requirements-dev.txt
ruff check backend
pytest backend/tests -q
uvicorn backend.app:app --reload --port 8000
# curl http://localhost:8000/health
```

## Next phase opener

**Phase 1:** sepsis criteria YAML, deterministic rules engine, synthetic generator, guidelines corpus.  
See [PHASE_1_PROGRESS.md](./PHASE_1_PROGRESS.md) for work already started in the same session after this gate.
