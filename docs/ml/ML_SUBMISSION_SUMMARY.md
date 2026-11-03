# UEBA ML Submission Summary

## Project summary

The project demonstrates an offline, experimental anomaly-detection workflow for user and entity behavior. A shared, point-in-time feature engine (`ueba-seven-v2`) generates seven numeric behavioral features from security-event history. An existing Isolation Forest is fit reproducibly on a chronological training partition. The system can score controlled synthetic events and evaluate against the checked-in synthetic benchmark. It remains separate from the active rule-based detection workflow.

## Architecture and workflow

1. **Dataset preparation:** `backend/app/services/ml_dataset.py` reads security events without writing to source records, generates a versioned snapshot, applies HMAC pseudonymization, and emits quality/provenance/split metadata. v1 feature snapshots are rejected rather than reinterpreted as v2.
2. **Feature generation:** `backend/app/services/ml_feature_engine.py` is shared by event scoring and snapshot construction. For an event, it derives UTC hour cycle, login indicator, prior same-user IP/type familiarity, 24-hour user event frequency, and cumulative prior same-user IP frequency. History is strictly point-in-time; equal timestamps and future events do not contribute.
3. **Experiment:** `backend/app/services/ml_experiments.py` validates the dataset and chronological manifests, trains preprocessing and Isolation Forest using the training split, then evaluates held-out partitions. It records configuration and local experiment artifacts. It does not train on identifiers, timestamps, scenario labels, or target labels as features.
4. **Demonstration:** `backend/scripts/demo_ml_anomaly.py` uses the existing synthetic fixture and v2 feature path to train on its train split, then scores normal, unusual-hour, unfamiliar-IP, and high-frequency synthetic events. This is offline and produces JSON output only.
5. **Operational boundary:** `GET /ml-analytics/demo` and the ML Analytics page expose only the bundled synthetic offline demonstration. There is no event-scoring service, model registry, production deployment, or connection from ML predictions to operational alerts. Existing rule-based detection remains active and unchanged.

Isolation Forest is used as the existing unsupervised experimental candidate because snapshots do not have trustworthy event-level outcomes and the project already has an implementation to evaluate. It was not selected as a production algorithm. The benchmark has labels solely for controlled evaluation; those labels are excluded from unsupervised fit.

## Seven features

| Feature | Interpretation |
| --- | --- |
| `hour_sin`, `hour_cos` | Cyclic representation of event hour in UTC. |
| `is_login` | Whether normalized event type contains the login term. |
| `is_known_ip` | Whether the source IP occurred in earlier same-user history. |
| `is_known_event_type` | Whether the event type occurred in earlier same-user history. |
| `user_event_frequency` | Log-transformed count of prior same-user events in the preceding 24 hours. |
| `source_ip_frequency` | Log-transformed count of prior same-user events from that IP. |

For exact transformations, missing-value behavior and leakage risks, see [ML_FEATURE_SPECIFICATION.md](ML_FEATURE_SPECIFICATION.md).

## Demonstration result

Run:

```sh
cd backend
PYTHONPATH=. ../.venv312/bin/python -m scripts.demo_ml_anomaly
```

With the checked-in fixture, v2 features, 1,077 chronological train rows, contamination `0.05`, 100 estimators, random state `42`, and `decision_function < 0`, the reproducible demonstration produced:

| Synthetic example | Decision score | Model decision |
| --- | ---: | --- |
| Normal 09:00 UTC login | 0.027364 | Not flagged |
| Unusual 02:00 UTC login | -0.014267 | Anomaly |
| Unfamiliar source IP | -0.154285 | Anomaly |
| 20 prior logins in ten minutes | -0.014577 | Anomaly |

Anomaly scores are model decision values, not probabilities. The output includes input event data and all seven extracted features. These outcomes are a demonstration of this fixture/model configuration, not validated behavior on real security data.

## Synthetic benchmark evaluation

Reproduce with:

```sh
cd backend
PYTHONPATH=. ../.venv312/bin/python -m scripts.run_ml_experiment \
  --synthetic-benchmark --fixture scripts/reports/synthetic_events.csv \
  --output-dir /private/tmp/ueba-submission-benchmark-v2 \
  --contamination 0.05 --random-state 42 --n-estimators 100
```

On the 218-row synthetic test partition, at the existing zero decision threshold:

| Metric | Result |
| --- | ---: |
| Precision | 0.5641 |
| Recall | 0.8800 |
| F1 | 0.6875 |
| False-positive rate | 0.0881 |

Confusion matrix (actual rows `[normal, anomaly]`; predicted columns `[normal, anomaly]`):

```text
[[176, 17],
 [  3, 22]]
```

These measurements apply only to the synthetic benchmark. The generated test period has a different anomaly mix from earlier periods; the test set includes 193 normal, 10 unfamiliar-IP, and 15 unusual-hour events. Five-seed, threshold, contamination, user-held-out, and scenario analyses are in [ML_MODEL_QUALITY_REPORT.md](ML_MODEL_QUALITY_REPORT.md). Snapshot experiments have no trustworthy labels and do not report supervised metrics.

## Dataset and snapshot validation

To reproduce feature/model quality analysis:

```sh
cd backend
PYTHONPATH=. ../.venv312/bin/python -m scripts.analyze_ml_quality \
  --fixture scripts/reports/synthetic_events.csv \
  --output /private/tmp/ueba-submission-quality-v2.json
```

To run the isolated PostgreSQL snapshot-to-model validation from the repository root:

```sh
UEBA_RUN_POSTGRES_INTEGRATION=1 PYTHONPATH=backend \
  .venv312/bin/pytest backend/tests/test_ml_dataset_postgres.py \
  -q -s -k snapshot_to_model_experiment
```

The integration test builds a fresh snapshot from controlled synthetic rows in disposable test PostgreSQL resources and validates v2 feature generation, HMAC sanitization, split outputs, and snapshot-mode evaluation. It does not query production. Since there are no trusted labels, the snapshot test reports anomaly scores/counts only.

## Limitations

- No real production event snapshot or adjudicated event outcomes have been validated for ML training.
- Synthetic precision, recall, F1, confusion matrix, and scenario outcomes are not production estimates.
- Only two labeled anomaly families are in the main benchmark; high-frequency authentication is demonstrated separately but not represented in benchmark metrics.
- Threshold and contamination behavior is sensitive to scenario mix, user profile, and random seed. The existing threshold is not an operationally approved policy.
- Isolation Forest scores are not calibrated probabilities and do not provide the demo's per-feature explanation.
- Data drift, source coverage, real-world false-positive burden, and analyst outcome linkage remain unknown.
- No production inference, deployment, registry, or alert integration is included.

