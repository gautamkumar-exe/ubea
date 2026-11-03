from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.services.ml_dataset import SnapshotOptions, build_snapshot, write_snapshot

KEY = b"test-key-material-that-is-at-least-32-bytes"
CUTOFF = datetime(2026, 10, 1, tzinfo=timezone.utc)


def make_event(
    event_id: str,
    at: str,
    *,
    user: str | None = "user-private-1",
    entity: str | None = None,
    event_type: str | None = "login_success",
    ip: str | None = "192.0.2.10",
    source: str = "source-private",
    external_id: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=event_id,
        source=source,
        external_id=external_id or f"external-{event_id}",
        user_id=user,
        entity_id=entity,
        event_type=event_type,
        source_ip=ip,
        event_time=datetime.fromisoformat(at),
        raw_event={"secret": "must-not-be-exported"},
    )


def test_snapshot_is_deterministic_and_does_not_mutate_source_records(tmp_path: Path):
    events = [
        make_event("one", "2026-09-01T08:00:00+00:00"),
        make_event("two", "2026-09-02T09:00:00+00:00"),
    ]
    before = [(event.user_id, event.source_ip, event.raw_event.copy()) for event in events]
    options = SnapshotOptions(CUTOFF, KEY)

    first = write_snapshot(events, options, tmp_path / "first")
    second = write_snapshot(events, options, tmp_path / "second")

    assert first["snapshot_id"] == second["snapshot_id"]
    first_dir = Path(first["output_directory"])
    second_dir = Path(second["output_directory"])
    for filename in ("dataset.csv", "manifest.json", "splits.json"):
        assert (first_dir / filename).read_bytes() == (second_dir / filename).read_bytes()
    assert before == [(event.user_id, event.source_ip, event.raw_event) for event in events]
    assert first["source_read_only"] is True


def test_features_are_correct_and_use_prior_same_user_events_only():
    earlier = make_event("one", "2026-09-01T08:00:00+00:00")
    target = make_event("two", "2026-09-01T09:00:00+00:00")
    other_user = make_event("other", "2026-09-01T08:30:00+00:00", user="another-user")
    rows, _ = build_snapshot([target, other_user, earlier], SnapshotOptions(CUTOFF, KEY))
    target_row = next(row for row in rows if row["event_key"] == _key("two"))

    assert target_row["is_login"] == 1.0
    assert target_row["is_known_ip"] == 1.0
    assert target_row["is_known_event_type"] == 1.0
    assert target_row["user_event_frequency"] > 0
    assert target_row["source_ip_frequency"] > 0


def _key(event_id: str) -> str:
    import hashlib
    import hmac
    return hmac.new(KEY, f"event-id\0{event_id}".encode(), hashlib.sha256).hexdigest()


def test_future_and_equal_timestamp_events_do_not_leak_into_features():
    target = make_event("target", "2026-09-01T09:00:00+00:00", event_type="file_access", ip="198.51.100.9")
    same_time = make_event("same", "2026-09-01T09:00:00+00:00", event_type="file_access", ip="198.51.100.9")
    future = make_event("future", "2026-09-01T10:00:00+00:00", event_type="file_access", ip="198.51.100.9")

    rows, _ = build_snapshot([future, same_time, target], SnapshotOptions(CUTOFF, KEY))
    target_row = next(row for row in rows if row["event_key"] == _key("target"))

    assert target_row["is_known_ip"] == 0.0
    assert target_row["is_known_event_type"] == 0.0
    assert target_row["user_event_frequency"] == 0.0
    assert target_row["source_ip_frequency"] == 0.0


def test_temporal_splits_are_deterministic_and_keep_timestamps_together():
    events = [make_event(str(i), f"2026-09-{i + 1:02d}T08:00:00+00:00") for i in range(20)]
    events.append(make_event("same-time", "2026-09-14T08:00:00+00:00"))
    rows, metadata = build_snapshot(events, SnapshotOptions(CUTOFF, KEY))
    by_time: dict[str, set[str]] = {}
    for row in rows:
        by_time.setdefault(row["event_time_utc"], set()).add(row["split"])

    assert all(len(partitions) == 1 for partitions in by_time.values())
    assert set(metadata["split_counts"]) == {"train", "validation", "test"}
    assert metadata["split_counts"]["train"] > metadata["split_counts"]["validation"] > 0
    assert metadata["split_counts"]["test"] > 0
    assert metadata["split_cutoffs_utc"]["train_end"] < metadata["split_cutoffs_utc"]["validation_end"]


def test_cutoff_duplicates_missing_invalid_values_and_labels_are_reported():
    base = make_event("one", "2026-09-01T08:00:00+00:00", external_id="duplicate")
    duplicate = make_event("two", "2026-09-01T08:00:00+00:00", external_id="duplicate")
    after_cutoff = make_event("late", "2026-10-02T08:00:00+00:00")
    missing = make_event("missing", "2026-09-03T08:00:00+00:00", user=None, ip=None)
    malformed = make_event("malformed", "2026-09-04T08:00:00+00:00", event_type=None, ip="not-an-ip")
    invalid_time = make_event("invalid-time", "2026-09-05T08:00:00+00:00")
    invalid_time.event_time = datetime(2026, 9, 5, 8)  # naive historic row

    rows, metadata = build_snapshot(
        [base, duplicate, after_cutoff, missing, malformed, invalid_time],
        SnapshotOptions(CUTOFF, KEY),
    )

    assert metadata["records_processed"] == 6
    assert metadata["records_at_or_before_cutoff"] == 4
    assert metadata["records_without_comparable_timestamp"] == 1
    assert metadata["duplicate_records_removed"] == 1
    assert metadata["records_in_snapshot"] == 4
    assert metadata["invalid_timestamps"] == 1
    assert metadata["invalid_feature_values"] >= 1
    assert metadata["labels"]["unlabeled_records"] == 4
    assert metadata["labels"]["class_distribution"] is None
    assert metadata["entity_coverage"] == 1
    missing_row = next(row for row in rows if row["event_key"] == _key("missing"))
    assert missing_row["source_ip_key"] is None
    assert missing_row["is_known_ip"] is None
    assert missing_row["user_event_frequency"] is None
    invalid_row = next(row for row in rows if row["event_key"] == _key("invalid-time"))
    assert invalid_row["split"] == "unassigned_invalid_time"
    assert metadata["missing_values"]["event_time_utc"] == 1


def test_snapshot_does_not_export_raw_identifiers_or_ip_values(tmp_path: Path):
    event = make_event("secret-event-id", "2026-09-01T08:00:00+00:00")
    result = write_snapshot([event], SnapshotOptions(CUTOFF, KEY), tmp_path)
    output = Path(result["output_directory"])
    exported = b"".join((output / name).read_bytes() for name in ("dataset.csv", "manifest.json", "splits.json"))

    for sensitive in (b"user-private-1", b"source-private", b"external-secret", b"192.0.2.10", b"must-not-be-exported", b"secret-event-id"):
        assert sensitive not in exported
    assert len(next(row for row in build_snapshot([event], SnapshotOptions(CUTOFF, KEY))[0])["user_key"]) == 64


def test_snapshot_preparation_leaves_persisted_event_rows_unchanged():
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.database import Base
    from app.models.security_event import SecurityEvent

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            event = SecurityEvent(
                source="synthetic-source",
                external_id="synthetic-external-id",
                event_type="login_success",
                user_id="synthetic-user",
                entity_id="synthetic-device",
                source_ip="192.0.2.1",
                event_time=datetime(2026, 9, 1, 8, tzinfo=timezone.utc),
                raw_event={"fixture": True},
            )
            session.add(event)
            session.commit()
            original_id = event.id
            original_snapshot = (
                event.source, event.external_id, event.event_type, event.user_id,
                event.entity_id, event.source_ip, event.event_time, event.raw_event.copy(),
            )
            selected = session.scalars(select(SecurityEvent)).all()
            build_snapshot(selected, SnapshotOptions(CUTOFF, KEY))
            session.expire_all()
            persisted = session.scalars(select(SecurityEvent)).one()
            after_snapshot = (
                persisted.source, persisted.external_id, persisted.event_type,
                persisted.user_id, persisted.entity_id, persisted.source_ip,
                persisted.event_time, persisted.raw_event.copy(),
            )
            assert persisted.id == original_id
            assert after_snapshot == original_snapshot
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_database_reader_declares_read_only_transaction(monkeypatch):
    from scripts import prepare_ml_dataset

    executed: list[object] = []

    class _Transaction:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class _Result:
        def scalars(self):
            return self

        def all(self):
            return []

    class _Session:
        def __init__(self, engine, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def begin(self):
            return _Transaction()

        def execute(self, statement):
            executed.append(statement)
            return _Result()

        def scalars(self, statement):
            executed.append(statement)
            return _Result()

    class _Engine:
        def dispose(self):
            pass

    monkeypatch.setattr(prepare_ml_dataset, "create_engine", lambda *args, **kwargs: _Engine())
    monkeypatch.setattr(prepare_ml_dataset, "Session", _Session)

    assert prepare_ml_dataset._read_events_read_only("postgresql://local", CUTOFF) == []
    assert str(executed[0]) == "SET TRANSACTION READ ONLY"
    assert str(executed[1]).lstrip().upper().startswith("SELECT")
    assert all("INSERT" not in str(statement).upper() for statement in executed)
