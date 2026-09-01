"""Observed post-action outcome feeding the learning update."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, utcnow

class OutcomeEvent(Base):
    __tablename__ = "outcome_event"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    outcome_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    observed_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    recovered_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
