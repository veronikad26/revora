"""Isolated in-memory SQLite fixtures for Phase 1 tests."""
import os

# Tests must not require real external-service credentials during collection.
os.environ["APP_ENV"] = "development"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()