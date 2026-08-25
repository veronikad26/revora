"""
FailureEvent entity (PRD Section 11).

Fields: id, payment_id, gateway_code, amount, method, timestamp,
customer_id.

Represents an incoming payment-failure event from Razorpay
(webhook/test-mode API) — one of the three entry points into the graph.

No implementation yet — skeleton only.
"""
"""Payment failure event persisted from a gateway webhook or test batch."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, utcnow


class FailureEvent(TimestampMixin, Base):
    __tablename__ = "failure_event"
    __table_args__ = (UniqueConstraint("payment_id", name="uq_failure_event_payment_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    gateway_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gateway_reason: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
