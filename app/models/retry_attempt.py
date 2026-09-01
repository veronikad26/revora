"""Idempotent retry slot for a payment failure."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, utcnow

class RetryAttempt(Base):
    __tablename__ = "retry_attempt"
    __table_args__ = (UniqueConstraint("failure_event_id", "attempt_number", name="uq_retry_failure_attempt"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    failure_event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    already_attempted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scheduled_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
