from __future__ import annotations

import math
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.ml_dataset import _feature_rows
from app.services.ml_features import features_for_event


def event(
    external_id: str,
    event_time: datetime,
    *,
    user_id: str | None = "user-a",
    event_type: str | None = "file_access",
    source_ip: str | None = "192.0.2.10",
    source: str = "fixture",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=external_id,
        source=source,
        external_id=external_id,
        user_id=user_id,
        event_type=event_type,
        source_ip=source_ip,
        event_time=event_time,
    )


def _snapshot_features(events):
    rows, _ = _feature_rows(events)
    return {getattr(item, "external_id"): rows[id(item)]["features"] for item in events}


def test_identical_histories_have_equal_snapshot_and_event_features():
    history = [
        event("prior-1", datetime(2026, 1, 1, 8, tzinfo=timezone.utc), event_type="login_success"),
        event("prior-2", datetime(2026, 1, 1, 8, 30, tzinfo=timezone.utc), source_ip="2001:0db8:0:0::1"),
    ]
    target = event(
        "target", datetime(2026, 1, 1, 9, 15, 42, 125000, tzinfo=timezone.utc),
        event_type="login_success", source_ip="2001:db8::1",
    )

    snapshot = _snapshot_features([*history, target])["target"]
    event_path = features_for_event(target, history)

    assert event_path == pytest.approx(snapshot)
    assert event_path[3] == 1.0
    assert event_path[4] == 1.0
    assert event_path[6] == pytest.approx(math.log1p(1))


@pytest.mark.parametrize("source_ip", [None, "", "not-an-ip", "  203.0.113.999  "])
def test_missing_or_malformed_ip_is_unavailable_in_both_paths(source_ip):
    prior = event("prior", datetime(2026, 1, 1, 8, tzinfo=timezone.utc))
    target = event(
        "target", datetime(2026, 1, 1, 9, tzinfo=timezone.utc), source_ip=source_ip
    )

    snapshot = _snapshot_features([prior, target])["target"]
    event_path = features_for_event(target, [prior])

    assert event_path == snapshot
    assert event_path[3] is None
    assert event_path[6] is None


def test_unknown_event_type_is_valid_novelty_and_blank_type_is_unavailable():
    prior = event("prior", datetime(2026, 1, 1, 8, tzinfo=timezone.utc))
    unknown = event(
        "unknown", datetime(2026, 1, 1, 9, tzinfo=timezone.utc),
        event_type="  provider_custom_operation  ",
    )
    blank = event(
        "blank", datetime(2026, 1, 1, 10, tzinfo=timezone.utc), event_type="   "
    )
    snapshot = _snapshot_features([prior, unknown, blank])

    assert features_for_event(unknown, [prior])[2:5] == [0.0, 1.0, 0.0]
    assert snapshot["unknown"] == features_for_event(unknown, [prior])
    assert snapshot["blank"][2] is None
    assert snapshot["blank"][4] is None


def test_missing_user_keeps_only_entity_independent_features():
    target = event(
        "target", datetime(2026, 1, 1, 9, tzinfo=timezone.utc), user_id=None
    )
    snapshot = _snapshot_features([target])["target"]
    event_path = features_for_event(target, [])

    assert event_path == snapshot
    assert event_path[0] is not None
    assert event_path[1] is not None
    assert event_path[2] == 0.0
    assert event_path[3:] == [None, None, None, None]


def test_timezones_and_subsecond_precision_are_preserved_consistently():
    utc_event = event(
        "utc", datetime(2026, 4, 2, 8, 30, 15, 750000, tzinfo=timezone.utc)
    )
    offset_event = event(
        "offset",
        datetime.fromisoformat("2026-04-02T10:30:15.750000+02:00"),
    )
    snapshot = _snapshot_features([utc_event, offset_event])

    assert snapshot["utc"] == pytest.approx(snapshot["offset"])
    assert features_for_event(offset_event, []) == pytest.approx(snapshot["offset"])
    fractional_hour = 8 + 30 / 60 + 15 / 3600 + 0.75 / 3600
    assert snapshot["utc"][0] == pytest.approx(
        math.sin(2 * math.pi * fractional_hour / 24)
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        features_for_event(
            event("naive", datetime(2026, 4, 2, 8, 30)), []
        )


def test_equal_time_order_and_cross_user_or_future_history_never_leak():
    timestamp = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
    target = event("target", timestamp, event_type="unknown_type", source_ip="203.0.113.7")
    peer = event("peer", timestamp, event_type="unknown_type", source_ip="203.0.113.7")
    other_user = event(
        "other", datetime(2026, 1, 1, 8, tzinfo=timezone.utc),
        user_id="user-b", event_type="unknown_type", source_ip="203.0.113.7",
    )
    future = event(
        "future", datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
        event_type="unknown_type", source_ip="203.0.113.7",
    )

    no_history = features_for_event(target, [])
    assert features_for_event(target, [peer, other_user, future]) == no_history
    assert _snapshot_features([future, peer, other_user, target])["target"] == pytest.approx(no_history)
    reversed_snapshot = _snapshot_features([target, other_user, peer, future])
    assert reversed_snapshot["target"] == pytest.approx(no_history)
    assert no_history[3] == 0.0
    assert no_history[4] == 0.0
    assert no_history[5] == 0.0
    assert no_history[6] == 0.0


def test_history_is_scoped_to_same_user_and_duplicate_source_ids_are_deduplicated():
    timestamp = datetime(2026, 1, 1, 8, tzinfo=timezone.utc)
    duplicate_a = event("duplicate-a", timestamp, event_type="login_success")
    duplicate_b = event("duplicate-b", timestamp.replace(minute=15), event_type="login_success")
    duplicate_b.external_id = duplicate_a.external_id
    other_user = event(
        "other-user", timestamp.replace(minute=30), user_id="user-b",
        source_ip="203.0.113.9",
    )
    target = event(
        "target", timestamp.replace(hour=9), event_type="login_success"
    )
    features = features_for_event(target, [other_user, duplicate_b, duplicate_a])
    reversed_features = features_for_event(target, [duplicate_a, duplicate_b, other_user])

    assert reversed_features == features
    assert features[4] == 1.0
    assert features[5] == pytest.approx(math.log1p(1))
    assert features[6] == pytest.approx(math.log1p(1))
