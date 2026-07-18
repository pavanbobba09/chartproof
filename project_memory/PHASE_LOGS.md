# Phase completion logs

**Rule:** When a phase gate passes, write a completion note under `project_memory/` and link it here. Do not start the next phase until that note exists.

## Naming

| Status | File name |
|--------|-----------|
| Phase fully done | `PHASE_<N>_COMPLETE.md` |
| Phase partially done (gate not fully green) | `PHASE_<N>_PROGRESS.md` |
| Index (this file) | `PHASE_LOGS.md` |

## What each completion note must include

1. Date and phase goal
2. Gate command and result (pass/fail)
3. Files added or changed (paths)
4. Tests / metrics run
5. Decisions and tradeoffs
6. Known gaps and next phase opener
7. Whether `GROQ_API_KEY` is required to *continue* into the next phase

## Groq API key: when it is required

`GROQ_API_KEY` is **not** needed for every phase. It is required only when work calls the LLM.

| After completing… | Next work needs Groq? | Why |
|-------------------|----------------------|-----|
| Phase 0 | **No** (until generator) | Scaffold is local-only |
| Phase 1 (rules only) | **Yes** for case generation | `data/generate.py` uses Groq free tier |
| Phase 1 (full) | Optional for Phase 2 index | Index/retrieval offline; evidence agents may use LLM |
| Phase 2 | **Yes** for Phase 3 | Composer + LLM verdict use Groq |
| Phase 3 | **Yes** for Phase 4 | Smoke/full eval + LLM-judge faithfulness |
| Phase 4 | **Yes** for Phase 5 demo | Live "run fresh analysis" on HF Space |
| Phase 5 | **Yes** ongoing | Deployed Space secret + CI smoke-eval secret |

**Setup (never commit the real key):**

```bash
cp .env.example .env
# edit .env and set GROQ_API_KEY=...
```

Also set `GROQ_API_KEY` as a GitHub Actions secret and as a Hugging Face Space secret before Phase 4/5 CI and deploy. See `DEPLOYMENT.md`.

Default model: `GROQ_MODEL=llama-3.3-70b-versatile` (verify still free-tier when starting LLM phases).

## Log index

| Phase | Status | Note |
|-------|--------|------|
| 0 Scaffold | Complete | [PHASE_0_COMPLETE.md](./PHASE_0_COMPLETE.md) |
| 1 Criteria + synthetic data | Complete | [PHASE_1_COMPLETE.md](./PHASE_1_COMPLETE.md) |
| 2 Retrieval + evidence | Not started | — |
| 3 Composer + QA | Not started | — |
| 4 UI + evals | Not started | — |
| 5 Deploy + demo | Not started | — |
