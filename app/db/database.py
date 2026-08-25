"""
SQLite database setup (PRD Section 10 — Tech Stack).

Responsibilities:
- Create/connect to the SQLite database (see schema.sql).
- Provide session/connection helpers used by app/models/*.py and by
  the graph nodes that read/write entities.

No implementation yet — skeleton only.
"""
"""SQLite engine, session, initialization, and transaction helpers."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from app.config import DATABASE_URL
from app.models import Base


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}

engine: Engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True, **_engine_kwargs(DATABASE_URL))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_db() -> None:
    """Create all ORM tables; safe to call during application startup and tests."""
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """Drop ORM tables, intended for isolated test databases only."""
    Base.metadata.drop_all(bind=engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a session and atomically commit or roll back its work."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def execute_schema_file(connection, schema_path: str | Path | None = None) -> None:
    """Execute the checked-in SQL schema for deployments that prefer SQL DDL."""
    path = Path(schema_path or Path(__file__).with_name("schema.sql"))
    statements = [part.strip() for part in path.read_text(encoding="utf-8").split(";") if part.strip()]
    for statement in statements:
        connection.execute(text(statement))
