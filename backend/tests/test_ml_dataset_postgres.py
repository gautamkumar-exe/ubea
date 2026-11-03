"""Opt-in PostgreSQL integration tests using a disposable local cluster.

These tests never use DATABASE_URL from the app environment to initialize,
select, or delete test data. They create a new cluster in a temporary directory.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import joblib
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models.security_event import SecurityEvent
from app.services.ml_dataset import CSV_FIELDS, SnapshotOptions, build_snapshot

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
TEST_DATABASE = "ueba_ml_test"
TEST_KEY = b"9fc2a307bd4e65f09876ab123456cdef" * 2
TEST_KEY_ID = "integration-test-v1"
CUTOFF = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


@pytest.fixture
def isolated_postgres():
    if os.environ.get("UEBA_RUN_POSTGRES_INTEGRATION") != "1":
        pytest.skip("set UEBA_RUN_POSTGRES_INTEGRATION=1 to launch an isolated PostgreSQL cluster")
    binaries = {name: shutil.which(name) for name in ("initdb", "pg_ctl")}
    if not all(binaries.values()):
        pytest.skip("initdb and pg_ctl are required for PostgreSQL integration tests")

    cluster_root = Path(tempfile.mkdtemp(prefix="ueba-ml-pg-", dir="/private/tmp"))
    data_dir = cluster_root / "data"
    log_path = cluster_root / "postgres.log"
    port = _free_port()
    started = False
    engine = None
    try:
        subprocess.run(
            [binaries["initdb"], "-D", str(data_dir), "--username=postgres", "--auth=trust", "--no-locale", "--encoding=UTF8"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [binaries["pg_ctl"], "-D", str(data_dir), "-o", f"-h 127.0.0.1 -p {port} -F", "-l", str(log_path), "-w", "start"],
            check=True,
            capture_output=True,
            text=True,
        )
        started = True
        with psycopg.connect(host="127.0.0.1", port=port, user="postgres", dbname="postgres", autocommit=True) as connection:
            connection.execute(f'CREATE DATABASE "{TEST_DATABASE}"')
        database_url = f"postgresql+psycopg://postgres@127.0.0.1:{port}/{TEST_DATABASE}"
        engine = create_engine(database_url, pool_pre_ping=True)
        SecurityEvent.__table__.create(engine)
        yield {"url": database_url, "engine": engine, "cluster_root": cluster_root}
    finally:
        if engine is not None:
            engine.dispose()
        if started:
            subprocess.run(
                [binaries["pg_ctl"], "-D", str(data_dir), "-m", "fast", "-w", "stop"],
                check=False,
                capture_output=True,
                text=True,
            )
        shutil.rmtree(cluster_root, ignore_errors=True)


def _event(
    event_type: str,
    event_time: datetime,
    *,
    external_id: str,
    user_id: str | None = "synthetic-user-a",
    source_ip: str | None = "192.0.2.10",
    raw_event: dict | None = None,
) -> SecurityEvent:
    return SecurityEvent(
        source="synthetic-source",
        external_id=external_id,
        event_type=event_type,
        user_id=user_id,
        entity_id="synthetic-entity-a" if user_id else None,
        source_ip=source_ip,
        event_time=event_time,
        raw_event=raw_event or {"payload_secret": "synthetic-payload-value"},
    )


def _seed_controlled_events(engine) -> dict[str, SecurityEvent]:
    before = _event("login_success", datetime(2026, 9, 1, 8, tzinfo=timezone.utc), external_id="before-id")
    malformed = _event("", datetime(2026, 9, 1, 8, 30, tzinfo=timezone.utc), external_id="malformed-id", user_id=None, source_ip="not-an-ip")
    filler = {
        "filler-1": _event("file_access", datetime(2026, 9, 1, 8, 10, tzinfo=timezone.utc), external_id="filler-1-id"),
        "filler-2": _event("file_access", datetime(2026, 9, 1, 8, 20, tzinfo=timezone.utc), external_id="filler-2-id"),
        "filler-3": _event("file_access", datetime(2026, 9, 1, 8, 40, tzinfo=timezone.utc), external_id="filler-3-id"),
        "filler-4": _event("file_access", datetime(2026, 9, 1, 8, 50, tzinfo=timezone.utc), external_id="filler-4-id"),
    }
    boundary = _event("login_success", CUTOFF, external_id="boundary-id")
    after = _event("admin_action", datetime(2026, 9, 1, 9, 0, 1, tzinfo=timezone.utc), external_id="after-id", source_ip="198.51.100.20")
    events = {"before": before, **filler, "malformed": malformed, "boundary": boundary, "after": after}
    with Session(engine, expire_on_commit=False) as session:
        session.add_all(events.values())
        session.commit()
    return events


def test_postgres_cutoff_ordering_and_read_only_extraction(isolated_postgres):
    engine = isolated_postgres["engine"]
    inserted = _seed_controlled_events(engine)
    before_values = {}
    with Session(engine) as session:
        for name, event in inserted.items():
            persisted = session.scalar(select(SecurityEvent).where(SecurityEvent.external_id == event.external_id))
            before_values[name] = (persisted.id, persisted.event_type, persisted.user_id, persisted.source_ip, persisted.event_time, persisted.raw_event.copy())

    from scripts.prepare_ml_dataset import _read_events_read_only

    extracted = _read_events_read_only(isolated_postgres["url"], CUTOFF)
    assert [event.event_time for event in extracted] == sorted(event.event_time for event in extracted)
    assert [event.external_id for event in extracted] == ["before-id", "filler-1-id", "filler-2-id", "malformed-id", "filler-3-id", "filler-4-id", "boundary-id"]
    assert extracted[-1].event_time == CUTOFF  # inclusive boundary
    assert all(event.external_id != "after-id" for event in extracted)

    # PostgreSQL itself rejects writes in the declared read-only transaction.
    with Session(engine) as session:
        with session.begin():
            session.execute(text("SET TRANSACTION READ ONLY"))
            with pytest.raises(DBAPIError):
                session.execute(
                    text("UPDATE security_events SET event_type = 'changed' WHERE external_id = 'before-id'")
                )
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(SecurityEvent)) == 8
        for name, event in inserted.items():
            persisted = session.scalar(select(SecurityEvent).where(SecurityEvent.external_id == event.external_id))
            assert (persisted.id, persisted.event_type, persisted.user_id, persisted.source_ip, persisted.event_time, persisted.raw_event) == before_values[name]


def test_postgres_rejects_malformed_timestamp_without_persisting_a_row(isolated_postgres):
    engine = isolated_postgres["engine"]
    with pytest.raises(DBAPIError):
        with engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO security_events
                      (id, source, external_id, event_type, event_time, raw_event)
                    VALUES
                      ('00000000-0000-4000-8000-000000000001', 'synthetic-source', 'invalid-time-id',
                       'login_success', 'not-a-timestamp', '{}')
                """)
            )
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(SecurityEvent)) == 0


def _run_cli(database_url: str, output_dir: Path, *, secret: str | None, key_id: str = TEST_KEY_ID, cutoff: str = "2026-09-01T09:00:00Z"):
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["ENVIRONMENT"] = "test"
    env.pop("UEBA_SNAPSHOT_HMAC_KEY", None)
    if secret is not None:
        env["UEBA_SNAPSHOT_HMAC_KEY"] = secret
    env["UEBA_SNAPSHOT_HMAC_KEY_ID"] = key_id
    return subprocess.run(
        [sys.executable, "-m", "scripts.prepare_ml_dataset", "--cutoff", cutoff, "--output-dir", str(output_dir)],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_snapshot_schema_privacy_features_quality_splits_and_determinism(isolated_postgres, tmp_path: Path):
    engine = isolated_postgres["engine"]
    _seed_controlled_events(engine)
    key_text = TEST_KEY.decode("latin-1")
    first = _run_cli(isolated_postgres["url"], tmp_path / "first", secret=key_text)
    second = _run_cli(isolated_postgres["url"], tmp_path / "second", secret=key_text)
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    first_summary, second_summary = json.loads(first.stdout), json.loads(second.stdout)
    assert first_summary["snapshot_id"] == second_summary["snapshot_id"]
    assert first_summary["pseudonymization_key_id"] == TEST_KEY_ID

    first_dir, second_dir = Path(first_summary["output_directory"]), Path(second_summary["output_directory"])
    for filename in ("dataset.csv", "manifest.json", "splits.json"):
        assert (first_dir / filename).read_bytes() == (second_dir / filename).read_bytes()
    with (first_dir / "dataset.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        assert tuple(reader.fieldnames) == CSV_FIELDS
    assert len(rows) == 7
    assert [row["external_key"] for row in rows] == [
        _token_for_test(value, "external-id")
        for value in ("before-id", "filler-1-id", "filler-2-id", "malformed-id", "filler-3-id", "filler-4-id", "boundary-id")
    ]
    # Validate each of the existing seven features on the cutoff event.
    assert float(rows[-1]["hour_sin"]) == pytest.approx(math.sin(2 * math.pi * 9 / 24))
    assert float(rows[-1]["hour_cos"]) == pytest.approx(math.cos(2 * math.pi * 9 / 24))
    assert rows[-1]["is_known_ip"] == "1.0"
    assert rows[-1]["is_known_event_type"] == "1.0"
    assert rows[-1]["is_login"] == "1.0"
    assert float(rows[-1]["user_event_frequency"]) == pytest.approx(math.log1p(5))
    assert float(rows[-1]["source_ip_frequency"]) == pytest.approx(math.log1p(5))
    assert rows[3]["feature_status"] == "invalid_event_type"
    assert rows[3]["is_known_ip"] == ""
    assert rows[0]["user_key"] == rows[-1]["user_key"]
    assert rows[0]["source_ip_key"] == rows[-1]["source_ip_key"]
    assert rows[0]["user_key"] != rows[0]["subject_key"]  # namespace separation

    exported = b"".join((first_dir / name).read_bytes() for name in ("dataset.csv", "manifest.json", "splits.json"))
    for sensitive in (b"synthetic-user-a", b"synthetic-entity-a", b"synthetic-source", b"before-id", b"boundary-id", b"192.0.2.10", b"not-an-ip", b"synthetic-payload-value"):
        assert sensitive not in exported
    assert TEST_KEY not in exported

    manifest = json.loads((first_dir / "manifest.json").read_text())
    assert manifest["source_environment"] == "test"
    assert manifest["records_processed"] == 7
    assert manifest["records_in_snapshot"] == 7
    assert manifest["invalid_feature_values"] == 1
    assert manifest["labels"]["unlabeled_records"] == 7
    assert manifest["labels"]["class_distribution"] is None
    assert manifest["entity_coverage"] == 1
    assert manifest["temporal_coverage_utc"]["start"] < manifest["temporal_coverage_utc"]["end"]
    assert manifest["missing_values"]["event_type_key"] == 1
    splits = json.loads((first_dir / "splits.json").read_text())
    assert [splits["partitions"][name]["records"] for name in ("train", "validation", "test")] == [5, 1, 1]
    assert splits["partitions"]["train"]["end_utc"] < splits["partitions"]["validation"]["end_utc"]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(SecurityEvent)) == 8
        stored_boundary = session.scalar(
            select(SecurityEvent).where(SecurityEvent.external_id == "boundary-id")
        )
        assert stored_boundary.event_type == "login_success"
        assert stored_boundary.raw_event == {"payload_secret": "synthetic-payload-value"}


def test_snapshot_to_model_experiment_end_to_end(isolated_postgres, tmp_path: Path):
    """Exercise snapshot and snapshot-mode training CLIs on disposable synthetic PostgreSQL."""
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    events = [
        _event(
            "login_success" if index % 3 == 0 else "file_access",
            start + timedelta(hours=index),
            external_id=f"controlled-experiment-event-{index}",
            user_id=f"controlled-experiment-user-{index % 4}",
            source_ip=f"192.0.2.{10 + index % 5}",
            raw_event={"controlled_payload": f"private-value-{index}"},
        )
        for index in range(60)
    ]
    with Session(isolated_postgres["engine"]) as session:
        session.add_all(events)
        session.commit()

    snapshot_output = tmp_path / "snapshots"
    snapshot_process = _run_cli(
        isolated_postgres["url"],
        snapshot_output,
        secret=TEST_KEY.decode("latin-1"),
        cutoff="2026-09-01T00:00:00Z",
    )
    assert snapshot_process.returncode == 0, snapshot_process.stderr
    snapshot_summary = json.loads(snapshot_process.stdout)
    snapshot_dir = Path(snapshot_summary["output_directory"])
    manifest = json.loads((snapshot_dir / "manifest.json").read_text())
    assert manifest["source_environment"] == "test"
    assert manifest["records_in_snapshot"] == 60
    assert manifest["feature_names"] == [
        "hour_sin", "hour_cos", "is_login", "is_known_ip",
        "is_known_event_type", "user_event_frequency", "source_ip_frequency",
    ]

    experiment_output = tmp_path / "experiments"
    experiment_env = os.environ.copy()
    experiment_env["PYTHONPATH"] = str(BACKEND_ROOT)
    experiment_process = subprocess.run(
        [
            sys.executable, "-m", "scripts.run_ml_experiment",
            "--snapshot-dir", str(snapshot_dir),
            "--confirm-nonproduction",
            "--output-dir", str(experiment_output),
            "--contamination", "0.05",
            "--random-state", "42",
            "--n-estimators", "100",
        ],
        cwd=BACKEND_ROOT,
        env=experiment_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert experiment_process.returncode == 0, experiment_process.stderr
    result = json.loads(experiment_process.stdout)
    experiment_dir = Path(result["output_directory"])
    metadata = json.loads((experiment_dir / "metadata.json").read_text())
    evaluation = json.loads((experiment_dir / "evaluation.json").read_text())

    assert metadata["experiment_status"] == "completed"
    assert metadata["dataset_kind"] == "validated_offline_snapshot"
    assert metadata["dataset_snapshot_id"] == snapshot_summary["snapshot_id"]
    assert metadata["source_environment"] == "test"
    assert metadata["feature_specification_version"] == "ueba-seven-v2"
    assert metadata["feature_names"] == manifest["feature_names"]
    assert metadata["model_configuration"] == {
        "contamination": 0.05,
        "random_state": 42,
        "n_estimators": 100,
    }
    assert metadata["decision_threshold"]["threshold"] == 0.0
    assert metadata["decision_threshold"]["validation_or_test_tuning"] is False
    assert metadata["training_records"] > 10
    assert metadata["validation_records"] > 0
    assert metadata["test_records"] > 0
    assert (
        metadata["training_records"]
        + metadata["validation_records"]
        + metadata["test_records"]
        == manifest["records_in_snapshot"]
    )
    assert evaluation["evaluation_status"] == "unavailable_no_trustworthy_ground_truth_labels"
    assert evaluation["supervised_metrics"] == {
        "precision": None,
        "recall": None,
        "f1": None,
        "confusion_matrix": None,
    }
    for split in ("validation", "test"):
        summary = evaluation["score_summary_by_split"][split]
        assert summary["scored_records"] > 0
        assert summary["decision_score_distribution"] is not None
        assert summary["predicted_anomalies"] <= summary["scored_records"]
        assert 0 <= summary["predicted_anomaly_rate"] <= 1

    model_path = experiment_dir / "model.joblib"
    assert hashlib.sha256(model_path.read_bytes()).hexdigest() == metadata["model_artifact_sha256"]
    model_artifact = joblib.load(model_path)
    assert model_artifact["feature_names"] == tuple(manifest["feature_names"])
    assert model_artifact["scaler"].n_samples_seen_ == metadata["training_records"]
    assert model_artifact["model"].random_state == 42
    assert len(model_artifact["model"].estimators_) == 100

    exported = b"".join(path.read_bytes() for path in experiment_dir.iterdir() if path.is_file())
    for sensitive in (
        TEST_KEY,
        b"controlled-experiment-user-",
        b"controlled-experiment-event-",
        b"private-value-",
        b"192.0.2.10",
    ):
        assert sensitive not in exported
    predictions = (experiment_dir / "predictions.csv").read_text()
    assert "event_key" in predictions
    assert "controlled-experiment-event-" not in predictions

    # Keep the verification output itself free of identifiers, keys, and raw event data.
    print(json.dumps({
        "snapshot_id": snapshot_summary["snapshot_id"],
        "source_environment": manifest["source_environment"],
        "snapshot_records": manifest["records_in_snapshot"],
        "split_records": {
            "train": metadata["training_records"],
            "validation": metadata["validation_records"],
            "test": metadata["test_records"],
        },
        "experiment_id": metadata["experiment_id"],
        "evaluation_status": evaluation["evaluation_status"],
        "test_anomaly_count": evaluation["score_summary_by_split"]["test"]["predicted_anomalies"],
        "test_anomaly_rate": evaluation["score_summary_by_split"]["test"]["predicted_anomaly_rate"],
        "model_sha256_verified": True,
        "sensitive_values_absent": True,
    }, sort_keys=True))


def _token_for_test(value: str, namespace: str) -> str:
    import hmac
    return hmac.new(TEST_KEY, f"{namespace}\0{value}".encode(), hashlib.sha256).hexdigest()


def test_cli_fails_closed_for_missing_database_or_hmac_key(isolated_postgres, tmp_path: Path):
    database_url = isolated_postgres["url"]
    no_secret = _run_cli(database_url, tmp_path / "missing-key", secret=None)
    assert no_secret.returncode == 2
    assert "UEBA_SNAPSHOT_HMAC_KEY is not configured" in no_secret.stderr
    assert no_secret.stdout == ""

    short_secret = "never-print-this-short-secret"
    invalid_secret = _run_cli(database_url, tmp_path / "short-key", secret=short_secret)
    assert invalid_secret.returncode == 2
    assert "at least 32 bytes" in invalid_secret.stderr
    assert short_secret not in invalid_secret.stdout + invalid_secret.stderr

    invalid_key_id = _run_cli(database_url, tmp_path / "bad-key-id", secret=TEST_KEY.decode("latin-1"), key_id="bad key id")
    assert invalid_key_id.returncode == 2
    assert "Invalid snapshot configuration" in invalid_key_id.stderr

    invalid_environment = os.environ.copy()
    invalid_environment["DATABASE_URL"] = database_url
    invalid_environment["ENVIRONMENT"] = "production"
    invalid_environment["UEBA_SNAPSHOT_HMAC_KEY"] = TEST_KEY.decode("latin-1")
    forbidden_environment = subprocess.run(
        [sys.executable, "-m", "scripts.prepare_ml_dataset", "--cutoff", "2026-09-01T09:00:00Z", "--output-dir", str(tmp_path / "production")],
        cwd=BACKEND_ROOT,
        env=invalid_environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert forbidden_environment.returncode == 2
    assert "development or test" in forbidden_environment.stderr

    env = os.environ.copy()
    env["DATABASE_URL"] = ""
    env["ENVIRONMENT"] = "test"
    env["UEBA_SNAPSHOT_HMAC_KEY"] = TEST_KEY.decode("latin-1")
    missing_database = subprocess.run(
        [sys.executable, "-m", "scripts.prepare_ml_dataset", "--cutoff", "2026-09-01T09:00:00Z", "--output-dir", str(tmp_path / "missing-db")],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing_database.returncode == 2
    assert "DATABASE_URL is not configured" in missing_database.stderr
    assert "isolated PostgreSQL" in missing_database.stderr


def test_hmac_validation_and_key_rotation_change_snapshot_identity():
    event = _event("login_success", datetime(2026, 9, 1, 8, tzinfo=timezone.utc), external_id="rotate-me")
    with pytest.raises(ValueError, match="at least 32 bytes"):
        SnapshotOptions(CUTOFF, b"short")
    assert SnapshotOptions(CUTOFF, bytes(range(32))).hmac_key == bytes(range(32))
    with pytest.raises(ValueError, match="at least 32 bytes"):
        SnapshotOptions(CUTOFF, "not-bytes")
    with pytest.raises(ValueError, match="key ID"):
        SnapshotOptions(CUTOFF, TEST_KEY, "invalid key id")

    _, original = build_snapshot([event], SnapshotOptions(CUTOFF, TEST_KEY, "key-v1"))
    _, new_version = build_snapshot([event], SnapshotOptions(CUTOFF, TEST_KEY, "key-v2"))
    _, rotated_secret = build_snapshot([event], SnapshotOptions(CUTOFF, bytes.fromhex("a3" * 32), "key-v2"))
    assert original["pseudonymization_key_id"] == "key-v1"
    assert original["snapshot_id"] != new_version["snapshot_id"]
    assert new_version["snapshot_id"] != rotated_secret["snapshot_id"]
