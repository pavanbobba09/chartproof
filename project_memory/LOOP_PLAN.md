# ChartProof: loop-engineering plan

Goal: ship a working auditor-assist CCV demo by running a tight **build → measure → fix** loop on every phase. No feature lands without a verifiable gate.

## Engineering loop (the unit of work)

```
1. Pick the smallest TASKS.md item that unblocks the next gate
2. Implement it behind a clear contract (DATA_SPEC / API)
3. Add or extend a test (unit, golden, or eval)
4. Run the local gate for this phase
5. Check the item off TASKS.md; only then move on
```

If the gate fails: fix that first. Do not start the next phase with a red loop.

## After every phase (mandatory writeup)

When a phase gate passes (or a meaningful mid-phase checkpoint lands):

1. Write `project_memory/PHASE_<N>_COMPLETE.md` (or `PHASE_<N>_PROGRESS.md` if incomplete).
2. Update the index in [PHASE_LOGS.md](./PHASE_LOGS.md).
3. Record gate commands, files touched, tests, decisions, and whether `GROQ_API_KEY` is needed next.

See PHASE_LOGS.md for the Groq key matrix by phase.

## Phase gates (definition of done)

| Phase | Loop gate | Command |
|-------|-----------|---------|
| 0 Scaffold | Lint + unit tests | `ruff check backend && pytest backend/tests -q` |
| 1 Data + rules | Generator + rules tests | `pytest` + `python -m data.generate --dx sepsis --n 10` |
| 2 Retrieval | One case end-to-end trace | evidence + rules produce real line spans |
| 3 Compose + QA | Citation-safe pipeline | audit 10 cases, zero invalid citations |
| 4 UI + evals | Smoke eval green | `python -m evals.run --suite smoke --enforce-thresholds` |
| 5 Deploy | Live demo from phone | push main → HF + Vercel healthy |

Hard rule from CLAUDE.md: for any pipeline change after Phase 4, also keep smoke eval above thresholds.

## Post-Phase-5 trust loop

Each trust iteration follows this gate:

```
reproduce with a regression test
  → make the smallest correctness fix
  → run lint + full backend tests
  → run the live smoke eval (not precomputed outputs)
  → build the production frontend
  → refresh precomputed demo results only after the live gate passes
```

The live deterministic audit path does not require `GROQ_API_KEY`. Groq is currently used only for generating additional synthetic cases.

## Loop metrics (what we optimize)

1. **Correctness**: determination accuracy vs answer keys
2. **Evidence recall**: planted spans found and cited
3. **Faithfulness**: every claim has a valid supporting span
4. **Deferral quality**: `needs_review` when rules and LLM disagree (human in the loop)

Target smoke thresholds (see DATA_SPEC): accuracy >= 0.80, recall >= 0.70, faithfulness >= 0.95.

## Human-in-the-loop product loop

The product itself is a loop, not a black-box decision:

```
chart + billed dx
  → rules (deterministic) + evidence agents (retrieval)
  → composer draft (citation-enforced)
  → QA gate (disagree / low conf → needs_review)
  → human auditor decides
```

Training mode closes a second loop: trainee → grade vs key → missed evidence → learn.

## Current focus

**Trust loop 3 complete** (see TRUST_LOOP_3_COMPLETE.md): honest draft_verdict naming, force_reasons in the audit UI, real deferral case with deferral_expected scoring, per-case recall floor, shared evidence lexicon, answer-key corrections, opt-in Groq composer behind the citation gate.

Next: go-live (HF Space + Vercel + LICENSE + demo video), then AKI via KDIGO as the second diagnosis.

## Working conventions

- Small commits, imperative messages
- Synthetic data only; auditor-assist framing always
- Rules engine stays LLM-free
- Secrets only via env vars
- Prefer the simpler demo option when ambiguous
