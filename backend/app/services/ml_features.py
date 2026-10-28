
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.security_event import SecurityEvent
from app.services.ml_anomaly import FEATURE_NAMES


def _as_utc(value: datetime) -> datetime:
    """Normalize a timestamp to UTC, including legacy naive timestamps."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def features_for_event(
    event: SecurityEvent,
    history: Sequence[SecurityEvent],
) -> list[float]:
    """
    Extract features using only events that occurred before this event.

    history must not contain the event being scored or events at/after
    its timestamp. This prevents direct target-event leakage.
    """
    event_time = _as_utc(event.event_time)

    prior_events = [
        previous
        for previous in history
        if _as_utc(previous.event_time) < event_time
    ]

    hour = event_time.hour + event_time.minute / 60.0
    hour_angle = 2 * math.pi * hour / 24.0

    known_ips = {
        previous.source_ip
        for previous in prior_events
        if previous.source_ip
    }
    known_event_types = {
        previous.event_type
        for previous in prior_events
    }

    window_start = event_time - timedelta(hours=24)
    recent_event_count = sum(
        1
        for previous in prior_events
        if _as_utc(previous.event_time) >= window_start
    )

    features = [
        math.sin(hour_angle),
        math.cos(hour_angle),
        float("login" in event.event_type.lower()),
        float(bool(event.source_ip and event.source_ip in known_ips)),
        float(event.event_type in known_event_types),
        math.log1p(recent_event_count),
    ]

    if len(features) != len(FEATURE_NAMES):
        raise RuntimeError("Feature count does not match the ML model")

    return features


def get_event_features(db: Session, event_id) -> list[float]:
    """Load one event and its strictly earlier user events."""
    event = db.get(SecurityEvent, event_id)

    if event is None:
        raise LookupError("Security event not found")

    if not event.user_id:
        raise ValueError("Event has no user_id")

    history = db.scalars(
        select(SecurityEvent)
        .where(
            SecurityEvent.user_id == event.user_id,
            SecurityEvent.event_time < event.event_time,
        )
        .order_by(SecurityEvent.event_time.asc())
    ).all()

    return features_for_event(event, history)


def get_historical_training_features(
    db: Session,
    user_id: str,
    before_event: SecurityEvent,
    limit: int = 500,
) -> list[list[float]]:
    """
    Build training rows from earlier events only.

    Each training event is represented using only events preceding it.
    The target event and events at/after its timestamp are excluded.
    """
    if limit < 1:
        raise ValueError("limit must be at least 1")

    historical_events = db.scalars(
        select(SecurityEvent)
        .where(
            SecurityEvent.user_id == user_id,
            SecurityEvent.event_time < before_event.event_time,
        )
        .order_by(SecurityEvent.event_time.desc())
        .limit(limit)
    ).all()

    historical_events = list(reversed(historical_events))
    training_rows: list[list[float]] = []
    history: list[SecurityEvent] = []

    for historical_event in historical_events:
        training_rows.append(features_for_event(historical_event, history))
        history.append(historical_event)

    return training_rows
