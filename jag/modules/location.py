"""Location module: the map of places the world contains.

Holds regions, locations, and their connections. The player's *current* position
lives in SelfStateModule; this module only describes the world geography. The
prompt focuses on the player's current location and where they can go, plus a
brief index of known places, so the Director stays grounded spatially.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import ModuleBase


@dataclass
class RegionData:
    id: str
    name: str = ""
    description: str = ""
    region_type: str = "settlement"


@dataclass
class LocationData:
    id: str
    name: str = ""
    description: str = ""
    region_id: str = ""
    location_type: str = "room"  # room/building/outdoor/dungeon
    light_level: int = 5  # 0-10
    danger_level: int = 0  # 0-10
    connected: list[str] = field(default_factory=list)  # location ids
    tags: list[str] = field(default_factory=list)


class LocationModule(ModuleBase):
    name = "location"

    def __init__(self) -> None:
        self.regions: dict[str, RegionData] = {}
        self.locations: dict[str, LocationData] = {}

    def is_empty(self) -> bool:
        return not self.locations

    def add_region(self, region: RegionData) -> None:
        self.regions[region.id] = region

    def add_location(self, loc: LocationData) -> None:
        self.locations[loc.id] = loc

    def get(self, loc_id: str) -> LocationData | None:
        return self.locations.get(loc_id)

    def connect(self, a: str, b: str) -> None:
        """Bidirectionally connect two locations."""
        la = self.locations.get(a)
        lb = self.locations.get(b)
        if la and b not in la.connected:
            la.connected.append(b)
        if lb and a not in lb.connected:
            lb.connected.append(a)

    def to_prompt(self) -> str:
        if self.is_empty():
            return "【地点】尚未建立任何地点。"
        lines = ["【地点】"]
        # Index of all locations (brief)
        index = "、".join(self.locations[l].name for l in self.locations)
        lines.append(f"已知地点: {index}")
        return "\n".join(lines)

    def prompt_for_location(self, loc_id: str) -> str:
        """Render a detailed prompt fragment for a specific (usually current) location."""
        loc = self.locations.get(loc_id)
        if not loc:
            return ""
        parts = [f"当前地点: {loc.name}"]
        if loc.description:
            parts.append(f"描述: {loc.description}")
        parts.append(f"类型: {loc.location_type} · 光照 {loc.light_level}/10 · 危险 {loc.danger_level}/10")
        if loc.connected:
            names = []
            for cid in loc.connected:
                cl = self.locations.get(cid)
                names.append(cl.name if cl else cid)
            parts.append("可前往: " + "、".join(names))
        else:
            parts.append("可前往: 无")
        return "\n".join(parts)

    def snapshot(self) -> dict[str, Any]:
        return {
            "regions": [
                {"id": r.id, "name": r.name, "description": r.description, "region_type": r.region_type}
                for r in self.regions.values()
            ],
            "locations": [
                {
                    "id": l.id,
                    "name": l.name,
                    "description": l.description,
                    "region_id": l.region_id,
                    "location_type": l.location_type,
                    "light_level": l.light_level,
                    "danger_level": l.danger_level,
                    "connected": list(l.connected),
                    "tags": list(l.tags),
                }
                for l in self.locations.values()
            ],
        }

    def restore(self, data: dict[str, Any]) -> None:
        self.regions = {
            r["id"]: RegionData(
                id=r["id"],
                name=r.get("name", ""),
                description=r.get("description", ""),
                region_type=r.get("region_type", "settlement"),
            )
            for r in data.get("regions", [])
        }
        self.locations = {
            l["id"]: LocationData(
                id=l["id"],
                name=l.get("name", ""),
                description=l.get("description", ""),
                region_id=l.get("region_id", ""),
                location_type=l.get("location_type", "room"),
                light_level=l.get("light_level", 5),
                danger_level=l.get("danger_level", 0),
                connected=list(l.get("connected", [])),
                tags=list(l.get("tags", [])),
            )
            for l in data.get("locations", [])
        }
