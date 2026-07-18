# ChartProof: clinical chart validation with a training mode

A portfolio-grade demo of an AI copilot for inpatient clinical chart validation (CCV) audits, built entirely on free software and 100% synthetic data. It reads an inpatient chart, checks a billed diagnosis against published clinical criteria, gathers evidence with pinpoint citations, drafts the audit determination and rationale letter, and routes uncertain cases to a human. A training mode uses the same case bank to quiz trainee auditors and grade them against known answer keys.

Built by Sai Pavan Tej Bobba as a targeted project for a healthcare payment integrity company (Cotiviti-style CCV team). The framing everywhere is auditor-assist: the tool drafts, a human decides.

## Domain context (read this before touching code)

- Hospitals bill insurers with ICD-10 diagnosis codes that map to a DRG (Diagnosis Related Group), which sets the payment amount. Higher-severity diagnoses (sepsis vs simple UTI) pay significantly more.
- Payment integrity auditors (nurses and certified coders) read the medical chart to verify the billed diagnosis is clinically supported. This is called clinical validation. The classic audit targets are sepsis, severe malnutrition, acute respiratory failure, encephalopathy, and acute kidney injury.
- A finding of "not clinically supported" can be appealed by the provider, so findings must cite exact chart evidence and coding guidelines to be defensible.
- Auditor pain points this tool addresses: slow evidence gathering, inconsistency between auditors, long new-hire ramp-up, and QA teams manually re-reviewing samples.

## What v1 does

1. Loads a synthetic inpatient chart (H&P, dated progress notes, labs, vitals, discharge summary) plus the billed codes.
2. Evaluates the billed target diagnosis against a criteria file (YAML) encoding published clinical criteria.
3. Retrieves evidence for and against each criterion from the chart, with citations down to document and line range.
4. Produces: a determination draft (supported / not_supported / needs_review), an evidence table, and a rationale letter draft that references ICD-10-CM Official Guidelines sections.
5. QA gate: compares the deterministic rules verdict with the LLM verdict and computes a confidence score. Disagreement or low confidence forces status needs_review.
6. Training mode: shows a chart with no answers, lets a trainee mark a verdict and select evidence lines, grades against the hidden answer key, and highlights missed evidence.
7. Eval harness: runs the full case bank and reports determination accuracy, evidence recall, and citation faithfulness.

## What v1 explicitly does NOT do (non-goals)

- No real patient data, ever. No PHI, no EHR integration, no MIMIC. Every chart is generated.
- No automated denials. Outputs are drafts with review status. Never present the tool as making payment decisions.
- Not clinical advice. Criteria files are simplified demo encodings with source notes, labeled not for clinical use.
- No auth or multi-tenancy in v1 (public demo). Note this as a known limitation in the README.
- v1 covers sepsis only. Malnutrition and AKI are stretch goals (see TASKS.md).

## Architecture

```
Chart generator (Groq)          Reference corpus (public PDFs)
        |                                  |
        v                                  v
   Chart bank  ------------------>  ChromaDB index (local HF embeddings)
 (JSON cases + hidden answer keys)         |
                                           v
                              LangGraph pipeline (FastAPI backend)
                    evidence agents -> composer
                    rules engine    -> QA gate
                                           |
                     +---------------------+---------------------+
                     v                     v                     v
              evidence table       rationale letter        review flag
                     \_____________________|____________________/
                                           v
                     Next.js frontend (Vercel) + FastAPI on HF Spaces
                          audit mode        training mode
```

## Components

### 1. Chart generator (`data/generate.py`)
- Calls the Groq API to generate one case at a time from a spec: target dx, intended verdict (supported / not_supported), difficulty (clear / borderline).
- The verdict is decided BEFORE generation. The prompt instructs the model to write a chart consistent with that verdict, and to output the planted evidence spans that justify it. This gives every case a free ground-truth label.
- Validates output against the pydantic schema in DATA_SPEC.md, runs a consistency checker (labs referenced in notes must exist in the labs table, line references in the answer key must exist), and regenerates on failure.
- Caches raw generations under `data/raw/` so reruns don't burn rate limits.

### 2. Reference corpus (`data/guidelines/`)
- Public documents only: ICD-10-CM Official Guidelines (CDC/CMS PDF), plus criteria summaries for target diagnoses (Sepsis-3, GLIM/ASPEN, KDIGO), stored as extracted text with a `manifest.json` recording source and URL.
- Text extraction with pypdf. Keep section headers so citations can name the section.

### 3. Index (`backend/index/`)
- ChromaDB, local persistent client. Embeddings: `sentence-transformers/all-MiniLM-L6-v2` (free, local).
- One collection for guidelines, one collection per case for chart chunks.
- Chart chunking: 3 to 5 lines per chunk with 1 line overlap, metadata `{case_id, doc_id, doc_type, date, line_start, line_end}`. Guideline chunks carry `{source, section}`.
- Index is built at Docker image build time so the deployed app cold-starts fast.

### 4. Rules engine (`backend/rules/`)
- Pure Python, zero LLM calls. Loads `data/criteria/<dx>.yaml`.
- Structured criteria (lactate threshold, MAP threshold, creatinine rise) are checked numerically against the labs and vitals tables.
- Narrative criteria (infection documented?) are delegated to the evidence agents and resolved from their findings.
- Emits a rules verdict plus a per-criterion breakdown.

### 5. LangGraph pipeline (`backend/pipeline/`)
Nodes, in order:
- `intake`: load case, load criteria, plan which criteria need retrieval.
- `evidence`: for each narrative or contested criterion, query the case collection for evidence FOR and AGAINST. Every evidence item carries a span `{doc_id, line_start, line_end}` and the verbatim span text.
- `rules`: run the rules engine with structured data plus resolved narrative criteria.
- `compose`: LLM (Groq) writes the determination and rationale letter. Hard constraint enforced in code: the composer receives only numbered evidence items and may reference only those IDs. Any sentence whose evidence ID is missing or invalid is dropped before output. Guideline citations come from the guidelines collection.
- `qa_gate`: compare rules verdict vs LLM verdict, compute confidence. Disagreement, low confidence, or any dropped-sentence event forces `needs_review`.
- Persist the full trace (inputs, retrievals, prompts, outputs) per run under `runs/` for debuggability and for the demo's "show your work" view.

### 6. API (`backend/app.py`, FastAPI)
- `GET /health`
- `GET /cases` (id, dx, difficulty; never expose answer keys)
- `POST /audit/{case_id}` runs the pipeline (or returns cached result if present)
- `GET /audit/{case_id}` returns the cached result
- `POST /training/{case_id}/grade` accepts `{verdict, selected_spans[]}`, grades against the answer key server-side, returns score plus missed evidence
- CORS restricted to the Vercel domain plus localhost (see DEPLOYMENT.md)

### 7. Frontend (`frontend/`, Next.js on Vercel)
- Audit mode: case picker, chart viewer with line numbers, evidence table where clicking a citation scrolls to and highlights the span, letter preview, status badge.
- Training mode: chart viewer, verdict buttons, click-to-select evidence lines, submit, graded result with missed evidence highlighted.
- Precomputed results for all bundled cases load instantly; a "run fresh analysis" button triggers a live pipeline run (`POST /audit/{case_id}?fresh=true`).
- Routes: `/` (case list with dx, difficulty, run status), `/audit/[caseId]`, `/training/[caseId]`. All API fetches use `cache: "no-store"`. Response shapes are fixed in DATA_SPEC.md section 8.

### 8. Eval harness (`evals/`)
Metrics, computed against answer keys:
- Determination accuracy: predicted verdict == key verdict (needs_review counts as wrong for accuracy but is tracked separately as the deferral rate).
- Evidence recall: fraction of planted evidence spans (for the correct side) that intersect at least one cited span.
- Citation faithfulness: for each output claim, does the cited span actually support it? Checked with a Groq LLM judge; deterministic pre-check that the span text is non-empty and the ID is valid.
Suites: `smoke` (5 fixed cases, runs in CI) and `full` (whole bank, run manually or nightly). Thresholds live in `evals/thresholds.yaml`: smoke accuracy >= 0.8, faithfulness >= 0.95, recall >= 0.7. CI fails below thresholds.

## Tech stack (all free)

Python 3.11, FastAPI, LangGraph, LangChain core, ChromaDB, sentence-transformers, PyYAML, pydantic v2, pypdf, pytest, ruff. LLM: Groq free tier (default model set by `GROQ_MODEL` env var; pick the best free Llama at build time). Frontend: Next.js 14+, TypeScript, Tailwind. Hosting: Hugging Face Spaces (Docker) plus Vercel Hobby. CI: GitHub Actions.

## Success criteria

- Live demo link that works from a phone.
- README with architecture diagram, eval results table, and a 2 minute demo video link.
- CI badge green: evals run on every push, deploy auto-syncs to the Space.
- A cold reader can go from clone to running locally with the commands in CLAUDE.md in under 10 minutes.

## Glossary

- CCV: clinical chart validation.
- DRG: Diagnosis Related Group, the payment grouping for an inpatient stay.
- Determination: the audit conclusion for a billed diagnosis.
- Rationale letter: the written justification sent to a provider explaining a finding.
- Planted evidence: spans the generator wrote specifically to justify the case's ground-truth verdict.
