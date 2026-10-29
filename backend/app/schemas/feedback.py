from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


FeedbackVerdict = Literal[
    "true_positive",
    "false_positive",
    "benign",
    "inconclusive",
]


class FeedbackCreate(BaseModel):
    analyst_id: str = Field(min_length=1, max_length=255)
    verdict: FeedbackVerdict
    comment: str | None = Field(default=None, max_length=5000)


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str
    analyst_id: str
    verdict: FeedbackVerdict
    comment: str | None
    created_at: datetime


class FeedbackListResponse(BaseModel):
    items: list[FeedbackResponse]
    total: int
