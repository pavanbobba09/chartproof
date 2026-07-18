# End-to-end requirements review

**Date:** 2026-07-18  
**Scope:** Phases 0–3 as shipped vs `PROJECT.md`, `DATA_SPEC.md`, `TASKS.md`, `CLAUDE.md`  
**Gate at review:** `ruff` clean, full `pytest` green, API smoke via TestClient  

---

## Executive summary

| Question | Answer |
|----------|--------|
| Are Phases 0–3 done per TASKS acceptance? | **Yes** |
| Does the backend deliver a working audit loop? | **Yes** (index → evidence → rules → compose → QA → API) |
| Is v1 product complete per PROJECT.md? | **No** — Phase 4 UI/evals and Phase 5 deploy remain |
| Are improvements required before Phase 4? | **Recommended, not blocking** (see below; one critical evidence bug fixed in this review) |

**Overall maturity:** solid backend demo of auditor-assist CCV on synthetic sepsis charts. Portfolio-ready for API demos; not yet a full product demo (no UI, no eval report, no public deploy).

---

## What we accomplished (mapped to PROJECT v1)

| v1 capability (PROJECT.md) | Status | Evidence |
|----------------------------|--------|----------|
| 1. Load synthetic chart + billed codes | **Done** | `data/cases/*.json`, `GET /cases` |
| 2. Evaluate vs criteria YAML | **Done** | `data/criteria/sepsis.yaml` + `backend/rules/` |
| 3. Retrieve evidence with line citations | **Done** | Chroma + evidence agents + span metadata |
| 4. Determination + evidence table + letter | **Done** | Composer + precomputed `AuditResult` |
| 5. QA gate (rules vs draft, needs_review) | **Done** | `backend/pipeline/qa.py`; 3/10 need review |
| 6. Training mode | **Not done** | Phase 4 |
| 7. Eval harness (accuracy/recall/faithfulness) | **Not done** | Phase 4 |

### Phase checklist (TASKS)

| Phase | Status | Notes |
|-------|--------|-------|
| 0 Scaffold | Complete | Health, schemas, CI, docs |
| 1 Data + rules | Complete | 10 cases, generator, guidelines summaries |
| 2 Retrieval + agents | Complete | Chroma, LangGraph through rules |
| 3 Composer + QA + API | Complete | Precomputed bank, citation filter |
| 4 UI + evals | **Open** | |
| 5 Deploy | **Open** | |

---

## Hard rules (CLAUDE.md)

| Rule | Status |
|------|--------|
| Synthetic data only | Pass |
| Auditor-assist framing | Pass (API description, letter disclaimer) |
| Citation or drop | Pass (Determination filter in code) |
| Rules engine no LLM | Pass |
| Criteria in YAML + disclaimer | Pass |
| Secrets via env | Pass (no keys in git) |
| Answer keys server-side | Pass (`/cases` and `/audit` omit keys) |
| No em dashes in copy | Pass on sampled letters/docs |
| Free stack | Pass |

---

## Automated E2E results (this review)

```
ruff check backend data     PASS
pytest (full suite)         PASS
GET /health                 PASS
GET /cases                  PASS (no answer-key fields)
GET/POST /audit/sepsis_001  PASS (source=precomputed)
Case bank consistency       10/10 PASS
Precomputed dropped_sentences  0 total
```

### Determination quality vs answer keys (after vaso negation fix)

| Metric | Value |
|--------|-------|
| Completed cases matching key | **7/7** |
| `needs_review` (deferred) | **3/10** (`sepsis_002`, `_006`, `_008`) |
| False completed mismatches | **0** (was 2 before negation fix) |

Deferred cases still have `llm_verdict=not_supported` aligned with keys; rules path returns unknown/unclear organ branch so QA correctly holds for human review.

---

## Gaps and improvements

### Fixed during this review

1. **Vasopressor negation bug (high)**  
   Text like "not requiring vasopressors" was scored as **met**.  
   Fixed in `backend/pipeline/evidence.py` (plural against phrases + regex negation).  
   Regression tests in `test_evidence_negation.py`.  
   Re-ran `data.precompute` for all 10 cases.

### Should improve soon (before or during Phase 4)

| Priority | Item | Why |
|----------|------|-----|
| **P0** | Eval harness + metrics | PROJECT success criteria; without it we cannot prove accuracy/recall/faithfulness |
| **P0** | Training grade endpoint | Spec exists; needed for training UI |
| **P1** | Richer case notes (less padding) | Many lines are filler from length compliance; hurts realism and retrieval quality |
| **P1** | Optional Groq in evidence/composer | Spec allows LLM; current path is deterministic keywords (good for free tier, weaker clinical nuance) |
| **P1** | Expand to 30-case bank | DATA_SPEC target; smoke ids 012/015 need later generation |
| **P2** | Full ICD-10-CM PDF + pypdf | PROJECT mentions extract; we use educational summaries only |
| **P2** | HF Space frontmatter at README top | Required before Phase 5 Space build |
| **P2** | CI install of heavy deps | Phase 2+ tests need chromadb/torch; ensure CI has enough time/cache |
| **P3** | Multi-tenancy/auth note already in README | OK; no code needed for v1 |

### Not bugs (by design for current phase)

- No frontend yet  
- No deploy Dockerfile yet  
- Composer does not call Groq by default (deterministic draft + QA still works)  
- `needs_review` with null verdict is valid pipeline status  

---

## Architecture loop status

```
[done] generate synthetic cases + keys
[done] index charts/guidelines (Chroma)
[done] retrieve spans
[done] evidence agents (narrative)
[done] deterministic rules
[done] compose letter (citation-enforced)
[done] QA gate → completed | needs_review
[done] API + precomputed cache
[open] training grade loop
[open] eval metrics loop (accuracy/recall/faithfulness)
[open] UI human loop (auditor + trainee)
[open] deploy + live demo loop
```

---

## Recommendation

1. **Treat Phases 0–3 as complete** for backend auditor-assist path.  
2. **Commit the vasopressor fix + refreshed precomputed results** (done in this session if pushed).  
3. **Next build priority = Phase 4:** eval harness first (proves quality), then training API, then Next.js UI.  
4. Optionally regenerate a few borderline charts with less pad-filler before UI demos.

### Success criteria still open (PROJECT)

- [ ] Live demo link from a phone  
- [ ] README eval results table + 2 min video  
- [ ] CI smoke-eval badge  
- [ ] Clone-to-run under 10 minutes for full stack (backend is close; frontend missing)

---

## Quick re-verify

```bash
source .venv/bin/activate
ruff check backend data && pytest backend/tests -q
uvicorn backend.app:app --port 8000
curl -s localhost:8000/health
curl -s localhost:8000/cases | head
curl -s localhost:8000/audit/sepsis_001 | head
```
