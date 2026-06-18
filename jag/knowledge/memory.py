"""Memory system: short-term (sliding window) + long-term (persistent)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MemoryEntry:
    """A single memory entry."""

    id: str
    owner_id: str
    content: str
    importance: int = 5  # 1-10
    memory_type: str = "general"  # general, reputation, relationship, historical
    turn: int = 0
    source_event_ids: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    last_accessed: str = field(default_factory=lambda: datetime.now().isoformat())


class ShortTermMemory:
    """Sliding window short-term memory."""

    def __init__(self, owner_id: str, max_size: int = 20) -> None:
        self.owner_id = owner_id
        self.max_size = max_size
        self._entries: list[MemoryEntry] = []

    def add(self, entry: MemoryEntry) -> None:
        """Add an entry, removing oldest if at capacity."""
        self._entries.append(entry)
        if len(self._entries) > self.max_size:
            self._entries = self._entries[-self.max_size:]

    def get_all(self) -> list[MemoryEntry]:
        """Get all short-term memories."""
        return list(self._entries)

    def get_recent(self, n: int = 5) -> list[MemoryEntry]:
        """Get the most recent N entries."""
        return self._entries[-n:]

    def get_by_importance(self, min_importance: int = 7) -> list[MemoryEntry]:
        """Get entries above importance threshold."""
        return [e for e in self._entries if e.importance >= min_importance]

    def clear(self) -> list[MemoryEntry]:
        """Clear and return all entries (for compression)."""
        entries = list(self._entries)
        self._entries.clear()
        return entries

    @property
    def count(self) -> int:
        return len(self._entries)

    @property
    def is_full(self) -> bool:
        return len(self._entries) >= self.max_size


class LongTermMemory:
    """Persistent long-term memory."""

    def __init__(self, owner_id: str) -> None:
        self.owner_id = owner_id
        self._entries: list[MemoryEntry] = []

    def add(self, entry: MemoryEntry) -> None:
        """Add a long-term memory."""
        entry.last_accessed = datetime.now().isoformat()
        self._entries.append(entry)

    def recall(self, context: str = "", limit: int = 10) -> list[MemoryEntry]:
        """Recall relevant memories based on context.

        Simple keyword matching for now; LLM-based recall can be layered on top.
        """
        if not context:
            return self._entries[-limit:]

        context_words = set(context.lower().split())
        scored: list[tuple[float, MemoryEntry]] = []
        for entry in self._entries:
            entry_words = set(entry.content.lower().split())
            overlap = len(context_words & entry_words)
            score = overlap + (entry.importance / 10.0)
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [entry for _, entry in scored[:limit]]

        # Update access time
        for entry in results:
            entry.last_accessed = datetime.now().isoformat()

        return results

    def get_all(self) -> list[MemoryEntry]:
        return list(self._entries)

    def get_by_type(self, memory_type: str) -> list[MemoryEntry]:
        return [e for e in self._entries if e.memory_type == memory_type]

    @property
    def count(self) -> int:
        return len(self._entries)


class MemoryStore:
    """Unified memory store managing short-term and long-term memory."""

    def __init__(
        self,
        owner_id: str,
        short_term_size: int = 20,
        compression_threshold: int = 100,
    ) -> None:
        self.owner_id = owner_id
        self.short_term = ShortTermMemory(owner_id, max_size=short_term_size)
        self.long_term = LongTermMemory(owner_id)
        self.compression_threshold = compression_threshold
        self._entry_counter = 0

    def record(self, content: str, importance: int = 5, turn: int = 0, event_id: str = "") -> MemoryEntry:
        """Record a new memory."""
        self._entry_counter += 1
        entry = MemoryEntry(
            id=f"mem_{self.owner_id}_{self._entry_counter}",
            owner_id=self.owner_id,
            content=content,
            importance=importance,
            turn=turn,
            source_event_ids=[event_id] if event_id else [],
        )
        self.short_term.add(entry)
        return entry

    def needs_compression(self) -> bool:
        """Check if memory needs compression."""
        return self.short_term.count >= self.compression_threshold

    def get_context(self, limit: int = 10) -> str:
        """Get memory context as a string for LLM prompts."""
        recent = self.short_term.get_recent(limit)
        long_term = self.long_term.recall(limit=5)

        parts = []
        if long_term:
            parts.append("Long-term memories:")
            for entry in long_term:
                parts.append(f"  - {entry.content}")
        if recent:
            parts.append("Recent events:")
            for entry in recent:
                parts.append(f"  - {entry.content}")
        return "\n".join(parts)
