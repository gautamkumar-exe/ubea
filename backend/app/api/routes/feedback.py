from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alert import Alert
from app.models.analyst_feedback import AnalystFeedback
from app.schemas.feedback import (
    FeedbackCreate,
    FeedbackListResponse,
    FeedbackResponse,
)

router = APIRouter(prefix="/alerts", tags=["Analyst Feedback"])


def serialize_feedback(feedback: AnalystFeedback) -> FeedbackResponse:
    return FeedbackResponse(
        id=str(feedback.id),
        alert_id=str(feedback.alert_id),
        analyst_id=feedback.analyst_id,
        verdict=feedback.verdict,
        comment=feedback.comment,
        created_at=feedback.created_at,
    )


@router.post(
    "/{alert_id}/feedback",
    response_model=FeedbackResponse,
    status_code=201,
)
def create_feedback(
    alert_id: UUID,
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
):
    if db.get(Alert, alert_id) is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    feedback = AnalystFeedback(
        alert_id=alert_id,
        analyst_id=payload.analyst_id.strip(),
        verdict=payload.verdict,
        comment=payload.comment.strip() if payload.comment else None,
    )

    if not feedback.analyst_id:
        raise HTTPException(
            status_code=422,
            detail="analyst_id must not be blank",
        )

    try:
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return serialize_feedback(feedback)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to save analyst feedback",
        ) from exc


@router.get(
    "/{alert_id}/feedback",
    response_model=FeedbackListResponse,
)
def list_feedback(
    alert_id: UUID,
    db: Session = Depends(get_db),
):
    if db.get(Alert, alert_id) is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    try:
        total = db.scalar(
            select(func.count())
            .select_from(AnalystFeedback)
            .where(AnalystFeedback.alert_id == alert_id)
        ) or 0

        statement = (
            select(AnalystFeedback)
            .where(AnalystFeedback.alert_id == alert_id)
            .order_by(
                AnalystFeedback.created_at.desc(),
                AnalystFeedback.id.desc(),
            )
        )

        feedback_items = db.scalars(statement).all()

        return FeedbackListResponse(
            items=[serialize_feedback(item) for item in feedback_items],
            total=total,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve analyst feedback",
        ) from exc
