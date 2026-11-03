# Offline ML Dataset Snapshot Pipeline

## Scope

The pipeline prepares reproducible, privacy-sanitized event snapshots for offline experiments. It is read-only with respect to application data. It does not train or deploy a model, run inference, call external services, change alert generation, or assign labels.

Implementation:

- `backend/app/services/ml_dataset.py` contains deterministic cutoff, deduplication, pseudonymization, point-in-time feature, split, and quality-report logic.
- `backend/scripts/prepare_ml_dataset.py` reads `SecurityEvent` rows in a PostgreSQL read-only transaction and writes a local snapshot.
- `backend/tests/test_ml_dataset.py` exercises the pipeline with synthetic in-memory records and a SQLite in-memory immutability check.
- `backend/tests/test_ml_dataset_postgres.py` can start a disposable local PostgreSQL cluster for opt-in integration tests. It never uses the application's configured database to seed or clean test records.

The source model is `backend/app/models/security_event.py::SecurityEvent`; no fields or API contracts were changed. The pipeline excludes `raw_event`, `created_at`, and raw identifiers from its exported dataset. There is no verified event-level label source today, so each exported record is counted as unlabeled and no class distribution is reported.

## Supported features

The snapshot uses the existing seven-feature order from `backend/app/services/ml_anomaly.py::FEATURE_NAMES`:

1. UTC `hour_sin` and `hour_cos` from `event_time`.
2. `is_login` from the existing event-type substring rule.
3. `is_known_ip` and `source_ip_frequency` from the same user's prior valid IP observations.
4. `is_known_event_type` and `user_event_frequency` from the same user's prior events.

Only strictly earlier timestamps contribute. All events with an equal timestamp are featurized before any of them enter history, since ordering within a timestamp is not known. The 24-hour event-frequency window includes its lower boundary. Histories are isolated by `user_id`; `entity_id` is pseudonymized for linkage but is not substituted for a user in these features.

Missing user identity makes user-history features null. Missing or malformed IP makes IP features null rather than treating it as an unfamiliar address. Missing event type makes `is_login` and event-type familiarity unavailable. Naive/invalid timestamps have no time features and are placed in `unassigned_invalid_time`. Non-finite calculated feature values are counted. Existing model input code expects numeric values; these nullable rows must be explicitly filtered or imputed under a separately versioned training policy before fitting anything.

No authentication outcome, local timezone, device/process context, point-in-time saved baseline deviation, or event label is fabricated. These remain unavailable.

## Privacy and output

The output uses namespace-separated HMAC-SHA256 tokens for event, subject, user, entity, source, producer event ID, event type, and validated source IP. Raw source IP and identifier values are not written. `raw_event` is excluded entirely. HMAC key material is never stored in the snapshot. Tokens remain linkable within snapshots made with the same secret, so these outputs are still sensitive derived data; store them with access controls.

`UEBA_SNAPSHOT_HMAC_KEY` is required and must contain at least 32 bytes. This length check is a minimum, not an entropy estimator: provision a cryptographically random key from a secure secret manager. Missing, short, or non-byte keys fail closed before extraction. The CLI never prints key material or includes it in manifests. Tests verify this for missing and short values.

`UEBA_SNAPSHOT_HMAC_KEY_ID` is a non-secret version tag (1–64 ASCII letters, digits, dots, underscores, or hyphens), defaulting to `local-v1`. It is included in the manifest and snapshot ID, never derived from or equal to the key. Bump it when rotating the key. Key rotation changes pseudonyms and snapshot IDs; old and new tokens cannot be joined without access to both protected keys. Keep historical snapshots and keys under the same retention/access controls. Do not put a key in shell history, the repository, a report, a command argument, or snapshot output.

The default output is `backend/data/ml_snapshots/<snapshot_id>/`, which is ignored by Git. Each directory contains:

- `dataset.csv`: sanitized pseudonymous fields, nullable feature values, and a split assignment.
- `manifest.json`: snapshot/version provenance, cutoff, counts, missingness, validity, privacy summary, feature names, unavailable capabilities, and label availability.
- `splits.json`: chronological train/validation/test cutoff and record-count manifest.

The snapshot ID is a SHA-256 digest of the feature-schema version, non-secret key ID, cutoff, and sanitized CSV bytes. It is deterministic for the same source records, cutoff, key ID, and HMAC key. Local output directories outside the ignored default path should be protected and excluded from source control by the operator.

## Read-only source behavior

The command uses the configured `DATABASE_URL` from the existing backend settings. It rejects non-PostgreSQL URLs and sets `SET TRANSACTION READ ONLY` before selecting events. The database role should also have SELECT-only privileges as a second control. The query filters on the inclusive event-time cutoff and orders by event time and primary key. No ORM mutation, commit of source changes, API call, or external transmission is performed. Snapshot files are written only to the requested local output directory.

The database model requires a timestamp and uses a typed DateTime column, so malformed stored timestamp rates may not be observable in a valid PostgreSQL table. The pure pipeline tests malformed/naive timestamps explicitly; the manifest distinguishes those rows from records whose timestamps can be compared with the cutoff. Production invalid-time measurements should be interpreted in light of the database type and ingestion validation.

Duplicate handling follows the existing `(source, external_id)` uniqueness identity when both values are present. The snapshot removes duplicate identities deterministically and reports the removed count; records lacking either key are not heuristically deduplicated. It does not deduplicate by behavioral similarity. A database with duplicate non-null keys would already violate the model's unique constraint; the check remains useful for synthetic input and source variations.

## Temporal split and labels

Records are split chronologically using unique valid event timestamps, approximately 70% train, 15% validation, 15% test. Equal timestamps stay in one partition. Cutoffs and record counts are recorded; invalid-time records are unassigned. With very few unique timestamps, partitions may be empty or approximate the target ratios poorly.

Entities can span chronological partitions for the intended known-entity future-event evaluation. Every feature uses only prior events, and timestamp peers do not influence each other. This is not an unseen-entity generalization estimate; that requires a separate group-held-out evaluation design.

No labels are currently read. `labels.unlabeled_records` therefore equals the snapshot row count and `class_distribution` is `null`, meaning unavailable. This does not claim all records are benign. Do not infer labels from alert existence, severity, status, rule score, or absent feedback. Add an approved, provenance-bearing label source before reporting class counts.

## Run locally

From the repository root, using the project's Python 3.12 environment:

```sh
cd backend
# Retrieve this value from an approved local secret manager; do not paste it into shell history.
read -s UEBA_SNAPSHOT_HMAC_KEY
export UEBA_SNAPSHOT_HMAC_KEY
export UEBA_SNAPSHOT_HMAC_KEY_ID='local-v1'
../.venv312/bin/python -m scripts.prepare_ml_dataset \
  --cutoff '2026-10-31T23:59:59Z'
```

The backend's existing settings load `DATABASE_URL` from its configured environment/`.env`; configure it to a PostgreSQL endpoint and a SELECT-only account. The command writes to `backend/data/ml_snapshots` unless `--output-dir` is supplied. `--cutoff` is an inclusive timezone-aware ISO-8601 event-time bound. It prints aggregate metadata only. Missing database configuration, missing/short HMAC key, unsupported database URL, and invalid key ID fail before data extraction. Other database failures print only an exception class and a generic next step, never the exception text or key.

## Tests

From the repository root:

```sh
PYTHONPATH=backend .venv312/bin/pytest \
  backend/tests/test_ml_dataset.py \
  backend/tests/test_ml_features.py \
  backend/tests/test_ml_anomaly.py -q
```

The dataset tests use synthetic in-memory records. They verify determinism, source-object immutability, causal feature behavior (including equal-time ties), temporal partitions, cutoff/dedup accounting, invalid and missing values, unknown-label accounting, and pseudonymization. No test fixture represents production telemetry.

PostgreSQL tests are opt-in. They create a fresh cluster under a temporary directory with a loopback-only listener and a test database named `ueba_ml_test`; they do not read `DATABASE_URL` to seed, select from, or delete data. PostgreSQL is stopped and its temporary directory removed at teardown. Run them using local PostgreSQL server binaries (`initdb` and `pg_ctl`):

```sh
UEBA_RUN_POSTGRES_INTEGRATION=1 PYTHONPATH=backend \
  .venv312/bin/pytest backend/tests/test_ml_dataset_postgres.py -q
```

The PostgreSQL suite verifies inclusive cutoff and SQL ordering, an actual `SET TRANSACTION READ ONLY` transaction (including PostgreSQL rejecting an attempted update), unchanged source rows, typed timestamp rejection, and the real CLI against the temporary database. The CLI test checks schema, feature values, token consistency and namespace separation, absence of sensitive values/raw payloads, quality metadata, chronological manifests, and byte-for-byte deterministic output. It also tests missing database/key configuration, short keys, safe key IDs, and key rotation. A PostgreSQL test may be skipped if the opt-in variable or local server binaries are absent.

Run the complete backend suite with PostgreSQL integration enabled:

```sh
UEBA_RUN_POSTGRES_INTEGRATION=1 PYTHONPATH=backend \
  .venv312/bin/pytest backend/tests -q
```

### Example aggregate quality report

The following values are from the controlled synthetic PostgreSQL integration fixture only. They are an example of report shape and are not production measurements:

```json
{
  "records_processed": 7,
  "records_at_or_before_cutoff": 7,
  "records_in_snapshot": 7,
  "duplicate_records_removed": 0,
  "invalid_timestamps": 0,
  "invalid_feature_values": 1,
  "missing_values": {
    "entity_key": 1,
    "event_type_key": 1,
    "is_known_event_type": 1,
    "is_known_ip": 1,
    "is_login": 1,
    "source_ip_frequency": 1,
    "source_ip_key": 1,
    "subject_key": 1,
    "user_event_frequency": 1,
    "user_key": 1
  },
  "entity_coverage": 1,
  "temporal_coverage_utc": {
    "start": "2026-09-01T08:00:00+00:00",
    "end": "2026-09-01T09:00:00+00:00"
  },
  "labels": {
    "status": "unavailable_no_verified_event_label_source",
    "unlabeled_records": 7,
    "class_distribution": null
  },
  "split_counts": {
    "train": 5,
    "validation": 1,
    "test": 1
  }
}
```

The fixture includes an event exactly at the cutoff, an event just after it, and a malformed-but-storable event type/IP. PostgreSQL's typed non-null timestamp column rejects a malformed timestamp at insertion; the pure in-memory tests cover naive timestamps for the snapshot transform.

### Verification results

Validation ran against PostgreSQL 18.6 initialized by the tests in a fresh temporary directory. The application database was never accessed; the CLI subprocess received the isolated test URL through an environment override. The PostgreSQL-backed test cases were:

- `test_postgres_cutoff_ordering_and_read_only_extraction`: synthetic rows queried through the production extractor; cutoff inclusion, ordering, write rejection, and source-row preservation.
- `test_postgres_rejects_malformed_timestamp_without_persisting_a_row`: database rejects the malformed timestamp; row count remains unchanged.
- `test_cli_snapshot_schema_privacy_features_quality_splits_and_determinism`: actual CLI run twice against the temporary database, using controlled synthetic records.
- `test_cli_fails_closed_for_missing_database_or_hmac_key`: launches the isolated fixture; verifies CLI configuration failures happen before data extraction.

`test_hmac_validation_and_key_rotation_change_snapshot_identity` uses synthetic in-memory records and no PostgreSQL. The eight tests in `test_ml_dataset.py` use synthetic in-memory inputs plus one SQLite in-memory database immutability check; no production or PostgreSQL data. The complete backend suite passed **24 tests** with the opt-in PostgreSQL integration enabled. It reported one existing Starlette/httpx deprecation warning.

## Operational limitations

- Only a newly initialized disposable PostgreSQL cluster with controlled synthetic rows was queried. The live production database was never accessed; production counts, quality rates, and label distribution remain unknown.
- Snapshot construction currently materializes selected event rows in memory. Very large datasets may require an ordered streaming implementation with equivalent deterministic results and causal history behavior.
- The existing seven-feature contract includes heuristic `is_login` behavior. The pipeline keeps it for compatibility; it is not a normalized authentication outcome.
- The output is prepared data only. No training or inference command consumes it yet.
