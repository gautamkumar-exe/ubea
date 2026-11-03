"""Shared point-in-time feature semantics for event scoring and snapshots."""
from __future__ import annotations

import ipaddress
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Iterable


FEATURE_NAMES = (
    "hour_sin",
    "hour_cos",
    "is_login",
    "is_known_ip",
    "is_known_event_type",
    "user_event_frequency",
    "source_ip_frequency",
)


def normalize_event_time(value: object) -> datetime:
    """Require an aware timestamp and normalize it to UTC without truncation."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("event_time must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def canonicalize_source_ip(value: object) -> str | None:
    """Return a canonical IP literal, or None for absent/malformed values."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return ipaddress.ip_address(value.strip()).compressed
    except ValueError:
        return None


def normalize_user_id(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def normalize_event_type(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def feature_event_order_key(event: object) -> tuple[datetime, str, str, str, str]:
    """Stable ordering shared by snapshot deduplication and direct histories."""
    raw_time = getattr(event, "event_time", None)
    try:
        event_time = normalize_event_time(raw_time)
    except ValueError:
        event_time = datetime.max.replace(tzinfo=timezone.utc)
    return (
        event_time,
        str(getattr(event, "id", "")),
        normalize_event_type(getattr(event, "event_type", None)) or "",
        canonicalize_source_ip(getattr(event, "source_ip", None)) or "",
        normalize_user_id(getattr(event, "user_id", None)) or "",
    )


def _dedup_identity(event: object) -> tuple[str, str] | None:
    source = getattr(event, "source", None)
    external_id = getattr(event, "external_id", None)
    if not isinstance(source, str) or not source.strip():
        return None
    if not isinstance(external_id, str) or not external_id.strip():
        return None
    return source.strip(), external_id.strip()


def _prior_user_events(
    event: object, history: Iterable[object], event_time: datetime, user_id: str | None
) -> list[object]:
    if user_id is None:
        return []
    candidates: list[tuple[datetime, str, str, str, str, object]] = []
    for previous in history:
        if normalize_user_id(getattr(previous, "user_id", None)) != user_id:
            continue
        try:
            previous_time = normalize_event_time(getattr(previous, "event_time", None))
        except ValueError:
            # Snapshot extraction quarantines invalid timestamps; direct callers
            # must not let those records influence a valid target event.
            continue
        if previous_time >= event_time:
            continue
        candidates.append((
            previous_time,
            str(getattr(previous, "id", "")),
            normalize_event_type(getattr(previous, "event_type", None)) or "",
            canonicalize_source_ip(getattr(previous, "source_ip", None)) or "",
            normalize_user_id(getattr(previous, "user_id", None)) or "",
            previous,
        ))
    candidates.sort(key=lambda candidate: candidate[:5])

    result: list[object] = []
    seen: set[tuple[str, str]] = set()
    for _, _, _, _, _, previous in candidates:
        identity = _dedup_identity(previous)
        if identity is not None:
            if identity in seen:
                continue
            seen.add(identity)
        result.append(previous)
    return result


def features_for_event(event: object, history: Iterable[object]) -> list[float | None]:
    """Build the seven approved features from strictly earlier same-user events.

    Missing/malformed user-scoped values remain unavailable (`None`). Unknown
    but nonempty event types are valid and receive novelty/login indicators.
    Events at the same timestamp, regardless of input ordering, never influence
    one another. The returned order matches ``FEATURE_NAMES``.
    """
    event_time = normalize_event_time(getattr(event, "event_time", None))
    user_id = normalize_user_id(getattr(event, "user_id", None))
    event_type = normalize_event_type(getattr(event, "event_type", None))
    source_ip = canonicalize_source_ip(getattr(event, "source_ip", None))
    prior = _prior_user_events(event, history, event_time, user_id)

    hour = (
        event_time.hour
        + event_time.minute / 60.0
        + event_time.second / 3600.0
        + event_time.microsecond / 3_600_000_000.0
    )
    angle = 2 * math.pi * hour / 24.0
    prior_types = {
        prior_type
        for previous in prior
        if (prior_type := normalize_event_type(getattr(previous, "event_type", None))) is not None
    }
    prior_ips = [
        prior_ip
        for previous in prior
        if (prior_ip := canonicalize_source_ip(getattr(previous, "source_ip", None))) is not None
    ]
    ip_counts = Counter(prior_ips)
    window_start = event_time - timedelta(hours=24)
    recent_count = 0
    for previous in prior:
        try:
            previous_time = normalize_event_time(getattr(previous, "event_time", None))
        except ValueError:
            continue
        if window_start <= previous_time < event_time:
            recent_count += 1

    return [
        math.sin(angle),
        math.cos(angle),
        float("login" in event_type.casefold()) if event_type is not None else None,
        float(source_ip in ip_counts) if source_ip is not None and user_id is not None else None,
        float(event_type in prior_types) if event_type is not None and user_id is not None else None,
        math.log1p(recent_count) if user_id is not None else None,
        math.log1p(ip_counts[source_ip]) if source_ip is not None and user_id is not None else None,
    ]
