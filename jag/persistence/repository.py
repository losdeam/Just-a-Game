"""Repository pattern for data access."""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from sqlmodel import SQLModel

T = TypeVar("T", bound=SQLModel)


class Repository(Protocol):
    """Repository protocol for data access."""

    def save(self, entity: SQLModel) -> None: ...

    def find(self, model: type[T], entity_id: str) -> T | None: ...

    def find_all(self, model: type[T], **filters: Any) -> list[T]: ...

    def delete(self, entity: SQLModel) -> None: ...

    def update(self, entity: SQLModel) -> None: ...
