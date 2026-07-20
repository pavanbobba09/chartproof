# ChartProof Production Readiness Audit

Date: 2026-07-18  
Scope: repository at `/Users/harsh/Documents/ChartProof`  
Mode: synthetic data only, read-only product review, no application fixes made

Update 2026-07-20: the bank was expanded after this audit to 100 synthetic records. Fifteen are independently generated scenarios and 85 are deterministic volume-test variants intended for UI, API, and load testing. The expanded bank improves volume coverage but does not resolve the clinical-diversity limitation or change the production release decision below.

## Release decision

| Intended use | Decision | Reason |
|---|---|---|
| Portfolio demonstration with synthetic cases | GO | Existing automated gates pass and the main demo workflows run successfully. |
| Internal prototype using synthetic or de-identified test data | CONDITIONAL | Suitable only with access restrictions, explicit non-clinical labeling, and no reliance on outputs for operational decisions. |
| Real-customer production, PHI, clinical validation, coding, denial, or payment use | NO-GO | Authentication, tenant isolation, PHI controls, clinical validation, durable auditability, operational safeguards, and production-grade failure handling are not implemented. |

ChartProof currently describes itself accurately as a synthetic educational demo. The following findings are the gap between that product and a real-customer production service.

## Test evidence

### Passed

| Area | Result |
|---|---|
| Backend unit and integration tests | 73 passed |
| Python lint | Passed |
| Frontend production build and TypeScript validation | Passed |
| Diff whitespace validation | Passed |
| Live smoke evaluation, 5 cases | Accuracy 1.000, evidence recall 1.000, citation faithfulness 1.000 |
| Full precomputed evaluation, 10 cases | Accuracy 1.000, evidence recall 0.818, citation faithfulness 1.000 |
| Case/key integrity | 10 of 10 load successfully; no dangling or out-of-range planted spans |
| Core API paths | Health, case list, known case, cached audit GET/POST, and training grade returned expected status codes |
| Basic input validation | Invalid verdict, negative line, and reversed span rejected with HTTP 422 |
| CORS | Configured localhost origin accepted; unconfigured external origin rejected |
| Cached-read concurrency | 100 requests with 20 workers all returned HTTP 200 in the local test environment |
| Production server route check | `/`, `/audit/sepsis_001`, and `/training/sepsis_001` served successfully from the production frontend build |

### Important interpretation

- The full-bank result has only 10 cases. Every case is sepsis, every case has exactly three documents, and every document has exactly 15 lines.
- The bank contains 8 clear and 2 borderline cases, split evenly between supported and not supported.
- Evidence recall is 0.50 for `sepsis_002`, 0.33 for `sepsis_005`, and 0.60 for `sepsis_009`.
- The deferral rate is 0.000. A human-review system that never defers on its entire test bank does not demonstrate safe uncertainty handling.
- Citation faithfulness is now grounded and much stronger than the old field-presence metric, but it is still deterministic, bank-specific validation rather than independent clinical adjudication.

### Not completed in this audit

- No tests used PHI or real customer records.
- No independent clinician or coding-auditor gold set exists.
- No automated browser, screen-reader, cross-browser, mobile-device, or visual-regression suite is installed.
- No sustained fresh-analysis load, soak, chaos, or multi-instance test exists.
- No container image build, image scan, penetration test, SAST, DAST, or SBOM generation was run.
- The npm advisory request could not be completed because sending workspace dependency metadata to the external advisory service was blocked by the execution policy. Python `pip-audit` is not installed. CI currently runs neither scanner.
- Coverage instrumentation is not installed, so passing test count should not be interpreted as line or branch coverage.

## P0 blockers for real-customer production

### P0-01: No identity, authorization, or tenant boundary

Evidence:

- The OpenAPI document advertises no security scheme.
- All case, audit, fresh-analysis, and grading endpoints are callable without a user identity.
- The repository explicitly lists no authentication or multi-tenancy as a known limitation.
- CORS restricts browser origins but is not an access-control mechanism. Direct HTTP clients remain unrestricted.

Customer impact:

- Any caller who can reach the API can enumerate cases, view charts, run expensive analysis, and retrieve training answers.
- Real customer records could be exposed across organizations because there is no ownership check.
- There is no attributable user identity for approvals, overrides, or audit history.

Required before production:

- Add authenticated users or service identities, tenant-scoped authorization, least-privilege roles, and server-side ownership checks on every record.
- Define separate roles for reviewers, trainers, administrators, and service accounts.
- Add negative authorization tests for cross-tenant reads, writes, ID enumeration, expired credentials, and privilege escalation.

### P0-02: The application is not designed or approved for PHI

Evidence:

- The API description, README, and project rules say synthetic data only and not for clinical or payment use.
- There is no documented PHI data flow, BAA posture, data residency control, retention/deletion policy, encryption/key management design, access review, breach process, or vendor inventory.
- The proposed free-tier Hugging Face and Vercel deployment is a demo topology, not a demonstrated healthcare production control environment.

Customer impact:

- Uploading real charts would exceed the application's stated data boundary.
- Privacy, regulatory, contractual, and incident-response requirements cannot be demonstrated.

Required before production:

- Complete a formal security/privacy architecture and legal/compliance review before accepting any PHI.
- Document every processor, storage location, model, log, cache, backup, and network path.
- Implement encryption, key rotation, access logging, retention, deletion, export, and incident-response controls appropriate to the approved use.

### P0-03: Clinical logic and confidence are not independently validated

Evidence:

- The product supports one diagnosis with simplified educational criteria.
- Narrative resolution uses a fixed keyword lexicon designed for the synthetic charts.
- Missing vasopressor or altered-mentation language is treated as `not_met` rather than unknown in `backend/pipeline/evidence.py`.
- The value called `llm_verdict` is a deterministic evidence-count heuristic and can fall back to the rules verdict in `backend/pipeline/compose.py`.
- Confidence starts at a fixed 0.85 and applies hand-written deductions in `backend/pipeline/qa.py`; it is not calibrated against an external population.
- The full ten-case bank produced zero review deferrals.

Customer impact:

- Missing documentation can be interpreted as negative evidence.
- Agreement and confidence can look more independent or statistically meaningful than they are.
- Performance on templated synthetic cases cannot establish safety or accuracy on real, incomplete, contradictory, longitudinal charts.

Required before production:

- Rename fields so they describe the actual implementation, or implement a genuinely independent second assessment.
- Treat absent documentation as unknown unless the criterion explicitly defines absence as negative.
- Version every criterion and guideline, require domain-owner approval, and record the exact version used for each audit.
- Build an independently adjudicated, representative test set with out-of-distribution, missing-data, contradictory, multilingual, copy-forward, unit-variation, and temporal edge cases.
- Calibrate confidence and deferral thresholds on held-out data. Report sensitivity, specificity, precision, recall, subgroup performance, and reviewer-overturn rates with confidence intervals.

### P0-04: No durable system of record or trustworthy audit trail

Evidence:

- Cases, answer keys, precomputed results, runtime caches, and traces are files rather than tenant-scoped records in a transactional store.
- Runtime files are described as ephemeral in the container design.
- Cache and trace writes use direct `write_text` calls without transactions, atomic replacement, locking, record versioning, or integrity signatures.
- Trace IDs have only second precision. Two IDs generated for the same case in one second were identical in the adversarial check.
- The final API result omits the QA `force_reasons`, reviewer identity, approval state, override reason, and record revision.

Customer impact:

- Concurrent runs can overwrite traces or cache files.
- A customer cannot reliably reconstruct who saw what data, which rule version ran, why review was required, or who approved the final outcome.
- Restart, rollback, backup, retention, and legal-hold behavior is undefined.

Required before production:

- Use a durable transactional store with immutable run IDs, tenant ownership, timestamps, versioned inputs/outputs, and append-only decision events.
- Add atomicity, concurrency control, backup/restore drills, retention policies, and tamper-evident audit logging.
- Persist reviewer actions, force reasons, overrides, and the exact model, rule, guideline, and code version.

### P0-05: Expensive endpoints have no abuse or capacity controls

Evidence:

- `POST /audit/{case_id}?fresh=true` is public and can run embeddings, retrieval, pipeline logic, trace writes, and cache writes.
- There is no rate limit, quota, concurrency limit, queue, request body limit, timeout, cancellation, or circuit breaker.
- The Docker command starts one Uvicorn worker and defines no server timeouts or resource policy.
- `/health` always returns `ok` and does not verify the case bank, guideline index, Chroma collection, writable storage, or required configuration.

Customer impact:

- A small number of clients can exhaust CPU, memory, file descriptors, provider quota, or disk.
- A process can appear healthy while unable to serve fresh audits.
- Repeated client retries can amplify an outage.

Required before production:

- Add per-user and per-tenant quotas, bounded concurrency, body-size limits, request deadlines, cancellation, backpressure, and idempotency.
- Separate liveness, readiness, and dependency-health checks.
- Load test cached and fresh paths at expected and overload traffic. Verify graceful degradation, recovery, and fair tenant isolation.

## P1 high-priority findings

### P1-01: Training evidence scoring can be gamed with oversized spans

Observed behavior:

- A request selecting lines `1-1000000` for each target document received an evidence score of 1.0 with no extras.
- A span naming a document that does not exist was accepted and graded instead of rejected.

Cause:

- `TrainingGradeRequest` validates only positive ordered line numbers.
- `grade_submission` awards credit when a selected range intersects planted evidence but does not verify that the document exists, the range is within the chart, the excerpt is reasonably bounded, or the selection came from the submitted chart revision.

Improvement:

- Validate every selected span against the current case document and line count.
- Enforce a reasonable maximum span length and request item count.
- Deduplicate spans and reject stale case revisions.
- Add adversarial tests for huge ranges, unknown documents, duplicates, overlapping ranges, empty documents, and excessive payloads.

### P1-02: Core clinical schemas accept malformed records

Observed behavior:

A constructed case was accepted with duplicate document IDs, invalid date strings, empty document lines, an unknown metric, a nonsense unit, invalid observation datetime, an empty ICD-10 value, and an empty DRG.

Cause:

- Dates and datetimes are plain strings.
- Canonical metric sets exist but are not enforced.
- Units, code formats, uniqueness, non-empty values, finite numeric values, and chronology are not validated.
- Pydantic models do not consistently reject unknown fields.

Improvement:

- Enforce typed dates/times with timezone policy, canonical metrics and units, finite physiological bounds, unique document IDs, non-empty lines/codes, code formats, and chronological consistency.
- Reject unexpected fields at external boundaries.
- Add contract tests for missing, duplicate, malformed, extreme, NaN/infinity, mixed-unit, timezone, and daylight-saving inputs.

### P1-03: Internal exception details are returned to clients

Observed behavior:

- A synthetic exception containing `/fake/internal/path/secret.db` was returned in the HTTP 500 body as `audit failed: /fake/internal/path/secret.db`.

Customer impact:

- Real exceptions can disclose filesystem paths, provider messages, internal configuration, or sensitive record context.

Improvement:

- Return a stable public error code and request ID. Log sanitized structured details server-side.
- Add tests proving secrets, paths, chart text, tokens, and stack details never appear in client errors.

### P1-04: Cache behavior can hide a fresh result

Evidence:

- Non-fresh loads check precomputed results before runtime cache results.
- A fresh run writes the runtime cache, but the next normal GET will still return the older precomputed file when both exist.

Customer impact:

- The UI can show a new result immediately after a fresh run and then revert to an older result after reload.

Improvement:

- Define explicit cache/version semantics. Prefer the requested immutable run, or use a versioned latest pointer with timestamps and provenance.
- Add tests for fresh-run reload, concurrent refresh, stale cache, failed refresh, and deployment rollback.

### P1-05: Production observability is absent

Evidence:

- No structured logging contract, metrics exporter, distributed tracing, alerting, dashboards, SLOs, runbooks, or request IDs are implemented.
- Current trace files are local debug artifacts and can collide.

Improvement:

- Define SLIs for latency, availability, error rate, queue depth, deferral, citation rejection, evidence recall proxies, dependency failures, and reviewer overrides.
- Add redaction-aware structured logs, immutable correlation IDs, alerts, dashboards, on-call runbooks, and synthetic probes.
- Prove that logs and telemetry do not contain PHI unless explicitly approved and protected.

### P1-06: Frontend resilience and accessibility are incomplete

Evidence:

- API requests have no timeout, cancellation, retry policy, or request correlation.
- Raw API response bodies can be displayed to users.
- Clickable chart lines are `<li>` elements with mouse handlers but no keyboard behavior, focusability, selected state, or accessible name.
- Clickable evidence rows are `<tr>` elements with the same mouse-only behavior.
- Invalid dynamic case routes return an initial HTTP 200 client shell and show an error only after browser-side loading.
- Only the first missed training span is highlighted.

Improvement:

- Add abortable requests, carefully bounded retries for safe operations, clear failure states, cold-start progress, and offline/reconnect behavior.
- Use semantic buttons/links or implement full keyboard and ARIA behavior.
- Add automated accessibility, keyboard, browser, mobile, slow-network, API-down, 404, 422, 429, 500, 503, and double-submit tests.

### P1-07: The evaluation bank is too small and regular

Evidence:

- 10 sepsis-only cases, 30 total documents, and every document is exactly 15 lines.
- Only three document types appear in the bank.
- Three cases have evidence recall below 0.70 even though aggregate recall passes.
- No deferrals occur.

Improvement:

- Expand case volume, diagnoses, sites, note types, lengths, writing styles, demographics, missingness, contradictory evidence, duplicate/copy-forward text, malformed inputs, units, and longitudinal complexity.
- Add per-case and subgroup minimums so aggregate metrics cannot hide severe local misses.
- Keep training, validation, and held-out test cases independent and prevent answer-key leakage into tuning.

### P1-08: Deployment and supply-chain controls are demo-grade

Evidence:

- The Python base image uses a mutable tag rather than a digest.
- Python requirements use broad ranges and have no resolved lock with hashes.
- Build tools remain in the runtime image.
- The image has no Docker `HEALTHCHECK` and no explicit read-only filesystem or dropped-capability policy.
- GitHub Actions are referenced by mutable major tags rather than commit SHAs.
- Deployment force-pushes the Space branch.
- A missing deployment token exits successfully, so CI can be green without a deployment.
- CI has no dependency scan, secret scan, static security scan, container scan, provenance, signing, or SBOM.

Improvement:

- Pin and lock dependencies, pin images and actions by digest/SHA, use a minimal multi-stage runtime, scan artifacts, generate an SBOM, sign releases, and verify provenance.
- Make deployment status truthful and use immutable artifacts with explicit promotion and rollback.
- Add a post-deploy readiness and synthetic-journey gate.

## P2 maintainability and product findings

### P2-01: API lifecycle controls are missing

- No API versioning, pagination, idempotency key, request ID, deprecation policy, compatibility tests, or documented error schema.
- Case IDs are interpolated directly into file paths rather than validated against a strict identifier format.
- Add a versioned contract and generated client compatibility tests before external integrations exist.

### P2-02: Review rationale is not fully exposed

- QA computes `force_reasons`, but `AuditResult` does not return them.
- Reviewers see rules and draft labels without a clear explanation of why the case was deferred or how confidence was calculated.
- Expose reviewer-safe reason codes and provenance while avoiding misleading labels such as `llm_verdict` for a deterministic heuristic.

### P2-03: Product/legal readiness is incomplete

- There is no repository license, customer terms, privacy notice, support policy, availability commitment, data-processing documentation, accessibility statement, or model/criteria change policy.
- These are acceptable omissions for a portfolio demo but must be settled before customer use.

### P2-04: Dependency deprecation warnings need ownership

- Tests report a Starlette/FastAPI TestClient deprecation warning related to `httpx` compatibility.
- LangGraph reports a pending default change for serialized allowed objects.
- Pin compatible versions and resolve warnings before they become breaking upgrades.

## Recommended implementation order

1. Freeze the current scope as synthetic demo only and prevent PHI ingestion.
2. Define the real production use case, accountable decision owner, regulatory boundary, and acceptable failure modes.
3. Design identity, tenant isolation, durable storage, audit history, privacy, and threat model together.
4. Fix external validation, the grading-span exploit, error disclosure, trace uniqueness, and cache semantics.
5. Replace misleading QA terminology, validate criteria with domain experts, and create an independent adjudicated evaluation set.
6. Add rate limits, queues, deadlines, readiness, observability, backups, and operational runbooks.
7. Add frontend accessibility, browser journeys, failure-state tests, and load/chaos testing.
8. Harden CI, dependencies, container artifacts, deployment promotion, rollback, and post-deploy verification.
9. Run security, privacy, accessibility, clinical-safety, and disaster-recovery reviews before any customer pilot.

## Minimum production acceptance suite to add

### API and security

- Authentication and authorization matrix, including cross-tenant denial.
- Object enumeration, path manipulation, oversized payload, malformed JSON, duplicate fields, and content-type tests.
- Rate-limit, quota, timeout, cancellation, idempotency, and replay tests.
- Secret/PHI redaction tests for responses, logs, traces, metrics, and error reporting.

### Clinical and data quality

- Exact threshold boundary tests and unit conversion tests for every structured rule.
- Missing, late, duplicated, corrected, out-of-order, and conflicting observation tests.
- Copy-forward, negation, hypothetical, family-history, ruled-out, and resolved-condition language tests.
- Independent clinician/coding-auditor adjudication and disagreement analysis.
- Calibration, subgroup, out-of-distribution, and deferral-safety evaluation.

### Reliability

- Cached and fresh load tests, sustained soak tests, and burst tests.
- Concurrent same-case runs, cache corruption, partial write, disk-full, dependency timeout, and process-restart tests.
- Backup restore, region failure, rollback, and recovery-time/recovery-point drills.

### Frontend

- End-to-end journeys for case list, audit review, fresh analysis, evidence jump, training selection, grading, and all error states.
- Keyboard-only and screen-reader tests, automated accessibility scans, browser matrix, mobile layout, zoom, and reduced-motion checks.
- Slow network, offline, refresh during submission, duplicate clicks, stale data, and session-expiry tests.

### Deployment

- Reproducible container build, vulnerability policy, SBOM, signing, provenance, and secret scanning.
- Pre-production migration, smoke, canary, post-deploy synthetic journey, rollback, and readiness checks.

## Final assessment

The repaired evidence-side logic, time-series behavior, and grounded citation-faithfulness checks are verified by the current regression suite. They are meaningful improvements to the demo. They do not make the application ready for real-customer or clinical production. The safest current release posture is a clearly labeled synthetic portfolio demo while the P0 architecture and validation work is designed explicitly for the intended production use.
