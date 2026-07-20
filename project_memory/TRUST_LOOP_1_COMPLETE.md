# Trust loop 1: structured evidence correctness

**Date:** 2026-07-18  
**Goal:** repair the highest-impact trust failures before adding diagnoses or product features.

## Changes

- Structured point criteria now preserve any qualifying abnormal observation instead of using only the latest value.
- Creatinine `rise_gte` now measures forward chronological rise, so a decrease cannot count as a rise.
- Structured chart evidence is classified per observation instead of inheriting one criterion-wide side.
- Narrative and composite criteria no longer receive duplicate keyword-scan evidence with incorrect sides.
- Vasopressor negation handling is scoped to the vasopressor criterion and no longer leaks into infection or mental-status scoring.
- QA disagreement now rewrites the letter determination as deferred instead of leaving a conflicting verdict in the letter.
- Eval tests and audit API tests no longer rewrite committed results.
- CI now builds the frontend and runs the live deterministic smoke pipeline.
- Docker build context explicitly includes guideline Markdown files.

## Gate results

```text
ruff check backend data evals                                      PASS
pytest backend/tests -q                                            PASS (66 tests)
python -m evals.run --suite smoke --live --enforce-thresholds      PASS
npm run build                                                      PASS
python -m evals.run --suite full --enforce-thresholds              PASS
```

Full-bank metrics after refreshing all 10 precomputed audits:

| Metric | Result | Threshold |
|--------|-------:|----------:|
| Determination accuracy | 1.000 | 0.80 |
| Evidence recall | 0.818 | 0.70 |
| Citation faithfulness | 1.000 | 0.95 |
| Deferral rate | 0.000 | tracked |

## Decisions and tradeoffs

- No clinical threshold changed.
- Normal follow-up values remain useful evidence against a specific observation, but they no longer erase earlier abnormalities.
- At this checkpoint citation faithfulness remained structural. Trust loop 2 subsequently replaced it with strict grounded validation.
- `llm_verdict` remains a compatibility name for a deterministic draft heuristic and should be renamed or replaced in a later contract revision.

## Next loop

1. Add semantic checks for evidence side and claim support. Completed in Trust loop 2.
2. Expose QA reasons and criteria explanations to auditors.
3. Validate training spans against actual document bounds.
4. Improve case realism and expand the bank only after the trust gate remains green.

`GROQ_API_KEY` is not required for the next trust loop.
