# ChartProof

**Auditor-assist clinical chart validation (CCV)** on 100% synthetic data.

ChartProof is a portfolio demo of an AI copilot for inpatient clinical validation audits. It reads a synthetic chart, checks a billed diagnosis against published clinical criteria, gathers line-level evidence, drafts a determination and rationale letter, and routes uncertain cases to a human. A training mode quizzes trainee auditors against hidden answer keys.

> **Drafts for human review only.** Not clinical advice. Not for payment decisions. Synthetic data only. Never real PHI.

| | |
|---|---|
| **Status** | Phase 0 complete; Phase 1 in progress (rules engine green; case generator open) |
| **Stack** | FastAPI · Pydantic · deterministic rules · (later) LangGraph · ChromaDB · Groq · Next.js |
| **Hosting (planned)** | Hugging Face Spaces (API) + Vercel (UI) |

---

## Why this exists

Hospitals bill insurers with ICD-10 codes that map to DRGs. Higher-severity diagnoses pay more. Payment-integrity auditors (nurses and coders) must verify that the billed diagnosis is clinically supported. Findings must cite chart evidence so they survive provider appeals.

ChartProof targets auditor pain: slow evidence gathering, inconsistency, long ramp-up, and manual QA sampling. Framing everywhere is **auditor-assist**: the tool drafts, a human decides.

**v1 target diagnosis:** sepsis only (malnutrition / AKI are stretch goals).

---

## Architecture (target)

```
Chart generator (Groq)          Reference corpus (public PDFs)
        |                                  |
        v                                  v
   Chart bank  ------------------>  ChromaDB index
 (JSON cases + hidden answer keys)         |
                                           v
                              LangGraph pipeline (FastAPI)
                    evidence agents -> composer
                    rules engine    -> QA gate
                                           |
                     +---------------------+---------------------+
                     v                     v                     v
              evidence table       rationale letter        review flag
                                           v
                     Next.js frontend: audit mode + training mode
```

**What works today**

- FastAPI health API
- Pydantic schemas (cases, answer keys, spans, audit/training contracts)
- Sepsis criteria YAML + deterministic rules engine (no LLM)
- Case/key consistency checker
- Unit tests + ruff + GitHub Actions CI (lint + pytest)

**Not yet**

- Groq case generator and 30-case bank
- Retrieval, LangGraph pipeline, composer, QA gate
- Next.js UI, full eval harness, live deploy

---

## Quickstart

### Prerequisites

- Python **3.11+**
- (Optional) [uv](https://github.com/astral-sh/uv) for fast envs
- `GROQ_API_KEY` only when you run LLM generation, compose, or evals (not needed for rules/tests)

### Setup

```bash
git clone <your-repo-url> ChartProof
cd ChartProof

python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt -r backend/requirements-dev.txt

cp .env.example .env               # add GROQ_API_KEY only when needed
```

With uv:

```bash
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install -r backend/requirements.txt -r backend/requirements-dev.txt
```

### Run the API

```bash
uvicorn backend.app:app --reload --port 8000
# open http://localhost:8000/health
# docs at http://localhost:8000/docs
```

### Quality gate (engineering loop)

```bash
ruff check backend data
pytest backend/tests -q
```

CI runs the same lint + test job on every push/PR (see `.github/workflows/ci.yml`).

---

## Project layout

```
backend/
  app.py              # FastAPI entry (GET /health)
  schemas.py          # DATA_SPEC pydantic models
  rules/              # Deterministic criteria engine (no LLM)
  pipeline/           # LangGraph nodes (planned)
  index/              # Chroma build (planned)
  tests/
data/
  criteria/sepsis.yaml
  consistency.py      # Case/key consistency checks
  cases/ keys/ guidelines/ raw/   # Generated assets (planned)
evals/                # Smoke/full eval harness (planned)
frontend/             # Next.js UI (planned)
project_memory/       # Specs, tasks, phase completion logs
```

---

## Hard rules

1. **Synthetic data only** — no real patient data, no EHR/MIMIC.
2. **Auditor-assist framing** — drafts and `needs_review`; humans decide.
3. **Citation or drop** — uncited composer claims are stripped in code (planned pipeline).
4. **Rules stay deterministic** — no LLM inside `backend/rules/`.
5. **Secrets via env only** — never commit `.env` or API keys.
6. **Answer keys stay server-side** — only training grade endpoint may reveal key content after submit.

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [project_memory/PROJECT.md](project_memory/PROJECT.md) | Product vision and architecture |
| [project_memory/DATA_SPEC.md](project_memory/DATA_SPEC.md) | Schemas and API contracts |
| [project_memory/TASKS.md](project_memory/TASKS.md) | Phased checklist |
| [project_memory/LOOP_PLAN.md](project_memory/LOOP_PLAN.md) | Build → measure → fix loop |
| [project_memory/PHASE_LOGS.md](project_memory/PHASE_LOGS.md) | Phase writeups + when Groq is needed |
| [project_memory/PHASE_0_COMPLETE.md](project_memory/PHASE_0_COMPLETE.md) | Phase 0 log |
| [project_memory/PHASE_1_PROGRESS.md](project_memory/PHASE_1_PROGRESS.md) | Phase 1 progress |
| [project_memory/DEPLOYMENT.md](project_memory/DEPLOYMENT.md) | CI, HF Spaces, Vercel |
| [project_memory/CLAUDE.md](project_memory/CLAUDE.md) | Implementer operating rules |

After each phase gate, add `project_memory/PHASE_<N>_COMPLETE.md` and update `PHASE_LOGS.md`.

---

## Environment variables

Copy `.env.example` to `.env`. Never commit real secrets.

| Variable | Used for |
|----------|----------|
| `GROQ_API_KEY` | Generation, compose, LLM-judge evals (later) |
| `GROQ_MODEL` | Default `llama-3.3-70b-versatile` |
| `CHROMA_DIR` | Vector index path (default `.chroma`) |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend → API base URL |
| `HF_TOKEN` | CI deploy to Hugging Face Space (later) |

---

## Roadmap (summary)

| Phase | Focus | Gate |
|-------|--------|------|
| 0 | Scaffold | `ruff` + `pytest` — **done** |
| 1 | Criteria, rules, synthetic cases | Generator + rules tests |
| 2 | Retrieval + evidence agents | One case E2E with real spans |
| 3 | Composer + QA gate | Zero invalid citations |
| 4 | UI + evals | Smoke eval thresholds |
| 5 | Deploy + demo | Live link works from a phone |

---

## Disclaimer

Educational portfolio project. Criteria files are simplified demo encodings with source notes and are **not for clinical use**. All charts are synthetic. Outputs are machine-drafted aids; a qualified auditor makes any real determination.

## License

All rights reserved unless a LICENSE file is added later. Intended as a portfolio demonstration.
