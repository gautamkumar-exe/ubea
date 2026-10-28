
from datetime import timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.security_event import SecurityEvent
from app.models.user_profile import UserProfile


def analyze_event(db: Session, event_id: UUID) -> dict:
    event = db.get(SecurityEvent, event_id)

    if event is None:
        raise LookupError("Security event not found")

    if not event.user_id:
        raise ValueError("Event has no user_id to analyze")

    profile = db.scalar(
        select(UserProfile).where(
            UserProfile.entity_type == "user",
            UserProfile.entity_id == event.user_id,
        )
    )

    if profile is None or not profile.baseline:
        raise LookupError(
            "User baseline not found. Build the baseline first."
        )

    baseline = profile.baseline
    score = 0
    reasons = []

    # Rule 1: unfamiliar source IP
    known_ips = baseline.get("source_ip_counts", {})

    if event.source_ip and event.source_ip not in known_ips:
        score += 40
        reasons.append({
            "factor": "unfamiliar_source_ip",
            "points": 40,
            "details": (
                f"Source IP {event.source_ip} was not observed "
                "in the user's baseline."
            ),
        })

    # Rule 2: unfamiliar event type
    known_types = baseline.get("event_type_counts", {})

    if event.event_type not in known_types:
        score += 25
        reasons.append({
            "factor": "unfamiliar_event_type",
            "points": 25,
            "details": (
                f"Event type '{event.event_type}' was not observed "
                "in the user's baseline."
            ),
        })

    # Rule 3: unfamiliar login hour
    if "login" in event.event_type.lower():
        login_hours = baseline.get("login_hour_counts_utc", {})

        event_time = event.event_time
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        hour = str(event_time.astimezone(timezone.utc).hour)

        if login_hours and hour not in login_hours:
            score += 30
            reasons.append({
                "factor": "unusual_login_hour",
                "points": 30,
                "details": (
                    f"Login at UTC hour {hour} was not observed "
                    "in the user's baseline."
                ),
            })

    score = min(score, 100)

    if score >= 80:
        severity = "critical"
    elif score >= 60:
        severity = "high"
    elif score >= 30:
        severity = "medium"
    else:
        severity = "low"

    return {
        "event_id": str(event.id),
        "user_id": event.user_id,
        "risk_score": score,
        "severity": severity,
        "is_anomalous": score >= 30,
        "reasons": reasons,
        "baseline_event_count": baseline.get("event_count", 0),
        "note": (
            "Preliminary rule-based score; not proof of malicious activity."
        ),
    }
