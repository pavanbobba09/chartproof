# ChartProof eval report (full)

Generated: 2026-07-18T18:16:26.327354+00:00

## Aggregate metrics

| Metric | Value | Threshold |
|--------|------:|----------:|
| Determination accuracy | 0.700 | 0.80 |
| Evidence recall | 0.872 | 0.70 |
| Citation faithfulness | 1.000 | 0.95 |
| Deferral rate | 0.300 | n/a |

**Suite passed thresholds:** False

## Per-case

| Case | Status | Key | Pred | Correct | Recall | Faithful |
|------|--------|-----|------|---------|-------:|---------:|
| sepsis_001 | completed | supported | supported | True | 1.00 | 1.00 |
| sepsis_002 | completed | not_supported | not_supported | True | 0.50 | 1.00 |
| sepsis_003 | needs_review | supported | None | False | 0.75 | 1.00 |
| sepsis_004 | completed | not_supported | not_supported | True | 1.00 | 1.00 |
| sepsis_005 | completed | supported | supported | True | 0.67 | 1.00 |
| sepsis_006 | completed | not_supported | not_supported | True | 1.00 | 1.00 |
| sepsis_007 | completed | supported | supported | True | 1.00 | 1.00 |
| sepsis_008 | needs_review | not_supported | None | False | 1.00 | 1.00 |
| sepsis_009 | needs_review | supported | None | False | 0.80 | 1.00 |
| sepsis_010 | completed | not_supported | not_supported | True | 1.00 | 1.00 |

## Threshold failures

- determination_accuracy: 0.700 < 0.800
