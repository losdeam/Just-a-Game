"""Memory compression using LLM for summarization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from jag.knowledge.memory import LongTermMemory, MemoryEntry, MemoryStore, ShortTermMemory


class LLMCompressor(Protocol):
    """Protocol for LLM-based compression."""

    async def compress(self, entries_text: str, max_summaries: int = 3) -> list[str]: ...


class RuleBasedCompressor:
    """Rule-based fallback compressor (no LLM needed)."""

    async def compress(self, entries_text: str, max_summaries: int = 3) -> list[str]:
        """Simple rule-based compression."""
        lines = [l.strip() for l in entries_text.strip().split("\n") if l.strip()]
        if len(lines) <= max_summaries:
            return lines

        # Group into chunks and summarize each
        chunk_size = max(1, len(lines) // max_summaries)
        summaries = []
        for i in range(0, len(lines), chunk_size):
            chunk = lines[i:i + chunk_size]
            if len(chunk) == 1:
                summaries.append(chunk[0])
            else:
                summaries.append(f"Multiple events: {'; '.join(chunk[:2])}...")
            if len(summaries) >= max_summaries:
                break

        return summaries


class MemoryCompressor:
    """Compress short-term memory into long-term summaries."""

    def __init__(self, compressor: LLMCompressor | None = None) -> None:
        self._compressor = compressor or RuleBasedCompressor()

    async def compress(self, store: MemoryStore, max_summaries: int = 3) -> list[MemoryEntry]:
        """Compress short-term memories into long-term entries."""
        entries = store.short_term.clear()
        if not entries:
            return []

        # Build text from entries
        entries_text = "\n".join(
            f"[Turn {e.turn}] {e.content} (importance: {e.importance})"
            for e in entries
        )

        # Compress
        summaries = await self._compressor.compress(entries_text, max_summaries)

        # Create long-term entries
        source_ids = [e.id for e in entries]
        long_term_entries = []
        for i, summary in enumerate(summaries):
            entry = MemoryEntry(
                id=f"ltm_{store.owner_id}_{store.long_term.count + i + 1}",
                owner_id=store.owner_id,
                content=summary,
                importance=7,
                memory_type="historical",
                source_event_ids=source_ids,
            )
            store.long_term.add(entry)
            long_term_entries.append(entry)

        # Re-add high-importance short-term entries that shouldn't be compressed
        important = [e for e in entries if e.importance >= 8]
        for entry in important:
            store.short_term.add(entry)

        return long_term_entries
