# Offline ML Dataset Snapshot Pipeline

## Scope

The pipeline prepares reproducible, privacy-sanitized event snapshots for offline experiments. It is read-only with respect to application data. It does not train or deploy a model, run inference, call external services, change alert generation, or assign labels.

Implementation:

- `backend/app/services/ml_dataset.py` contains deterministic cutoff, deduplication, pseudonymization, point-in-time feature, split, and quality-report logic.
- `backend/scripts/prepare_ml_dataset.py` reads `SecurityEvent` rows in a PostgreSQL read-only transaction and writes a local snapshot.
- `backend/tests/test_ml_dataset.py` exercises the pipeline with synthetic in-memory records. These tests are not production data evidence.

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

Set `UEBA_SNAPSHOT_HMAC_KEY` from a secure local secret source. Use the same protected key to reproduce linkable tokens; key rotation intentionally changes pseudonyms and snapshot IDs. Do not put the key in shell history, the repository, a report, or a command argument.

The default output is `backend/data/ml_snapshots/<snapshot_id>/`, which is ignored by Git. Each directory contains:

- `dataset.csv`: sanitized pseudonymous fields, nullable feature values, and a split assignment.
- `manifest.json`: snapshot/version provenance, cutoff, counts, missingness, validity, privacy summary, feature names, unavailable capabilities, and label availability.
- `splits.json`: chronological train/validation/test cutoff and record-count manifest.

The snapshot ID is a SHA-256 digest of the feature-schema version, cutoff, and sanitized CSV bytes. It is deterministic for the same source records, cutoff, and HMAC key. Local output directories outside the ignored default path should be protected and excluded from source control by the operator.

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
export UEBA_SNAPSHOT_HMAC_KEY='<at least 32 bytes supplied securely>'
../.venv312/bin/python -m scripts.prepare_ml_dataset \
  --cutoff '2026-10-31T23:59:59Z'
```

The backend's existing settings load `DATABASE_URL` from its configured environment/`.env`. The command writes to `backend/data/ml_snapshots` unless `--output-dir` is supplied. It prints aggregate metadata only. Database failures produce a generic message so driver exceptions cannot echo sensitive values; check local connectivity and read-only permissions separately.

## Tests

From the repository root:

```sh
PYTHONPATH=backend .venv312/bin/pytest \
  backend/tests/test_ml_dataset.py \
  backend/tests/test_ml_features.py \
  backend/tests/test_ml_anomaly.py -q
```

The dataset tests use synthetic in-memory records. They verify determinism, source-object immutability, causal feature behavior (including equal-time ties), temporal partitions, cutoff/dedup accounting, invalid and missing values, unknown-label accounting, and pseudonymization. No test fixture represents production telemetry.

## Operational limitations

- The live production database was not queried as part of implementation; production counts, quality rates, and label distribution remain unknown.
- Snapshot construction currently materializes selected event rows in memory. Very large datasets may require an ordered streaming implementation with equivalent deterministic results and causal history behavior.
- The existing seven-feature contract includes heuristic `is_login` behavior. The pipeline keeps it for compatibility; it is not a normalized authentication outcome.
- The output is prepared data only. No training or inference command consumes it yet.
