"""Faction simulation: relationships, reputation, conflicts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Faction:
    """A faction in the world."""

    id: str
    name: str
    description: str = ""
    faction_type: str = "organization"
    leader_id: str = ""
    members: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    resources: dict[str, int] = field(default_factory=lambda: {"gold": 100, "influence": 10})
    player_reputation: int = 0  # -100 to 100


class FactionSimulator:
    """Simulate faction dynamics."""

    def __init__(self) -> None:
        self.factions: dict[str, Faction] = {}
        self.relations: dict[tuple[str, str], str] = {}  # (id1, id2) -> relation

    def add_faction(self, faction: Faction) -> None:
        self.factions[faction.id] = faction

    def set_relation(self, faction_a: str, faction_b: str, relation: str) -> None:
        """Set relation: hostile, neutral, friendly, allied."""
        key = tuple(sorted([faction_a, faction_b]))
        self.relations[key] = relation

    def get_relation(self, faction_a: str, faction_b: str) -> str:
        key = tuple(sorted([faction_a, faction_b]))
        return self.relations.get(key, "neutral")

    def modify_reputation(self, faction_id: str, delta: int) -> None:
        if faction_id in self.factions:
            f = self.factions[faction_id]
            f.player_reputation = max(-100, min(100, f.player_reputation + delta))

    def tick(self, world_state: Any = None) -> list[dict[str, Any]]:
        """Process one tick of faction simulation. Returns events."""
        events = []

        # Check for conflicts between hostile factions
        faction_ids = list(self.factions.keys())
        for i in range(len(faction_ids)):
            for j in range(i + 1, len(faction_ids)):
                rel = self.get_relation(faction_ids[i], faction_ids[j])
                if rel == "hostile":
                    events.append({
                        "type": "faction_tension",
                        "factions": [faction_ids[i], faction_ids[j]],
                        "description": f"Tension between {self.factions[faction_ids[i]].name} and {self.factions[faction_ids[j]].name}",
                    })

        return events
