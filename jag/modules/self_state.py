"""Self-state module: the player character's current situation.

Holds the player's identity, vitals, attributes, status effects, current
location, and the world time (turn/hour/day/season). Time lives here because it
is the player's temporal context — every action advances it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import ModuleBase


SEASON_NAMES = ["春季", "夏季", "秋季", "冬季"]
TIME_NAMES = {
    0: "深夜", 1: "深夜", 2: "深夜", 3: "深夜", 4: "黎明",
    5: "黎明", 6: "清晨", 7: "清晨", 8: "清晨", 9: "上午",
    10: "上午", 11: "上午", 12: "正午", 13: "下午", 14: "下午",
    15: "下午", 16: "傍晚", 17: "傍晚", 18: "黄昏", 19: "黄昏",
    20: "夜晚", 21: "夜晚", 22: "夜晚", 23: "夜晚",
}


@dataclass
class StatusEffect:
    name: str
    description: str = ""
    duration: int = 0  # turns remaining, 0 = indefinite


class SelfStateModule(ModuleBase):
    name = "self_state"

    def __init__(self) -> None:
        self.name: str = "冒险者"
        self.health: int = 100
        self.max_health: int = 100
        self.attributes: dict[str, int] = {}
        self.status_effects: list[StatusEffect] = []
        self.current_location_id: str = ""
        self.current_action: str = ""
        # Time state
        self.turn: int = 0
        self.hour: int = 8
        self.day: int = 1
        self.season: str = "春季"

    def is_empty(self) -> bool:
        return not self.current_location_id and self.turn == 0

    def advance_time(self, hours: int = 1) -> None:
        """Advance game time by a number of hours (1 turn = 1 hour, 30 days/season)."""
        self.turn += hours
        for _ in range(hours):
            self.hour += 1
            if self.hour >= 24:
                self.hour = 0
                self.day += 1
                if self.day > 30:
                    self.day = 1
                    idx = SEASON_NAMES.index(self.season) if self.season in SEASON_NAMES else 0
                    self.season = SEASON_NAMES[(idx + 1) % 4]
        # tick status effect durations
        for eff in self.status_effects:
            if eff.duration > 0:
                eff.duration -= 1
        self.status_effects = [e for e in self.status_effects if e.duration != 0]

    def time_of_day(self) -> str:
        return TIME_NAMES.get(self.hour, "未知")

    def time_display(self) -> str:
        return f"{self.hour:02d}:00（{self.time_of_day()}）"

    def to_prompt(self) -> str:
        lines = ["【自身状态】"]
        lines.append(f"姓名: {self.name} · 生命: {self.health}/{self.max_health}")
        lines.append(f"时间: 回合{self.turn} · 第{self.day}天 · {self.season} · {self.time_display()}")
        if self.current_location_id:
            lines.append(f"所在地点ID: {self.current_location_id}")
        if self.attributes:
            attrs = " ".join(f"{k}{v}" for k, v in self.attributes.items())
            lines.append(f"属性: {attrs}")
        if self.status_effects:
            effs = "、".join(
                e.name + (f"({e.duration}回合)" if e.duration > 0 else "") for e in self.status_effects
            )
            lines.append(f"状态效果: {effs}")
        else:
            lines.append("状态效果: 无")
        if self.current_action:
            lines.append(f"当前行为: {self.current_action}")
        return "\n".join(lines)

    def snapshot(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "health": self.health,
            "max_health": self.max_health,
            "attributes": dict(self.attributes),
            "status_effects": [
                {"name": e.name, "description": e.description, "duration": e.duration}
                for e in self.status_effects
            ],
            "current_location_id": self.current_location_id,
            "current_action": self.current_action,
            "turn": self.turn,
            "hour": self.hour,
            "day": self.day,
            "season": self.season,
        }

    def restore(self, data: dict[str, Any]) -> None:
        self.name = data.get("name", "冒险者")
        self.health = data.get("health", 100)
        self.max_health = data.get("max_health", 100)
        self.attributes = dict(data.get("attributes", {}))
        self.status_effects = [
            StatusEffect(
                name=e.get("name", ""),
                description=e.get("description", ""),
                duration=e.get("duration", 0),
            )
            for e in data.get("status_effects", [])
        ]
        self.current_location_id = data.get("current_location_id", "")
        self.current_action = data.get("current_action", "")
        self.turn = data.get("turn", 0)
        self.hour = data.get("hour", 8)
        self.day = data.get("day", 1)
        self.season = data.get("season", "春季")
