# ML Analytics Implementation Roadmap

This roadmap follows the current-state evidence in [`ML_CURRENT_STATE.md`](ML_CURRENT_STATE.md) and the target design in [`ML_ANALYTICS_ARCHITECTURE.md`](ML_ANALYTICS_ARCHITECTURE.md). It does not select an algorithm, authorize training, or imply that a deployable model exists.

## Guiding gates

- Keep the existing rule-based analysis route operational and independently testable throughout.
- Do not enable the ML Analytics navigation item as a working page until real read APIs exist.
- Do not move from synthetic evaluation to operational claims without representative, governed security data and independently validated labels.
- Do not create alerts from ML output until shadow results, error behavior, authorization, and rollback have been reviewed.
- Treat each stage as a gate: if its exit criteria fail, stop and resolve the data or reliability issue before proceeding.

## Phases

### 0. Data and detection-policy readiness

**Work**

- Identify the first supported use case, entity scope, event sources, and consequence of an ML flag.
- Define what qualifies as a label, who may provide it, how analyst feedback maps to labels, and how inconclusive/unreviewed cases are handled.
- Obtain a sanitized representative event sample with source/time/user coverage and a documented retention/access policy. The committed 1,515-row synthetic fixture is insufficient for this gate.
- Define chronological, entity-aware evaluation windows and a final untouched holdout. Document deduplication, missing-field handling, and how history-derived features treat previously flagged events.
- Set operational review criteria with security analysts: acceptable false-positive workload, false-negative risk, evidence requirements, and an explicit decision process for later threshold/model selection.

**Exit criteria**

- Data provenance and label quality are documented and approved.
- The holdout cannot leak into feature fitting, preprocessing, or threshold tuning.
- Model choice and operating threshold remain open for a separate design decision informed by the resulting evaluation.

### 1. Backend lifecycle and data contracts

**Work**

- Design and review versioned records for model versions, training runs, evaluation results, and per-event ML detections.
- Add migrations only after the record design and retention/access requirements are approved.
- Define API schemas and versioning for model status, model versions, training history, evaluations, and detections. Include score semantics and detection method explicitly.
- Add authentication, authorization, and audit mechanisms before implementing training, promotion, or rollback endpoints. The repository currently lacks production RBAC.
- Define secure artifact storage, hash verification, trusted loading, feature-schema compatibility checks, and rollback metadata.

**Exit criteria**

- Contract tests cover status/unavailable/empty/error conditions and record ownership/scope.
- A model version can be tied to its artifact hash, code/dependency versions, feature schema, training snapshot, and evaluation.
- The existing rule-based alert API and stored evidence remain unchanged in meaning.

### 2. Reproducible data-quality and evaluation pipeline

**Work**

- Make dataset snapshots immutable or fingerprinted; report input rows, entities, time range, duplicates, excluded rows, missingness, label source, and class counts.
- Add train-only preprocessing, causal feature construction, schema validation, entity-boundary checks, and tests for timestamp ties and missing values.
- Use chronological/entity-aware train, validation, and untouched test splits. Tune parameters/thresholds on validation data only.
- Report confusion matrix, precision, recall, F1, false-positive rate, false-negative rate, denominators, and uncertainty where sample size permits. Include comparison to current rules and a non-ML reference.
- Test class imbalance handling and error cases; do not let synthetic scenario labels stand in for analyst-verified production labels.

**Exit criteria**

- A reviewer can reproduce a report from a named snapshot and code/dependency versions.
- Results include label provenance, class balance, temporal windows, threshold, per-entity coverage, and error counts.
- Data leakage checks pass and the test holdout has not been used to tune the candidate.

### 3. Candidate model training and artifact lifecycle

**Work**

- After a separate model-selection decision, train candidate(s) only from an approved snapshot with a versioned feature schema.
- Run training as a privileged background job with resource/time limits, cancellation, idempotency, sanitized logs, and immutable run records.
- Store candidate artifacts in trusted storage with integrity metadata; do not overwrite an existing version.
- Persist evaluation output before any model can be promoted. Keep a rejected candidate and its evaluation auditable without making it active.

**Exit criteria**

- Artifact can be loaded only from a registered trusted version and passes hash/schema/runtime compatibility checks.
- Training run, data snapshot, feature schema, artifact, and evaluation join without ambiguity.
- No automatic training on newly ingested or analyst-unreviewed events.

### 4. Shadow inference and operational observation

**Work**

- Add asynchronous inference for new events using a promoted candidate; do not block or fail event ingestion if inference is unavailable.
- Persist one idempotent detection record per event/version with score, threshold, mode, feature schema, and inference status.
- Start in shadow mode: do not create or update alerts. Keep rule-based behavior unchanged.
- Monitor latency, failure rate, missing/invalid features, score distributions, entity coverage, and disagreement with rule outputs. Treat these as observation data, not proof of detection quality.
- Define drift baselines and minimum sample windows before showing drift states.

**Exit criteria**

- Inference can be disabled or rolled back without affecting event ingestion or rule detection.
- Shadow outputs are traceable to event and model version; duplicate delivery does not duplicate detections.
- Security and analyst reviewers can sample disagreements and inspect only model-produced evidence.

### 5. Read-only ML Analytics workspace

**Work**

- Implement the React workspace against the read APIs from Phase 1, using the existing state-driven navigation and dark SOC design system.
- Show actual lifecycle, active version, training runs, evaluation records, and paginated detections.
- Label model decision score, threshold, rule risk score, and detection method separately. Display evaluation scope, labels, counts, and dates with metrics.
- Add loading, empty, stale, unavailable, and error states. Keep model training/promotion controls out of the UI until authorization, audit, and background-job behavior exist.
- Retain the disabled navigation state if the backend contracts are not available in the target environment; do not use static JSON as a production fallback.

**Exit criteria**

- Every displayed metric and status can be traced to a backend response and version/evaluation record.
- No model or metric is invented when the API is empty or unavailable.
- Review confirms responsive layout, authorization scope, accessibility, and no regression to Overview, Alerts, Events, or User Analytics.

### 6. Promotion and controlled alert integration (separate approval gate)

**Work**

- Review shadow performance against analyst labels, false-positive workload, false-negative risk, drift and reliability evidence.
- Only after an explicit operational approval, define whether ML creates alerts, contributes evidence to rule alerts, or remains advisory.
- Use explicit `detection_method` and `model_version`; keep anomaly score separate from the existing rule risk score.
- Add deduplication/correlation behavior, analyst review/feedback handling, model disable switch, rollback, and post-promotion monitoring.

**Exit criteria**

- Promotion/rollback is authorized and audited; prior known-good version is recoverable.
- Rule-only behavior remains available as a fallback and its meaning does not change.
- Analyst workflow documents how ML evidence is reviewed, corrected, and excluded from future training when appropriate.

## Cross-cutting verification

- Unit tests for features, temporal ordering, entity isolation, missing/invalid input, score semantics, and artifact compatibility.
- API tests for lifecycle, pagination, authorization, training-job transitions, artifact errors, and unavailable-model behavior.
- Evaluation tests for time leakage, label imbalance, metric denominators, and reproducibility.
- Integration tests showing ingestion succeeds when ML is disabled or failing and rule-based analysis remains unchanged.
- Security tests for unauthorized training/promotion, artifact tampering, poisoned/replayed events, sensitive log exposure, and audit completeness.
- Frontend verification that “No model,” “Training,” “Failed,” “Stale,” and API-unavailable states differ and never present fixture metrics as live values.

## Recommended next implementation milestone

Begin with **Phase 0 and the contract design in Phase 1**: secure a representative sanitized dataset and label policy, then agree on version/run/evaluation/detection records and read API schemas. Do not start with the ML page or model training; neither can be truthful or safely operated until its backend evidence and provenance exist.

