"""NPC module: the cast of characters populating the world.

Holds all NPCs and their state (personality, goals, mood, relationship to the
player, location). The prompt surfaces NPCs at the player's current location and
any globally relevant NPCs, so the Director knows who can be interacted with.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import ModuleBase


@dataclass
class NPCData:
    id: str
    name: str = ""
    description: str = ""
    location_id: str = ""
    personality: str = "neutral"  # friendly/stern/charming/neutral/...
    goal: str = ""
    desires: list[str] = field(default_factory=list)
    fears: list[str] = field(default_factory=list)
    mood: str = "neutral"  # happy/sad/angry/fearful/neutral/...
    energy: float = 1.0  # 0.0-1.0
    relationship: float = 0.0  # -100..100 toward the player
    status: str = ""  # free-text current status, e.g. "正在巡逻"

    def relationship_label(self) -> str:
        r = self.relationship
        if r >= 60:
            return "亲密"
        if r >= 20:
            return "友善"
        if r > -20:
            return "中立"
        if r > -60:
            return "敌视"
        return "仇恨"


class NPCModule(ModuleBase):
    name = "npc"

    def __init__(self) -> None:
        self.npcs: dict[str, NPCData] = {}

    def is_empty(self) -> bool:
        return not self.npcs

    def add(self, npc: NPCData) -> None:
        self.npcs[npc.id] = npc

    def get(self, npc_id: str) -> NPCData | None:
        return self.npcs.get(npc_id)

    def at_location(self, loc_id: str) -> list[NPCData]:
        return [n for n in self.npcs.values() if n.location_id == loc_id]

    def to_prompt(self) -> str:
        if self.is_empty():
            return "【NPC】世界中尚无其他角色。"
        lines = ["【NPC】"]
        names = "、".join(n.name for n in self.npcs.values())
        lines.append(f"已知角色: {names}")
        return "\n".join(lines)

    def prompt_for_location(self, loc_id: str) -> str:
        """Render NPCs present at a given (usually current) location."""
        present = self.at_location(loc_id)
        if not present:
            return "此处没有其他人。"
        lines = ["此处的人:"]
        for n in present:
            bits = [f"{n.name}（{n.personality}）"]
            if n.description:
                bits.append(n.description)
            if n.goal:
                bits.append(f"目标: {n.goal}")
            bits.append(f"心情: {n.mood}")
            bits.append(f"对你: {n.relationship_label()}")
            if n.status:
                bits.append(f"状态: {n.status}")
            lines.append("- " + " | ".join(bits))
        return "\n".join(lines)

    def snapshot(self) -> dict[str, Any]:
        return {
            "npcs": [
                {
                    "id": n.id,
                    "name": n.name,
                    "description": n.description,
                    "location_id": n.location_id,
                    "personality": n.personality,
                    "goal": n.goal,
                    "desires": list(n.desires),
                    "fears": list(n.fears),
                    "mood": n.mood,
                    "energy": n.energy,
                    "relationship": n.relationship,
                    "status": n.status,
                }
                for n in self.npcs.values()
            ]
        }

    def restore(self, data: dict[str, Any]) -> None:
        self.npcs = {
            n["id"]: NPCData(
                id=n["id"],
                name=n.get("name", ""),
                description=n.get("description", ""),
                location_id=n.get("location_id", ""),
                personality=n.get("personality", "neutral"),
                goal=n.get("goal", ""),
                desires=list(n.get("desires", [])),
                fears=list(n.get("fears", [])),
                mood=n.get("mood", "neutral"),
                energy=n.get("energy", 1.0),
                relationship=n.get("relationship", 0.0),
                status=n.get("status", ""),
            )
            for n in data.get("npcs", [])
        }
