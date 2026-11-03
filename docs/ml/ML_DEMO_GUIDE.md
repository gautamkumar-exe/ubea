# UEBA ML Demonstration Guide

## Purpose and boundaries

This guide runs the experimental UEBA feature and anomaly-scoring workflow locally using only the committed synthetic benchmark fixture and additional in-memory synthetic events. The `GET /ml-analytics/demo` endpoint and ML Analytics page expose this same computation. The endpoint does not query a database, accept caller-provided paths or commands, send data externally, change operational rule-based detection, or connect model predictions to alerts. Every demonstration result is synthetic and is not production performance.

The implementation uses the shared feature specification `ueba-seven-v2` in `backend/app/services/ml_feature_engine.py`, exposed through `ml_features.py` and the snapshot builder. The demo trains an Isolation Forest using only the fixture's chronological training feature vectors. The benchmark's scenario labels are not passed to model fitting. Four new example events are then converted with the same v2 event feature function and scored.

## Architecture

1. The dataset pipeline reads security-event fields, applies deterministic point-in-time feature generation and privacy controls, and writes versioned offline snapshots. See [ML_DATASET_PIPELINE.md](ML_DATASET_PIPELINE.md).
2. The experiment code validates snapshot schema/version/splits or loads the explicitly synthetic benchmark, fits preprocessing and Isolation Forest on training rows only, then evaluates held-out rows. Snapshot experiments have no trustworthy event-level labels and therefore report score distributions and anomaly counts rather than supervised metrics. See [ML_TRAINING_AND_EVALUATION.md](ML_TRAINING_AND_EVALUATION.md).
3. `backend/app/services/ml_analytics.py` trains from the benchmark's chronological train split, scores four controlled events using `features_for_event`, and evaluates the model on the held-out synthetic test split. The script `backend/scripts/demo_ml_anomaly.py` and read-only `GET /ml-analytics/demo` API call this service. The endpoint reads a fixed bundled fixture, returns data in memory, and writes no experiment files. The model decision is `decision_function < 0` with the configured detector contamination.

Isolation Forest is retained because this project has no trusted event-level labels for snapshot data, and it is already implemented as an unsupervised experimental candidate. This is a practical demonstration choice, not evidence that it is the best algorithm or suitable for production. Contamination and the decision threshold strongly affect results; see the quality reports.

## Seven behavioral features

Feature order is fixed by `backend/app/services/ml_anomaly.py::FEATURE_NAMES`:

| Feature | Meaning |
| --- | --- |
| `hour_sin` | Sine encoding of the event's UTC hour on a 24-hour cycle. |
| `hour_cos` | Cosine encoding of the event's UTC hour on the same cycle. |
| `is_login` | 1 when the normalized event type contains `login`, otherwise 0. |
| `is_known_ip` | 1 when the valid, normalized source IP appeared in earlier events for this user; otherwise 0. |
| `is_known_event_type` | 1 when the normalized nonempty event type appeared in earlier events for this user; otherwise 0. |
| `user_event_frequency` | `log1p` count of this user's deduplicated prior events in the previous 24 hours. |
| `source_ip_frequency` | `log1p` count of this user's prior events from this valid normalized IP. |

The engine uses only events strictly before the target event, with equal-time events excluded. Timestamps are timezone-aware and normalized to UTC without discarding subsecond precision. Missing or malformed IPs do not become evidence of a new IP; IP-dependent feature values remain unavailable. The demo inputs use documentation-reserved test IP ranges. More detail, including reliability and leakage considerations, is in [ML_FEATURE_SPECIFICATION.md](ML_FEATURE_SPECIFICATION.md).

## Run the demonstration

From the repository root, in the Python 3.12 project environment:

```sh
cd backend
PYTHONPATH=. ../.venv312/bin/python -m scripts.demo_ml_anomaly
```

Optional configuration is available through `--fixture`, `--contamination`, `--random-state`, and `--n-estimators`. The default fixture is `backend/scripts/reports/synthetic_events.csv`; the default model configuration is contamination `0.05`, random state `42`, and `100` estimators. The command prints JSON to stdout and creates no artifact files.

Open **ML Analytics** in the sidebar and select **Run offline demonstration** to request the same data from the backend. The page presents model configuration, synthetic benchmark metrics/confusion matrix, per-scenario test results, and the four separate demonstration inputs with their feature values and scores. The endpoint recomputes results on each request; it does not call the CLI or execute a shell command.

The four output scenarios are:

| Scenario | Demonstration event | Intended observation |
| --- | --- | --- |
| `normal_login` | 09:00 UTC login from a previously seen fixture IP and event type. | Model score is at or above zero; not flagged under this configuration. |
| `unusual_login_hour` | Same synthetic user and known IP at 02:00 UTC. | Cyclic hour values differ from the generated daytime pattern. |
| `unfamiliar_source_ip` | 09:00 UTC login from an unseen documentation-reserved IP. | IP familiarity and prior-IP frequency features change. |
| `high_authentication_frequency` | A synthetic user has 20 prior logins in ten minutes, then another login. | The 24-hour prior event frequency is high; the model flags this example under the demonstrated configuration. |

The `context` field explains the constructed input. Isolation Forest does not provide calibrated confidence here, and the demo does not claim per-feature causal attribution. A negative decision score is not a probability, and an anomaly prediction is not proof of malicious activity. Conversely, a non-flagged event is not proof of benign activity.

## Reproduce the benchmark and quality reports

The checked-in benchmark has synthetic scenario labels reserved for evaluation. The experiment uses the chronological split and fits on train rows only. Run from `backend/`:

```sh
PYTHONPATH=. ../.venv312/bin/python -m scripts.run_ml_experiment \
  --synthetic-benchmark \
  --fixture scripts/reports/synthetic_events.csv \
  --output-dir /private/tmp/ueba-demo-benchmark-v2 \
  --contamination 0.05 --random-state 42 --n-estimators 100

PYTHONPATH=. ../.venv312/bin/python -m scripts.analyze_ml_quality \
  --fixture scripts/reports/synthetic_events.csv \
  --output /private/tmp/ueba-demo-quality-v2.json
```

The benchmark's reported fixed-zero test confusion matrix uses rows actual `[normal, anomaly]` and columns predicted `[normal, anomaly]`. Current reproduced values and their scenario/seed limitations are documented in [ML_MODEL_QUALITY_REPORT.md](ML_MODEL_QUALITY_REPORT.md). The benchmark includes unusual-hour and unfamiliar-IP labels, but not an abnormally high authentication-frequency benchmark scenario. The high-frequency row in this guide is a demonstration input, not an added benchmark result.

## Reproduce snapshot-to-model validation

Snapshot validation uses disposable PostgreSQL resources and synthetic test records only. The integration test creates a fresh v2 snapshot; do not reuse older v1 snapshots because their semantics are incompatible. From the repository root:

```sh
UEBA_RUN_POSTGRES_INTEGRATION=1 PYTHONPATH=backend \
  .venv312/bin/pytest backend/tests/test_ml_dataset_postgres.py \
  -q -s -k snapshot_to_model_experiment
```

This test follows the existing PostgreSQL test harness and does not use production database configuration or records. Snapshot experiments do not contain trusted labels, so supervised metrics remain unavailable; their anomaly counts and score summaries must not be compared with labeled benchmark precision/recall as though they measured the same thing. See [ML_SNAPSHOT_EXPERIMENT_VALIDATION.md](ML_SNAPSHOT_EXPERIMENT_VALIDATION.md).

## Interpretation and limitations

- The checked-in benchmark is generated and intentionally patterned; its small number of users and anomaly types do not represent a production population.
- The temporal benchmark has a changed scenario mix in its late test period. Its scores depend on the split, contamination, seed, user profiles, and threshold.
- The benchmark's supervised metrics are valid only against its synthetic scenario labels. Snapshot-mode evaluation has no trustworthy labels and must not report invented precision, recall, F1, or confusion matrices.
- The high-frequency case illustrates one controlled feature pattern; it is not evidence of general authentication-abuse detection quality.
- No inference service, persistent approved model, registry, production rollout, or operational alert integration is included.
- Use of a test fixture does not validate data quality, privacy approvals, label validity, or generalization for real event data.

