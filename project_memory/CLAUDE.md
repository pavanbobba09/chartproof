# CLAUDE.md

Operating instructions for Claude Code in this repo. Read PROJECT.md for architecture and scope, DATA_SPEC.md for schemas, TASKS.md for the current phase, DEPLOYMENT.md for CI and hosting. Work in small verifiable steps and keep the eval suite green.

## What this project is

ChartProof: an auditor-assist tool for clinical chart validation, built on 100% synthetic data with a free stack (FastAPI + LangGraph + ChromaDB backend on Hugging Face Spaces, Next.js frontend on Vercel, Groq free tier for LLM calls). See PROJECT.md.

## Hard rules

1. Synthetic data only. Never add, fetch, or reference real patient data. If a task seems to need real data, stop and flag it.
2. Auditor-assist framing everywhere: outputs are drafts, statuses are for review, a human decides. Never word anything as an automated denial or payment decision.
3. Citation or it doesn't ship: every claim the composer outputs must carry a valid evidence span ID, enforced in code, not in the prompt alone. Uncited sentences get dropped and the drop is logged.
4. The rules engine stays deterministic. No LLM calls inside `backend/rules/`.
5. Clinical criteria live only in `data/criteria/*.yaml` with a `source_note`. Do not invent or silently edit clinical thresholds; if a criterion looks wrong, raise it and note the published source. Keep the "simplified demo, not for clinical use" disclaimer.
6. Secrets only via environment variables (`GROQ_API_KEY`, `HF_TOKEN`). Never hardcode or commit keys. `.env` is gitignored.
7. Answer keys are server-side only. No API response may include answer key contents except the grading endpoint's feedback after a submission.
8. Writing style for all docs, UI copy, and letters: plain English, no em dashes anywhere.
9. Keep costs at zero. Do not add paid services or paid API tiers.

## Workflow expectations

- Follow TASKS.md phase order. Check off items as they are completed and add newly discovered tasks under the right phase.
- After each phase gate (or major checkpoint), write `project_memory/PHASE_<N>_COMPLETE.md` or `PHASE_<N>_PROGRESS.md` and update `PHASE_LOGS.md`. Include files touched, gate results, and whether `GROQ_API_KEY` is required next.
- Definition of done for any pipeline change: `pytest` passes, `ruff check` clean, and `python -m evals.run --suite smoke` meets thresholds. If thresholds fail, fix that before adding features.
- Prefer small commits with imperative messages ("add sepsis criteria evaluator"). Do not force-push main.
- Cache LLM outputs where repeatable (generation under `data/raw/`, audit runs under `runs/`) to respect Groq free-tier rate limits. Batch generation with sleeps; on 429, back off and resume, don't fail the batch.
- When something is ambiguous, choose the option that is simpler to demo and note the tradeoff in the PR description or commit body.

## Commands

Backend (from repo root):
```
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
uvicorn backend.app:app --reload --port 8000
```

Data and index:
```
python -m data.generate --dx sepsis --n 10          # generate cases + answer keys
python -m backend.index.build --data data --out .chroma
```

Quality gates:
```
pytest backend/tests -q
ruff check backend
python -m evals.run --suite smoke
python -m evals.run --suite full                    # whole bank, writes evals/out/results.md
```

Frontend:
```
cd frontend && npm install && npm run dev           # expects NEXT_PUBLIC_API_BASE_URL
```

## Environment variables

- `GROQ_API_KEY` (required for generation, compose, LLM-judge evals)
- `GROQ_MODEL` (default `llama-3.3-70b-versatile`; verify it is still on Groq's free tier when starting Phase 1 and keep the default in one config module so a model swap is a one-line change)
- `CHROMA_DIR` (default `.chroma`)
- `ALLOWED_ORIGINS` (comma separated, see DEPLOYMENT.md)
- `NEXT_PUBLIC_API_BASE_URL` (frontend only)

## Repo layout

```
backend/    app.py, pipeline/, rules/, index/, tests/
frontend/   Next.js app
data/       generate.py, criteria/, guidelines/, cases/, keys/, raw/
evals/      run.py, thresholds.yaml, out/
runs/       persisted pipeline traces (gitignored)
.github/    workflows/ci.yml, workflows/full-eval.yml
Dockerfile  Hugging Face Space image
```

## Known gotchas

- Groq free tier rate limits: batch generation is the only heavy consumer; keep per-request sleeps configurable.
- HF Spaces runs the container as user 1000 and free storage resets on restart: build the Chroma index and pre-download the embedding model at image build time (see DEPLOYMENT.md and Dockerfile).
- Files over 10 MB pushed to the Space need Git LFS; avoid by never committing the index, it is built in Docker.
- Fork PRs do not receive repo secrets, so the smoke-eval CI job is skipped for them by design.
