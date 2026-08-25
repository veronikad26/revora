"""Shared SQLAlchemy model infrastructure for Revora's Phase 1 data layer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all persisted domain entities."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """UTC timestamps shared by entities whose lifecycle is time-based."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


def utcnow() -> datetime:
    """Return an aware UTC datetime for explicit event timestamps."""

    return datetime.now(timezone.utc)


def model_dict(instance: Any) -> dict[str, Any]:
    """Return a simple column/value mapping useful to nodes and API serializers."""

    return {column.name: getattr(instance, column.name) for column in instance.__table__.columns}
