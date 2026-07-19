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
| Phase 2 | **No** for the current Phase 3 path | Composer and draft verdict are deterministic |
| Phase 3 | **No** for the current Phase 4 path | Smoke/full evals use deterministic checks |
| Phase 4 | **No** for the current Phase 5 demo | Live audit uses local retrieval and rules |
| Phase 5 | Optional | Groq is required only when generating more synthetic cases |

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
| 0+1 joint audit | Complete | [PHASE_0_1_AUDIT.md](./PHASE_0_1_AUDIT.md) |
| 2 Retrieval + evidence | Complete | [PHASE_2_COMPLETE.md](./PHASE_2_COMPLETE.md) |
| 3 Composer + QA + audit API | Complete | [PHASE_3_COMPLETE.md](./PHASE_3_COMPLETE.md) |
| Features inventory | Living | [FEATURES.md](./FEATURES.md) |
| 4 UI + evals | Complete | [PHASE_4_COMPLETE.md](./PHASE_4_COMPLETE.md) |
| 5 Deploy + demo | Engineering complete | [PHASE_5_COMPLETE.md](./PHASE_5_COMPLETE.md) |
| Trust loop 1 | Complete | [TRUST_LOOP_1_COMPLETE.md](./TRUST_LOOP_1_COMPLETE.md) |
| Trust loop 2 | Complete | [TRUST_LOOP_2_COMPLETE.md](./TRUST_LOOP_2_COMPLETE.md) |
| Trust loop 3 | Complete | [TRUST_LOOP_3_COMPLETE.md](./TRUST_LOOP_3_COMPLETE.md) |
