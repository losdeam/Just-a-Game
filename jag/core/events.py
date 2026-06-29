"""Event system for publish/subscribe game events."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine


class EventType(Enum):
    COMBAT = "combat"
    INTERACTION = "interaction"
    ENVIRONMENT = "environment"
    QUEST = "quest"
    SOCIAL = "social"
    ECONOMY = "economy"
    NPC_ACTION = "npc_action"
    WORLD = "world"
    SYSTEM = "system"
    DANGER = "danger"


@dataclass
class GameEvent:
    """A game event."""

    event_type: EventType
    source_id: str = ""
    target_id: str = ""
    location_id: str = ""
    description: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    turn: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = f"evt_{self.turn}_{id(self)}"


EventHandler = Callable[[GameEvent], Coroutine[Any, Any, None] | None]


class EventBus:
    """Event publish/subscribe bus."""

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._global_handlers: list[EventHandler] = []

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe to a specific event type."""
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe to all events."""
        self._global_handlers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe from a specific event type."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    async def publish(self, event: GameEvent) -> None:
        """Publish an event to all subscribers."""
        handlers = list(self._handlers.get(event.event_type, []))
        handlers.extend(self._global_handlers)

        for handler in handlers:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result


class EventQueue:
    """FIFO queue for pending events."""

    def __init__(self) -> None:
        self._queue: deque[GameEvent] = deque()
        self._history: list[GameEvent] = []
        self._max_history: int = 100

    def enqueue(self, event: GameEvent) -> None:
        """Add an event to the queue."""
        self._queue.append(event)

    def dequeue(self) -> GameEvent | None:
        """Get the next event from the queue."""
        if self._queue:
            event = self._queue.popleft()
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            return event
        return None

    def peek(self) -> GameEvent | None:
        """Peek at the next event without removing it."""
        return self._queue[0] if self._queue else None

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    def get_history(self, limit: int = 20) -> list[GameEvent]:
        """Get recent event history."""
        return self._history[-limit:]

    def clear(self) -> None:
        """Clear the queue."""
        self._queue.clear()
