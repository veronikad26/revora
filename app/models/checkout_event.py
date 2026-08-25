"""
CheckoutEvent entity (PRD Section 11).

Fields: id, cart_id, customer_id, cart_value, funnel_stage_reached,
created_at, last_activity_at, prior_abandonment_count.

Represents an abandoned-checkout entry point — no gateway code exists,
so this is detected via behavioral signal (app/rules/abandonment_scorer.py).

No implementation yet — skeleton only.
"""
"""Checkout abandonment event."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, utcnow

class CheckoutEvent(Base):
    __tablename__ = "checkout_event"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cart_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    cart_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    funnel_stage_reached: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prior_abandonment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
