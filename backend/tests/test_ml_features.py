
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.ml_features import features_for_event


def make_event(event_time, event_type="login_success", source_ip="192.0.2.10"):
    return SimpleNamespace(
        event_time=datetime.fromisoformat(event_time).replace(
            tzinfo=timezone.utc
        ),
        event_type=event_type,
        source_ip=source_ip,
    )


def test_first_event_has_no_prior_familiarity():
    event = make_event("2026-10-28T09:00:00")
    features = features_for_event(event, [])

    assert len(features) == 7
    assert features[2] == 1.0
    assert features[3] == 0.0
    assert features[4] == 0.0
    assert features[5] == 0.0
    assert features[6] == 0.0


def test_known_ip_and_event_type_are_detected_from_history():
    earlier = make_event("2026-10-28T08:00:00")
    event = make_event("2026-10-28T09:00:00")

    features = features_for_event(event, [earlier])

    assert features[3] == 1.0
    assert features[4] == 1.0
    assert features[5] > 0.0
    assert features[6] > 0.0


def test_repeated_ip_has_higher_frequency():
    event = make_event("2026-10-28T12:00:00")
    one_prior = make_event("2026-10-28T10:00:00")
    two_prior = make_event("2026-10-28T10:00:00")
    two_prior_later = make_event("2026-10-28T11:00:00")

    once = features_for_event(event, [one_prior])
    twice = features_for_event(event, [two_prior, two_prior_later])

    assert twice[6] > once[6]


def test_future_events_do_not_influence_features():
    event = make_event("2026-10-28T09:00:00")
    future = make_event(
        "2026-10-28T10:00:00",
        event_type="admin_action",
        source_ip="203.0.113.77",
    )

    assert features_for_event(event, [future]) == features_for_event(event, [])
