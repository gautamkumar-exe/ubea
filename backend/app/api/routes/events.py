
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from fastapi import Query
from sqlalchemy import func, select

from app.database import get_db
from app.models.security_event import SecurityEvent
from app.schemas.security_event import (
    SecurityEventCreate,
    SecurityEventResponse,
    SecurityEventListItem,
    SecurityEventListResponse,
)

router = APIRouter(prefix="/events", tags=["Security Events"])



@router.get("", response_model=SecurityEventListResponse)
def list_events(
    user_id: str | None = None,
    event_type: str | None = None,
    source: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    filters = []

    if user_id:
        filters.append(SecurityEvent.user_id == user_id)

    if event_type:
        filters.append(SecurityEvent.event_type == event_type)

    if source:
        filters.append(SecurityEvent.source == source)

    total = db.scalar(
        select(func.count())
        .select_from(SecurityEvent)
        .where(*filters)
    )

    statement = (
        select(SecurityEvent)
        .where(*filters)
        .order_by(
            SecurityEvent.event_time.desc(),
            SecurityEvent.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    events = db.scalars(statement).all()

    items = [
        SecurityEventListItem(
            id=str(event.id),
            source=event.source,
            external_id=event.external_id,
            event_type=event.event_type,
            user_id=event.user_id,
            entity_id=event.entity_id,
            source_ip=event.source_ip,
            event_time=event.event_time,
            raw_event=event.raw_event or {},
        )
        for event in events
    ]

    return SecurityEventListResponse(
        items=items,
        total=total or 0,
        limit=limit,
        offset=offset,
    )

@router.post(
    "",
    response_model=SecurityEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_event(
    event: SecurityEventCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    event_data = event.model_dump()

    statement = (
        insert(SecurityEvent)
        .values(**event_data)
        .on_conflict_do_nothing(
            index_elements=[
                SecurityEvent.source,
                SecurityEvent.external_id,
            ]
        )
        .returning(SecurityEvent.id)
    )

    try:
        inserted_id = db.execute(statement).scalar_one_or_none()

        if inserted_id is not None:
            db.commit()

            response.status_code = status.HTTP_201_CREATED

            return SecurityEventResponse(
                id=str(inserted_id),
                source=event.source,
                external_id=event.external_id,
                event_type=event.event_type,
                user_id=event.user_id,
                entity_id=event.entity_id,
                source_ip=event.source_ip,
                event_time=event.event_time,
                status="created",
                duplicate=False,
            )

        existing_event = db.execute(
            select(SecurityEvent).where(
                SecurityEvent.source == event.source,
                SecurityEvent.external_id == event.external_id,
            )
        ).scalar_one()

        db.commit()
        response.status_code = status.HTTP_200_OK

        return SecurityEventResponse(
            id=str(existing_event.id),
            source=existing_event.source,
            external_id=existing_event.external_id,
            event_type=existing_event.event_type,
            user_id=existing_event.user_id,
            entity_id=existing_event.entity_id,
            source_ip=existing_event.source_ip,
            event_time=existing_event.event_time,
            status="duplicate",
            duplicate=True,
        )

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to store the security event",
        ) from exc
