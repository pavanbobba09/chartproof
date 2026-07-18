# Phase 5 complete: deploy assets + demo hardening

**Date:** 2026-07-18  
**Status:** Code and CI complete; **live HF/Vercel URLs require one-time account secrets** (see below)  
**Loop focus:** containerize → CI gate → force-sync Space → demo hardening → document go-live  
**Groq key on Space:** optional for precomputed demos; required for live LLM paths if enabled later  

---

## Goal

Ship a deployable free-tier stack: Dockerized FastAPI for Hugging Face Spaces, CI deploy on green main, graceful live-audit failures, and a demo-day checklist. Frontend remains Vercel Hobby (import once).

## Gate

```bash
ruff check backend data evals
pytest backend/tests -q
python -m evals.run --suite smoke --enforce-thresholds
# Docker (when daemon available):
docker build -t chartproof-api .
```

**Result:** Lint + 62 tests green. Smoke eval green. Docker image recipe committed; local docker build needs Docker Desktop running.

## Work completed

### Container (`Dockerfile`)

- Python 3.11-slim, user 1000 (HF Spaces)
- Install deps, pre-download MiniLM embeddings
- Bake Chroma index at image build (`CHROMA_DIR=/home/user/app/chroma`)
- Uvicorn on port **7860**
- `.dockerignore` keeps image lean (no node_modules / .venv / local chroma)

### CI deploy (`.github/workflows/ci.yml`)

Jobs: `test` → `smoke-eval` → `deploy` (main push only).

Deploy force-pushes `main` to:

`https://huggingface.co/spaces/trippy09/chartproof`

If `HF_TOKEN` secret is missing, deploy **skips cleanly** (exit 0) with a log message so CI stays green until you add the secret.

### Demo hardening

- `POST /audit/{id}?fresh=true` maps rate limits to **503** with human-readable copy
- Missing Chroma index → **503** (precomputed GET still works)
- Frontend audit page shows a friendly message when fresh analysis fails
- `scripts/demo_day_checklist.md` for call prep

### Vercel helper

- `frontend/vercel.json` (Next.js region hint)
- `frontend/.env.example` already documents `NEXT_PUBLIC_API_BASE_URL`

## One-time go-live (you run once)

### A. Hugging Face Space

1. Create Space: owner `trippy09` (or your HF user), name `chartproof`, SDK **Docker**, public, CPU basic.
2. Create write token → GitHub secret **`HF_TOKEN`**.
3. Space **Variables**:  
   `ALLOWED_ORIGINS=https://YOUR-VERCEL-URL,http://localhost:3000`
4. Optional Space **Secret**: `GROQ_API_KEY` if you enable live LLM later.
5. Push to `main` (or re-run deploy job) so the Space syncs and builds.

API base (example): `https://trippy09-chartproof.hf.space`

### B. Vercel frontend

1. Import `pavanbobba09/chartproof`, root directory **`frontend/`**.
2. Env: `NEXT_PUBLIC_API_BASE_URL=https://trippy09-chartproof.hf.space`
3. Deploy. Add that origin to Space `ALLOWED_ORIGINS`.

### C. Demo video (optional)

Record ~2 minutes (case list → audit evidence jump → training grade). Link in README.

## Acceptance checklist (TASKS.md)

- [x] Dockerfile (model + index at build, user 1000, port 7860)
- [x] Deploy job on CI (skips if no HF_TOKEN)
- [ ] Create HF Space + secrets (account action)
- [ ] Vercel import + env (account action)
- [x] Demo-day hardening (rate limit / index / UI message)
- [x] Demo checklist doc
- [ ] 2 min video link
- [ ] Phone cellular E2E after live URLs exist

## Known gaps

- Live Space/Vercel not verified in this environment (no HF_TOKEN / Docker daemon).
- Force-push deploy assumes Space `trippy09/chartproof`; rename in workflow if your HF username differs.
- First Space build can take 10–20+ minutes (torch + embeddings + index).

## How to re-verify locally

```bash
source .venv/bin/activate
pytest backend/tests -q
python -m evals.run --suite smoke --enforce-thresholds
# API
uvicorn backend.app:app --port 8000
# UI
cd frontend && npm run dev
```

## Next after go-live

- Paste live API + Vercel URLs into README
- Warm Space before demos
- Optional: nightly full-eval workflow badge
