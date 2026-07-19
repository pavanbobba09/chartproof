---
title: ChartProof API
emoji: "🩺"
colorFrom: purple
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# ChartProof

**Auditor-assist clinical chart validation (CCV)** on 100% synthetic data.

ChartProof is a portfolio demo of an AI copilot for inpatient clinical validation audits. It reads a synthetic chart, checks a billed diagnosis against published clinical criteria, gathers line-level evidence, drafts a determination and rationale letter, and routes uncertain cases to a human. A training mode quizzes trainee auditors against hidden answer keys.

> **Drafts for human review only.** Not clinical advice. Not for payment decisions. Synthetic data only. Never real PHI.

| | |
|---|---|
| **Status** | Phase 5 engineering complete (Docker + CI deploy + demo hardening); set HF/Vercel secrets for live URLs |
| **Stack** | FastAPI · LangGraph · ChromaDB · deterministic rules · Groq (generation) · Next.js |
| **Hosting** | Hugging Face Spaces (Docker API) + Vercel Hobby (UI) |
| **Repo** | https://github.com/pavanbobba09/chartproof |
| **API (planned)** | `https://trippy09-chartproof.hf.space` |
| **UI (planned)** | Vercel project root `frontend/` |

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

Suite: **full** (10 sepsis cases, precomputed pipeline). Smoke suite (5 fixed cases) is enforced in CI.

| Metric | Full bank | Smoke (CI) | Threshold |
|--------|----------:|-----------:|----------:|
| Determination accuracy | 1.000 | 1.000 | >= 0.80 |
| Evidence recall | 0.818 | 1.000 | >= 0.70 |
| Citation faithfulness | 1.000 | 1.000 | >= 0.95 |
| Deferral rate (`needs_review`) | 0.000 | 0.000 | tracked |

Smoke and full suites **pass** thresholds. Citation faithfulness is a strict grounded check covering exact chart spans, criterion-specific evidence sides, determination support, evidence-table IDs, and guideline source/section pairs. See `evals/out/results.md`.

```bash
python -m evals.run --suite smoke --enforce-thresholds
python -m evals.run --suite full
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

- Synthetic sepsis case bank (10) + answer keys + guidelines corpus
- Deterministic rules engine (no LLM in `backend/rules/`)
- Chroma retrieval + narrative evidence agents
- Citation-enforced rationale letter + QA `needs_review`
- Precomputed audits for instant demo
- Eval harness (smoke/full) with CI smoke job
- Next.js audit mode (chart, evidence click-to-highlight, letter, fresh run)
- Next.js training mode (verdict + line select + graded feedback)

Inventory: [project_memory/FEATURES.md](project_memory/FEATURES.md)

---

## Deploy (Phase 5)

### Backend image (Hugging Face Spaces)

```bash
docker build -t chartproof-api .
# Space sync is automated on green main when GitHub secret HF_TOKEN is set.
```

One-time:

1. Create Docker Space `trippy09/chartproof` on Hugging Face.
2. Add GitHub Actions secret `HF_TOKEN` (write access to that Space).
3. Set Space variable `ALLOWED_ORIGINS` to your Vercel URL(s) and `http://localhost:3000`.

### Frontend (Vercel)

1. Import this repo; **Root Directory** = `frontend`.
2. Env: `NEXT_PUBLIC_API_BASE_URL=https://trippy09-chartproof.hf.space`.

See [scripts/demo_day_checklist.md](scripts/demo_day_checklist.md) and [project_memory/DEPLOYMENT.md](project_memory/DEPLOYMENT.md).

## Known limitations

- No auth or multi-tenancy (public demo)
- Sepsis only; criteria are simplified educational encodings
- Faithfulness validation is deterministic and tailored to the encoded demo criteria; external clinical adjudication remains out of scope
- Case notes include some pad lines for schema length compliance
- Live public URLs require HF_TOKEN + Vercel project (not bound in CI without secrets)

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
| [project_memory/DEPLOYMENT.md](project_memory/DEPLOYMENT.md) | CI / HF / Vercel |
| [evals/out/results.md](evals/out/results.md) | Latest eval report |

Demo video: *(add link after recording)*  
Live API: `https://trippy09-chartproof.hf.space` *(after Space is created and CI deploy runs)*  
Live UI: *(Vercel URL after import)*

---

## Disclaimer

Educational portfolio project. Criteria files are simplified demo encodings with source notes and are **not for clinical use**. All charts are synthetic. Outputs are machine-drafted aids; a qualified auditor makes any real determination.

## License

All rights reserved unless a LICENSE file is added later. Intended as a portfolio demonstration.
