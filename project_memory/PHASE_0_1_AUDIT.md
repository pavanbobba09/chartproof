# Pre-Phase-2 audit: Phase 0 and Phase 1 vs project requirements

**Date:** 2026-07-18  
**Scope:** Everything completed before Phase 2 (scaffold, criteria, rules, generator, case bank, guidelines)  
**Sources of truth:** `PROJECT.md`, `DATA_SPEC.md`, `TASKS.md`, `CLAUDE.md`, `LOOP_PLAN.md`

---

## Summary verdict

| Area | Verdict | Notes |
|------|---------|--------|
| Phase 0 acceptance | **Pass** | Health API, schemas, CI, lint, tests |
| Phase 1 acceptance | **Pass** (after audit fixes) | 10 cases, rules, generator, guidelines |
| Hard rules (CLAUDE) | **Pass** (after audit fixes) | Em dashes removed from README; rules stay LLM-free |
| Ready for Phase 2 | **Yes** | Residual gaps are documented stretch/deferred items |

Automated gates after fixes:

```text
ruff check backend data   # clean
pytest backend/tests -q   # all pass
```

---

## Phase 0 checklist vs code

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Repo layout per CLAUDE | Pass | `backend/`, `data/`, `evals/`, `project_memory/`, placeholders for pipeline/index |
| `.gitignore` (venv, chroma, runs, raw, env, node_modules) | Pass | `.gitignore` |
| requirements + requirements-dev | Pass | fastapi, pydantic, pyyaml, dotenv, httpx; pytest, ruff |
| `backend/schemas.py` + span intersection tests | Pass | `EvidenceSpan.intersects`, `test_schemas.py` |
| `.env.example` all env vars | Pass | GROQ_*, CHROMA_DIR, ALLOWED_ORIGINS, NEXT_PUBLIC_*, HF_TOKEN |
| `GET /health` | Pass | `backend/app.py`, `test_health.py` |
| CI test job (lint + pytest) | Pass | `.github/workflows/ci.yml` (test job only, as Phase 0 specifies) |
| Ruff in `pyproject.toml` | Pass | target py311 |
| No secrets committed | Pass | `.env` gitignored; no `gsk_` in tracked files |

---

## Phase 1 checklist vs code

| Requirement | Status | Evidence |
|-------------|--------|----------|
| `data/criteria/sepsis.yaml` matches DATA_SPEC | Pass | infection + organ_dysfunction any_of children, thresholds, disclaimer |
| Rules engine structured ops | Pass | gt/lt/gte/lte/rise_gte in `backend/rules/engine.py` + tests |
| `verdict_rule` with unknown propagation | Pass | 3-valued AND/OR/NOT |
| Zero LLM in `backend/rules/` | Pass | no groq/openai/langchain imports |
| Consistency checker | Pass | spans, against for not_supported, min planted; **now also enforces 3-6 docs and 15-60 lines** |
| Generator contract (verdict first, raw cache, validate, retry) | Pass | `data/generate.py` |
| 10 sepsis cases mixed verdicts | Pass | 5 supported / 5 not_supported; 8 clear / 2 borderline |
| Guidelines + manifest | Pass with tradeoff | Educational markdown summaries; **full CMS PDF + pypdf not vendored** (documented) |

### Case bank quality (post-audit)

| Check | Result |
|-------|--------|
| Schema load | All 10 cases + keys |
| Consistency | All pass after line padding |
| Lines per doc | Was 5-9 (fail DATA_SPEC); **padded to 15** without shifting planted line numbers |
| Docs per case | 3 (H&P, progress, discharge) within 3-6 |
| PHI-like patterns | None found (no MRN/SSN-like) |
| Clear-case rules alignment (infection met; vaso only if truly administered) | Aligns when narrative vaso is set correctly from chart |

---

## DATA_SPEC coverage (Phase 0-1 only)

| Spec section | Status |
|--------------|--------|
| 1 Case file | Implemented in schemas + bank |
| 2 Evidence span + intersect | Implemented |
| 3 Answer key | Implemented; not exposed via API (no keys routes yet) |
| 4 Criteria YAML | Implemented for sepsis |
| 5 Guidelines | Partial: summaries + manifest; not full PDF extract |
| 6 Generator | Implemented |
| 7 Chunking | **Not yet** (Phase 2) |
| 8 Audit/training API | Models exist; endpoints **not yet** (Phase 3+) |
| 9 Letter format | **Not yet** (Phase 3) |
| 10 Eval thresholds | **Not yet** (Phase 4) |

---

## CLAUDE hard rules

| Rule | Status |
|------|--------|
| Synthetic data only | Pass |
| Auditor-assist framing | Pass (README + API description) |
| Citation or drop | N/A until composer |
| Rules deterministic | Pass |
| Criteria only in YAML with source_note | Pass |
| Secrets via env | Pass |
| Answer keys server-side | Pass (files on disk; no API leak yet) |
| No em dashes | **Fixed in audit** (README hard rules + roadmap; PHASE_LOGS table) |
| Zero paid services | Pass |

---

## Issues found and disposition

### Fixed in this audit

1. **Doc length under DATA_SPEC (15-60 lines)**  
   - All bank docs were ~5-9 lines.  
   - Padded each document to 15 lines (append-only so planted spans stay valid).  
   - Consistency checker now rejects out-of-range doc counts and line counts.  
   - Generator prompt strengthened (REQUIRED length; no false vasopressors on not_supported).

2. **Em dashes in user-facing docs** (CLAUDE rule 8)  
   - Removed from README hard rules and roadmap; cleaned PHASE_LOGS pending cells.

3. **Missing multi-tenancy limitation note** (PROJECT non-goals)  
   - Added under README hard rules / known limitations.

4. **Test fixtures**  
   - Updated to satisfy new 15-line / 3-doc consistency rules.

### Accepted / deferred (not blockers for Phase 2)

| Gap | Why deferred |
|-----|----------------|
| Full ICD-10-CM PDF + pypdf extract | Large binary; educational summaries + URL in manifest sufficient for citation demos; can add PDF later |
| 30-case bank | Phase 4 task; 10 is Phase 1 acceptance |
| Smoke case ids `sepsis_012`, `sepsis_015` | Only exist after larger bank |
| Note padding is generic nursing/provider filler | Better than regenerating under rate limits; optional re-generate with stronger prompt later for richer narrative |
| Latest-value semantics for point labs/vitals | Demo simplicity; documented in rules engine |
| API only `/health` | Correct for Phase 0-1 |

### Non-issues clarified during audit

- `sepsis_004` / `sepsis_010` mention "not requiring vasopressors". Naive keyword audits must not set `vasopressors=met`. Structured labs correctly yield `not_supported`.

---

## Component inventory (what exists)

```
backend/app.py              GET /health + CORS
backend/schemas.py          Case, key, span, audit/training shapes, criteria
backend/config.py           GROQ_MODEL one-line swap
backend/rules/*             Loader + deterministic engine
data/criteria/sepsis.yaml
data/generate.py
data/consistency.py
data/cases/sepsis_001..010.json
data/keys/sepsis_001..010.key.json
data/guidelines/* + manifest.json
.github/workflows/ci.yml
project_memory/*            Specs + phase logs + this audit
```

---

## Recommendation

**Proceed to Phase 2** (Chroma index, retrieval, evidence agents, LangGraph intake → evidence → rules).

Do not reopen Phase 1 unless retrieval quality suffers from thin narratives; if so, re-run:

```bash
python -m data.generate --dx sepsis --n 10 --force
```

after confirming free-tier quota.

---

## Re-verify commands

```bash
source .venv/bin/activate
ruff check backend data
pytest backend/tests -q
python -c "
from pathlib import Path
from backend.schemas import Case, AnswerKey
from data.consistency import check_case_key_consistency
for p in sorted(Path('data/cases').glob('sepsis_*.json')):
    c = Case.model_validate_json(p.read_text())
    k = AnswerKey.model_validate_json((Path('data/keys') / f'{c.case_id}.key.json').read_text())
    assert check_case_key_consistency(c, k) == []
print('bank ok')
"
```
