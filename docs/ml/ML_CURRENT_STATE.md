# ML Current State

**Inspection date:** 2026-11-03

**Scope:** repository inspection only. No model was trained, deployed, or changed for this assessment.

## Executive assessment

The repository contains an experimental, in-process Isolation Forest implementation, a seven-feature builder, and offline scripts that evaluate the detector against a committed synthetic dataset. These are research and smoke-test assets, not an operational ML service. There is no persisted trained model, ML inference route, model registry, training history, or stored ML detection record.

The active event-analysis route is rule-based. It reads a saved per-user baseline, assigns a 0–100 rule risk score, and may create or update an alert. It does not call the ML detector. ML Analytics remains a disabled “Planned / Not connected” navigation item in `frontend/src/layout/Sidebar.tsx`.

The current data supports code-path testing and exploratory comparison only. The committed test data is generated, small, and labeled from a few prearranged scenarios; its evaluation metrics do not establish performance on actual security telemetry.

## Existing ML-related files

| Path | Current responsibility | Status |
| --- | --- | --- |
| `backend/app/services/ml_anomaly.py` | Defines `MLAnomalyDetector`, an `IsolationForest` plus `StandardScaler`, seven fixed feature names, an in-memory `fit`, and `score`. | Functional library prototype; not wired into a route or event ingestion. The class and output explicitly call the result experimental. |
| `backend/app/services/ml_features.py` | Produces event-time features from strictly earlier history; includes database helpers for one-event features and historical training rows. | Functional feature helper. No application route currently calls its database helpers. |
| `backend/scripts/generate_synthetic_events.py` | Deterministically generates five synthetic users across 60 days, with normal events and injected unfamiliar-IP / unusual-hour cases. | Reproducible synthetic fixture generator. |
| `backend/scripts/evaluate_ml.py` | Runs a chronological per-user 80/20 train/test split, fits per-user detectors on normal training rows, and writes event-level and summary CSV/JSON reports. | Offline experiment only. Does not save a fitted model. |
| `backend/scripts/compare_contamination.py` | Repeats the synthetic evaluation with contamination settings 0.01, 0.02, 0.03, and 0.05. | Offline parameter comparison only. |
| `backend/scripts/reports/synthetic_events.csv` | Generated synthetic input with `user_id`, `event_time`, `event_type`, `source_ip`, and `scenario`. | 1,515 rows; not production telemetry. |
| `backend/scripts/reports/ml_evaluation.csv` | Event-level holdout output including scenario label, prediction, decision score, feature values, and training-row count. | 305 synthetic holdout rows; not an inference log from the application. |
| `backend/scripts/reports/ml_evaluation_summary.json` | Summary of the committed synthetic evaluation. | Static experiment output; no API exposes or refreshes it. |
| `backend/scripts/reports/contamination_comparison.json` | Static results from the four-setting synthetic comparison. | Static experiment output; not model-selection evidence for production. |
| `backend/tests/test_ml_anomaly.py` | Tests unfitted scoring rejection, too-small training input rejection, and a synthetic fit/score smoke path. | Unit-level smoke coverage; no saved-artifact, route, database, or live-event integration coverage. |
| `backend/tests/test_ml_features.py` | Tests feature construction, familiarity/frequency behavior, and that later events do not affect an earlier event's features. | Unit-level feature coverage; no test for mixed-user histories or online inference. |
| `backend/requirements.txt` | Lists `scikit-learn` without a pinned version. | Reproduction/versioning gap. |
| `UEBA_README.md` | States that ML development is paused and ML files are not part of the active workflow. | Consistent with the code and routes inspected. |

No serialized model files (`.pkl`, `.joblib`, `.onnx`, `.pt`, `.model`, or `.h5`) were found under `backend/app` or `backend/scripts`.

## Data and preprocessing

The committed synthetic dataset has 1,515 rows and five synthetic users. Its scenario labels are 1,485 `normal`, 15 `unfamiliar_ip`, and 15 `unusual_hour`. The generator uses a fixed random seed, a small set of ordinary IPs and event types, and places injected anomalies in selected late days. It does not represent customer telemetry, ingestion variability, missing fields, multiple data sources, real attack behavior, or production class prevalence.

The offline evaluator sorts events chronologically per user, reserves the final 20% for testing, and fits each per-user detector using rows labeled `normal` in the earlier partition. Feature values are built from prior history. It records synthetic scenario labels to compute a confusion matrix. The held-out set contains 30 labeled anomalies among 305 rows (about 9.8%), while the full generated set contains 30 among 1,515 (about 2.0%). Because anomaly scenarios are deliberately injected late, the holdout prevalence is not a representative production estimate.

The pipeline has useful initial safeguards: the detector checks feature dimensionality, minimum training rows, finite values, and that scoring follows fitting; feature calculations exclude events at or after the scored event time; the evaluation fits the scaler on training rows and uses it to transform test rows. Gaps include event-quality and provenance contracts, null/missing-field policy, deduplication rules for ML snapshots, data snapshots/hashes, multi-entity isolation guarantees in the pure feature helper, and a documented policy for excluding or handling suspicious historical events in future features.

## Feature engineering

`backend/app/services/ml_anomaly.py::FEATURE_NAMES` fixes the feature order to:

1. `hour_sin` and `hour_cos` — event time as a 24-hour UTC cycle.
2. `is_login` — whether the event type contains the text `login`.
3. `is_known_ip` — whether the event IP appeared in earlier history.
4. `is_known_event_type` — whether the event type appeared in earlier history.
5. `user_event_frequency` — `log1p` of earlier events in the prior 24 hours.
6. `source_ip_frequency` — `log1p` of prior occurrences of the event IP.

`backend/app/services/ml_features.py::features_for_event` delegates to the shared `backend/app/services/ml_feature_engine.py` implementation used by offline snapshots. It enforces same-user, strictly earlier history, canonical IP handling, aware UTC timestamps, and equal-time exclusion. These semantics are versioned as `ueba-seven-v2`; older feature snapshots are rejected by the experiment loader.

There is no feature selection/evaluation study or feature contribution/explanation implementation. `MLAnomalyDetector.score` returns the raw feature values and a scikit-learn decision function score. That score is explicitly not a probability. It does not return per-feature explanations. Rule reasons in `backend/app/services/anomaly.py` are produced by the separate rule engine and must not be presented as ML explanations.

## Training and evaluation evidence

The committed `ml_evaluation_summary.json` reports an Isolation Forest with 80/20 chronological splitting and contamination `0.05` over 305 synthetic held-out rows:

| Measure | Synthetic report value |
| --- | ---: |
| Actual anomalies | 30 |
| Predicted anomalies | 51 |
| True positives | 26 |
| False positives | 25 |
| False negatives | 4 |
| True negatives | 250 |
| Precision | 0.5098 |
| Recall | 0.8667 |
| F1 | 0.6420 |
| Accuracy | 0.9049 |

The report itself warns that synthetic metrics do not establish real-world security detection performance. The results imply 25 false alerts in this fixture; the high accuracy should not be used as a readiness argument in an imbalanced security workload. `contamination_comparison.json` reports different precision/recall tradeoffs across its four settings, all on the same synthetic design. None of these static results should be represented in a production UI as current model performance.

Training currently occurs only when the offline scripts instantiate and fit in-memory detectors. The scripts persist evaluation rows and summary reports, not model weights or fitted scalers. There is no production training window, scheduled or authorized training job, independent validation set, model promotion/deployment process, reproducible runtime lock, or rollback workflow.

## Detection boundary

The active endpoint is `POST /anomalies/analyze/{event_id}` in `backend/app/api/routes/anomalies.py`. It invokes `backend/app/services/anomaly.py::analyze_event`, which:

- requires an event with a user ID and an existing `UserProfile` baseline;
- adds fixed rule points for unfamiliar source IP, unfamiliar event type, and unfamiliar UTC login hour;
- maps the resulting rule risk score to severity;
- creates or updates an alert at the rule threshold; and
- stores `detection_method: "rule_based"` with rule reasons and baseline event count in alert evidence.

The route does not import `ml_anomaly.py` or `ml_features.py`. Event ingestion in `backend/app/api/routes/events.py` stores events but does not trigger ML training or inference. ML and rule-based detections are therefore separate today: only the latter is active, persisted as alerts, and exposed by the existing APIs.

## Readiness summary

| Capability | Assessment |
| --- | --- |
| Feature calculation | Prototype works for the fixed seven-feature schema; not production-hardened. |
| Fit and score | Works in memory when called directly; cannot load a deployed model because none is persisted. |
| Synthetic evaluation | Reproducible offline experiment with static synthetic-only metrics. |
| Real-data suitability | Not established. No sanitized representative corpus, independently reviewed labels, or production prevalence evidence was inspected. |
| Online inference | Not available. No inference route or ingestion integration. |
| ML result persistence | Not available. Current `Alert.evidence` represents the rule-based detection route. |
| Model lifecycle/versioning | Not available. No registry, artifact hash, training-run record, or version metadata. |
| Analyst UI data source | Not available. ML Analytics is intentionally disabled in the sidebar. |

