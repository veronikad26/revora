"""
PTPRecord entity (PRD Section 7 / 11).

Fields: id, customer_id, invoice/payment_ref, amount, promised_date,
state, conversation_id, negotiation_limit_max_date, dispute_flag.

Tracks a case through the full PTP state machine:
DETECTED -> CONTACTED -> NEGOTIATING -> PROMISED -> KEPT/BROKEN,
with DISPUTED -> ESCALATED and BROKEN -> RENEGOTIATE (max 1x) -> ESCALATED.

No implementation yet — skeleton only.
"""
"""Promise-to-Pay record and bounded negotiation state."""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, utcnow

class PTPRecord(Base):
    __tablename__ = "ptp_record"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    invoice_payment_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    promised_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    state: Mapped[str] = mapped_column(String(32), default="DETECTED", nullable=False, index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    negotiation_limit_max_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    dispute_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    renegotiation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
