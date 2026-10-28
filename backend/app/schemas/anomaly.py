
from typing import Any

from pydantic import BaseModel


class AnomalyAnalysisResponse(BaseModel):
    event_id: str
    user_id: str
    risk_score: int
    severity: str
    is_anomalous: bool
    reasons: list[dict[str, Any]]
    baseline_event_count: int
    note: str
    alert_id: str | None = None
