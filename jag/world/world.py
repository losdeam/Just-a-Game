"""World state management: regions, locations, entities, time system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TimeState:
    """Game time tracking."""

    turn: int = 0
    hour: int = 8  # 0-23
    day: int = 1
    season: str = "spring"  # spring, summer, autumn, winter

    SEASON_NAMES = {"spring": "春季", "summer": "夏季", "autumn": "秋季", "winter": "冬季"}
    TIME_NAMES = {"morning": "清晨", "afternoon": "午后", "evening": "傍晚", "night": "深夜"}

    def advance(self, turns: int = 1) -> None:
        """Advance time by N turns (1 turn = ~1 hour)."""
        for _ in range(turns):
            self.turn += 1
            self.hour += 1
            if self.hour >= 24:
                self.hour = 0
                self.day += 1
                if self.day > 30:
                    self.day = 1
                    seasons = ["spring", "summer", "autumn", "winter"]
                    idx = seasons.index(self.season)
                    self.season = seasons[(idx + 1) % 4]

    def time_of_day(self) -> str:
        if 6 <= self.hour < 12:
            return "morning"
        elif 12 <= self.hour < 18:
            return "afternoon"
        elif 18 <= self.hour < 22:
            return "evening"
        else:
            return "night"

    def time_of_day_display(self) -> str:
        """Get Chinese display name for time of day."""
        return self.TIME_NAMES.get(self.time_of_day(), self.time_of_day())

    def season_display(self) -> str:
        """Get Chinese display name for season."""
        return self.SEASON_NAMES.get(self.season, self.season)

    def is_dark(self) -> bool:
        return self.hour < 6 or self.hour >= 20


@dataclass
class WorldLocation:
    """A location in the world."""

    id: str
    name: str
    description: str = ""
    region_id: str = ""
    location_type: str = "room"
    light_level: int = 5
    danger_level: int = 0
    connected: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)  # character IDs
    items: list[str] = field(default_factory=list)  # item IDs
    tags: list[str] = field(default_factory=list)


@dataclass
class WorldRegion:
    """A region containing locations."""

    id: str
    name: str
    description: str = ""
    region_type: str = "settlement"
    danger_level: int = 0
    locations: list[str] = field(default_factory=list)


class WorldState:
    """Main world state container."""

    def __init__(self) -> None:
        self.time = TimeState()
        self.regions: dict[str, WorldRegion] = {}
        self.locations: dict[str, WorldLocation] = {}
        self.characters: dict[str, dict[str, Any]] = {}  # char_id -> data
        self.items: dict[str, dict[str, Any]] = {}  # item_id -> data
        self.global_flags: dict[str, Any] = {}

    def add_region(self, region: WorldRegion) -> None:
        self.regions[region.id] = region

    def add_location(self, location: WorldLocation) -> None:
        self.locations[location.id] = location
        if location.region_id and location.region_id in self.regions:
            self.regions[location.region_id].locations.append(location.id)

    def add_character(self, char_id: str, data: dict[str, Any]) -> None:
        self.characters[char_id] = data
        loc_id = data.get("location_id", "")
        if loc_id in self.locations:
            if char_id not in self.locations[loc_id].entities:
                self.locations[loc_id].entities.append(char_id)

    def add_item(self, item_id: str, data: dict[str, Any]) -> None:
        self.items[item_id] = data
        loc_id = data.get("location_id", "")
        if loc_id in self.locations:
            if item_id not in self.locations[loc_id].items:
                self.locations[loc_id].items.append(item_id)

    def move_character(self, char_id: str, from_loc: str, to_loc: str) -> None:
        """Move a character between locations."""
        if from_loc in self.locations and char_id in self.locations[from_loc].entities:
            self.locations[from_loc].entities.remove(char_id)
        if to_loc in self.locations:
            if char_id not in self.locations[to_loc].entities:
                self.locations[to_loc].entities.append(char_id)
        if char_id in self.characters:
            self.characters[char_id]["location_id"] = to_loc

    def get_location_entities(self, location_id: str) -> list[str]:
        loc = self.locations.get(location_id)
        return list(loc.entities) if loc else []

    def get_location_items(self, location_id: str) -> list[str]:
        loc = self.locations.get(location_id)
        return list(loc.items) if loc else []

    def advance_time(self, turns: int = 1) -> None:
        self.time.advance(turns)
        # Update light levels based on time
        for loc in self.locations.values():
            if loc.location_type == "outdoor":
                if self.time.is_dark():
                    loc.light_level = max(1, loc.light_level - 3)
                else:
                    loc.light_level = min(10, loc.light_level + 2)

    def snapshot(self) -> dict[str, Any]:
        """Get a snapshot of world state."""
        return {
            "turn": self.time.turn,
            "time": f"{self.time.hour:02d}:00 ({self.time.time_of_day()})",
            "day": self.time.day,
            "season": self.time.season,
            "regions": len(self.regions),
            "locations": len(self.locations),
            "characters": len(self.characters),
        }
