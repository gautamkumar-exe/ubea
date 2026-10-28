
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AlertStatus = Literal["open", "investigating", "resolved", "dismissed"]
AlertSeverity = Literal["low", "medium", "high", "critical"]


class AlertStatusUpdate(BaseModel):
    status: AlertStatus


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str | None
    user_id: str | None
    title: str
    severity: str
    risk_score: int
    status: str
    explanation: str
    evidence: dict[str, Any]
    created_at: datetime


class AlertListResponse(BaseModel):
    items: list[AlertResponse]
    total: int
    limit: int
    offset: int
