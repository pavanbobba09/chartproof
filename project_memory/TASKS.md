# TASKS.md

Work top to bottom. Check items off as they land. Each phase ends with an acceptance check; do not start the next phase until it passes. Add newly discovered tasks under the correct phase rather than doing them ad hoc.

## Phase 0: scaffold (target: half a day)

- [x] Init repo structure per CLAUDE.md layout; add `.gitignore` (`.venv`, `.chroma`, `runs/`, `data/raw/`, `.env`, `node_modules`)
- [x] `backend/requirements.txt` and `requirements-dev.txt` (pytest, ruff)
- [x] `backend/schemas.py` with pydantic models from DATA_SPEC.md plus unit tests for span intersection
- [x] `.env.example` listing every env var from CLAUDE.md with placeholder values
- [x] FastAPI skeleton with `GET /health`
- [x] `.github/workflows/ci.yml` with the `test` job only (lint + pytest), from DEPLOYMENT.md
- [x] Pre-commit basics: ruff configured in `pyproject.toml`
- [x] Loop plan documented in `project_memory/LOOP_PLAN.md`
- [x] Phase completion note: `project_memory/PHASE_0_COMPLETE.md` (+ `PHASE_LOGS.md` index)

Acceptance: `pytest` and `ruff check backend` pass locally and in CI on push. **Local gate: green (2026-07-18).** Writeup: [PHASE_0_COMPLETE.md](./PHASE_0_COMPLETE.md).

## Phase 1: criteria + synthetic data (target: days 1 to 3)

- [x] `data/criteria/sepsis.yaml` exactly per DATA_SPEC.md, plus loader with schema validation
- [x] Rules engine for structured ops (`gt`, `lt`, `gte`, `lte`, `rise_gte`) with unit tests using hand-built fixtures
- [x] `verdict_rule` boolean evaluator with unknown propagation, tested
- [x] Consistency checker (`data/consistency.py`) for case/key span ranges and planted-evidence rules
- [x] `data/generate.py` per the generator contract, including raw-output caching (uses consistency checker)
- [x] Generate 10 sepsis cases (mixed verdicts and difficulties); automated consistency + rules alignment checks
- [x] Guidelines corpus: educational summaries + `manifest.json` (full CMS PDF not vendored; URL in manifest)

Acceptance: `python -m data.generate --dx sepsis --n 10` yields 10 valid case + key pairs; rules engine tests green. **Phase 1 complete (2026-07-18).** Writeup: [PHASE_1_COMPLETE.md](./PHASE_1_COMPLETE.md).

## Phase 2: retrieval + evidence agents (target: days 4 to 7)

- [x] `backend/index/build.py` builds Chroma collections per the chunking spec; idempotent rebuild
- [x] Retrieval wrapper returning spans with metadata and verbatim span text
- [x] Evidence agent node: for each narrative criterion, gather FOR and AGAINST evidence, answer yes/no/unclear with spans
- [x] LangGraph wiring: intake -> evidence -> rules, trace persisted under `runs/`
- [x] Golden test: on one hand-checked case, the agent finds the planted infection span

Acceptance: one case runs end to end through evidence + rules and the trace file shows correct spans with real line numbers. **Phase 2 complete (2026-07-18).** Writeup: [PHASE_2_COMPLETE.md](./PHASE_2_COMPLETE.md).

## Phase 3: composer + QA gate (target: days 8 to 10)

- [ ] Composer node with the evidence-ID constraint enforced in code (drop uncited sentences, log drops)
- [ ] Rationale letter template: finding, evidence citations, guideline references (source_id + section), review disclaimer
- [ ] QA gate: rules vs LLM comparison, confidence score, `needs_review` forcing logic, unit tests for each trigger
- [ ] `POST /audit/{case_id}` and `GET /audit/{case_id}` with result caching to disk
- [ ] Precompute and commit cached results for all bundled cases (`data/precomputed/`)

Acceptance: full pipeline on 10 cases produces determinations with zero invalid citations; at least one disagreement case lands in `needs_review`.

## Phase 4: UI + evals (target: days 11 to 14)

- [ ] `evals/run.py` with `smoke` and `full` suites, metrics per PROJECT.md, thresholds file, markdown report to `evals/out/results.md`
- [ ] Add `smoke-eval` job to CI per DEPLOYMENT.md
- [ ] Next.js app: case picker, chart viewer with line numbers, evidence table with click-to-highlight citation jumps, letter view, status badge
- [ ] Training mode: verdict buttons, line-select for evidence, `POST /training/{case_id}/grade`, graded feedback view
- [ ] Generate remaining cases to reach the 30-case bank; run full eval; put the results table in the README
- [ ] README.md: pitch, architecture diagram image, quickstart, eval table, limitations, demo link placeholders. Must BEGIN with the HF Space frontmatter block from DEPLOYMENT.md section 3, or the Phase 5 Space build will fail

Acceptance: `evals.run --suite full` completes with results.md written; both UI modes work against local backend; smoke eval green in CI.

## Phase 5: deploy + demo (target: days 15 to 16)

- [ ] Dockerfile per DEPLOYMENT.md (model pre-download, index built at build time, user 1000, port 7860)
- [ ] Create HF Space, add secrets, add `deploy` job to CI, verify auto-sync on push to main
- [ ] Vercel: import `frontend/`, set `NEXT_PUBLIC_API_BASE_URL`, verify CORS, optional subdomain chartproof.pavanbobba-developer.com
- [ ] Demo-day hardening: precomputed results served instantly, "run fresh analysis" button does a live run, graceful error if Groq rate-limited
- [ ] Record 2 minute demo video; link it in the README
- [ ] End-to-end check from a phone on cellular

Acceptance: pushing to main deploys automatically; the live link works cold from a phone.

## Stretch (only after Phase 5)

- [ ] Malnutrition criteria (`glim.yaml`) + 10 cases
- [ ] AKI criteria (`kdigo.yaml`) + 10 cases
- [ ] Appeals module: given a provider appeal letter, draft a response with citations
- [ ] Deferral-rate and per-difficulty breakdown in the eval report
- [ ] Nightly `full-eval` workflow badge in README
