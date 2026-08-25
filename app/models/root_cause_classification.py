"""
RootCauseClassification entity (PRD Section 11).

Fields: event_id, event_type, category, confidence, reason.

Written by the Diagnosis node for every event, regardless of entry
point. confidence drives the low-confidence -> human-review guardrail.

No implementation yet — skeleton only.
"""
"""Deterministic diagnosis result for any recovery entry point."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, utcnow

class RootCauseClassification(Base):
    __tablename__ = "root_cause_classification"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
