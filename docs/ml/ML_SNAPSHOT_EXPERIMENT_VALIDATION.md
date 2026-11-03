# End-to-End Snapshot Experiment Validation

## Purpose and safety boundary

This validation exercises the existing snapshot-to-model workflow using only controlled synthetic `SecurityEvent` records in a disposable local PostgreSQL cluster. It does not use the application's configured database, development records, or production data. The integration fixture creates a new PostgreSQL cluster under a temporary directory, creates only the `security_events` table from the existing SQLAlchemy model, inserts the test records, and stops and removes the cluster at teardown.

The workflow runs the actual `scripts.prepare_ml_dataset` CLI, followed by `scripts.run_ml_experiment` in snapshot mode. The experiment is an unsupervised development experiment. It does not modify rule-based detection, publish predictions, or deploy/serve the model.

## Run the complete controlled workflow

Requirements are the repository's Python 3.12 backend dependencies and local PostgreSQL `initdb`/`pg_ctl` binaries. Run from the repository root:

```sh
UEBA_RUN_POSTGRES_INTEGRATION=1 PYTHONPATH=backend \
  .venv312/bin/pytest backend/tests/test_ml_dataset_postgres.py \
  -q -s -k snapshot_to_model_experiment
```

This test provisions its own database and sets `DATABASE_URL` and `ENVIRONMENT=test` only in the snapshot CLI subprocess. It supplies a fixed, test-only HMAC secret and writes both the snapshot and experiment into pytest's temporary directory. The secret is not printed or written to artifacts. Do not replace this fixture URL with a development or production database URL.

The test invokes the equivalent commands below internally, using the generated disposable database URL, temporary output paths, and fixture-only secret:

```sh
python -m scripts.prepare_ml_dataset \
  --cutoff '2026-09-01T00:00:00Z' \
  --output-dir "$TEMP/snapshots"

python -m scripts.run_ml_experiment \
  --snapshot-dir "$SNAPSHOT_DIR" \
  --confirm-nonproduction \
  --output-dir "$TEMP/experiments" \
  --contamination 0.05 \
  --random-state 42 \
  --n-estimators 100
```

`TEMP` and `SNAPSHOT_DIR` above represent paths returned/generated inside the test; the integration test is the safe, exact command to reproduce the entire workflow without manually managing a database. The snapshot CLI requires explicit development/test provenance that matches backend configuration. The experiment CLI independently validates snapshot identity, columns, feature version, event-time cutoff, split manifests, pseudonym tokens, and nonproduction provenance.

## Controlled input and feature/model checks

The integration test inserts 60 generated events with synthetic-only users, external IDs, IPs, and payload values. The event timestamps span 60 hours. Event types mix the existing `login_success` and `file_access` categories, and test-network IP addresses are used. No target labels are inserted or inferred.

The snapshot manifest confirms `source_environment: test` and all 60 rows. It includes the seven existing features:

- `hour_sin`
- `hour_cos`
- `is_login`
- `is_known_ip`
- `is_known_event_type`
- `user_event_frequency`
- `source_ip_frequency`

The experiment metadata records the snapshot ID, feature specification version, Isolation Forest parameters, seed, cutoff rule, timestamps, software versions, and model SHA-256. The test loads the saved joblib artifact and verifies its hash, feature order, estimator count, random state, and that the fitted scaler saw exactly the training-row count. The training, validation, and test partitions remain distinct; only training rows are passed to model fit and preprocessing.

Snapshot pseudonyms are used for event linkage in `predictions.csv`. The validation scans the output files for the fixture HMAC key, original synthetic user/event identifiers, raw payload markers, and original IP text. Those values are absent. Artifacts are written outside the repository in pytest's temporary directory and removed when the test completes.

## Observed verification result

Verified on 2026-11-03 using the opt-in PostgreSQL test fixture:

- Result: `1 passed, 5 deselected` for the focused integration command.
- Snapshot provenance: `test`.
- Snapshot rows: 60.
- Temporal rows: 42 train, 9 validation, 9 test.
- Model: existing Isolation Forest, 100 estimators, random state 42, contamination 0.05.
- Threshold: fixed decision-function rule `score < 0`; validation/test tuning disabled.
- Test split: 0 predicted anomalies of 9 rows (0.0%) in this controlled fixture.
- Supervised precision, recall, F1, and confusion matrix: unavailable because the snapshot contains no trustworthy labels.
- Model artifact hash and sensitive-value exclusion: verified.

The zero anomaly count is only an observed result on this small generated dataset. It is not a quality or production-performance claim. The experiment output reports per-split anomaly counts, proportions, and decision-score distributions; it does not assign attack labels.

## Full verification

Run the full backend suite, including the PostgreSQL integration module:

```sh
UEBA_RUN_POSTGRES_INTEGRATION=1 PYTHONPATH=backend \
  .venv312/bin/pytest backend/tests -q
```

Also run:

```sh
.venv312/bin/python -m compileall -q backend/app backend/scripts backend/tests
git diff --check
```

PostgreSQL tests require permission to bind loopback on a temporary port. Every integration test starts a unique cluster and removes it afterward. Without `UEBA_RUN_POSTGRES_INTEGRATION=1`, those tests are skipped.

## Limitations

- `source_environment` is configuration provenance and defense in depth, not cryptographic proof of a database endpoint. The integration test validates only that the configured test marker is propagated and checked.
- The generated events are not representative production activity; the 60-record fixture has no trustworthy labels and cannot establish model quality.
- This run does not validate behavior on real development records, production data, or operational alert streams.
- There is no production inference service, model registry, deployment, or alert integration.
