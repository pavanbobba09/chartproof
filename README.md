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
| **Status** | Phase 4 complete (evals + training API + Next.js UI); Phase 5 deploy next |
| **Stack** | FastAPI · LangGraph · ChromaDB · deterministic rules · Groq (generation) · Next.js |
| **Hosting (planned)** | Hugging Face Spaces (API) + Vercel (UI) |
| **Repo** | https://github.com/pavanbobba09/chartproof |

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
| Determination accuracy | 0.700 | 1.000 | >= 0.80 |
| Evidence recall | 0.872 | 1.000 | >= 0.70 |
| Citation faithfulness | 1.000 | 1.000 | >= 0.95 |
| Deferral rate (`needs_review`) | 0.300 | 0.000 | tracked |

Smoke suite **passes** thresholds. Full-bank accuracy is below 0.80 because three cases correctly defer to human review (`needs_review` counts as wrong for accuracy). Citation faithfulness is perfect on the deterministic check. See `evals/out/results.md`.

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
cp .env.example .env   # GROQ only needed for generation / live LLM paths

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

## Known limitations

- No auth or multi-tenancy (public demo)
- Sepsis only; criteria are simplified educational encodings
- Full-bank determination accuracy still below smoke threshold due to deliberate deferrals
- Case notes include some pad lines for schema length compliance
- Live deploy (HF Space + Vercel) is Phase 5

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

Demo video: *(placeholder for Phase 5)*  
Live demo: *(placeholder for Phase 5)*

---

## Disclaimer

Educational portfolio project. Criteria files are simplified demo encodings with source notes and are **not for clinical use**. All charts are synthetic. Outputs are machine-drafted aids; a qualified auditor makes any real determination.

## License

All rights reserved unless a LICENSE file is added later. Intended as a portfolio demonstration.
