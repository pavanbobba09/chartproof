# Trust loop 3: honest QA, real deferral, evidence quality

**Date:** 2026-07-19  
**Goal:** close the gaps a technical reviewer would find first: a "second opinion" that was neither an LLM nor independent, a human-in-the-loop system that never deferred, evidence lexicons that missed the bank's own phrasing, and hidden defects in the answer keys themselves.

## Commits in this loop

1. `0659a73` Quick-win trust bundle
2. `1a070a9` Auditor panel + honest naming
3. `defe8dd` Deferral case, per-case recall floor, opt-in Groq composer

## Changes

### Evidence quality (quick-win bundle)

- New `backend/pipeline/lexicon.py`: one canonical narrative lexicon shared by the evidence agents and the faithfulness oracle. The two copies had already diverged; the grader no longer drifts from the system it grades. The oracle's independence lives in its grounding, structured re-computation, table, and guideline checks.
- Affirmative vasopressor regexes (started on / titrated / treated with / receiving), spelled-out Glasgow Coma Scale, chills / cough / dysuria as infection signals.
- Removed the overfit phrase copied from a sepsis_001 sentence, and removed "sepsis" from infection evidence: the billed label is not evidence for itself.
- Ambiguous excerpts with equal signals on both sides are cited for neither.
- Evidence agents always sweep the full chart in addition to retrieval; retrieval rank no longer bounds recall on demo-size charts.
- Composite criteria cite explicit statements ("no evidence of organ dysfunction") with per-line sides; monitoring language counts for neither side.
- **Nine answer keys had off-by-one planted spans** (generator defect exposed once citations tightened; the old wide chunks masked it). Each fix verified line-by-line against chart text.

### Honest QA and auditor surface

- `llm_verdict` renamed to `draft_verdict` everywhere: the value is a deterministic evidence-balance heuristic and the old name claimed an LLM the audit path did not have.
- `AuditResult.force_reasons` now exposes why QA forced review; the audit UI renders them in plain language plus a per-criterion met / not_met / unclear checklist with clickable citation jumps.
- The rationale letter's evidence table gained a Criterion column and renders correctly in the UI (remark-gfm).

### Real deferral and eval hardening

- `sepsis_011`: ambiguous by design (clear pyelonephritis, incomplete organ-dysfunction workup). The pipeline defers with reasons `rules_draft_disagreement`, `unknown_verdict`, `low_confidence`. The key carries `deferral_expected`, and evals score deferral as the correct output for such cases.
- Per-case evidence-recall floor (0.50) in thresholds: aggregates can no longer hide a local miss like the old 0.33.

### Opt-in LLM composer

- `CHARTPROOF_LLM_COMPOSE=1` + `GROQ_API_KEY` enables a Groq draft: independent verdict and determination prose. The prompt never sees the rules verdict, the prose passes the same citation gate (uncited sentences dropped), and any failure falls back to the deterministic path. `AuditResult.composer` records which path ran. Default remains deterministic so CI, evals, and precompute stay offline and reproducible.

### Hardening

- Training grading validates spans against real documents, caps span length and count, dedupes; the lines 1-1000000 exploit now returns 422.
- 500 responses return an error_id instead of exception text; details go to server logs.
- Fresh-run runtime cache takes precedence over committed precomputed results.
- Trace IDs carry microseconds plus a random suffix; concurrent runs cannot collide.
- Offline compose fallback cites a real manifest source_id and passes the faithfulness gate (regression test added).

## Gate results

```text
ruff check backend data evals                                      PASS
pytest backend/tests -q                                            PASS (90 tests)
python -m evals.run --suite smoke --live --enforce-thresholds      PASS
python -m evals.run --suite full --enforce-thresholds              PASS
npm run build                                                      PASS
```

Full-bank metrics (11 cases):

| Metric | Result | Threshold |
|--------|-------:|----------:|
| Determination accuracy | 1.000 | 0.80 |
| Evidence recall | 1.000 (per case >= 0.50 enforced) | 0.70 |
| Grounded citation faithfulness | 1.000 | 0.95 |
| Deferral rate | 0.091 (the designed case) | tracked |

## Decisions and tradeoffs

- No clinical threshold changed.
- Sharing the lexicon trades a nominally independent narrative side-check for guaranteed consistency; the oracle keeps genuinely independent checks elsewhere. Documented in `lexicon.py`.
- Answer keys are generated data; correcting their misplanted spans is data QA, not metric tuning. The correction was found because tighter citations stopped masking it.
- The LLM composer is opt-in so committed artifacts stay deterministic and reproducible.

## Next loop

1. Go-live: HF Space + Vercel + LICENSE + CI badge + demo video (TASKS.md Phase 5 remainder).
2. AKI via KDIGO as the second diagnosis (criteria file + cases) to prove the architecture generalizes.
3. Bank expansion with varied document counts, lengths, and styles.

`GROQ_API_KEY` is only needed for case generation and the opt-in LLM composer.
