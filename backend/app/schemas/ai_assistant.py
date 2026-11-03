from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


AssistantMode = Literal["general", "explain_alert", "incident_summary"]
MessageRole = Literal["user", "assistant"]


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: MessageRole
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def require_nonblank_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message content cannot be blank")
        return value


class AssistantChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    mode: AssistantMode = "general"
    alert_id: UUID | None = None
    event_id: UUID | None = None
    history: list[ConversationMessage] = Field(default_factory=list, max_length=12)

    @field_validator("message")
    @classmethod
    def require_nonblank_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value


class ContextReference(BaseModel):
    type: Literal["alert", "event", "related_event"]
    id: str
    status: Literal["available", "not_found"]


class AssistantStatusResponse(BaseModel):
    configured: bool
    api_key_available: bool
    model: str | None
    availability_status: Literal["available", "not_configured"]


class AssistantChatResponse(BaseModel):
    response: str
    context_references: list[ContextReference]
    context_types_used: list[str]
    security_context_available: bool
    model: str
