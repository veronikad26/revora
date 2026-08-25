"""
ConsentFlag entity (PRD Section 11, simplified Consent Gate).

Fields: customer_id, channel, consent (bool).

Checked by the Consent Gate node before any outreach. If false or
missing, the case is routed to DO NOTHING with reason
"no consent on file".

No implementation yet — skeleton only.
"""
"""Customer/channel outreach consent."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, utcnow

class ConsentFlag(Base):
    __tablename__ = "consent_flag"
    __table_args__ = (UniqueConstraint("customer_id", "channel", name="uq_consent_customer_channel"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
