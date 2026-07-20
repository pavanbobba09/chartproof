# ChartProof

**Auditor-assist clinical chart validation (CCV)** on 100% synthetic data.

ChartProof is a portfolio demo of an AI copilot for inpatient clinical validation audits. It reads a synthetic chart, checks a billed diagnosis against published clinical criteria, gathers line-level evidence, drafts a determination and rationale letter, and routes uncertain cases to a human. A training mode quizzes trainee auditors against hidden answer keys.

> **Drafts for human review only.** Not clinical advice. Not for payment decisions. Synthetic data only. Never real PHI.

| | |
|---|---|
| **Status** | Live portfolio deployment; full pipeline covered by CI and local Docker |
| **Stack** | FastAPI · LangGraph · ChromaDB · deterministic rules · Groq (generation) · Next.js |
| **Hosting** | Vercel Hobby (Next.js UI + lightweight FastAPI portfolio API) |
| **Repo** | https://github.com/pavanbobba09/chartproof |
| **Live API** | https://chartproof-api.vercel.app |
| **Live UI** | https://chartproof.vercel.app |

---

## Why this exists

Hospitals bill insurers with ICD-10 codes that map to DRGs. Higher-severity diagnoses pay more. Payment-integrity auditors (nurses and coders) must verify that the billed diagnosis is clinically supported. Findings must cite chart evidence so they survive provider appeals.

ChartProof targets auditor pain: slow evidence gathering, inconsistency, long ramp-up, and manual QA sampling. Framing everywhere is **auditor-assist**: the tool drafts, a human decides.

**v1 target diagnosis:** sepsis only (malnutrition / AKI are stretch goals).

---

## Architecture

```
Chart generator (Groq)          Reference corpus (guidelines)
        |                                  |
        v                                  v
   Chart bank  ------------------>  ChromaDB index
 (JSON cases + hidden answer keys)         |
                                           v
                              LangGraph pipeline (FastAPI)
                    evidence -> rules -> compose -> QA gate
                                           |
                     +---------------------+---------------------+
                     v                     v                     v
              evidence table       rationale letter        review flag
                                           v
                     Next.js: audit mode + training mode
```

---

## Eval results (latest full bank)

Suite: **full** (100 synthetic sepsis records, precomputed pipeline). The bank contains 15 independently generated scenarios and 85 deterministic volume-test variants for UI, API, and load testing. Smoke suite (5 fixed cases) is enforced in CI. A per-case evidence-recall floor (0.50) prevents aggregates from hiding local misses.

| Metric | Full bank | Smoke (CI) | Threshold |
|--------|----------:|-----------:|----------:|
| Determination accuracy | 1.000 | 1.000 | >= 0.80 |
| Evidence recall | 0.946 | 1.000 | >= 0.70 (>= 0.50 per case) |
| Citation faithfulness | 1.000 | 1.000 | >= 0.95 |
| Deferral rate (`needs_review`) | 0.060 | 0.000 | tracked |

The nonzero deferral rate is by design: `sepsis_011` is ambiguous on purpose (clear infection, incomplete organ-dysfunction workup) and the volume bank includes variants derived from it. The correct pipeline behavior, scored as correct by the evals, is routing these records to a human with explicit review reasons.

Smoke and full suites **pass** thresholds. Citation faithfulness is a strict grounded check covering exact chart spans, criterion-specific evidence sides, determination support, evidence-table IDs, and guideline source/section pairs. See `evals/out/results.md`.

```bash
python -m evals.run --suite smoke --enforce-thresholds
python -m evals.run --suite full
cd frontend && npm run test:e2e  # requires the local API/UI and Chrome
```

---

## Quickstart

### Backend

```bash
git clone https://github.com/pavanbobba09/chartproof.git ChartProof
cd ChartProof
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
cp .env.example .env   # GROQ is only needed for synthetic case generation

# Optional: rebuild index if you will run live audits
python -m backend.index.build --data data --out .chroma

uvicorn backend.app:app --reload --port 8000
```

### Frontend

```bash
cd frontend
cp .env.example .env.local   # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm install
npm run dev                  # http://localhost:3000
```

### Quality loop

```bash
ruff check backend data evals
pytest backend/tests -q
python -m evals.run --suite smoke --enforce-thresholds
```

### API highlights

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness |
| GET | `/cases` | Case list (no answer keys) |
| GET | `/cases/{id}` | Full synthetic chart |
| GET/POST | `/audit/{id}` | Audit result (`?fresh=true` live) |
| POST | `/training/{id}/grade` | Grade trainee (reveals key after submit) |

---

## Features (shipped)

- Synthetic sepsis case bank (100) + answer keys + guidelines corpus. Fifteen scenarios are independently generated and 85 are deterministic volume-test variants. The bank includes ambiguous-by-design records that correctly defer to a human.
- Deterministic rules engine (no LLM in `backend/rules/`)
- Chroma retrieval + narrative evidence agents (shared lexicon with the faithfulness oracle)
- Citation-enforced rationale letter + QA `needs_review` with reviewer-readable force reasons
- Optional LLM composer (`CHARTPROOF_LLM_COMPOSE=1` + `GROQ_API_KEY`): independent Groq draft verdict and prose, filtered through the same citation gate, deterministic fallback on any failure
- Precomputed audits for instant demo
- Eval harness (smoke/full) with CI smoke job, per-case recall floor, and deferral-correctness scoring
- Next.js audit mode (chart, criteria checklist, evidence click-to-highlight, review reasons, letter, fresh run)
- Next.js training mode (verdict + line select + graded feedback)

Inventory: [project_memory/FEATURES.md](project_memory/FEATURES.md)

---

## Deploy

The $0 portfolio deployment uses two Vercel Hobby projects:

- `chartproof`: Next.js project rooted at `frontend/`.
- `chartproof-api`: repository-root FastAPI project using `app.py`.

The public API deliberately serves committed, CI-verified audit drafts and
server-side training grading. It does not claim to run the model/retrieval path.
The full pipeline remains available locally through `backend.app` and the Docker
image, and is exercised by CI's live deterministic smoke evaluation.

```bash
# API (repository root)
vercel deploy --prod

# UI (frontend/), configured with:
# NEXT_PUBLIC_API_BASE_URL=https://chartproof-api.vercel.app
cd frontend && vercel deploy --prod
```

See [scripts/demo_day_checklist.md](scripts/demo_day_checklist.md) and [project_memory/DEPLOYMENT.md](project_memory/DEPLOYMENT.md).

## Known limitations

- No auth or multi-tenancy (public demo)
- Sepsis only; criteria are simplified educational encodings
- Faithfulness validation is deterministic and tailored to the encoded demo criteria; external clinical adjudication remains out of scope
- Case notes include some pad lines for schema length compliance
- The free public API serves immutable precomputed drafts; run the local backend for fresh retrieval/model execution
- Vercel Hobby is appropriate only for this personal, non-commercial portfolio demo

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [project_memory/PROJECT.md](project_memory/PROJECT.md) | Product vision |
| [project_memory/DATA_SPEC.md](project_memory/DATA_SPEC.md) | Schemas and contracts |
| [project_memory/TASKS.md](project_memory/TASKS.md) | Phased checklist |
| [project_memory/LOOP_PLAN.md](project_memory/LOOP_PLAN.md) | Engineering loop |
| [project_memory/FEATURES.md](project_memory/FEATURES.md) | Feature inventory |
| [project_memory/E2E_REQUIREMENTS_REVIEW.md](project_memory/E2E_REQUIREMENTS_REVIEW.md) | Requirements audit |
| [project_memory/PHASE_LOGS.md](project_memory/PHASE_LOGS.md) | Phase completion index |
| [project_memory/DEPLOYMENT.md](project_memory/DEPLOYMENT.md) | CI / Vercel deployment profiles |
| [evals/out/results.md](evals/out/results.md) | Latest eval report |

Demo video: *(add link after recording)*  
Live API: https://chartproof-api.vercel.app<br>
Live UI: https://chartproof.vercel.app

---

## Disclaimer

Educational portfolio project. Criteria files are simplified demo encodings with source notes and are **not for clinical use**. All charts are synthetic. Outputs are machine-drafted aids; a qualified auditor makes any real determination.

## License

All rights reserved unless a LICENSE file is added later. Intended as a portfolio demonstration.
