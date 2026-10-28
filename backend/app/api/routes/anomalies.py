
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alert import Alert
from app.schemas.anomaly import AnomalyAnalysisResponse
from app.services.anomaly import analyze_event

router = APIRouter(prefix="/anomalies", tags=["Anomaly Detection"])

ALERT_THRESHOLD = 30


@router.post(
    "/analyze/{event_id}",
    response_model=AnomalyAnalysisResponse,
)
def analyze_security_event(
    event_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        result = analyze_event(db, event_id)

        if result["risk_score"] >= ALERT_THRESHOLD:
            existing_alert = db.scalar(
                select(Alert).where(Alert.event_id == event_id)
            )

            reasons = result["reasons"]

            explanation = (
                "; ".join(reason["details"] for reason in reasons)
                or "Unusual activity detected."
            )

            evidence = {
                "reasons": reasons,
                "baseline_event_count": result["baseline_event_count"],
                "detection_method": "rule_based",
            }

            if existing_alert is None:
                alert = Alert(
                    event_id=event_id,
                    user_id=result["user_id"],
                    title=f"Unusual activity detected for {result['user_id']}",
                    severity=result["severity"],
                    risk_score=result["risk_score"],
                    status="open",
                    explanation=explanation,
                    evidence=evidence,
                )
                db.add(alert)
            else:
                alert = existing_alert
                alert.user_id = result["user_id"]
                alert.title = (
                    f"Unusual activity detected for {result['user_id']}"
                )
                alert.severity = result["severity"]
                alert.risk_score = result["risk_score"]
                alert.explanation = explanation
                alert.evidence = evidence

            db.commit()
            db.refresh(alert)
            result["alert_id"] = str(alert.id)

        else:
            result["alert_id"] = None

        return result

    except LookupError as exc:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to analyze event or persist alert",
        ) from exc
