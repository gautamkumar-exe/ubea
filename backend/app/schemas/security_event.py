
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SecurityEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=100)
    external_id: str = Field(min_length=1, max_length=255)
    event_type: str = Field(min_length=1, max_length=100)

    user_id: str | None = Field(default=None, max_length=255)
    entity_id: str | None = Field(default=None, max_length=255)
    source_ip: str | None = Field(default=None, max_length=45)

    event_time: datetime
    raw_event: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "source",
        "external_id",
        "event_type",
        "user_id",
        "entity_id",
        "source_ip",
    )
    @classmethod
    def strip_string_fields(cls, value):
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError("This field cannot be blank")

        return value

    @field_validator("event_time")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "event_time must include a timezone, such as Z or +05:30"
            )

        return value


class SecurityEventResponse(BaseModel):
    id: str
    source: str
    external_id: str
    event_type: str
    user_id: str | None
    entity_id: str | None
    source_ip: str | None
    event_time: datetime
    status: str
    duplicate: bool

class SecurityEventListItem(BaseModel):
    id: str
    source: str
    external_id: str
    event_type: str
    user_id: str | None
    entity_id: str | None
    source_ip: str | None
    event_time: datetime
    raw_event: dict[str, Any]


class SecurityEventListResponse(BaseModel):
    items: list[SecurityEventListItem]
    total: int
    limit: int
    offset: int
