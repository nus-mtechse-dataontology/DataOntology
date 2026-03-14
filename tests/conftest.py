import pytest
from sqlmodel import SQLModel, create_engine

from entities import *

@pytest.fixture
def in_memory_engine():
    """Return a fresh SQLite in-memory engine with tables created."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine
