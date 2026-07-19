# DATA_SPEC.md

Schemas for cases, answer keys, criteria files, and the reference corpus. Implement these as pydantic v2 models in `backend/schemas.py` and validate everything at load time. If a schema needs to change, update this file in the same commit.

## 1. Case file (`data/cases/<case_id>.json`)

```json
{
  "case_id": "sepsis_007",
  "target_dx": "sepsis",
  "billed": { "icd10": ["A41.9"], "drg": "871" },
  "patient": { "age": 67, "sex": "F" },
  "documents": [
    {
      "doc_id": "hp",
      "doc_type": "history_and_physical",
      "date": "2026-01-03",
      "lines": [
        "Chief complaint: fever and dysuria x2 days.",
        "HPI: 67F presenting with fever to 38.9, chills, urinary frequency..."
      ]
    },
    { "doc_id": "pn_01", "doc_type": "progress_note", "date": "2026-01-04", "lines": ["..."] },
    { "doc_id": "ds", "doc_type": "discharge_summary", "date": "2026-01-07", "lines": ["..."] }
  ],
  "labs": [
    { "name": "lactate", "value": 1.4, "unit": "mmol/L", "datetime": "2026-01-03T09:12" },
    { "name": "creatinine", "value": 0.9, "unit": "mg/dL", "datetime": "2026-01-03T09:12" }
  ],
  "vitals": [
    { "name": "map", "value": 78, "unit": "mmHg", "datetime": "2026-01-03T08:40" },
    { "name": "temp", "value": 38.9, "unit": "C", "datetime": "2026-01-03T08:40" }
  ]
}
```

Rules:
- Line numbers are 1-based positions in `lines`. They are the citation currency of the whole system.
- `doc_type` enum: `history_and_physical`, `progress_note`, `nursing_note`, `discharge_summary`, `lab_report_narrative`.
- Lab `name` and vital `name` values are lowercase canonical strings; keep the canonical list in `backend/schemas.py` (`lactate`, `creatinine`, `wbc`, `platelets`, `bilirubin`, `map`, `sbp`, `temp`, `spo2`, `fio2`, `gcs`, ...).
- 3 to 6 documents per case, 15 to 60 lines each. Notes must reference labs/vitals that actually exist in the tables (consistency checker enforces this).

## 2. Evidence span (shared shape)

```json
{ "doc_id": "pn_01", "line_start": 8, "line_end": 9 }
```
Spans always reference a case document. `line_end >= line_start`. Two spans "intersect" if same `doc_id` and ranges overlap; intersection is how evidence recall is scored.

## 3. Answer key (`data/keys/<case_id>.key.json`, server-side only)

```json
{
  "case_id": "sepsis_007",
  "verdict": "not_supported",
  "difficulty": "borderline",
  "planted_evidence": [
    { "doc_id": "pn_01", "line_start": 8, "line_end": 9, "side": "against", "criterion_id": "organ_dysfunction" },
    { "doc_id": "hp", "line_start": 2, "line_end": 4, "side": "for", "criterion_id": "infection" }
  ],
  "key_rationale": "Infection documented and treated, but no organ dysfunction: lactate normal, MAP stable, no vasopressors, creatinine at baseline."
}
```

- `verdict` enum: `supported`, `not_supported`. (Keys are never `needs_review`; that status belongs to the pipeline output.)
- `side` enum: `for`, `against` (relative to the billed diagnosis being supported).
- Never serve this file through the API except as grading feedback after a training submission.

## 4. Criteria file (`data/criteria/<dx>.yaml`)

Sepsis example (simplified demo encoding, keep the disclaimer):

```yaml
dx: sepsis
display_name: Sepsis
icd10_prefixes: ["A40", "A41", "R65.2"]
source_note: >
  Simplified demo encoding informed by Sepsis-3 (Singer et al., JAMA 2016).
  Educational demo only, not for clinical use.
verdict_rule: "infection AND organ_dysfunction"
criteria:
  - id: infection
    kind: narrative
    question: >
      Is an infection documented or clinically suspected (positive cultures,
      identified source, or antibiotics started for a presumed infection)?

  - id: organ_dysfunction
    kind: any_of
    children:
      - id: lactate_elevated
        kind: structured
        metric: lab.lactate
        op: gt
        threshold: 2.0
      - id: hypotension
        kind: structured
        metric: vital.map
        op: lt
        threshold: 65
      - id: vasopressors
        kind: narrative
        question: "Were vasopressors administered?"
      - id: creatinine_rise
        kind: structured
        metric: lab.creatinine
        op: rise_gte
        threshold: 0.3
        window_hours: 48
      - id: thrombocytopenia
        kind: structured
        metric: lab.platelets
        op: lt
        threshold: 100
      - id: altered_mentation
        kind: narrative
        question: "Is acute altered mental status or GCS below 15 documented?"
```

Semantics:
- `kind: structured` is evaluated numerically by the rules engine. Supported ops: `gt`, `lt`, `gte`, `lte`, `rise_gte` (max minus min within `window_hours`, requires 2+ values).
- `kind: narrative` is resolved by the evidence agents: answer yes/no/unclear plus the supporting spans.
- `kind: any_of` / `all_of` combine children.
- `verdict_rule` is a boolean expression over top-level criterion ids, evaluated by the rules engine. `unclear` narrative results make the affected branch unknown; an unknown verdict maps to pipeline status `needs_review`.

## 5. Reference corpus (`data/guidelines/`)

- `manifest.json`: list of `{ source_id, title, url, license_note, file }`.
- Sources for v1: ICD-10-CM Official Guidelines (CDC/CMS, public), short criteria summaries the generator and composer can cite (Sepsis-3, GLIM, KDIGO) written in our own words with references, stored as markdown.
- Guideline chunks carry metadata `{ source_id, section }`. Rationale letters cite `source_id` plus section, never long verbatim quotes.

## 6. Generator contract (`data/generate.py`)

Input spec per case: `{ dx, verdict, difficulty, seed }`. The generator must:
1. Decide the verdict first, then ask the LLM for a chart consistent with it, including at least 2 planted evidence spans (at least 1 `against` span for `not_supported` cases) and realistic distractor content.
2. For `not_supported` cases, the clinician notes still mention the billed diagnosis (that is what makes validation non-trivial) while the objective data contradicts it.
3. `borderline` difficulty means exactly one organ-dysfunction child is near threshold or the narrative is ambiguous.
4. Emit the case JSON and answer key JSON, validate both against schemas, run the consistency checker, regenerate on failure (max 3 attempts, then log and skip).
5. Write raw LLM output to `data/raw/` before parsing, so failures are inspectable and reruns are cheap.

Bank composition target for v1: 30 sepsis cases: 12 supported / 12 not_supported clear, 3 + 3 borderline. The 5 smoke-eval cases are fixed by id in `evals/thresholds.yaml` and never regenerated.

## 7. Chunking spec (`backend/index/`)

- Chart chunks: sliding window of 4 lines, overlap 1, per document. Chunk text prefixed with `"[{doc_type} {date}] "` for retrieval context. Metadata: `case_id, doc_id, doc_type, date, line_start, line_end`.
- Guideline chunks: split on section headers, max ~1200 characters. Metadata: `source_id, section`.
- Collection names: `case_{case_id}` and `guidelines`. Rebuildable at any time from `data/` with one command.

## 8. API contracts (`backend/app.py`)

AuditResult, returned by `POST /audit/{case_id}` and `GET /audit/{case_id}`:

```json
{
  "case_id": "sepsis_007",
  "status": "completed",
  "verdict": "not_supported",
  "confidence": 0.86,
  "rules_verdict": "not_supported",
  "draft_verdict": "not_supported",
  "force_reasons": [],
  "composer": "deterministic",
  "criteria_results": [
    { "criterion_id": "infection", "result": "met", "method": "narrative", "evidence_ids": ["E1"] },
    { "criterion_id": "organ_dysfunction", "result": "not_met", "method": "mixed", "evidence_ids": ["E2", "E3"] }
  ],
  "evidence": [
    { "evidence_id": "E1", "side": "for", "criterion_id": "infection",
      "span": { "doc_id": "hp", "line_start": 2, "line_end": 4 }, "text": "verbatim span text" }
  ],
  "letter_markdown": "...",
  "dropped_sentences": 0,
  "source": "precomputed",
  "trace_id": "run_2026..."
}
```

- `status` enum: `completed`, `needs_review`. `verdict` is null when the verdict rule evaluates unknown.
- `result` enum per criterion: `met`, `not_met`, `unclear`. `source` enum: `precomputed`, `cached`, `live`.
- Cache lookup order for `POST /audit/{case_id}`: `data/precomputed/<case_id>.json` (committed, ships in the image), then `runs/cache/<case_id>.json` (runtime, ephemeral), else run live. Query param `?fresh=true` skips both caches; this is what the "run fresh analysis" button calls.

`POST /training/{case_id}/grade` request and response:

```json
{ "verdict": "supported", "selected_spans": [ { "doc_id": "pn_01", "line_start": 8, "line_end": 9 } ] }
```
```json
{
  "verdict_correct": false,
  "key_verdict": "not_supported",
  "evidence_score": 0.5,
  "missed_spans": [ { "span": { "doc_id": "pn_01", "line_start": 8, "line_end": 9 }, "criterion_id": "organ_dysfunction" } ],
  "extra_spans": [],
  "feedback": "2 to 3 sentence explanation referencing the key_rationale"
}
```
`evidence_score` = fraction of planted spans (correct side) intersected by at least one selected span. This is the only endpoint allowed to reveal answer-key content, and only after a submission.

## 9. Rationale letter format (composer output, markdown)

Exactly these sections, in order:

```
# Clinical validation finding: {display_name}
Case {case_id} | Status: {status} | Draft for auditor review

## Determination
One paragraph: the draft verdict and the single strongest reason.

## Evidence
A table with columns: #, For/Against, Source (doc_type + date), Lines, Excerpt.
Every row maps to an evidence_id. No row, no claim.

## Coding rationale
2 to 4 sentences referencing guideline sections as (source_id, section), in our own words. No long verbatim quotes.

## Reviewer note
Fixed text: "Machine-drafted aid generated from synthetic data. A qualified auditor makes the final determination."
```

## 10. Thresholds file (`evals/thresholds.yaml`)

```yaml
smoke_case_ids: [sepsis_001, sepsis_004, sepsis_007, sepsis_012, sepsis_015]
smoke:
  determination_accuracy: 0.80
  evidence_recall: 0.70
  citation_faithfulness: 0.95
full:
  determination_accuracy: 0.80
  evidence_recall: 0.70
  citation_faithfulness: 0.95
```

The five smoke case ids are frozen once generated (see section 6) so CI numbers are comparable across commits. `evals.run --enforce-thresholds` exits non-zero if any metric for the selected suite is below its threshold.
