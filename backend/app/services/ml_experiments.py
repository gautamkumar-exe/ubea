"""Reproducible offline training and evaluation for experimental UEBA models."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import joblib
import numpy as np
import sklearn

from app.services.ml_anomaly import FEATURE_NAMES, MLAnomalyDetector
from app.services.ml_dataset import CSV_FIELDS, FEATURE_SCHEMA_VERSION

SAFE_TRAINING_ENVIRONMENTS = {"test", "development"}
ALLOWED_SPLITS = {"train", "validation", "test", "unassigned_invalid_time"}
SYNTHETIC_SCENARIOS = {"normal", "unfamiliar_ip", "unusual_hour"}
SYNTHETIC_FIELDS = ("user_id", "event_time", "event_type", "source_ip", "scenario")
EXPERIMENT_VERSION = "ueba-offline-experiment-v1"


class SnapshotValidationError(ValueError):
    """Snapshot is incompatible, tampered, or unsafe for this workflow."""


class ExperimentError(RuntimeError):
    """An experiment failed; details are recorded without source values."""


@dataclass(frozen=True)
class SnapshotRow:
    event_key: str
    event_time: datetime | None
    split: str
    features: tuple[float | None, ...]

    @property
    def has_valid_features(self) -> bool:
        return len(self.features) == len(FEATURE_NAMES) and all(
            value is not None and math.isfinite(value) for value in self.features
        )


@dataclass(frozen=True)
class DatasetSnapshot:
    snapshot_id: str
    feature_schema_version: str
    source_environment: str
    rows: tuple[SnapshotRow, ...]
    manifest: dict[str, object]


@dataclass(frozen=True)
class SyntheticRow:
    row_number: int
    split: str
    features: tuple[float, ...]
    scenario: str


@dataclass(frozen=True)
class SyntheticBenchmark:
    fixture_id: str
    rows: tuple[SyntheticRow, ...]
    split_cutoffs: dict[str, str | None]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, description: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotValidationError(f"Could not read {description}") from exc
    if not isinstance(value, dict):
        raise SnapshotValidationError(f"Invalid {description} structure")
    return value


def _parse_aware(value: object, field: str) -> datetime | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise SnapshotValidationError(f"Invalid timestamp field: {field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SnapshotValidationError(f"Invalid timestamp field: {field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SnapshotValidationError(f"Timestamp must include timezone: {field}")
    return parsed.astimezone(timezone.utc)


def _keyed_token(value: str | None) -> bool:
    return value is None or bool(re.fullmatch(r"[0-9a-f]{64}", value))


def _snapshot_digest(key_id: str, source_environment: str, cutoff: str, dataset_bytes: bytes) -> str:
    payload = (
        FEATURE_SCHEMA_VERSION
        + "\0"
        + key_id
        + "\0"
        + source_environment
        + "\0"
        + cutoff
        + "\0"
    ).encode("utf-8") + dataset_bytes
    return hashlib.sha256(payload).hexdigest()


def _parse_features(row: dict[str, str], row_number: int) -> tuple[float | None, ...]:
    parsed: list[float | None] = []
    for feature in FEATURE_NAMES:
        value = row.get(feature, "")
        if value in (None, ""):
            parsed.append(None)
            continue
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise SnapshotValidationError(
                f"Invalid feature value in CSV row {row_number}: {feature}"
            ) from exc
        if not math.isfinite(number):
            raise SnapshotValidationError(
                f"Non-finite feature value in CSV row {row_number}: {feature}"
            )
        parsed.append(number)
    return tuple(parsed)


def load_validated_snapshot(snapshot_dir: Path) -> DatasetSnapshot:
    """Load and validate a snapshot without reading labels as model features."""
    snapshot_dir = Path(snapshot_dir)
    manifest = _read_json(snapshot_dir / "manifest.json", "snapshot manifest")
    split_manifest = _read_json(snapshot_dir / "splits.json", "split manifest")
    dataset_path = snapshot_dir / "dataset.csv"
    try:
        dataset_bytes = dataset_path.read_bytes()
    except OSError as exc:
        raise SnapshotValidationError("Could not read snapshot dataset") from exc

    snapshot_id = manifest.get("snapshot_id")
    key_id = manifest.get("pseudonymization_key_id")
    environment = manifest.get("source_environment")
    cutoff_raw = manifest.get("cutoff_utc")
    if not isinstance(snapshot_id, str) or not re.fullmatch(r"[0-9a-f]{64}", snapshot_id):
        raise SnapshotValidationError("Invalid snapshot identity")
    if environment is None:
        raise SnapshotValidationError(
            "Snapshot has no source-environment provenance; regenerate it before training"
        )
    if not isinstance(environment, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", environment):
        raise SnapshotValidationError("Missing or invalid source environment")
    environment = environment.lower()
    if environment not in SAFE_TRAINING_ENVIRONMENTS:
        raise SnapshotValidationError("Refusing to train on production or unclassified snapshot data")
    if not isinstance(key_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", key_id):
        raise SnapshotValidationError("Missing or invalid pseudonymization key ID")
    cutoff = _parse_aware(cutoff_raw, "cutoff_utc")
    if cutoff is None:
        raise SnapshotValidationError("Snapshot cutoff is missing")
    if manifest.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        raise SnapshotValidationError("Incompatible feature specification version")
    if manifest.get("feature_names") != list(FEATURE_NAMES):
        raise SnapshotValidationError("Snapshot feature order does not match the model specification")
    if manifest.get("source_read_only") is not True:
        raise SnapshotValidationError("Snapshot provenance is not marked read-only")
    if _snapshot_digest(key_id, environment, str(cutoff_raw), dataset_bytes) != snapshot_id:
        raise SnapshotValidationError("Snapshot content digest does not match its manifest")
    if split_manifest.get("snapshot_id") != snapshot_id:
        raise SnapshotValidationError("Split manifest belongs to a different snapshot")
    if split_manifest.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        raise SnapshotValidationError("Split manifest feature version is incompatible")

    try:
        text = dataset_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SnapshotValidationError("Snapshot dataset is not UTF-8") from exc
    reader = csv.DictReader(text.splitlines())
    if tuple(reader.fieldnames or ()) != CSV_FIELDS:
        raise SnapshotValidationError("Snapshot columns do not match the approved schema")

    split_cutoffs = manifest.get("split_cutoffs_utc")
    if not isinstance(split_cutoffs, dict):
        raise SnapshotValidationError("Snapshot split cutoffs are missing")
    train_end = _parse_aware(split_cutoffs.get("train_end"), "train_end")
    validation_end = _parse_aware(split_cutoffs.get("validation_end"), "validation_end")
    if train_end is not None and validation_end is not None and train_end > validation_end:
        raise SnapshotValidationError("Train cutoff must not follow validation cutoff")
    rows: list[SnapshotRow] = []
    seen_event_keys: set[str] = set()
    split_counts: dict[str, int] = {}
    same_time_splits: dict[datetime, str] = {}
    previous_event_time: datetime | None = None

    for row_number, row in enumerate(reader, start=2):
        event_key = row.get("event_key", "")
        if not _keyed_token(event_key) or not event_key:
            raise SnapshotValidationError(f"Invalid pseudonymous event key in CSV row {row_number}")
        if event_key in seen_event_keys:
            raise SnapshotValidationError("Snapshot contains duplicate event keys")
        seen_event_keys.add(event_key)
        for field in ("subject_key", "user_key", "entity_key", "source_key", "external_key", "event_type_key", "source_ip_key"):
            if not _keyed_token(row.get(field) or None):
                raise SnapshotValidationError(f"Unsanitized token field in CSV row {row_number}: {field}")
        split = row.get("split", "")
        if split not in ALLOWED_SPLITS:
            raise SnapshotValidationError(f"Unknown temporal partition in CSV row {row_number}")
        event_time = _parse_aware(row.get("event_time_utc"), "event_time_utc")
        if event_time is None:
            if split != "unassigned_invalid_time":
                raise SnapshotValidationError("Invalid-time row has a temporal partition")
        else:
            if event_time > cutoff:
                raise SnapshotValidationError("Snapshot row exceeds the inclusive cutoff")
            if previous_event_time is not None and event_time < previous_event_time:
                raise SnapshotValidationError("Snapshot rows are not in chronological order")
            previous_event_time = event_time
            if split == "unassigned_invalid_time":
                raise SnapshotValidationError("Timestamped row is marked unassigned")
            expected_split = (
                "train" if train_end is None or event_time <= train_end
                else "validation" if validation_end is None or event_time <= validation_end
                else "test"
            )
            if split != expected_split:
                raise SnapshotValidationError("Row partition conflicts with chronological cutoffs")
            previous_split = same_time_splits.setdefault(event_time, split)
            if previous_split != split:
                raise SnapshotValidationError("Equal timestamps cross temporal partitions")
        feature_values = _parse_features(row, row_number)
        if row.get("subject_type") not in ("", "user", "entity"):
            raise SnapshotValidationError(f"Invalid subject type in CSV row {row_number}")
        rows.append(SnapshotRow(event_key, event_time, split, feature_values))
        split_counts[split] = split_counts.get(split, 0) + 1

    if len(rows) != manifest.get("records_in_snapshot"):
        raise SnapshotValidationError("Snapshot record count does not match its manifest")
    declared_counts = manifest.get("split_counts")
    partition_manifest = split_manifest.get("partitions")
    if not isinstance(declared_counts, dict) or not isinstance(partition_manifest, dict):
        raise SnapshotValidationError("Split counts are missing")
    partition_docs = {
        name: partition_manifest.get(name)
        for name in ("train", "validation", "test", "unassigned_invalid_time")
    }
    if any(not isinstance(value, dict) for value in partition_docs.values()):
        raise SnapshotValidationError("Temporal partition definitions are missing")
    if partition_docs["train"].get("end_utc") != split_cutoffs.get("train_end"):
        raise SnapshotValidationError("Train cutoff differs between manifests")
    if partition_docs["validation"].get("end_utc") != split_cutoffs.get("validation_end"):
        raise SnapshotValidationError("Validation cutoff differs between manifests")
    if partition_docs["test"].get("after_utc") != split_cutoffs.get("validation_end"):
        raise SnapshotValidationError("Test cutoff differs between manifests")
    for split in ALLOWED_SPLITS:
        observed = split_counts.get(split, 0)
        if declared_counts.get(split, 0) != observed:
            raise SnapshotValidationError("Split count does not match dataset rows")
        if partition_docs[split].get("records") != observed:
            raise SnapshotValidationError("Split manifest count does not match dataset rows")
    if split_manifest.get("policy") != manifest.get("split_policy"):
        raise SnapshotValidationError("Split policy does not match snapshot metadata")

    return DatasetSnapshot(
        snapshot_id=snapshot_id,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        source_environment=environment,
        rows=tuple(rows),
        manifest=manifest,
    )


def fit_detector(
    training_features: Sequence[Sequence[float]],
    *,
    contamination: float = 0.05,
    random_state: int = 42,
    n_estimators: int = 100,
) -> MLAnomalyDetector:
    """Fit the existing detector only from the explicitly supplied train rows."""
    detector = MLAnomalyDetector(
        contamination=contamination,
        random_state=random_state,
        n_estimators=n_estimators,
    )
    detector.fit(training_features)
    return detector


def _valid_rows(rows: Iterable[SnapshotRow], split: str) -> tuple[list[SnapshotRow], int]:
    selected = [row for row in rows if row.split == split]
    valid = [row for row in selected if row.has_valid_features]
    return valid, len(selected) - len(valid)


def _score_rows(detector: MLAnomalyDetector, rows: Sequence[SnapshotRow]) -> tuple[list[dict[str, object]], dict[str, object]]:
    predictions: list[dict[str, object]] = []
    scores_by_split: dict[str, list[float]] = {}
    for row in rows:
        result = detector.score([float(value) for value in row.features if value is not None])
        score = float(result["decision_score"])
        predictions.append({
            "event_key": row.event_key,
            "split": row.split,
            "decision_score": score,
            "predicted_anomaly": bool(result["is_anomalous"]),
        })
        scores_by_split.setdefault(row.split, []).append(score)
    summaries: dict[str, object] = {}
    for split in ("validation", "test"):
        values = scores_by_split.get(split, [])
        summaries[split] = {
            "scored_records": len(values),
            "predicted_anomalies": sum(score < 0 for score in values),
            "predicted_anomaly_rate": sum(score < 0 for score in values) / len(values) if values else None,
            "decision_score_distribution": _score_distribution(values),
        }
    return predictions, summaries


def _score_distribution(values: Sequence[float]) -> dict[str, float] | None:
    if not values:
        return None
    array = np.asarray(values, dtype=float)
    if not np.isfinite(array).all():
        raise ValueError("Model produced non-finite evaluation scores")
    return {
        "min": float(np.min(array)),
        "p05": float(np.percentile(array, 5)),
        "median": float(np.median(array)),
        "mean": float(np.mean(array)),
        "p95": float(np.percentile(array, 95)),
        "max": float(np.max(array)),
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _write_predictions(path: Path, rows: Sequence[dict[str, object]], fields: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scikit_learn": sklearn.__version__,
        "joblib": joblib.__version__,
    }


def _experiment_dir(output_dir: Path) -> tuple[str, Path]:
    experiment_id = f"exp-{uuid.uuid4().hex}"
    path = Path(output_dir) / experiment_id
    path.mkdir(parents=True, exist_ok=False)
    return experiment_id, path


def run_snapshot_experiment(
    snapshot_dir: Path,
    output_dir: Path,
    *,
    contamination: float = 0.05,
    random_state: int = 42,
    n_estimators: int = 100,
) -> dict[str, object]:
    experiment_id, experiment_dir = _experiment_dir(output_dir)
    started_at = _now()
    metadata: dict[str, object] = {
        "experiment_id": experiment_id,
        "experiment_version": EXPERIMENT_VERSION,
        "experiment_status": "running",
        "dataset_kind": "validated_offline_snapshot",
        "started_at_utc": started_at,
        "model_type": "IsolationForest",
        "model_configuration": {
            "contamination": contamination,
            "random_state": random_state,
            "n_estimators": n_estimators,
        },
        "feature_names": list(FEATURE_NAMES),
        "decision_threshold": {
            "score_name": "decision_function",
            "anomaly_rule": "score < 0",
            "threshold": 0.0,
            "selection": "fixed zero threshold; IsolationForest offset is fitted on training split from contamination",
            "validation_or_test_tuning": False,
        },
        "software_versions": _versions(),
    }
    try:
        snapshot = load_validated_snapshot(Path(snapshot_dir))
        training_rows, excluded_train = _valid_rows(snapshot.rows, "train")
        if len(training_rows) < 10:
            raise ExperimentError("At least 10 complete training rows are required")
        validation_rows, excluded_validation = _valid_rows(snapshot.rows, "validation")
        test_rows, excluded_test = _valid_rows(snapshot.rows, "test")
        training_features = [[float(value) for value in row.features] for row in training_rows]
        training_started_at = _now()
        detector = fit_detector(
            training_features,
            contamination=contamination,
            random_state=random_state,
            n_estimators=n_estimators,
        )
        training_completed_at = _now()
        scored_rows = validation_rows + test_rows
        evaluation_started_at = _now()
        predictions, score_summaries = _score_rows(detector, scored_rows)
        evaluation_completed_at = _now()
        artifact_path = experiment_dir / "model.joblib"
        joblib.dump({
            "model": detector.model,
            "scaler": detector.scaler,
            "feature_names": FEATURE_NAMES,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
        }, artifact_path)
        artifact_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        _write_predictions(
            experiment_dir / "predictions.csv",
            predictions,
            ("event_key", "split", "decision_score", "predicted_anomaly"),
        )
        evaluation = {
            "dataset_snapshot_id": snapshot.snapshot_id,
            "evaluation_status": "unavailable_no_trustworthy_ground_truth_labels",
            "supervised_metrics": {
                "precision": None,
                "recall": None,
                "f1": None,
                "confusion_matrix": None,
            },
            "false_positive_analysis": "unavailable_no_trustworthy_ground_truth_labels",
            "false_negative_analysis": "unavailable_no_trustworthy_ground_truth_labels",
            "decision_threshold": metadata["decision_threshold"],
            "score_summary_by_split": score_summaries,
            "excluded_rows_missing_or_invalid_features": {
                "train": excluded_train,
                "validation": excluded_validation,
                "test": excluded_test,
            },
            "evaluation_label_source": None,
        }
        _write_json(experiment_dir / "evaluation.json", evaluation)
        metadata.update({
            "experiment_status": "completed",
            "completed_at_utc": evaluation_completed_at,
            "training_started_at_utc": training_started_at,
            "training_completed_at_utc": training_completed_at,
            "evaluation_started_at_utc": evaluation_started_at,
            "evaluation_completed_at_utc": evaluation_completed_at,
            "dataset_snapshot_id": snapshot.snapshot_id,
            "source_environment": snapshot.source_environment,
            "feature_specification_version": snapshot.feature_schema_version,
            "training_records": len(training_rows),
            "validation_records": len(validation_rows),
            "test_records": len(test_rows),
            "model_artifact": "model.joblib",
            "model_artifact_sha256": artifact_hash,
            "fitted_model_offset": float(detector.model.offset_),
            "evaluation_file": "evaluation.json",
        })
        _write_json(experiment_dir / "metadata.json", metadata)
        return {**metadata, "output_directory": str(experiment_dir), "evaluation": evaluation}
    except Exception as exc:
        try:
            failed_manifest = json.loads(
                (Path(snapshot_dir) / "manifest.json").read_text(encoding="utf-8")
            )
            if isinstance(failed_manifest, dict):
                for field, destination in (
                    ("snapshot_id", "dataset_snapshot_id"),
                    ("source_environment", "source_environment"),
                    ("feature_schema_version", "feature_specification_version"),
                ):
                    value = failed_manifest.get(field)
                    pattern = r"[0-9a-f]{64}" if field == "snapshot_id" else r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}"
                    if isinstance(value, str) and re.fullmatch(pattern, value):
                        metadata[destination] = value
        except (OSError, json.JSONDecodeError):
            pass
        metadata.update({
            "experiment_status": "failed",
            "completed_at_utc": _now(),
            "failure_type": type(exc).__name__,
        })
        _write_json(experiment_dir / "metadata.json", metadata)
        if isinstance(exc, (SnapshotValidationError, ExperimentError)):
            raise
        raise ExperimentError("Offline experiment failed; see metadata failure_type") from None


def _temporal_cutoffs(times: Sequence[datetime]) -> tuple[datetime | None, datetime | None]:
    unique = sorted(set(times))
    if not unique:
        return None, None
    train_index = max(0, min(len(unique) - 1, math.ceil(len(unique) * 0.70) - 1))
    validation_index = max(train_index, min(len(unique) - 1, math.ceil(len(unique) * 0.85) - 1))
    return unique[train_index], unique[validation_index]


def load_synthetic_benchmark(fixture_path: Path) -> SyntheticBenchmark:
    """Load existing generated scenario data; labels remain eval-side metadata."""
    from types import SimpleNamespace

    from app.services.ml_features import features_for_event

    fixture_path = Path(fixture_path)
    try:
        fixture_bytes = fixture_path.read_bytes()
        text = fixture_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError("Could not read synthetic benchmark fixture") from exc
    reader = csv.DictReader(text.splitlines())
    if tuple(reader.fieldnames or ()) != SYNTHETIC_FIELDS:
        raise ValueError("Synthetic fixture schema is not supported")
    raw_rows: list[tuple[int, object, str]] = []
    for row_number, row in enumerate(reader):
        user_id = (row.get("user_id") or "").strip()
        event_type = (row.get("event_type") or "").strip()
        source_ip = (row.get("source_ip") or "").strip()
        scenario = row.get("scenario") or ""
        if not user_id or not event_type or not source_ip or scenario not in SYNTHETIC_SCENARIOS:
            raise ValueError(f"Invalid synthetic fixture row {row_number + 2}")
        try:
            event_time = datetime.fromisoformat(row["event_time"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Invalid synthetic fixture timestamp at row {row_number + 2}") from exc
        if event_time.tzinfo is None or event_time.utcoffset() is None:
            raise ValueError(f"Synthetic fixture timestamp must be timezone-aware at row {row_number + 2}")
        event = SimpleNamespace(
            user_id=user_id,
            event_time=event_time,
            event_type=event_type,
            source_ip=source_ip,
        )
        raw_rows.append((row_number, event, scenario))
    raw_rows.sort(key=lambda item: (item[1].event_time.astimezone(timezone.utc), item[0]))
    times = [item[1].event_time.astimezone(timezone.utc) for item in raw_rows]
    train_end, validation_end = _temporal_cutoffs(times)
    histories: dict[str, list[object]] = {}
    result: list[SyntheticRow] = []
    for row_number, event, scenario in raw_rows:
        event_time = event.event_time.astimezone(timezone.utc)
        features = features_for_event(event, histories.setdefault(event.user_id, []))
        if event_time <= train_end:
            split = "train"
        elif event_time <= validation_end:
            split = "validation"
        else:
            split = "test"
        result.append(SyntheticRow(row_number, split, tuple(float(value) for value in features), scenario))
        histories[event.user_id].append(event)
    fixture_id = hashlib.sha256(fixture_bytes).hexdigest()
    return SyntheticBenchmark(
        fixture_id,
        tuple(result),
        {
            "train_end": train_end.isoformat() if train_end else None,
            "validation_end": validation_end.isoformat() if validation_end else None,
        },
    )


def _binary_metrics(scenarios: Sequence[str], predictions: Sequence[bool]) -> dict[str, object]:
    if len(scenarios) != len(predictions):
        raise ValueError("Expected one prediction for each labeled evaluation row")
    actual = [scenario != "normal" for scenario in scenarios]
    tp = sum(y and pred for y, pred in zip(actual, predictions))
    fp = sum((not y) and pred for y, pred in zip(actual, predictions))
    fn = sum(y and (not pred) for y, pred in zip(actual, predictions))
    tn = sum((not y) and (not pred) for y, pred in zip(actual, predictions))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if recall is not None and precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": {"labels": ["normal", "anomaly"], "values": [[tn, fp], [fn, tp]]},
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "support": len(actual),
    }


def run_synthetic_benchmark(
    fixture_path: Path,
    output_dir: Path,
    *,
    contamination: float = 0.05,
    random_state: int = 42,
    n_estimators: int = 100,
) -> dict[str, object]:
    experiment_id, experiment_dir = _experiment_dir(output_dir)
    started_at = _now()
    try:
        benchmark = load_synthetic_benchmark(fixture_path)
        # The fit API receives features only; scenario labels are not passed to training.
        training_rows = [row for row in benchmark.rows if row.split == "train"]
        if len(training_rows) < 10:
            raise ExperimentError("At least 10 synthetic training rows are required")
        training_started_at = _now()
        detector = fit_detector(
            [row.features for row in training_rows],
            contamination=contamination,
            random_state=random_state,
            n_estimators=n_estimators,
        )
        training_completed_at = _now()
        evaluation_started_at = _now()
        validation_rows = [row for row in benchmark.rows if row.split == "validation"]
        test_rows = [row for row in benchmark.rows if row.split == "test"]
        scored: dict[str, list[tuple[SyntheticRow, dict[str, object]]]] = {"validation": [], "test": []}
        for split, selected in (("validation", validation_rows), ("test", test_rows)):
            for row in selected:
                scored[split].append((row, detector.score(row.features)))
        evaluation_completed_at = _now()
        test_pairs = scored["test"]
        scenarios = [row.scenario for row, _ in test_pairs]
        predictions = [bool(score["is_anomalous"]) for _, score in test_pairs]
        metrics = _binary_metrics(scenarios, predictions)
        by_scenario: dict[str, object] = {}
        for scenario in sorted(SYNTHETIC_SCENARIOS):
            pairs = [(row, score) for row, score in test_pairs if row.scenario == scenario]
            scenario_scores = [float(score["decision_score"]) for _, score in pairs]
            flagged = sum(bool(score["is_anomalous"]) for _, score in pairs)
            by_scenario[scenario] = {
                "support": len(pairs),
                "predicted_anomalies": flagged,
                "predicted_anomaly_rate": flagged / len(pairs) if pairs else None,
                "decision_score_distribution": _score_distribution(scenario_scores),
            }
        evaluation = {
            "evaluation_status": "synthetic_ground_truth_only",
            "label_source": "generator scenario column; evaluation only",
            "warning": "Synthetic scenario metrics are not production performance or confirmation of malicious activity.",
            "test_metrics": metrics,
            "false_positive_analysis": {"count": metrics["false_positive"], "scenario": "normal"},
            "false_negative_analysis": {"count": metrics["false_negative"], "positive_scenarios": ["unfamiliar_ip", "unusual_hour"]},
            "by_synthetic_scenario": by_scenario,
            "score_summary_by_split": {
                split: {
                    "scored_records": len(items),
                    "predicted_anomalies": sum(bool(score["is_anomalous"]) for _, score in items),
                    "decision_score_distribution": _score_distribution([float(score["decision_score"]) for _, score in items]),
                }
                for split, items in scored.items()
            },
        }
        prediction_rows = []
        for split, items in scored.items():
            for row, score in items:
                prediction_rows.append({
                    "record_number": row.row_number,
                    "split": split,
                    "scenario": row.scenario,
                    "actual_anomaly": row.scenario != "normal",
                    "predicted_anomaly": bool(score["is_anomalous"]),
                    "decision_score": float(score["decision_score"]),
                })
        _write_predictions(
            experiment_dir / "predictions.csv",
            prediction_rows,
            ("record_number", "split", "scenario", "actual_anomaly", "predicted_anomaly", "decision_score"),
        )
        artifact_path = experiment_dir / "model.joblib"
        joblib.dump({
            "model": detector.model,
            "scaler": detector.scaler,
            "feature_names": FEATURE_NAMES,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
        }, artifact_path)
        artifact_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        metadata = {
            "experiment_id": experiment_id,
            "experiment_version": EXPERIMENT_VERSION,
            "experiment_status": "completed",
            "dataset_kind": "deterministic_synthetic_fixture",
            "source_environment": "synthetic",
            "dataset_fixture_sha256": benchmark.fixture_id,
            "dataset_snapshot_id": None,
            "feature_specification_version": FEATURE_SCHEMA_VERSION,
            "feature_names": list(FEATURE_NAMES),
            "model_type": "IsolationForest",
            "model_configuration": {"contamination": contamination, "random_state": random_state, "n_estimators": n_estimators},
            "training_started_at_utc": training_started_at,
            "training_completed_at_utc": training_completed_at,
            "evaluation_started_at_utc": evaluation_started_at,
            "evaluation_completed_at_utc": evaluation_completed_at,
            "training_records": len(training_rows),
            "validation_records": len(validation_rows),
            "test_records": len(test_rows),
            "training_used_scenario_labels": False,
            "temporal_cutoffs_utc": benchmark.split_cutoffs,
            "decision_threshold": {
                "score_name": "decision_function",
                "anomaly_rule": "score < 0",
                "threshold": 0.0,
                "selection": "fixed zero threshold; IsolationForest offset is fitted on training split from contamination",
                "validation_or_test_tuning": False,
            },
            "software_versions": _versions(),
            "model_artifact": "model.joblib",
            "model_artifact_sha256": artifact_hash,
            "fitted_model_offset": float(detector.model.offset_),
            "evaluation_file": "evaluation.json",
            "evaluation_warning": evaluation["warning"],
        }
        _write_json(experiment_dir / "evaluation.json", evaluation)
        _write_json(experiment_dir / "metadata.json", metadata)
        return {**metadata, "output_directory": str(experiment_dir), "evaluation": evaluation}
    except Exception as exc:
        _write_json(experiment_dir / "metadata.json", {
            "experiment_id": experiment_id,
            "experiment_version": EXPERIMENT_VERSION,
            "experiment_status": "failed",
            "dataset_kind": "deterministic_synthetic_fixture",
            "source_environment": "synthetic",
            "started_at_utc": started_at,
            "completed_at_utc": _now(),
            "failure_type": type(exc).__name__,
        })
        if isinstance(exc, ExperimentError):
            raise
        raise ExperimentError("Synthetic benchmark failed; see metadata failure_type") from None
