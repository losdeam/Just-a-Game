"""Demo world: sample world data, NPCs, items, rules, factions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from jag.core.items import GameItem, ItemProperties
from jag.world.economy import Commodity, EconomySimulator, Market
from jag.world.faction import Faction, FactionSimulator
from jag.world.npc import NPC, ScheduleEntry
from jag.world.world import WorldLocation, WorldRegion

DEMO_DIR = Path(__file__).parent


def _load_yaml(filename: str) -> dict[str, Any]:
    """Load a YAML file from the demo directory."""
    path = DEMO_DIR / filename
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_regions() -> list[WorldRegion]:
    """Load regions from world_data.yaml."""
    data = _load_yaml("world_data.yaml")
    regions = []
    for r in data.get("regions", []):
        regions.append(WorldRegion(
            id=r["id"],
            name=r["name"],
            description=r.get("description", ""),
            region_type=r.get("region_type", "settlement"),
            danger_level=r.get("danger_level", 0),
        ))
    return regions


def load_locations() -> list[WorldLocation]:
    """Load locations from world_data.yaml."""
    data = _load_yaml("world_data.yaml")
    locations = []
    for loc in data.get("locations", []):
        locations.append(WorldLocation(
            id=loc["id"],
            name=loc["name"],
            description=loc.get("description", ""),
            region_id=loc.get("region_id", ""),
            location_type=loc.get("location_type", "room"),
            light_level=loc.get("light_level", 5),
            danger_level=loc.get("danger_level", 0),
            connected=loc.get("connected", []),
            tags=loc.get("tags", []),
        ))
    return locations


def load_npcs() -> list[NPC]:
    """Load NPCs from npcs.yaml."""
    data = _load_yaml("npcs.yaml")
    npcs = []
    for n in data.get("npcs", []):
        schedule = []
        for s in n.get("schedule", []):
            schedule.append(ScheduleEntry(
                hour_start=s.get("hour_start", 0),
                hour_end=s.get("hour_end", 24),
                activity=s.get("activity", ""),
                location_id=s.get("location_id", ""),
            ))

        npcs.append(NPC(
            id=n["id"],
            name=n["name"],
            description=n.get("description", ""),
            location_id=n.get("location_id", ""),
            personality=n.get("personality", "neutral"),
            goal=n.get("goal", ""),
            desires=n.get("desires", []),
            fears=n.get("fears", []),
            attributes=n.get("attributes", {}),
            resources=n.get("resources", {"gold": 10}),
            schedule=schedule,
        ))
    return npcs


def load_items() -> list[GameItem]:
    """Load items from items.yaml."""
    data = _load_yaml("items.yaml")
    items = []
    # Map YAML property names to ItemProperties field names
    prop_map = {
        "weapon": "sharp",
        "sharp": "sharp",
        "metallic": "conductive",
        "portable": None,  # not a property, skip
        "container": "container",
        "light_source": "light_source",
        "flammable": "flammable",
        "consumable": "edible",
        "food": "edible",
        "healing": "magical",
        "liquid": "liquid",
        "climbable": "rope_like",
        "flexible": "rope_like",
        "valuable": None,
        "tool": None,
        "readable": None,
        "heavy": "heavy",
    }
    for it in data.get("items", []):
        raw_props = it.get("properties", {})
        mapped = {}
        for key, val in raw_props.items():
            field_name = prop_map.get(key)
            if field_name and val:
                mapped[field_name] = True
        items.append(GameItem(
            id=it["id"],
            name=it["name"],
            description=it.get("description", ""),
            properties=ItemProperties(**mapped),
            value=it.get("value", 1),
            tags=list(raw_props.keys()),
        ))
    return items


def load_factions() -> tuple[list[Faction], list[dict[str, str]]]:
    """Load factions and relations from factions.yaml."""
    data = _load_yaml("factions.yaml")
    factions = []
    for f in data.get("factions", []):
        factions.append(Faction(
            id=f["id"],
            name=f["name"],
            description=f.get("description", ""),
            faction_type=f.get("faction_type", "organization"),
            leader_id=f.get("leader_id", ""),
            members=f.get("members", []),
            goals=f.get("goals", []),
            resources=f.get("resources", {"gold": 100, "influence": 10}),
        ))
    relations = data.get("relations", [])
    return factions, relations


def setup_economy(economy: EconomySimulator, locations: list[WorldLocation]) -> None:
    """Set up basic economy for demo locations."""
    # Market at village square
    market = Market(location_id="village_square")
    market.commodities = {
        "bread": Commodity(id="bread", name="Bread", base_price=2.0),
        "ale": Commodity(id="ale", name="Ale", base_price=3.0),
        "iron": Commodity(id="iron", name="Iron Ore", base_price=15.0),
        "herbs": Commodity(id="herbs", name="Herbs", base_price=5.0),
    }
    economy.add_market(market)

    # Market at market stall
    stall = Market(location_id="market_stall")
    stall.commodities = {
        "bread": Commodity(id="bread", name="Bread", base_price=2.5),
        "herbs": Commodity(id="herbs", name="Herbs", base_price=4.0, supply=60),
        "potion": Commodity(id="potion", name="Healing Potion", base_price=15.0, supply=5),
    }
    economy.add_market(stall)


class WorldLoader:
    """Load and set up the complete demo world."""

    def __init__(self, demo_dir: Path | None = None) -> None:
        self.demo_dir = demo_dir or DEMO_DIR

    def load_all(self) -> dict[str, Any]:
        """Load all demo world data.

        Returns a dict with keys: regions, locations, npcs, items, factions, relations
        """
        return {
            "regions": load_regions(),
            "locations": load_locations(),
            "npcs": load_npcs(),
            "items": load_items(),
            "factions": load_factions()[0],
            "relations": load_factions()[1],
        }

    def validate(self, data: dict[str, Any]) -> list[str]:
        """Validate loaded data for completeness.

        Returns list of validation error messages (empty if valid).
        """
        errors = []

        # Check regions exist
        region_ids = {r.id for r in data.get("regions", [])}
        if not region_ids:
            errors.append("No regions defined")

        # Check locations reference valid regions
        location_ids = set()
        for loc in data.get("locations", []):
            location_ids.add(loc.id)
            if loc.region_id and loc.region_id not in region_ids:
                errors.append(f"Location '{loc.id}' references unknown region '{loc.region_id}'")

        if not location_ids:
            errors.append("No locations defined")

        # Check NPCs reference valid locations
        for npc in data.get("npcs", []):
            if npc.location_id and npc.location_id not in location_ids:
                errors.append(f"NPC '{npc.id}' at unknown location '{npc.location_id}'")
            for entry in npc.schedule:
                if entry.location_id and entry.location_id not in location_ids:
                    errors.append(f"NPC '{npc.id}' schedule references unknown location '{entry.location_id}'")

        # Check connections
        for loc in data.get("locations", []):
            for conn in loc.connected:
                if conn not in location_ids:
                    errors.append(f"Location '{loc.id}' connects to unknown location '{conn}'")

        return errors
