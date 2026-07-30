"""Worldview module: the world setting / lore.

Holds the immutable-ish setting of the world (name, genre, era, atmosphere,
history, main quest, factions). The Director reads it to stay consistent with
the world's tone, and tools may refine it (e.g. add a faction, append history).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import ModuleBase


@dataclass
class Faction:
    name: str
    description: str = ""
    relationship: str = "neutral"  # ally / neutral / hostile


class WorldviewModule(ModuleBase):
    name = "worldview"

    def __init__(self) -> None:
        self.world_name: str = ""
        self.genre: str = ""
        self.era: str = ""
        self.atmosphere: str = ""
        self.terrain: str = ""
        self.magic_level: str = ""
        self.danger_level: str = ""
        self.description: str = ""
        self.history: str = ""
        self.main_quest: str = ""
        self.factions: list[Faction] = []

    def is_empty(self) -> bool:
        return not self.world_name

    def to_prompt(self) -> str:
        if self.is_empty():
            return "【世界观】尚未建立。"
        lines = ["【世界观】"]
        lines.append(f"世界: {self.world_name}")
        tags = [t for t in (self.genre, self.era, self.terrain, self.magic_level, self.danger_level) if t]
        if tags:
            lines.append("标签: " + " · ".join(tags))
        if self.atmosphere:
            lines.append(f"氛围: {self.atmosphere}")
        if self.description:
            lines.append(f"简介: {self.description}")
        if self.history:
            lines.append(f"历史: {self.history}")
        if self.main_quest:
            lines.append(f"主线任务: {self.main_quest}")
        if self.factions:
            fac = "、".join(
                f"{f.name}({f.relationship})" + (f": {f.description}" if f.description else "")
                for f in self.factions
            )
            lines.append(f"势力: {fac}")
        return "\n".join(lines)

    def snapshot(self) -> dict[str, Any]:
        return {
            "world_name": self.world_name,
            "genre": self.genre,
            "era": self.era,
            "atmosphere": self.atmosphere,
            "terrain": self.terrain,
            "magic_level": self.magic_level,
            "danger_level": self.danger_level,
            "description": self.description,
            "history": self.history,
            "main_quest": self.main_quest,
            "factions": [
                {"name": f.name, "description": f.description, "relationship": f.relationship}
                for f in self.factions
            ],
        }

    def restore(self, data: dict[str, Any]) -> None:
        self.world_name = data.get("world_name", "")
        self.genre = data.get("genre", "")
        self.era = data.get("era", "")
        self.atmosphere = data.get("atmosphere", "")
        self.terrain = data.get("terrain", "")
        self.magic_level = data.get("magic_level", "")
        self.danger_level = data.get("danger_level", "")
        self.description = data.get("description", "")
        self.history = data.get("history", "")
        self.main_quest = data.get("main_quest", "")
        self.factions = [
            Faction(
                name=f.get("name", ""),
                description=f.get("description", ""),
                relationship=f.get("relationship", "neutral"),
            )
            for f in data.get("factions", [])
        ]
