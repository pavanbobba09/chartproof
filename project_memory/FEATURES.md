# ChartProof: features built so far

Living inventory of shipped product and engineering capabilities. Update this file at the end of each phase.

**Last updated:** 2026-07-18 (through Phase 5 engineering)  
**Repo:** https://github.com/pavanbobba09/chartproof

---

## Product framing (always)

| Feature | Description |
|---------|-------------|
| Auditor-assist only | Outputs are drafts for human review, never payment decisions or automated denials |
| Synthetic data only | All charts generated; no PHI, EHR, or MIMIC |
| Sepsis v1 scope | Clinical validation demo for billed sepsis (A41.9 / DRG 871 style) |
| Human in the loop | `needs_review` when uncertain; training mode planned for trainees |

---

## Phase 0: scaffold

| Feature | How to use / where |
|---------|---------------------|
| FastAPI health API | `GET /health` → `{status, service, version}` |
| CORS | `ALLOWED_ORIGINS` env (default localhost:3000) |
| Pydantic schemas | Cases, keys, spans, audit/training contracts in `backend/schemas.py` |
| Span intersection | Citation currency for recall scoring (`EvidenceSpan.intersects`) |
| Dev quality loop | `ruff check` + `pytest`; CI on push/PR |
| Env template | `.env.example` (never commit real keys) |
| Project memory | Specs, tasks, phase logs, loop plan under `project_memory/` |

---

## Phase 1: criteria + synthetic data

| Feature | How to use / where |
|---------|---------------------|
| Sepsis criteria YAML | `data/criteria/sepsis.yaml` (Sepsis-3 simplified, not for clinical use) |
| Deterministic rules engine | Structured ops `gt/lt/gte/lte/rise_gte`; narrative answers injected later |
| Verdict rule evaluator | 3-valued logic (`supported` / `not_supported` / `unknown`) |
| Case/key consistency checker | Span ranges, min planted evidence, lab/vital mentions, doc length 15–60 |
| Groq case generator | `python -m data.generate --dx sepsis --n 10` (needs `GROQ_API_KEY`) |
| Raw generation cache | `data/raw/` (gitignored) for rate-limit friendly reruns |
| Synthetic case bank | 10 cases: `data/cases/sepsis_001` … `sepsis_010` |
| Hidden answer keys | `data/keys/*.key.json` (server-side; not exposed by public list APIs) |
| Guidelines corpus | Educational markdown + `data/guidelines/manifest.json` |

**Bank mix:** 5 supported / 5 not_supported; 8 clear / 2 borderline.

---

## Phase 2: retrieval + evidence + partial pipeline

| Feature | How to use / where |
|---------|---------------------|
| Chart chunking | 4-line window, 1-line overlap; prefix `[doc_type date]` |
| Guideline chunking | Split on `##` sections, max ~1200 chars |
| Chroma index build | `python -m backend.index.build --data data --out .chroma` |
| Local embeddings | `sentence-transformers/all-MiniLM-L6-v2` (free, local) |
| Case retrieval | Per-case collections `case_{case_id}` with line-level spans |
| Guideline retrieval | Collection `guidelines` with `source_id` + `section` |
| Evidence agents | Narrative criteria → FOR/AGAINST spans + met/not_met/unclear |
| LangGraph partial graph | `intake → evidence → rules` |
| Trace persistence | `runs/run_<case_id>_<timestamp>.json` (gitignored) |
| Partial pipeline API (Python) | `from backend.pipeline import run_partial_pipeline` |

**Example:**

```bash
python -m backend.index.build --data data --out .chroma
python -c "from backend.pipeline import run_partial_pipeline; print(run_partial_pipeline('sepsis_001')['rules_verdict'])"
```

---

## Engineering loop features

| Practice | Detail |
|----------|--------|
| Phase gates | Each phase ends with ruff + pytest (later smoke eval) |
| Phase writeups | `PHASE_<N>_COMPLETE.md` + `PHASE_LOGS.md` index |
| Pre-Phase-2 audit | `PHASE_0_1_AUDIT.md` requirements check |
| Loop plan | `LOOP_PLAN.md` (build → measure → fix) |
| Groq when needed | Documented matrix in `PHASE_LOGS.md` |

---

## Phase 3: composer + QA + audit API

| Feature | How to use / where |
|---------|---------------------|
| Evidence catalog (E1, E2, ...) | Built from agent spans + structured criteria hits |
| Citation-enforced composer | Drops uncited claims in Determination (`backend/pipeline/compose.py`) |
| Rationale letter draft | DATA_SPEC sections + synthetic-data reviewer disclaimer |
| QA gate | Disagreement / low confidence / drops → `needs_review` |
| Full LangGraph pipeline | `intake → evidence → rules → compose → qa_gate` |
| `GET /cases` | Case list without answer keys |
| `GET /audit/{case_id}` | Precomputed or runtime cache |
| `POST /audit/{case_id}` | Cache then live; `?fresh=true` forces live |
| Precomputed results | `data/precomputed/*.json` via `python -m data.precompute` |
| Runtime cache | `runs/cache/` (gitignored) |

**Example:**

```bash
uvicorn backend.app:app --reload --port 8000
curl http://localhost:8000/cases
curl http://localhost:8000/audit/sepsis_001
curl -X POST 'http://localhost:8000/audit/sepsis_002?fresh=true'
```

---

## Phase 4: evals + UI + training

| Feature | How to use / where |
|---------|---------------------|
| Eval harness smoke/full | `python -m evals.run --suite smoke --enforce-thresholds` |
| Metrics | accuracy, evidence recall, citation faithfulness, deferral rate |
| CI smoke-eval job | `.github/workflows/ci.yml` |
| `GET /cases/{id}` | Full chart JSON, no keys |
| `POST /training/{id}/grade` | Trainee grading against hidden key |
| Next.js case list | `frontend/` → `/` |
| Audit UI | `/audit/[caseId]` evidence jump + letter + fresh run |
| Training UI | `/training/[caseId]` verdict + line select + feedback |

```bash
cd frontend && npm install && npm run dev
# backend: uvicorn backend.app:app --port 8000
```

---

## Phase 5: deploy + demo hardening

| Feature | How to use / where |
|---------|---------------------|
| Docker API image | root `Dockerfile` (port 7860, baked index + embeddings) |
| CI deploy to HF Space | `.github/workflows/ci.yml` `deploy` job (`HF_TOKEN` secret) |
| Graceful live audit errors | HTTP 503 + clear message on rate limit / missing index |
| Frontend fresh-run fallback copy | `frontend/app/audit/[caseId]/page.tsx` |
| Demo checklist | `scripts/demo_day_checklist.md` |
| Vercel helper | `frontend/vercel.json` |

**Go-live (manual once):** create HF Space `trippy09/chartproof`, set GitHub `HF_TOKEN`, import Vercel with `NEXT_PUBLIC_API_BASE_URL`.

---

## Not built yet / stretch

| Item | Notes |
|------|--------|
| Live HF + Vercel URLs | Needs account secrets |
| Demo video | Record after go-live |
| 30-case bank | Optional expansion |
| Malnutrition/AKI, appeals | Stretch product |

---

## Quick feature map (commands)

```bash
# Health
uvicorn backend.app:app --reload --port 8000

# Quality
ruff check backend data && pytest backend/tests -q

# Generate more synthetic cases (needs Groq)
python -m data.generate --dx sepsis --n 10

# Index for retrieval
python -m backend.index.build --data data --out .chroma

# Full audit pipeline (Python)
python -c "from backend.pipeline import run_full_pipeline; print(run_full_pipeline('sepsis_001')['audit_result']['verdict'])"

# Precompute demo results
python -m data.precompute

# API
uvicorn backend.app:app --reload --port 8000
```

---

## Related docs

| Doc | Purpose |
|-----|---------|
| [PROJECT.md](./PROJECT.md) | Product vision and architecture |
| [DATA_SPEC.md](./DATA_SPEC.md) | Schemas and API contracts |
| [TASKS.md](./TASKS.md) | Phased checklist |
| [LOOP_PLAN.md](./LOOP_PLAN.md) | Engineering loop |
| [PHASE_LOGS.md](./PHASE_LOGS.md) | Phase completion index |
