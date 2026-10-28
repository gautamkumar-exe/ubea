
from collections import Counter
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.security_event import SecurityEvent
from app.models.user_profile import UserProfile


def build_user_baseline(db: Session, user_id: str) -> dict:
    events = db.scalars(
        select(SecurityEvent)
        .where(SecurityEvent.user_id == user_id)
        .order_by(SecurityEvent.event_time.asc())
    ).all()

    if not events:
        raise ValueError(f"No security events found for user: {user_id}")

    event_types = Counter()
    login_hours = Counter()
    source_ips = Counter()
    active_days = set()

    for event in events:
        event_types[event.event_type] += 1

        event_time = event.event_time
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        event_time_utc = event_time.astimezone(timezone.utc)
        active_days.add(event_time_utc.date().isoformat())

        if "login" in event.event_type.lower():
            login_hours[str(event_time_utc.hour)] += 1

        if event.source_ip:
            source_ips[event.source_ip] += 1

    first_seen = events[0].event_time
    last_seen = events[-1].event_time

    baseline = {
        "event_count": len(events),
        "event_type_counts": dict(event_types),
        "login_hour_counts_utc": dict(login_hours),
        "source_ip_counts": dict(source_ips),
        "active_days": len(active_days),
        "first_seen": first_seen.isoformat(),
        "last_seen": last_seen.isoformat(),
    }

    profile = db.scalar(
        select(UserProfile).where(
            UserProfile.entity_type == "user",
            UserProfile.entity_id == user_id,
        )
    )

    if profile is None:
        profile = UserProfile(
            entity_type="user",
            entity_id=user_id,
            baseline=baseline,
            last_seen=last_seen,
        )
        db.add(profile)
    else:
        profile.baseline = baseline
        profile.last_seen = last_seen

    db.commit()

    return baseline
