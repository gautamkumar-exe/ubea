
from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.security_event import SecurityEvent
from app.services.ml_feature_engine import FEATURE_NAMES, features_for_event as _features_for_event


def features_for_event(
    event: SecurityEvent,
    history: Sequence[SecurityEvent],
) -> list[float | None]:
    """Public event feature helper backed by the shared snapshot engine."""
    features = _features_for_event(event, history)
    if len(features) != len(FEATURE_NAMES):
        raise RuntimeError("Feature count does not match the ML model")
    return features


def get_event_features(db: Session, event_id) -> list[float | None]:
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
        features = features_for_event(historical_event, history)
        if all(value is not None for value in features):
            training_rows.append([float(value) for value in features])
        history.append(historical_event)

    return training_rows
