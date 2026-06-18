"""NPC model and behavior system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jag.knowledge.memory import MemoryStore


@dataclass
class ScheduleEntry:
    """NPC daily schedule entry."""

    hour_start: int = 0
    hour_end: int = 0
    activity: str = ""
    location_id: str = ""


@dataclass
class NPCState:
    """NPC runtime state."""

    mood: str = "neutral"  # happy, neutral, sad, angry, fearful
    energy: float = 1.0  # 0.0-1.0
    hunger: float = 0.0  # 0.0-1.0
    current_action: str = ""
    current_location_id: str = ""


@dataclass
class NPC:
    """NPC data model with autonomous behavior support."""

    id: str
    name: str
    description: str = ""
    location_id: str = ""
    # Personality
    goal: str = ""
    desires: list[str] = field(default_factory=list)
    fears: list[str] = field(default_factory=list)
    personality: str = "neutral"
    # State
    state: NPCState = field(default_factory=NPCState)
    # Memory
    memory: MemoryStore = field(default_factory=lambda: MemoryStore("npc"))
    # Social
    relationships: dict[str, float] = field(default_factory=dict)  # char_id -> -100..100
    # Resources
    resources: dict[str, int] = field(default_factory=lambda: {"gold": 10})
    inventory: list[str] = field(default_factory=list)
    # Schedule
    schedule: list[ScheduleEntry] = field(default_factory=list)
    # Attributes
    attributes: dict[str, int] = field(default_factory=lambda: {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10})

    def __post_init__(self) -> None:
        if self.memory.owner_id == "npc":
            self.memory.owner_id = self.id
        self.state.current_location_id = self.location_id

    def get_current_schedule(self, hour: int) -> ScheduleEntry | None:
        """Get the schedule entry for the current hour."""
        for entry in self.schedule:
            if entry.hour_start <= hour < entry.hour_end:
                return entry
        return None

    def update_relationship(self, char_id: str, delta: float) -> None:
        """Update relationship value with another character."""
        current = self.relationships.get(char_id, 0.0)
        self.relationships[char_id] = max(-100, min(100, current + delta))

    def get_observation(self, world_data: dict[str, Any]) -> dict[str, Any]:
        """Get NPC's observation of the world (local perception)."""
        return {
            "location": world_data.get("location", {}),
            "nearby_characters": world_data.get("nearby_characters", []),
            "nearby_items": world_data.get("nearby_items", []),
            "time": world_data.get("time", ""),
            "self_state": {
                "mood": self.state.mood,
                "energy": self.state.energy,
                "hunger": self.state.hunger,
                "location": self.state.current_location_id,
            },
        }

    def record_memory(self, content: str, importance: int = 5, turn: int = 0) -> None:
        """Record a memory."""
        self.memory.record(content, importance=importance, turn=turn)
