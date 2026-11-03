from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import joblib
import numpy as np
import pytest

from app.services.ml_anomaly import FEATURE_NAMES
from app.services.ml_dataset import SnapshotOptions, write_snapshot
from app.services.ml_experiments import (
    SnapshotValidationError,
    _binary_metrics,
    fit_detector,
    load_synthetic_benchmark,
    load_validated_snapshot,
    run_snapshot_experiment,
    run_synthetic_benchmark,
)

KEY = bytes.fromhex("43" * 32)
CUTOFF = datetime(2026, 3, 1, tzinfo=timezone.utc)


def _events(count: int = 30, *, missing_user_at: set[int] | None = None):
    missing_user_at = missing_user_at or set()
    events = []
    start = datetime(2026, 1, 1, 8, tzinfo=timezone.utc)
    for index in range(count):
        events.append(SimpleNamespace(
            id=f"synthetic-event-{index}",
            source="synthetic-source",
            external_id=f"synthetic-external-{index}",
            user_id=None if index in missing_user_at else "synthetic-user-a",
            entity_id="synthetic-device-a",
            event_type="login_success" if index % 3 == 0 else "file_access",
            source_ip="192.0.2.10" if index % 5 else "192.0.2.11",
            event_time=start + timedelta(hours=index),
            raw_event={"synthetic_only": True},
        ))
    return events


def _make_snapshot(root: Path, *, count: int = 30, missing_user_at: set[int] | None = None, environment: str = "test") -> Path:
    result = write_snapshot(
        _events(count, missing_user_at=missing_user_at),
        SnapshotOptions(CUTOFF, KEY, "pytest-key-v1", environment),
        root,
    )
    return Path(result["output_directory"])


def _rewrite_snapshot_id(snapshot_dir: Path, csv_bytes: bytes) -> None:
    from app.services.ml_experiments import _snapshot_digest

    (snapshot_dir / "dataset.csv").write_bytes(csv_bytes)
    manifest_path = snapshot_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    snapshot_id = _snapshot_digest(
        manifest["pseudonymization_key_id"],
        manifest["source_environment"],
        manifest["cutoff_utc"],
        csv_bytes,
    )
    manifest["snapshot_id"] = snapshot_id
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    splits_path = snapshot_dir / "splits.json"
    splits = json.loads(splits_path.read_text())
    splits["snapshot_id"] = snapshot_id
    splits_path.write_text(json.dumps(splits, indent=2, sort_keys=True) + "\n")


def test_snapshot_compatibility_and_split_integrity(tmp_path: Path):
    snapshot_dir = _make_snapshot(tmp_path / "snapshot")
    snapshot = load_validated_snapshot(snapshot_dir)

    assert snapshot.feature_schema_version == "ueba-seven-v1"
    assert snapshot.source_environment == "test"
    assert len(snapshot.rows) == 30
    assert all(len(row.features) == len(FEATURE_NAMES) for row in snapshot.rows)
    assert {row.split for row in snapshot.rows} == {"train", "validation", "test"}

    splits_path = snapshot_dir / "splits.json"
    splits = json.loads(splits_path.read_text())
    splits["partitions"]["test"]["after_utc"] = "2026-01-01T08:00:00+00:00"
    splits_path.write_text(json.dumps(splits))
    with pytest.raises(SnapshotValidationError, match="Test cutoff"):
        load_validated_snapshot(snapshot_dir)


def test_production_and_unclassified_snapshots_are_refused(tmp_path: Path):
    production = _make_snapshot(tmp_path / "production", environment="production")
    with pytest.raises(SnapshotValidationError, match="Refusing to train"):
        load_validated_snapshot(production)

    unclassified = _make_snapshot(tmp_path / "unclassified", environment="unclassified")
    with pytest.raises(SnapshotValidationError, match="Refusing to train"):
        load_validated_snapshot(unclassified)


def test_invalid_nonfinite_feature_is_rejected(tmp_path: Path):
    snapshot_dir = _make_snapshot(tmp_path / "snapshot")
    with (snapshot_dir / "dataset.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    rows[0]["hour_sin"] = "NaN"
    import io
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    _rewrite_snapshot_id(snapshot_dir, buffer.getvalue().encode())

    with pytest.raises(SnapshotValidationError, match="Non-finite feature"):
        load_validated_snapshot(snapshot_dir)


def test_missing_features_are_excluded_and_labels_are_unavailable(tmp_path: Path):
    snapshot_dir = _make_snapshot(tmp_path / "snapshot", missing_user_at={0})
    loaded = load_validated_snapshot(snapshot_dir)
    assert sum(not row.has_valid_features for row in loaded.rows) == 1

    result = run_snapshot_experiment(snapshot_dir, tmp_path / "experiments")
    evaluation = result["evaluation"]
    assert evaluation["evaluation_status"] == "unavailable_no_trustworthy_ground_truth_labels"
    assert evaluation["supervised_metrics"] == {
        "precision": None,
        "recall": None,
        "f1": None,
        "confusion_matrix": None,
    }
    assert evaluation["false_positive_analysis"].startswith("unavailable")
    assert evaluation["excluded_rows_missing_or_invalid_features"]["train"] == 1


def test_snapshot_training_is_reproducible_and_records_artifact_metadata(tmp_path: Path):
    snapshot_dir = _make_snapshot(tmp_path / "snapshot")
    first = run_snapshot_experiment(snapshot_dir, tmp_path / "first", random_state=17)
    second = run_snapshot_experiment(snapshot_dir, tmp_path / "second", random_state=17)

    assert first["experiment_status"] == "completed"
    assert first["experiment_id"] != second["experiment_id"]
    assert first["dataset_snapshot_id"] == second["dataset_snapshot_id"]
    assert first["model_configuration"]["random_state"] == 17
    assert first["feature_specification_version"] == "ueba-seven-v1"
    assert first["training_records"] == 21
    assert first["validation_records"] == 5
    assert first["test_records"] == 4
    assert first["model_artifact_sha256"]
    for name in ("training_started_at_utc", "training_completed_at_utc", "evaluation_started_at_utc", "evaluation_completed_at_utc"):
        assert first[name]
    first_dir, second_dir = Path(first["output_directory"]), Path(second["output_directory"])
    first_predictions = (first_dir / "predictions.csv").read_bytes()
    second_predictions = (second_dir / "predictions.csv").read_bytes()
    assert first_predictions == second_predictions
    metadata = json.loads((first_dir / "metadata.json").read_text())
    assert metadata["experiment_status"] == "completed"
    assert metadata["dataset_snapshot_id"] == first["dataset_snapshot_id"]
    assert metadata["source_environment"] == "test"
    assert metadata["decision_threshold"]["validation_or_test_tuning"] is False
    assert hashlib.sha256((first_dir / "model.joblib").read_bytes()).hexdigest() == metadata["model_artifact_sha256"]
    reports = b"".join(
        (first_dir / filename).read_bytes()
        for filename in ("metadata.json", "evaluation.json", "predictions.csv")
    )
    for sensitive in (b"synthetic-user-a", b"synthetic-external-", b"192.0.2.10", KEY):
        assert sensitive not in reports


def test_test_partition_cannot_affect_fitted_preprocessing_or_model(tmp_path: Path):
    original_dir = _make_snapshot(tmp_path / "original")
    changed_dir = tmp_path / "changed"
    shutil.copytree(original_dir, changed_dir)
    with (changed_dir / "dataset.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        if row["split"] == "test":
            for feature in FEATURE_NAMES:
                row[feature] = "999999.0"
    import io
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    _rewrite_snapshot_id(changed_dir, buffer.getvalue().encode())

    original_run = run_snapshot_experiment(original_dir, tmp_path / "run-original")
    changed_run = run_snapshot_experiment(changed_dir, tmp_path / "run-changed")
    original_model = joblib.load(Path(original_run["output_directory"]) / "model.joblib")
    changed_model = joblib.load(Path(changed_run["output_directory"]) / "model.joblib")

    np.testing.assert_array_equal(original_model["scaler"].mean_, changed_model["scaler"].mean_)
    np.testing.assert_array_equal(original_model["model"].estimators_[0].tree_.threshold, changed_model["model"].estimators_[0].tree_.threshold)
    assert original_model["model"].offset_ == changed_model["model"].offset_


def test_binary_evaluation_metrics_are_correct():
    result = _binary_metrics(
        ["normal", "normal", "unusual_hour", "unfamiliar_ip"],
        [False, True, True, False],
    )

    assert result["confusion_matrix"] == {"labels": ["normal", "anomaly"], "values": [[1, 1], [1, 1]]}
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f1"] == 0.5
    assert result["false_positive"] == 1
    assert result["false_negative"] == 1


def test_training_preprocessing_is_deterministic():
    features = [
        [float(index + offset) for offset in range(len(FEATURE_NAMES))]
        for index in range(20)
    ]
    first = fit_detector(features, random_state=23, n_estimators=20)
    second = fit_detector(features, random_state=23, n_estimators=20)
    np.testing.assert_array_equal(first.scaler.mean_, second.scaler.mean_)
    np.testing.assert_array_equal(first.scaler.scale_, second.scaler.scale_)
    np.testing.assert_array_equal(first.model.offset_, second.model.offset_)
    sample = [float(index) for index in range(len(FEATURE_NAMES))]
    assert first.score(sample)["decision_score"] == second.score(sample)["decision_score"]


def test_snapshot_fit_receives_only_feature_columns(tmp_path: Path, monkeypatch):
    from app.services import ml_experiments

    snapshot_dir = _make_snapshot(tmp_path / "snapshot")
    captured: dict[str, object] = {}
    actual_fit = ml_experiments.fit_detector

    def capture_training_matrix(features, **kwargs):
        captured["features"] = [list(row) for row in features]
        return actual_fit(features, **kwargs)

    monkeypatch.setattr(ml_experiments, "fit_detector", capture_training_matrix)
    result = run_snapshot_experiment(snapshot_dir, tmp_path / "experiments")

    matrix = captured["features"]
    assert len(matrix) == result["training_records"] == 21
    assert all(len(row) == 7 for row in matrix)
    assert all(isinstance(value, float) for row in matrix for value in row)
    assert result["feature_names"] == list(FEATURE_NAMES)


def test_existing_synthetic_scenarios_are_eval_only_and_reported_by_scenario(
    tmp_path: Path, monkeypatch
):
    from app.services import ml_experiments

    fixture = Path(__file__).resolve().parents[1] / "scripts" / "reports" / "synthetic_events.csv"
    benchmark = load_synthetic_benchmark(fixture)
    assert {row.scenario for row in benchmark.rows} == {"normal", "unfamiliar_ip", "unusual_hour"}
    assert all(len(row.features) == 7 for row in benchmark.rows)

    captured: dict[str, object] = {}
    actual_fit = ml_experiments.fit_detector

    def capture_training_matrix(features, **kwargs):
        captured["features"] = [list(row) for row in features]
        return actual_fit(features, **kwargs)

    monkeypatch.setattr(ml_experiments, "fit_detector", capture_training_matrix)

    result = run_synthetic_benchmark(fixture, tmp_path / "experiments", random_state=31)
    assert result["experiment_status"] == "completed"
    assert result["dataset_kind"] == "deterministic_synthetic_fixture"
    assert result["training_used_scenario_labels"] is False
    assert result["evaluation_warning"].startswith("Synthetic scenario metrics")
    assert result["evaluation"]["evaluation_status"] == "synthetic_ground_truth_only"
    assert result["evaluation"]["test_metrics"]["support"] == result["test_records"]
    assert set(result["evaluation"]["by_synthetic_scenario"]) == {"normal", "unfamiliar_ip", "unusual_hour"}
    training_matrix = captured["features"]
    assert len(training_matrix) == result["training_records"]
    assert all(len(row) == len(FEATURE_NAMES) for row in training_matrix)
    assert all(isinstance(value, float) for row in training_matrix for value in row)
    output = Path(result["output_directory"])
    assert (output / "model.joblib").exists()
    assert (output / "evaluation.json").exists()
    assert (output / "metadata.json").exists()


def test_incompatible_feature_specification_is_rejected(tmp_path: Path):
    snapshot_dir = _make_snapshot(tmp_path / "snapshot")
    manifest_path = snapshot_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["feature_schema_version"] = "future-version"
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(SnapshotValidationError, match="Incompatible feature"):
        load_validated_snapshot(snapshot_dir)


def test_snapshot_target_label_column_is_rejected(tmp_path: Path):
    snapshot_dir = _make_snapshot(tmp_path / "snapshot")
    with (snapshot_dir / "dataset.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        old_fields, rows = reader.fieldnames, list(reader)
    fields = [*old_fields, "scenario"]
    for row in rows:
        row["scenario"] = "normal"
    import io
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    _rewrite_snapshot_id(snapshot_dir, buffer.getvalue().encode())

    with pytest.raises(SnapshotValidationError, match="columns"):
        load_validated_snapshot(snapshot_dir)


def test_missing_environment_provenance_fails_closed(tmp_path: Path):
    snapshot_dir = _make_snapshot(tmp_path / "snapshot")
    manifest_path = snapshot_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("source_environment")
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(SnapshotValidationError, match="no source-environment provenance"):
        load_validated_snapshot(snapshot_dir)


def test_development_snapshot_is_accepted(tmp_path: Path):
    snapshot_dir = _make_snapshot(tmp_path / "snapshot", environment="development")
    assert load_validated_snapshot(snapshot_dir).source_environment == "development"
