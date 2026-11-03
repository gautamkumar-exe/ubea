# User and Entity Behavior Analytics (UEBA) Platform

**College project report**

**Project:** UEBA Security Operations Platform with Experimental Offline Anomaly Analysis

**Implementation:** React and TypeScript frontend, FastAPI backend, PostgreSQL database

**ML feature specification:** `ueba-seven-v2`

> **Scope statement:** This report describes functionality verified in the repository. Rule-based anomaly analysis is the active alert-generation path. The Isolation Forest is an offline experiment and demonstration; it is not a production model or an operational alert source. All ML metrics in this report are from synthetic benchmark data.

## Abstract

Security teams receive events from identity, endpoint, application, and network systems. Reviewing raw records one by one makes it difficult to understand which activity is unusual for a particular user. This project implements a small User and Entity Behavior Analytics (UEBA) platform with a React SOC interface, a FastAPI service, and PostgreSQL storage. The application accepts and lists security events, builds per-user behavioral summaries, analyzes a selected event with explicit rules, stores qualifying alerts, and supports status updates and analyst feedback.

The project also contains an experimental offline machine-learning workflow. A shared point-in-time feature engine (`ueba-seven-v2`) builds seven behavioral features. A reproducible Isolation Forest workflow trains and evaluates on chronologically split synthetic data; a separate demonstration scores four controlled examples. The reported synthetic benchmark result at its fixed threshold is precision 0.5641, recall 0.8800, F1 0.6875, and false-positive rate 0.0881. These results are not estimates of production effectiveness. ML predictions do not currently create operational alerts.

## 1. Introduction

Security events record actions or observations. An alert is a triage item produced after an analysis policy decides an event merits attention. UEBA adds a subject-centered view: it summarizes activity associated with a user or entity and checks an event against observed behavior. This repository demonstrates an explainable rule-based workflow and supports investigation through the Overview, Security Alerts, Events, and User Analytics screens.

The implementation is an educational project and local development application. It has no authentication or authorization layer, so it should not be exposed as a public or production service.

## 2. Problem statement

Analysts need a way to ingest security events, inspect recent activity, compare a user's event with a baseline, and record an investigation outcome. Without a structured workflow, event data and findings can be scattered across tools, and repeated manual comparisons can be inconsistent. The project addresses this problem with event storage, simple behavioral summaries, deterministic rule checks, alerts, and an analyst-facing interface.

## 3. Project objectives

1. Store security events with source, event type, subject identifiers, source IP, event timestamp, and source metadata.
2. Summarize stored event behavior for a user in a baseline.
3. Analyze a selected event with documented, explainable rules.
4. Persist qualifying alerts and allow analysts to update their status and submit feedback.
5. Present alerts, events, baselines, and derived counts in a responsive SOC interface.
6. Build a reproducible, offline ML experiment using synthetic data without coupling its predictions to operational alerts.

## 4. Existing system and limitations

Traditional event review may rely on individual logs and fixed rules. Fixed rules are understandable but can miss activity not anticipated by a rule and can flag legitimate changes. A baseline can add user-specific context, but an all-history summary may be stale, poisoned, or include the event being investigated if rebuilt at the wrong time.

This project is an MVP. It does not provide identity management, authorization, source-specific ingestion adapters, a complete user directory, baseline aging, analyst identity verification, high availability, or production monitoring. Its ML data is a small generated benchmark, not representative security telemetry.

## 5. Proposed system

The implemented application combines:

- A React single-page interface with a persistent sidebar and Overview, Alerts, Events, and User Analytics pages.
- A FastAPI API for event ingestion/listing, baseline retrieval/rebuild, rule-based analysis, alert listing/detail/status, and analyst feedback.
- PostgreSQL persistence through SQLAlchemy models and Alembic migrations.
- A separate experimental offline ML toolchain for snapshots, feature building, Isolation Forest training, evaluation, and synthetic demonstrations.

The active rule path and experimental ML path are intentionally separate.

## 6. Functional requirements

| ID | Requirement | Implemented behavior |
| --- | --- | --- |
| FR-01 | Accept security events | `POST /events` validates fields and timezone-aware event time; repeated `(source, external_id)` submissions are idempotent. |
| FR-02 | Browse events | `GET /events` supports user ID, event type, and source filters with limit/offset pagination. |
| FR-03 | Build and retrieve baseline | `POST /baselines/{user_id}/rebuild` summarizes stored user events; `GET /baselines/{user_id}` retrieves it. |
| FR-04 | Analyze an event | `POST /anomalies/analyze/{event_id}` evaluates rule conditions against a saved user baseline. |
| FR-05 | Manage alerts | `GET /alerts` supports status, severity, user ID, limit, and offset; detail and status update routes are provided. |
| FR-06 | Record feedback | Feedback can be submitted and listed per alert using true-positive, false-positive, benign, or inconclusive verdicts. |
| FR-07 | Investigate through UI | Tables and dialogs expose alert/event evidence, status controls, feedback history, and baseline details. |
| FR-08 | Offline ML experiment | Scripts generate/validate snapshots, train/evaluate an experimental Isolation Forest, and demonstrate synthetic examples without calling the operational alert API. |

## 7. Non-functional requirements and project qualities

- **Understandability:** The rule detector returns individual reasons and a preliminary risk score.
- **Data integrity:** Event timestamps must include timezone information; `(source, external_id)` is unique in PostgreSQL.
- **Privacy in offline snapshots:** The ML snapshot pipeline uses namespace-separated HMAC pseudonyms and does not write to the source event database.
- **Reproducibility:** Synthetic fixtures, seeds, snapshot metadata, feature version, and experiment configuration are recorded.
- **Responsive usability:** The frontend provides responsive layouts and loading, error, empty, and retry states.
- **Limitations:** No authentication, authorization, or production hardening is implemented; no operational SLA is claimed.

## 8. Technology stack

| Layer | Technology in repository |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, CSS |
| API | Python 3.12, FastAPI, Pydantic |
| Persistence | PostgreSQL 16 Compose image, SQLAlchemy ORM, psycopg 3, Alembic |
| ML experiment | NumPy, scikit-learn (`StandardScaler`, `IsolationForest`), joblib |
| Test tools | pytest, FastAPI TestClient/httpx, disposable local PostgreSQL test cluster |
| Local services | Docker Compose for the application database |

No React Router or external AI provider is part of the application.

## 9. System architecture

The operational flow is a browser SPA calling FastAPI endpoints, which use SQLAlchemy sessions to read and write PostgreSQL. Event ingestion only stores the event; it does not automatically run the ML model. Rule analysis is an explicit API action.

```mermaid
flowchart LR
    Analyst[Analyst] --> UI[React + TypeScript SOC SPA]
    UI --> API[FastAPI]
    API --> Ingest[POST /events]
    API --> EventRead[GET /events]
    API --> BaselineAPI[GET /baselines and POST rebuild]
    API --> RuleAPI[POST /anomalies/analyze/{event_id}]
    API --> AlertAPI[GET/PATCH /alerts]
    API --> FeedbackAPI[POST/GET alert feedback]
    Ingest --> Events[(security_events)]
    EventRead --> Events
    BaselineAPI --> BaselineService[Behavioral baseline service]
    BaselineService --> Events
    BaselineService --> Profiles[(user_profiles)]
    RuleAPI --> RuleEngine[Rule-based anomaly service]
    RuleEngine --> Profiles
    RuleEngine --> Events
    RuleEngine --> AlertStore[(alerts)]
    AlertAPI --> AlertStore
    FeedbackAPI --> FeedbackStore[(analyst_feedback)]
    FeedbackStore --> AlertStore
    UI -->|displays| AlertAPI
    UI -->|displays| EventRead
    UI -->|displays| BaselineAPI
```

The separate offline ML workflow is detailed in [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md). It reads a snapshot and writes local experiment artifacts; it has no active connection to operational alert generation.

## 10. Backend architecture

`backend/app/main.py` creates the FastAPI application, configures local CORS origins, and includes the event, baseline, anomaly, alert, feedback, and demo-only ML routers. `backend/app/database.py` creates a SQLAlchemy engine/session factory from `backend/app/config.py`. Route handlers validate input with Pydantic, use SQLAlchemy models and commit state changes; the ML demo route does not use the database.

Key modules:

| Module | Responsibility |
| --- | --- |
| `app/api/routes/events.py` | Event ingestion, duplicate handling, filtered/paginated event listing. |
| `app/api/routes/baselines.py` | Retrieve or rebuild one user's saved baseline. |
| `app/services/baseline.py` | Aggregates all stored events for a user into counts and first/last-seen values. |
| `app/api/routes/anomalies.py` | Explicit rule analysis endpoint and alert persistence when risk reaches 30. |
| `app/services/anomaly.py` | Rule score, severity, reasons, and note. |
| `app/api/routes/alerts.py` | Alert listing, detail, and status update. |
| `app/api/routes/feedback.py` | Feedback submission and history for alerts. |
| `app/api/routes/ml_analytics.py`, `app/services/ml_analytics.py` | Read-only `GET /ml-analytics/demo` for the bundled synthetic demonstration and held-out benchmark evaluation. |
| `app/services/ml_dataset.py`, `ml_experiments.py` | Offline snapshot validation, training, evaluation, and local artifacts. |

## 11. Frontend architecture

`frontend/src/App.tsx` uses React component state to select the active page; navigation is not URL-router based. The sidebar exposes Overview, Security Alerts, User Analytics, Events, and a functional synthetic-only ML Analytics page. AI SOC Assistant remains “Planned / Not connected.” The feature components call functions in `frontend/src/api.ts`. The API base defaults to `http://127.0.0.1:8001` and can be overridden at build/dev time by `VITE_API_BASE_URL`.

| Component | Role |
| --- | --- |
| `OverviewFeature.tsx` | Global alert totals/severity counts and recent alert/event lists. Counts come from backend response totals; date filtering is not supported by the alert API. |
| `AlertsFeature.tsx`, `AlertDetailsDialog.tsx` | Alert filters/table, investigation evidence, status updates, feedback form/history. |
| `EventsFeature.tsx`, `EventDetailsDialog.tsx` | Supported event filters, pagination, event details, source metadata, and action to run explicit rule analysis. |
| `UserAnalyticsFeature.tsx` | User ID lookup from sampled event/alert results or typed input, saved baseline, rebuild, related alert/event activity, and rule-analysis result. |
| `MlAnalyticsFeature.tsx` | Calls the read-only demo endpoint on button click; presents model configuration, synthetic test metrics/confusion matrix, scenario breakdown, and four feature/score examples. |
| `Sidebar.tsx`, `PageHeader.tsx` | Global navigation, API status and page heading/refresh controls. |

User ID discovery is not a directory API: the UI samples up to the first 100 event records and first 100 alerts returned by their APIs. Baseline rebuild replaces the saved aggregate using every stored event for that user.

## 12. Database design

The SQLAlchemy models are in `backend/app/models/` and migrations are under `backend/migrations/versions/`.

| Table | Main fields and constraints | Purpose |
| --- | --- | --- |
| `security_events` | UUID `id`; `source`; nullable `external_id`; `event_type`; nullable `user_id`, `entity_id`, `source_ip`; timezone-aware `event_time`; JSON `raw_event`; `created_at`. Unique `(source, external_id)` and indexes for subject/time and type/time. | Source security event records. |
| `user_profiles` | UUID `id`; `entity_type`, `entity_id`; JSON `baseline`; optional `last_seen`; created/updated timestamps. Unique `(entity_type, entity_id)`. | Saved aggregate profile; event user IDs are not foreign keys to this table. |
| `alerts` | UUID `id`; nullable FK `event_id` (`ON DELETE SET NULL`); optional `user_id`; title, severity, 0–100 rule risk score, status, explanation, JSON evidence, timestamp. Check constraints on severity/status/score. | Investigative alert generated by current explicit rule analysis. |
| `analyst_feedback` | UUID `id`; required FK `alert_id` (`ON DELETE CASCADE`); analyst ID, verdict, optional comment, timestamp. | Analyst assessment history attached to an alert. |

There is no separate ML detection, experiment, or model registry table. Model artifacts and experiment metadata are local offline files.

## 13. Security event processing

`POST /events` accepts a source, external ID, event type, optional user/entity ID and source IP, timezone-aware event time, and JSON object. The schema trims strings, rejects blank required strings and naive timestamps, and forbids unrecognized input fields. PostgreSQL uniqueness on `(source, external_id)` makes repeat submissions return the existing event as a duplicate. Ingestion does not automatically create an alert.

`GET /events` returns newest-first event records and supports `user_id`, `event_type`, `source`, `limit` (1–100, default 20), and `offset`. The event details UI exposes `raw_event` only when an analyst expands the metadata section; synthetic examples should be used for screenshots.

## 14. Rule-based detection methodology

The endpoint `POST /anomalies/analyze/{event_id}` loads an existing event and its saved `user_profiles` baseline. It adds fixed rule points:

| Condition | Points |
| --- | ---: |
| Event source IP is not in the baseline's source IP counts | 40 |
| Event type is not in the baseline's event type counts | 25 |
| Login hour in UTC has not appeared in the baseline | 30 |

The score is capped at 100. Severity mapping is low below 30, medium from 30, high from 60, and critical from 80. `is_anomalous` is true for scores at least 30. At a score of 30 or higher, the route creates or updates an alert for that event. Evidence contains reasons, baseline event count, and `detection_method: "rule_based"`. This score is a simple rule-risk score, not an ML score or proof of malicious intent.

## 15. UEBA behavioral baseline methodology

`build_user_baseline` reads every stored event with the target `user_id`, ordered by event time. It saves total event count, event type counts, UTC login-hour counts, source-IP counts, number of active UTC dates, first seen, and last seen in `UserProfile.baseline`. It is an all-history summary: no lookback-window, decay, or baseline version is stored. Rebuilding replaces the JSON summary. For meaningful demo analysis, create baseline events first, rebuild, and then ingest/analyze the unusual event so the candidate event is not already included in the baseline.

## 16. Machine-learning methodology

The offline ML path consists of:

1. A read-only PostgreSQL extractor applies an inclusive cutoff for snapshot experiments. The separate demo page does not read PostgreSQL.
2. The snapshot builder deduplicates records, validates timestamps, pseudonymizes identifiers and valid IPs with namespace-separated HMAC, generates point-in-time features, and writes manifest/split metadata.
3. Chronological 70/15/15 split manifests keep equal-time records together. Snapshots must declare `development` or `test` provenance and feature version `ueba-seven-v2`; production and unclassified snapshots are rejected for training.
4. The experiment loader verifies snapshot digest, schema, feature order/version, provenance, and splits. The experiment fits `StandardScaler` and Isolation Forest on training features only. IDs, event times, and labels are not model inputs.
5. Validation and test partitions remain outside fitting. Snapshot experiments have no trustworthy ground-truth labels; supervised metrics remain unavailable. The checked-in synthetic benchmark has generated scenario labels for experiment-only evaluation.

`IsolationForest` is used because it is already implemented as an unsupervised experiment and the snapshot data has no trusted labels. Its tree-based random partition process can isolate points that differ from the fitted feature distribution with shorter paths. This project does not establish that it is the best algorithm. The local demo uses the fixed zero decision-function threshold (the library model's contamination-derived offset is fit on training data). Scores are not calibrated probabilities and the demo has no per-feature causal explanation.

### 16.1 Seven behavioral features (`ueba-seven-v2`)

| Feature | Meaning and transformation |
| --- | --- |
| `hour_sin` | Sine encoding of the target event's UTC hour on a daily cycle. |
| `hour_cos` | Cosine encoding of the same UTC hour; the pair avoids a discontinuity at midnight. |
| `is_login` | 1 when the trimmed/case-folded event type contains `login`; else 0. |
| `is_known_ip` | 1 when a valid normalized IP occurred in strictly earlier events for the same user; else 0. |
| `is_known_event_type` | 1 when the nonempty event type occurred in strictly earlier same-user history; else 0. |
| `user_event_frequency` | `log1p` of same-user deduplicated event count in the preceding 24 hours. |
| `source_ip_frequency` | `log1p` of earlier same-user event count for the normalized source IP. |

The shared engine enforces same-user history, excludes equal-time and future events, normalizes IP literals, and requires aware timestamps normalized to UTC. Missing or malformed IP-dependent inputs remain unavailable. The exact behavior and edge cases are in [ML_FEATURE_SPECIFICATION.md](../ml/ML_FEATURE_SPECIFICATION.md).

## 17. Dataset preparation and preprocessing

The committed benchmark is generated with a fixed seed and has five synthetic users and 1,515 records: 1,485 normal, 15 unfamiliar-IP, and 15 unusual-hour scenarios. Those scenario labels are used only for evaluation. They are excluded from the unsupervised fit. Temporal splitting and training-only scaling reduce train/test leakage; scenario placement late in the generated timeline creates a distribution shift, which is a limitation rather than a production sampling design.

Offline PostgreSQL snapshots use pseudonymous keys and aggregate quality reports. The experiment pipeline checks finite feature values and schema integrity, excludes invalid/incomplete feature vectors where required, records unlabeled counts, and does not assign a label to unknown events. Generated snapshot/model artifacts are local and should remain outside Git.

## 18. Model training and evaluation

The reproducible experiment records dataset/snapshot identity, source environment, feature version, model configuration, seed, software versions, threshold configuration, evaluation values, and artifact integrity hash. Synthetic benchmark evaluation reports supervised classification measures against synthetic scenario labels. Snapshot evaluation reports score distributions and anomaly counts/rates only.

At threshold `decision_function < 0`, the latest fixed synthetic benchmark run used contamination `0.05`, 100 estimators, and random state 42. Test confusion-matrix rows are actual `[normal, anomaly]`; columns are predicted `[normal, anomaly]`.

|  | Predicted normal | Predicted anomaly |
| --- | ---: | ---: |
| Actual normal | 176 (TN) | 17 (FP) |
| Actual anomaly | 3 (FN) | 22 (TP) |

| Metric | Synthetic test result |
| --- | ---: |
| Precision | 0.5641 |
| Recall | 0.8800 |
| F1 | 0.6875 |
| False-positive rate | 0.0881 (8.81%) |

Five-seed mean F1 was **0.7082** on the same synthetic benchmark design. The leave-one-user-out aggregate was precision **0.4630**, recall **1.0000**, F1 **0.6329**, and false-positive rate **15.0%**. These results show sensitivity to split, user, threshold, and synthetic scenario mix; they do not predict operational performance. Expanded analyses are in [ML_MODEL_QUALITY_REPORT.md](../ml/ML_MODEL_QUALITY_REPORT.md) and [ML_FEATURE_QUALITY_REPORT.md](../ml/ML_FEATURE_QUALITY_REPORT.md).

## 19. Demonstration output

The demo-only `GET /ml-analytics/demo` endpoint fits on the synthetic chronological training partition, scores a normal login, unusual login hour, unfamiliar source IP, and high-frequency login example, and evaluates the held-out synthetic test rows. The React page presents input fields, all seven features, decision score, prediction, benchmark metrics, and confusion matrix. This route does not read the event database or connect to the alert table. See [ML_DEMO_GUIDE.md](../ml/ML_DEMO_GUIDE.md).

## 20. Screenshots

Capture the real application with local synthetic or sanitized records only. Use the capture steps and filenames in [SCREENSHOT_CHECKLIST.md](SCREENSHOT_CHECKLIST.md). Place verified captures in `docs/submission/screenshots/`. These are explicit placeholders; no screenshot is represented as captured until a real image is added and reviewed.

| Capture | Placeholder |
| --- | --- |
| SOC Overview | `[Capture pending: screenshots/soc-overview.png]` |
| Security Alerts table and investigation details | `[Capture pending: screenshots/alert-investigation.png]` |
| Security Events table and details | `[Capture pending: screenshots/event-investigation.png]` |
| User Analytics baseline | `[Capture pending: screenshots/user-analytics-baseline.png]` |
| ML demo and evaluation | `[Capture pending: screenshots/ml-demonstration.png]` |
| System architecture | `[Capture pending: screenshots/system-architecture.png]` |

## 21. Limitations

1. No authentication, authorization, verified analyst identity, or production hardening.
2. Ingestion accepts the project's common schema; it does not include production source adapters or schema normalization.
3. Baselines use all stored history without point-in-time versioning, decay, or aging.
4. Current rules are simple fixed-point checks; legitimate behavior changes can raise false positives and unmodeled attacks can be missed.
5. No production events, real labels, or real-world prevalence were used for ML evaluation.
6. Synthetic labels are scenario labels, not independently adjudicated incident outcomes.
7. The synthetic benchmark is small and scenario mix shifts across time splits; results are unstable across thresholds/users/seeds.
8. Isolation Forest scores are not calibrated probabilities; no feature-attribution explanation is implemented.
9. No online ML inference route, model registry, deployment process, drift monitoring, or ML-generated operational alerts exist.
10. Local demo database credentials and permissive development configuration must not be used for public deployment.

## 22. Future scope

- Add authentication, role-based authorization, audit trails, and safer handling of analyst identity.
- Add validated source-specific ingestion schemas and deduplication/retention policy.
- Introduce point-in-time, time-windowed baseline versions with clear rebuild policy.
- Collect privacy-reviewed, representative data and a governed analyst outcome-labeling process.
- Expand evaluation to include scenario and user coverage, temporal validation, calibration only if justified, and cost-aware false-positive analysis.
- Consider a separately approved design for offline-to-shadow evaluation and model lifecycle governance. Any future model should remain separate from alerts until an explicit evaluation and operational approval process exists.
- Improve automated API/UI integration and deployment tests.

## 23. Conclusion

The project delivers a working local SOC workflow for event ingestion, user baselines, explicit rule analysis, alerts, investigation status, and analyst feedback. It also provides a reproducible offline Isolation Forest experiment using versioned point-in-time features. The separation is intentional: the rule engine powers operational alert behavior in this application, while ML remains a controlled educational experiment. Synthetic measurements are useful for demonstrating code paths and evaluation methods, but do not establish production readiness or real-world security effectiveness.

## 24. References

### Repository implementation and project documentation

- [`backend/app/main.py`](../../backend/app/main.py), API routers under [`backend/app/api/routes/`](../../backend/app/api/routes/), models under [`backend/app/models/`](../../backend/app/models/), and services under [`backend/app/services/`](../../backend/app/services/).
- [`backend/app/services/ml_feature_engine.py`](../../backend/app/services/ml_feature_engine.py), [`ml_dataset.py`](../../backend/app/services/ml_dataset.py), [`ml_experiments.py`](../../backend/app/services/ml_experiments.py), and [`backend/scripts/demo_ml_anomaly.py`](../../backend/scripts/demo_ml_anomaly.py).
- [ML feature specification](../ml/ML_FEATURE_SPECIFICATION.md), [dataset pipeline](../ml/ML_DATASET_PIPELINE.md), [training/evaluation](../ml/ML_TRAINING_AND_EVALUATION.md), [model quality report](../ml/ML_MODEL_QUALITY_REPORT.md), and [snapshot validation](../ml/ML_SNAPSHOT_EXPERIMENT_VALIDATION.md).

### Technical references

- [FastAPI Tutorial](https://fastapi.tiangolo.com/tutorial/) and [FastAPI first steps / OpenAPI docs](https://fastapi.tiangolo.com/tutorial/first-steps/).
- [React Learn](https://react.dev/learn) and [React with TypeScript](https://react.dev/learn/typescript).
- [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/).
- [Vite Guide](https://vite.dev/guide/).
- [SQLAlchemy 2.0 ORM documentation](https://docs.sqlalchemy.org/en/20/orm/index.html) and [PostgreSQL dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html).
- [PostgreSQL documentation](https://www.postgresql.org/docs/), including the [PostgreSQL 16 manual](https://www.postgresql.org/docs/16/).
- [scikit-learn IsolationForest API](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html) and [scikit-learn preprocessing API](https://scikit-learn.org/stable/modules/preprocessing.html).

