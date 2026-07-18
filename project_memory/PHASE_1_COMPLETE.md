# Phase 1 complete: criteria + synthetic data

**Date:** 2026-07-18  
**Status:** Complete (local gate green)  
**Loop focus:** generate → validate schema → consistency check → rules smoke → pytest  
**Groq key required for this phase:** Yes (case generation)  
**Groq key required for Phase 2 start:** No for index build; optional if evidence agents call LLM later  

---

## Goal

Encode sepsis criteria, keep the rules engine deterministic, generate a synthetic case bank with answer keys, and seed a public-style guidelines corpus for later retrieval.

## Gate

```bash
ruff check backend data
pytest backend/tests -q
python -m data.generate --dx sepsis --n 10   # idempotent if cases exist
```

**Result:** Pass. 10/10 cases saved; full pytest suite green (includes case-bank load tests).

## Work completed

### Criteria and rules (from Phase 1 progress)

| Item | Path |
|------|------|
| Sepsis YAML | `data/criteria/sepsis.yaml` |
| Loader | `backend/rules/loader.py` |
| Engine | `backend/rules/engine.py` |
| Consistency | `data/consistency.py` |

### Generator (new)

| Item | Path |
|------|------|
| Config (model one-liner) | `backend/config.py` |
| Generator CLI | `data/generate.py` |
| Deps | `httpx` in `backend/requirements.txt` |

Generator loop:

1. Plan specs (verdict + difficulty before LLM call)
2. Call Groq with JSON-only contract
3. Write raw text to `data/raw/` (gitignored)
4. Parse JSON, force case_id/verdict/difficulty from spec
5. Pydantic validate + consistency check
6. Retry up to 3 times; back off on 429
7. Write `data/cases/<id>.json` and `data/keys/<id>.key.json`

Command:

```bash
set -a && source .env && set +a
python -m data.generate --dx sepsis --n 10
```

### Case bank (10 sepsis)

| case_id | key verdict | difficulty |
|---------|-------------|------------|
| sepsis_001 | supported | clear |
| sepsis_002 | not_supported | clear |
| sepsis_003 | supported | clear |
| sepsis_004 | not_supported | clear |
| sepsis_005 | supported | borderline |
| sepsis_006 | not_supported | borderline |
| sepsis_007 | supported | clear |
| sepsis_008 | not_supported | clear |
| sepsis_009 | supported | clear |
| sepsis_010 | not_supported | clear |

All pairs pass consistency. Rules engine (infection forced met) matches key verdict on clear cases checked during bank validation.

### Guidelines corpus

| Item | Path |
|------|------|
| Manifest | `data/guidelines/manifest.json` |
| ICD-10-CM summary | `data/guidelines/icd10cm_coding_summary.md` |
| Sepsis-3 summary | `data/guidelines/sepsis3_summary.md` |
| GLIM / KDIGO stubs | `glim_summary.md`, `kdigo_aki_summary.md` |

Summaries are educational paraphrases with source notes. Full CMS PDF not vendored (size/license simplicity); URL recorded in manifest.

### Tests added

| File | Coverage |
|------|----------|
| `backend/tests/test_generate.py` | plan_specs, JSON extract, parse + consistency fixture |
| `backend/tests/test_guidelines.py` | manifest files exist + disclaimers |
| `backend/tests/test_case_bank.py` | load 10 cases, consistency, rules alignment |

## Decisions and tradeoffs

- **Educational guideline summaries** instead of full ICD-10-CM PDF in git (keeps repo small; enough for citation sections).
- **Soft consistency** on lab mentions caught missing `wbc` rows; retries fixed those cases.
- **Rate limits:** free-tier 429s handled with backoff; generation of 10 cases took ~4 minutes.
- **Note length:** some generated notes are shorter than the 15–60 line ideal in DATA_SPEC. Acceptable for Phase 1 demo bank; tighten prompt in a later polish pass if retrieval quality suffers.
- Raw LLM dumps stay gitignored under `data/raw/`.

## Acceptance checklist (TASKS.md)

- [x] sepsis.yaml + loader
- [x] Rules engine structured ops + tests
- [x] verdict_rule with unknown propagation
- [x] Consistency checker
- [x] `data/generate.py` with raw cache and retries
- [x] 10 sepsis cases generated and skim-validated via automation
- [x] Guidelines corpus + manifest

## How to re-verify

```bash
source .venv/bin/activate
ruff check backend data
pytest backend/tests -q
python -c "from pathlib import Path; print(len(list(Path('data/cases').glob('sepsis_*.json'))))"
```

## Next phase opener (Phase 2)

**Retrieval + evidence agents**

1. `backend/index/build.py` Chroma collections (chart chunks + guidelines)
2. Retrieval wrapper with verbatim span text
3. Evidence agent for narrative criteria
4. LangGraph: intake → evidence → rules; persist traces under `runs/`

Gate: one case end-to-end with real line-number spans in the trace.
