from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnalystFeedback(Base):
    __tablename__ = "analyst_feedback"
    __table_args__ = (
        CheckConstraint(
            "verdict IN ('true_positive', 'false_positive', 'benign', 'inconclusive')",
            name="ck_feedback_verdict",
        ),
    )

    id: Mapped[Any] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    alert_id: Mapped[Any] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analyst_id: Mapped[str] = mapped_column(String(255), nullable=False)
    verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )