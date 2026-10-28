
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user_profile import UserProfile
from app.schemas.baseline import BaselineResponse
from app.services.baseline import build_user_baseline

router = APIRouter(prefix="/baselines", tags=["Behavioral Baselines"])


@router.post("/{user_id}/rebuild", response_model=BaselineResponse)
def rebuild_baseline(
    user_id: str,
    db: Session = Depends(get_db),
):
    try:
        baseline = build_user_baseline(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return BaselineResponse(
        user_id=user_id,
        baseline=baseline,
        status="created_or_updated",
    )


@router.get("/{user_id}", response_model=BaselineResponse)
def get_baseline(
    user_id: str,
    db: Session = Depends(get_db),
):
    profile = db.scalar(
        select(UserProfile).where(
            UserProfile.entity_type == "user",
            UserProfile.entity_id == user_id,
        )
    )

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Baseline not found. Rebuild it first.",
        )

    return BaselineResponse(
        user_id=user_id,
        baseline=profile.baseline,
        status="available",
    )
