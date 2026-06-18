"""SQLite repository implementation."""

from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, select

T = TypeVar("T", bound=SQLModel)


class SQLiteRepository:
    """SQLite-backed repository implementing the Repository protocol."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save(self, entity: SQLModel) -> None:
        """Save an entity (insert or update)."""
        with Session(self._engine) as session:
            session.merge(entity)
            session.commit()

    def find(self, model: type[T], entity_id: str) -> T | None:
        """Find an entity by ID."""
        with Session(self._engine) as session:
            return session.get(model, entity_id)

    def find_all(self, model: type[T], **filters: Any) -> list[T]:
        """Find all entities matching filters."""
        with Session(self._engine) as session:
            stmt = select(model)
            for key, value in filters.items():
                if hasattr(model, key):
                    col = getattr(model, key)
                    if isinstance(value, list):
                        stmt = stmt.where(col.in_(value))
                    else:
                        stmt = stmt.where(col == value)
            return list(session.exec(stmt).all())

    def delete(self, entity: SQLModel) -> None:
        """Delete an entity."""
        with Session(self._engine) as session:
            merged = session.merge(entity)
            session.delete(merged)
            session.commit()

    def update(self, entity: SQLModel) -> None:
        """Update an existing entity."""
        self.save(entity)

    def save_batch(self, entities: list[SQLModel]) -> None:
        """Save multiple entities in a single transaction."""
        with Session(self._engine) as session:
            for entity in entities:
                session.merge(entity)
            session.commit()

    def query(self, model: type[T], conditions: dict[str, Any]) -> list[T]:
        """Query entities with conditions."""
        return self.find_all(model, **conditions)

    def count(self, model: type[T], **filters: Any) -> int:
        """Count entities matching filters."""
        return len(self.find_all(model, **filters))
