# UEBA Platform Viva Preparation

These sample answers describe this repository's current implementation. They distinguish active rule-based behavior from offline experimental ML.

## UEBA and SOC fundamentals

### 1. What is UEBA?

UEBA means User and Entity Behavior Analytics. It examines activity associated with users or other entities and compares current activity with a known pattern. In this project, user baselines summarize events, and a rule service checks selected events against those summaries.

### 2. What is a SOC?

A Security Operations Center is a team and process for monitoring, triaging, investigating, and responding to security events. This project demonstrates a small analyst interface for those steps; it is not a complete SOC platform.

### 3. What is a security event?

An event is an observation from a source, such as a login or file access. Here, events are stored in `security_events` and include source, event type, timestamp, optional subject/IP fields, and source JSON metadata.

### 4. How is an alert different from an event?

An event records activity. An alert is an investigation record that the current rule analysis creates when its score reaches 30. Not every event becomes an alert.

### 5. What happens during event ingestion?

`POST /events` validates the payload and requires a timezone-aware timestamp. It inserts the event unless `(source, external_id)` already exists, in which case it returns the existing record as a duplicate. Ingestion itself does not analyze the event.

### 6. What are false positives and false negatives?

A false positive is normal activity classified as anomalous. A false negative is anomalous activity classified as normal. The synthetic benchmark has 17 false positives and 3 false negatives in its test split at the documented setting.

### 7. Why do analysts need alert statuses?

Statuses show triage progress. This app supports `open`, `investigating`, `resolved`, and `dismissed`; the PATCH endpoint updates a stored alert's status.

## Backend and database

### 8. Why use FastAPI?

The repository uses FastAPI to define typed HTTP routes, validate request/response data with Pydantic, and expose interactive API documentation. The route handlers are in `backend/app/api/routes/`.

### 9. What does Pydantic do here?

Pydantic schemas validate API payloads and response shapes. For example, event ingestion rejects blank required strings and timestamps without timezone information.

### 10. Why PostgreSQL?

PostgreSQL is the relational store used for events, profiles, alerts, and feedback. It supports constraints such as unique source/external event IDs and alert status/severity checks.

### 11. What is SQLAlchemy's role?

SQLAlchemy maps Python model classes to database tables and manages database sessions/queries. Models are in `backend/app/models/`.

### 12. What is an Alembic migration?

It is a versioned schema change. The project stores migration scripts under `backend/migrations/versions/`; `alembic upgrade head` applies the current migration chain.

### 13. Is `user_id` a foreign key to `user_profiles`?

No. `user_profiles` has a unique `(entity_type, entity_id)` constraint, but `security_events.user_id` is a string without a foreign key. The baseline service locates the matching profile by values.

### 14. How are duplicate events handled?

The database has a unique constraint on `(source, external_id)`. The ingestion endpoint uses insert-on-conflict-do-nothing and returns the existing event for a duplicate pair.

### 15. What does the event listing API filter on?

`GET /events` supports `user_id`, `event_type`, and `source`, plus `limit` and `offset`. It returns the total count and the requested page.

### 16. What does the alert API filter on?

`GET /alerts` supports status, severity, user ID, limit, and offset. The frontend text search only applies to the records currently loaded in the page.

### 17. Does the app authenticate analysts?

No. Authentication and authorization are future work. Feedback currently accepts a client-supplied analyst ID, so that value is not verified identity.

## Behavioral baselines and rule analysis

### 18. What is a behavioral baseline?

A baseline is a summary of past events for a user. This service stores event type counts, UTC login-hour counts, source IP counts, event count, active days, and first/last-seen timestamps.

### 19. How is a baseline rebuilt?

`POST /baselines/{user_id}/rebuild` reads all stored events for that user, orders them by event time, computes counts, and replaces the JSON baseline in `user_profiles`.

### 20. Does the baseline use a rolling time window?

No. It currently summarizes all stored events, with no aging, decay, or window/version parameter. That makes baseline point-in-time handling an important limitation.

### 21. What checks are in the rule detector?

It adds 40 points for an unfamiliar IP, 25 for an unfamiliar event type, and 30 for a login at a UTC hour absent from the baseline. The score is capped at 100.

### 22. When does a rule result create an alert?

When the risk score is at least 30. The endpoint creates or updates an alert associated with the event, and the evidence includes `detection_method: "rule_based"`.

### 23. How is severity assigned?

The current service maps scores below 30 to low, 30–59 to medium, 60–79 to high, and 80 or above to critical.

### 24. Is a high rule score proof of an attack?

No. It means the event matched the implemented conditions. The API explicitly calls the result preliminary; an analyst must investigate context.

### 25. Does event ingestion automatically create an alert?

No. An analyst or caller must invoke `POST /anomalies/analyze/{event_id}` after the event is stored and a baseline is available.

## Features and machine learning

### 26. What is feature engineering?

It converts raw observations into measurable inputs for a model. This project converts event timestamp, event type, user history, and source IP into seven numeric features.

### 27. What are the seven features?

`hour_sin`, `hour_cos`, `is_login`, `is_known_ip`, `is_known_event_type`, `user_event_frequency`, and `source_ip_frequency`. The first pair encodes UTC hour cyclically; the flags represent event/familiarity; the final two are log-transformed prior event counts.

### 28. Why encode hour with sine and cosine?

Hours are circular: 23:00 and 00:00 are close in time. Sine/cosine coordinates represent that cycle without making midnight look far from late night.

### 29. How does the feature engine avoid future leakage?

It only uses events strictly earlier than the target event for history-derived features. Equal-timestamp peers and future events are excluded. Snapshot and event scoring paths share the versioned `ueba-seven-v2` implementation.

### 30. Why normalize IP addresses?

Equivalent IPv4/IPv6 strings can have different textual formats. Canonicalization lets history comparisons match consistently. In snapshots, valid IP values are pseudonymized rather than exposed in the sanitized dataset.

### 31. What is unsupervised learning?

It learns patterns from data without requiring a known normal/anomaly label for each training row. Isolation Forest is trained on feature vectors from the train split; synthetic scenario labels are reserved for evaluation.

### 32. Why was Isolation Forest chosen?

It was already present in the repository and is a practical unsupervised candidate for experimentation when real event labels are unavailable. The choice is not a claim that it is best or production-ready.

### 33. How does Isolation Forest work conceptually?

It builds randomized trees that repeatedly partition feature space. Points isolated in fewer splits have shorter path lengths and are treated as more unusual relative to the fitted data distribution.

### 34. What does contamination mean?

It is a model configuration parameter used to define the expected outlier fraction for the Isolation Forest decision boundary. It is not the true attack prevalence and the selected value changes anomaly decisions.

### 35. What is the model anomaly score?

The experiment uses scikit-learn's `decision_function`; the demonstration flags scores below zero. This is a decision value, not a calibrated probability or a measure of certainty.

### 36. Why is the scaler fitted only on training data?

If preprocessing learned means/scales from validation or test data, it would leak information about held-out periods into model fitting. The experiment fits the StandardScaler on training features and reuses it unchanged for later splits.

### 37. Why split chronologically?

The intended task is to learn from earlier activity and assess later activity. Chronological splits better reveal temporal leakage and scenario changes than random shuffling.

### 38. What are precision, recall, and F1?

Precision is the share of predicted anomalies that are labeled anomaly. Recall is the share of labeled anomalies detected. F1 is their harmonic mean. In a security setting, precision affects analyst workload and recall affects missed cases.

### 39. Explain this confusion matrix.

`[[176,17],[3,22]]` uses actual rows `[normal, anomaly]` and prediction columns `[normal, anomaly]`: 176 true negatives, 17 false positives, 3 false negatives, and 22 true positives.

### 40. What were the main synthetic benchmark metrics?

Precision 0.5641, recall 0.8800, F1 0.6875, and FPR 0.0881 at the fixed threshold, contamination 0.05, seed 42. These describe only a generated test split, not production.

### 41. What do five-seed and leave-one-user-out results tell us?

Five-seed mean F1 was 0.7082. Leave-one-user-out yielded precision 0.4630, recall 1.0000, F1 0.6329, and FPR 15.0%. Variation warns that results depend on seed and user profile and are not stable operating guarantees.

### 42. Why is the benchmark synthetic?

The committed benchmark is generated deterministically with a few known scenarios, making it useful for repeatable code-path and evaluation checks. It does not contain real-world security diversity or adjudicated incident outcomes.

### 43. Why not calculate precision/recall on the database snapshot?

The offline snapshot has no trustworthy event-level labels. Without ground truth, the pipeline reports anomaly-score distributions/counts; calculating supervised metrics would be misleading.

### 44. What is HMAC pseudonymization?

HMAC is a keyed hash. The snapshot pipeline applies namespace-separated HMAC tokens to identifiers and valid IP values so values can be linked within a snapshot without publishing the original values or key. It is pseudonymization, not a guarantee of anonymity.

### 45. Why does the snapshot record a key ID?

It lets local operators identify which pseudonymization-key version produced a snapshot and reason about rotations. The key ID is not secret key material; the HMAC key is never included in metadata.

### 46. How is dataset leakage reduced?

Identifiers, timestamps, and labels are excluded from model features. Splits are chronological, preprocessing/model fit uses the train partition only, validation is separate from final test, and point-in-time features exclude future/equal-time history.

### 47. What is still unknown about data readiness?

Representative production data quality, source coverage, event outcome linkage, true class prevalence, and analyst-label reliability have not been established. The snapshot pipeline's tests use synthetic fixtures.

## Frontend and project boundaries

### 48. Why React and TypeScript?

React builds the interface from reusable components and state. TypeScript gives the API client and UI static types for alert/event data and navigation state. Vite serves and builds this frontend.

### 49. How does page navigation work?

`App.tsx` stores the selected page in React state and renders the corresponding feature component. React Router is not used.

### 50. Why are ML Analytics and AI SOC Assistant disabled?

There is no ML metrics/detection API or AI assistant integration in the application. The sidebar labels these capabilities “Planned / Not connected” instead of implying functionality.

### 51. Why are ML predictions not connected to operational alerts?

The ML model and data are experimental and synthetic, with unstable threshold/user results and no validated production labels, lifecycle, inference API, or analyst governance. Connecting its output to alerts would overstate the evidence and risk disrupting the existing rule workflow.

### 52. What future work would be most important?

Add authentication/authorization; improve baseline time-window/versioning; gather privacy-reviewed representative data with governed outcomes; evaluate temporal/user generalization and false-positive costs; then separately design shadow inference and promotion controls if results justify it.

