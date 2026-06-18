"""Database abstraction layer."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

from jag.persistence.models import ALL_MODELS


class Database(Protocol):
    """Database connection protocol."""

    @property
    def engine(self) -> Engine: ...

    def create_tables(self) -> None: ...

    def close(self) -> None: ...


class SQLiteDatabase:
    """SQLite database implementation."""

    def __init__(self, path: str = "jag_world.db") -> None:
        self._path = path
        self._engine = create_engine(f"sqlite:///{path}", echo=False)

    @property
    def engine(self) -> Engine:
        return self._engine

    def create_tables(self) -> None:
        """Create all tables."""
        SQLModel.metadata.create_all(self._engine)

    def close(self) -> None:
        """Close the database connection."""
        self._engine.dispose()


class InMemoryDatabase:
    """In-memory SQLite database for testing."""

    def __init__(self) -> None:
        self._engine = create_engine("sqlite:///:memory:", echo=False)

    @property
    def engine(self) -> Engine:
        return self._engine

    def create_tables(self) -> None:
        SQLModel.metadata.create_all(self._engine)

    def close(self) -> None:
        self._engine.dispose()
