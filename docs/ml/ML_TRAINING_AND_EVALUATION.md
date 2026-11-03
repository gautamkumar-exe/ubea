# UEBA Offline Model Training and Evaluation

## Purpose and boundaries

This is a reproducible **offline experiment** around the existing Isolation Forest prototype. It is not an approved production detector. It does not connect to a database while training, serve predictions, change rule-based detection, or write predictions to alerts. Snapshot preparation remains a separate read-only command.

The training workflow reuses `MLAnomalyDetector` and its `StandardScaler`, feature order, and Isolation Forest implementation. It accepts only the seven features from `backend/app/services/ml_anomaly.py::FEATURE_NAMES`; pseudonymous IDs, event keys, timestamps, split names, labels, and raw payloads are never model inputs.

## Environment and installation

Use Python 3.12 and the existing backend dependencies. From the repository root:

```sh
python3.12 -m venv .venv312
.venv312/bin/python -m pip install -r backend/requirements.txt
```

`scikit-learn` supplies the existing Isolation Forest, `StandardScaler`, NumPy, and joblib artifact support. No new dependency was added.

Experiments and serialized models are written under `backend/data/ml_experiments/`, which is ignored by Git. Treat these local artifacts as sensitive derived data. The snapshot-mode prediction report includes pseudonymous event keys. Do not load joblib models from untrusted sources.

## Create or select a snapshot

The existing snapshot command reads PostgreSQL in a read-only transaction and writes a sanitized local snapshot. Only use a dedicated development or test database. Snapshot preparation requires the `ENVIRONMENT` variable to be explicitly set to `development` or `test`; it refuses other values. The snapshot's `source_environment` is copied from that setting and checked against the backend configuration. It is provenance metadata, not cryptographic proof of the database's origin.

The current training loader requires a new-format snapshot with:

- `source_environment` exactly `development` or `test`;
- an integrity-matching snapshot ID and `splits.json` identity;
- feature schema version `ueba-seven-v1` and the exact seven-feature order;
- the expected dataset columns, with no target-label column;
- split counts and cutoffs that agree with row event times and equal-time grouping.

Production, unclassified, malformed, and older snapshots without environment provenance fail closed. Regenerate older snapshots from an isolated nonproduction database. The environment check is defense in depth: maintain accurate environment settings and verify the database endpoint separately. There is no command-line flag that changes snapshot provenance. `--confirm-nonproduction` only requires an explicit operator acknowledgement; it does not relabel a snapshot.

Example from the repository root, with `DATABASE_URL` already configured for a dedicated test database and a secure HMAC key retrieved locally:

```sh
cd backend
export ENVIRONMENT=test
read -s UEBA_SNAPSHOT_HMAC_KEY
export UEBA_SNAPSHOT_HMAC_KEY
export UEBA_SNAPSHOT_HMAC_KEY_ID='test-v1'
../.venv312/bin/python -m scripts.prepare_ml_dataset \
  --cutoff '2026-10-31T23:59:59Z' \
  --output-dir data/ml_snapshots
```

The snapshot output prints its directory and ID. Keep the HMAC key outside shell history, source control, and all artifacts. Do not point this process at production.

## Run a snapshot experiment

From `backend/`, substitute the ID printed by snapshot preparation:

```sh
../.venv312/bin/python -m scripts.run_ml_experiment \
  --snapshot-dir 'data/ml_snapshots/<snapshot-id>' \
  --confirm-nonproduction \
  --output-dir data/ml_experiments \
  --contamination 0.05 \
  --random-state 42 \
  --n-estimators 100
```

The experiment loader verifies the snapshot content digest, format, feature version/order, pseudonymous token fields, source environment, and temporal split manifest. It rejects extra columns such as a label or scenario. Rows with missing feature values are excluded and counted; malformed or non-finite feature values fail validation. At least ten complete training rows are required.

Only complete rows assigned to `train` are passed to fitting. `StandardScaler` is fit inside the existing detector on those rows only. Validation and test rows are scored after fitting and cannot affect preprocessing, training, or the threshold. The contamination parameter determines the Isolation Forest's fitted offset on training data. The reported decision function uses the fixed rule `score < 0` for an anomaly; validation/test data do not tune this threshold.

When the snapshot has no verified event labels, the evaluation explicitly sets precision, recall, F1, confusion matrix, false-positive analysis, and false-negative analysis to unavailable. It still reports per-split score distributions, anomaly counts and proportions, and rows excluded for missing features. No label is inferred from alert state, risk, detector output, or missing feedback.

## Run the synthetic benchmark

The checked-in fixture already provides generated `normal`, `unfamiliar_ip`, and `unusual_hour` scenarios. The separate benchmark mode reuses `features_for_event`; it does not add new scenarios or modify the fixture. It calculates features causally, creates chronological 70/15/15 splits on unique timestamps, and trains on **all feature vectors in the training partition without consulting scenario labels**. Scenario labels are read only for evaluation after model fitting. The test partition is used for reported synthetic metrics and is not used for model fitting or threshold choice.

```sh
cd backend
../.venv312/bin/python -m scripts.run_ml_experiment \
  --synthetic-benchmark \
  --fixture scripts/reports/synthetic_events.csv \
  --output-dir data/ml_experiments \
  --contamination 0.05 \
  --random-state 42 \
  --n-estimators 100
```

### Controlled synthetic run

A complete run with the command above produced 1,077 training rows, 220 validation rows, and 218 test rows. The held-out test set contained 193 generated normal events, 10 unfamiliar-IP cases, and 15 unusual-hour cases. Results were:

- Precision: 0.5641
- Recall: 0.8800
- F1: 0.6875
- Confusion matrix, labels `[normal, anomaly]`: `[[176, 17], [3, 22]]`
- False positives: 17 of 193 generated normal test records (8.8%).
- False negatives: 3 of 25 generated anomaly test records.
- Synthetic unfamiliar-IP detection: 10 of 10; unusual-hour detection: 12 of 15.

These are measured results from the checked-in synthetic generator and its scenario labels only. They are not production performance, proof of malicious activity, or directly comparable to the earlier 0.5098 precision / 0.8667 recall / 0.6420 F1 report, which used a different evaluation procedure. The fixture does not establish realistic base rates, label quality, evasion behavior, or operational false-positive cost.

## Experiment artifacts

Each run receives a unique `experiment_id` directory containing:

- `model.joblib`: fitted Isolation Forest and scaler, feature names, and feature schema version.
- `metadata.json`: experiment status/ID, snapshot ID or synthetic fixture SHA-256, source environment, feature version, model parameters, random seed, train/validation/test row counts, training/evaluation timestamps, threshold rule and fitted offset, Python/NumPy/scikit-learn/joblib versions, and model artifact SHA-256.
- `evaluation.json`: supervised metrics when labels are explicitly available for synthetic evaluation; otherwise an explicit unavailable status, plus score distributions, counts/proportions, and exclusion counts.
- `predictions.csv`: pseudonymous event key and score/split for snapshots; record number, split, synthetic scenario, actual/predicted anomaly, and score for the synthetic benchmark.

A repeated run with the same input and parameters creates a different experiment ID and timestamps, but the fitted model and predictions are deterministic under the recorded versions and `random_state`. Artifact hashes allow later integrity checks. HMAC key material and raw event identifiers, IP addresses, and payloads are not copied into experiment metadata.

## Tests

From the repository root:

```sh
PYTHONPATH=backend .venv312/bin/pytest backend/tests/test_ml_experiments.py -q
```

The tests cover compatible development/test snapshots, rejection of production/unclassified/missing-provenance snapshots, schema and label-column checks, split integrity, missing/non-finite features, deterministic preprocessing and training, threshold isolation from test data, metrics, no-label reporting, synthetic scenario separation, artifacts, and sensitive-value exclusion. They use controlled synthetic records and temporary directories only.

## Limitations and interpretation

- Environment provenance is copied from configuration and can be wrong if configuration is wrong; it is not a signed statement about a database endpoint. The CLI acknowledgement and loader environment check reduce accidental use but do not replace endpoint verification.
- Current event snapshots have no trustworthy event-level ground truth. Snapshot-mode precision/recall/F1 remain unavailable until an approved label source with reliable linkage exists.
- Synthetic scenarios cover unfamiliar IP and unusual hour only; they do not cover the proposed high-frequency or multi-feature interaction scenarios.
- `is_login` is the existing event-type substring heuristic, not a normalized authentication result.
- Snapshot scoring excludes incomplete feature rows. This can bias results if missingness correlates with source or behavior.
- Model, split, and threshold behavior has not been validated against production data; production training is rejected by environment provenance.
- The model remains an experimental candidate. There is no online inference API, deployment, model registry, drift monitoring, or operational analyst workflow.
