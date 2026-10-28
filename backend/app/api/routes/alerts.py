
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alert import Alert
from app.schemas.alert import (
    AlertListResponse,
    AlertResponse,
    AlertSeverity,
    AlertStatus,
    AlertStatusUpdate,
)

router = APIRouter(prefix="/alerts", tags=["Alert Management"])


@router.get("", response_model=AlertListResponse)
def list_alerts(
    status: AlertStatus | None = None,
    severity: AlertSeverity | None = None,
    user_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    filters = []

    if status is not None:
        filters.append(Alert.status == status)

    if severity is not None:
        filters.append(Alert.severity == severity)

    if user_id is not None:
        filters.append(Alert.user_id == user_id)

    total = db.scalar(
        select(func.count())
        .select_from(Alert)
        .where(*filters)
    ) or 0

    statement = (
        select(Alert)
        .where(*filters)
        .order_by(Alert.created_at.desc(), Alert.id.desc())
        .limit(limit)
        .offset(offset)
    )

    alerts = db.scalars(statement).all()

    return AlertListResponse(
        items=[
            AlertResponse(
                id=str(alert.id),
                event_id=(
                    str(alert.event_id)
                    if alert.event_id is not None
                    else None
                ),
                user_id=alert.user_id,
                title=alert.title,
                severity=alert.severity,
                risk_score=alert.risk_score,
                status=alert.status,
                explanation=alert.explanation,
                evidence=alert.evidence or {},
                created_at=alert.created_at,
            )
            for alert in alerts
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
):
    alert = db.get(Alert, alert_id)

    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    return AlertResponse(
        id=str(alert.id),
        event_id=str(alert.event_id) if alert.event_id else None,
        user_id=alert.user_id,
        title=alert.title,
        severity=alert.severity,
        risk_score=alert.risk_score,
        status=alert.status,
        explanation=alert.explanation,
        evidence=alert.evidence or {},
        created_at=alert.created_at,
    )


@router.patch("/{alert_id}/status", response_model=AlertResponse)
def update_alert_status(
    alert_id: UUID,
    payload: AlertStatusUpdate,
    db: Session = Depends(get_db),
):
    alert = db.get(Alert, alert_id)

    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    try:
        alert.status = payload.status
        db.commit()
        db.refresh(alert)

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to update alert status",
        ) from exc

    return AlertResponse(
        id=str(alert.id),
        event_id=str(alert.event_id) if alert.event_id else None,
        user_id=alert.user_id,
        title=alert.title,
        severity=alert.severity,
        risk_score=alert.risk_score,
        status=alert.status,
        explanation=alert.explanation,
        evidence=alert.evidence or {},
        created_at=alert.created_at,
    )
