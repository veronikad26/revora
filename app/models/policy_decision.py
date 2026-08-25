"""
PolicyDecision entity (PRD Section 11).

Fields: id, case_id, action_proposed, proposing_node, authorized (bool),
reason, timestamp.

Written by the Policy Engine for every action it authorizes or rejects
— the record that proves execution authority was independently checked.

No implementation yet — skeleton only.
"""
"""Independent authorization decision made before execution."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, utcnow

class PolicyDecision(Base):
    __tablename__ = "policy_decision"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action_proposed: Mapped[str] = mapped_column(String(64), nullable=False)
    proposing_node: Mapped[str] = mapped_column(String(64), nullable=False)
    authorized: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
