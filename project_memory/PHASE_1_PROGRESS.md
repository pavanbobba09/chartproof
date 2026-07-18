# Phase 1 progress: criteria + rules + consistency

**Date:** 2026-07-18  
**Status:** In progress (not fully complete)  
**Phase goal:** Sepsis criteria, deterministic rules engine, synthetic case bank, guidelines corpus  
**Groq key required for completed work below:** No  
**Groq key required to finish this phase:** **Yes** for `data/generate.py` and generating 10 cases  

---

## Goal

Encode sepsis criteria, evaluate structured labs/vitals without an LLM, validate case/key pairs, then generate a synthetic chart bank with Groq.

## Gate (full Phase 1)

```bash
pytest backend/tests -q
python -m data.generate --dx sepsis --n 10
```

**Current result:** Unit/rules/consistency tests **pass**. Generator command **not implemented yet**.

## Work completed so far

### Criteria

| Item | Path |
|------|------|
| Sepsis criteria YAML | `data/criteria/sepsis.yaml` |
| Loader + schema validation | `backend/rules/loader.py` |

Matches DATA_SPEC: infection (narrative) + organ_dysfunction (any_of structured/narrative children), `verdict_rule: infection AND organ_dysfunction`, source_note disclaimer.

### Rules engine (deterministic, zero LLM)

| Item | Path |
|------|------|
| Package exports | `backend/rules/__init__.py` |
| Engine | `backend/rules/engine.py` |

Implemented:

- Structured ops: `gt`, `lt`, `gte`, `lte`, `rise_gte` (window hours)
- Metrics: `lab.*` and `vital.*` against case tables
- Missing data → `unclear`
- `any_of` / `all_of` with 3-valued logic
- Narrative answers supplied by caller (`met` / `not_met` / `unclear`)
- `verdict_rule` parser: `AND` / `OR` / `NOT` / parentheses, Kleene 3-valued logic → `supported` | `not_supported` | `unknown`

### Consistency checker

| Item | Path |
|------|------|
| Checker | `data/consistency.py` |
| Package init | `data/__init__.py` |

Checks: case_id match, planted span line ranges, min planted spans, at least one `against` for `not_supported`, soft note↔lab/vital mention consistency.

### Tests added this phase

| File | Coverage |
|------|----------|
| `backend/tests/test_rules.py` | Loader, structured ops, verdict_rule, full sepsis supported/not_supported/unknown |
| `backend/tests/test_consistency.py` | OK pair, out-of-range span, missing against spans |

**Last local run:** 23 tests, ruff clean (`backend` + `data`).

## Still open (required for Phase 1 complete)

- [ ] `data/generate.py` (Groq) with raw cache under `data/raw/`, schema validate, consistency, max 3 retries
- [ ] Generate 10 sepsis cases (mixed verdicts / difficulties); manual skim of 3
- [ ] Guidelines corpus: ICD-10-CM extract + Sepsis-3 style summary + `manifest.json`
- [ ] Flip this file to `PHASE_1_COMPLETE.md` when the full gate passes

## Decisions and tradeoffs

- **Structured-only path can resolve `not_supported`** only if every organ-dysfunction child resolves (including `rise_gte` needing 2+ creatinine values). Tests supply full lab series so `unclear` does not leak into `any_of`.
- Latest lab/vital value used for point ops (demo simplicity).
- Consistency lab-mention check is soft keyword-based; tighten later if generator produces noisy notes.
- No Groq calls in rules path: preserves CLAUDE.md rule "no LLM inside `backend/rules/`".

## How to re-verify completed work

```bash
source .venv/bin/activate
ruff check backend data
pytest backend/tests -q
python -c "from backend.rules import load_criteria, evaluate_case; print(load_criteria('sepsis').dx)"
```

## Before starting generator (Groq)

1. Copy env and set key:

```bash
cp .env.example .env
# GROQ_API_KEY=...
# GROQ_MODEL=llama-3.3-70b-versatile
```

2. Confirm free-tier model still available on Groq.
3. Batch with sleeps; on 429 back off and resume (CLAUDE.md).

## Next step

Implement `data/generate.py` + run 10-case bank, then guidelines corpus. When acceptance passes, rename/replace this note with `PHASE_1_COMPLETE.md` and update [PHASE_LOGS.md](./PHASE_LOGS.md).
