# Phase 4 complete: evals + training API + Next.js UI

**Date:** 2026-07-18  
**Status:** Complete for Phase 4 scope (30-case bank expansion deferred)  
**Loop focus:** measure metrics → grade training → ship UI → CI smoke gate  
**Groq key:** Not required for smoke eval (precomputed). Required for generation / live LLM paths.

---

## Goal

Close the measurement loop (accuracy, recall, faithfulness), enable trainee grading against hidden keys, and ship audit + training UIs that talk to the FastAPI backend.

## Gate

```bash
ruff check backend data evals
pytest backend/tests -q
python -m evals.run --suite smoke --enforce-thresholds
python -m evals.run --suite full
cd frontend && npm run build
```

**Result:** All pass. Smoke metrics: accuracy 1.0, recall 1.0, faithfulness 1.0. Full bank accuracy 0.70 (3 deferrals). Frontend production build succeeds.

## Work completed

### Eval harness (`evals/`)

| Item | Path |
|------|------|
| Thresholds | `evals/thresholds.yaml` |
| Metrics | `evals/metrics.py` |
| Runner | `evals/run.py` |
| Report | `evals/out/results.md` |

Suites:

- `smoke`: 5 fixed cases, enforced in CI
- `full`: entire bank, report written (accuracy may be under threshold when deferral rate is high)

### Training API

- `POST /training/{case_id}/grade` grades verdict + selected spans
- Reveals key content only after submission
- `GET /cases/{case_id}` returns chart without keys

### CI

- `smoke-eval` job after unit tests: `python -m evals.run --suite smoke --enforce-thresholds`
- Uploads `evals/out/` artifact

### Next.js frontend (`frontend/`)

| Route | Mode |
|-------|------|
| `/` | Case picker |
| `/audit/[caseId]` | Chart + evidence click-to-highlight + letter + fresh analysis |
| `/training/[caseId]` | Verdict buttons + line select + graded feedback |

All fetches use `cache: "no-store"`. Env: `NEXT_PUBLIC_API_BASE_URL`.

### README

- HF Space frontmatter at top (required for Phase 5 Docker Space)
- Eval results table
- Frontend quickstart

## Acceptance checklist (TASKS.md)

- [x] `evals/run.py` smoke + full, thresholds, results.md
- [x] smoke-eval CI job
- [x] Next.js audit mode (picker, chart lines, evidence jump, letter, badge)
- [x] Training mode + grade endpoint + feedback UI
- [ ] 30-case bank (deferred; 10-case bank retained)
- [x] README frontmatter + eval table + limitations + demo placeholders

## Known gaps

- Full-bank determination accuracy 0.70 < 0.80 due to `needs_review` counting as incorrect (by design)
- 30-case expansion not done (stretch into Phase 5 prep)
- Next.js 14.2.25 npm audit warning (upgrade when convenient)
- No live Vercel/HF deploy yet (Phase 5)

## Next phase opener (Phase 5)

Dockerfile, HF Space auto-deploy, Vercel frontend, demo-day hardening, phone check, demo video.
