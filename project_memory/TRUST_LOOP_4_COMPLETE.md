# Trust Loop 4 Complete: Focused Portfolio Hardening

Date: 2026-07-20

## Goal

Complete the smallest high-value engineering loop for the hiring demo without inventing a larger product scope: harden demonstrated correctness boundaries, make the 100-record bank usable and honest, add keyboard access, and prove the primary workflow in a real browser.

## What changed

### Dataset provenance

- `Case` and `CaseSummary` now expose `dataset_role`.
- Volume records must include `source_case_id`.
- The bank is explicitly split into 15 independently generated clinical scenarios and 85 deterministic volume-test variants.
- Tests enforce exactly 100 records and the 15/85 provenance split.

### Case-bank workflow

- Added search by case ID or diagnosis.
- Added difficulty and dataset-purpose filters.
- Added 20-record pagination.
- Added visible totals for all records, clinical scenarios, and volume variants.
- Added plain-language copy explaining that volume variants do not increase the clinical evidence base.

### Correctness and test isolation

- Verified the existing training guardrails for unknown documents, out-of-range spans, oversized spans, excessive selections, and duplicates.
- Verified that internal exception text is replaced by a safe error reference.
- API tests now use an isolated runtime cache and cannot fail because a developer previously ran a fresh local audit.

### Accessibility

- Selectable chart lines are semantic buttons with keyboard activation and `aria-pressed` state.
- Evidence-to-chart navigation is a semantic button with a descriptive accessible name.
- Case actions have record-specific accessible names and visible focus treatment.
- Added a local favicon so the browser journey has no console 404.

### Browser and CI verification

- Added one focused Playwright Core journey using the installed system Chrome.
- The journey covers case count, pagination, dataset filter, search, audit navigation, evidence highlighting, keyboard chart selection, and training grading.
- Browser console and page errors fail the test.
- CI now runs the browser journey after backend and frontend gates, and deployment depends on it.

## Gate evidence

| Gate | Result |
|---|---|
| Backend tests | 92 passed |
| Python lint | Passed |
| Frontend TypeScript check | Passed |
| Frontend production build | Passed |
| Production Chrome journey | Passed |
| Live smoke evaluation | Accuracy 1.000, recall 1.000, faithfulness 1.000 |
| Full 100-record evaluation | Accuracy 1.000, recall 0.946, faithfulness 1.000, deferral 0.060 |
| Production dependency audit from local npm cache | 0 known production vulnerabilities |
| Whitespace and repository integrity checks | Passed |

## Decisions and tradeoffs

- The 85 deterministic variants are for workflow and volume testing only. They are not presented as independent clinical validation cases.
- The browser test uses `playwright-core` with system Chrome, avoiding browser downloads and keeping the stack small.
- Frontend `lint` runs the strict TypeScript checker. The deprecated ESLint 8 stack required by `next lint` was deliberately not added.
- Authentication, multi-tenancy, EHR integration, PHI support, a database, and additional diagnoses remain outside this loop because the target product requirements are unknown.

## Next opener

Stop feature expansion. Prepare the demo narrative and only add another capability when it is tied to a confirmed job or product requirement.

`GROQ_API_KEY` is not required for the next step. It is needed only for generating additional independently authored synthetic scenarios.
