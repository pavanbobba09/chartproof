# Trust loop 2: grounded citation faithfulness

**Date:** 2026-07-18  
**Goal:** replace the superficial citation metric with a strict, independently implemented grounding oracle that can block CI.

## Validation contract

A case receives faithfulness `1.0` only when every check passes:

- Every evidence ID is valid and unique.
- Every document and line range exists in the case.
- Evidence text exactly matches the cited chart lines.
- An independent criterion oracle agrees with every `for` or `against` label.
- Every evidence item appears in the letter evidence table and no unknown row is present.
- Every determination sentence cites a known evidence ID that supports the stated verdict.
- A supported sepsis determination cites organ-dysfunction evidence, not infection alone.
- Every guideline citation matches a real manifest source and Markdown section.
- Empty evidence is never treated as vacuously faithful.

Any failure makes the case score `0.0` and adds an actionable issue code to JSON and Markdown eval reports.

## Defects found by the new gate

The first strict run correctly dropped smoke faithfulness from `1.000` to `0.000` and exposed two real defects hidden by the previous metric:

1. Supported determinations sometimes cited infection alone instead of organ-dysfunction evidence.
2. A Sepsis-3 source ID was paired with a section retrieved from the ICD-10-CM summary.

The composer now prefers non-infection support for supported determinations and selects one clinical-criteria source plus one coding source with matching sections.

## Regression coverage

The faithfulness suite proves that these defects fail:

- altered excerpt text
- out-of-range span
- wrong evidence side
- determination without verdict-supporting evidence
- zero evidence
- unknown guideline section

## Gate results

```text
ruff check backend data evals                                      PASS
pytest backend/tests -q                                            PASS (73 tests)
python -m evals.run --suite smoke --live --enforce-thresholds      PASS
python -m evals.run --suite full --enforce-thresholds              PASS
npm run build                                                      PASS
```

Full-bank metrics:

| Metric | Result | Threshold |
|--------|-------:|----------:|
| Determination accuracy | 1.000 | 0.80 |
| Evidence recall | 0.818 | 0.70 |
| Grounded citation faithfulness | 1.000 | 0.95 |
| Deferral rate | 0.000 | tracked |

## Next loop

Make the QA comparison genuinely independent, calibrate confidence, and expose review reasons in the audit UI.

`GROQ_API_KEY` is not required for the next trust loop.
