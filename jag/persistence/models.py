"""Data models for JAG persistence layer (20 tables)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlmodel import Field, SQLModel


# ──────────────────────────────────────────────
# Core entities
# ──────────────────────────────────────────────


class Character(SQLModel, table=True):
    __tablename__ = "characters"

    id: str = Field(primary_key=True)
    name: str
    description: str = ""
    character_type: str = "npc"  # npc, player, creature
    location_id: str = Field(default="", foreign_key="locations.id")
    hp: int = 20
    max_hp: int = 20
    level: int = 1
    experience: int = 0
    attributes_json: str = "{}"  # {"STR": 10, "DEX": 10, ...}
    skills_json: str = "{}"
    status_effects_json: str = "[]"
    is_alive: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def get_attributes(self) -> dict[str, int]:
        return json.loads(self.attributes_json)

    def set_attributes(self, attrs: dict[str, int]) -> None:
        self.attributes_json = json.dumps(attrs)

    def get_status_effects(self) -> list[str]:
        return json.loads(self.status_effects_json)


class Item(SQLModel, table=True):
    __tablename__ = "items"

    id: str = Field(primary_key=True)
    name: str
    description: str = ""
    item_type: str = "misc"  # weapon, armor, consumable, tool, misc
    location_id: str = ""
    owner_id: str = ""
    properties_json: str = "{}"  # {"flammable": true, "sharp": false, ...}
    quantity: int = 1
    value: int = 0  # gold value
    weight: float = 0.0
    is_equipped: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def get_properties(self) -> dict[str, bool]:
        return json.loads(self.properties_json)

    def set_properties(self, props: dict[str, bool]) -> None:
        self.properties_json = json.dumps(props)


class Location(SQLModel, table=True):
    __tablename__ = "locations"

    id: str = Field(primary_key=True)
    name: str
    description: str = ""
    region_id: str = Field(default="", foreign_key="regions.id")
    location_type: str = "room"  # room, building, outdoor, dungeon
    light_level: int = 5  # 0-10
    danger_level: int = 0
    is_accessible: bool = True
    connected_locations_json: str = "[]"  # list of location IDs
    tags_json: str = "[]"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def get_connected_locations(self) -> list[str]:
        return json.loads(self.connected_locations_json)


class Region(SQLModel, table=True):
    __tablename__ = "regions"

    id: str = Field(primary_key=True)
    name: str
    description: str = ""
    region_type: str = "settlement"  # settlement, wilderness, dungeon, city
    danger_level: int = 0
    weather_state: str = "clear"
    season: str = "spring"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ──────────────────────────────────────────────
# Quests
# ──────────────────────────────────────────────


class Quest(SQLModel, table=True):
    __tablename__ = "quests"

    id: str = Field(primary_key=True)
    title: str
    description: str = ""
    quest_type: str = "main"  # main, side, personal, faction
    status: str = "available"  # available, active, completed, failed
    giver_id: str = ""  # NPC who gives the quest
    objectives_json: str = "[]"  # [{"desc": "...", "completed": false}]
    rewards_json: str = "{}"  # {"xp": 100, "gold": 50, "items": [...]}
    source: str = ""  # npc_need, faction_conflict, world_event, player_action
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def get_objectives(self) -> list[dict[str, Any]]:
        return json.loads(self.objectives_json)


# ──────────────────────────────────────────────
# Factions & Relationships
# ──────────────────────────────────────────────


class Faction(SQLModel, table=True):
    __tablename__ = "factions"

    id: str = Field(primary_key=True)
    name: str
    description: str = ""
    faction_type: str = "organization"  # organization, guild, kingdom, tribe
    leader_id: str = ""
    member_ids_json: str = "[]"
    goals_json: str = "[]"
    resources_json: str = "{}"  # {"gold": 1000, "influence": 50}
    reputation: int = 0  # player reputation with this faction
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def get_members(self) -> list[str]:
        return json.loads(self.member_ids_json)

    def get_goals(self) -> list[str]:
        return json.loads(self.goals_json)


class Relationship(SQLModel, table=True):
    __tablename__ = "relationships"

    id: str = Field(primary_key=True)
    source_id: str
    target_id: str
    relation_type: str = "neutral"  # friendly, neutral, hostile, allied, enemy
    value: float = 0.0  # -100 to 100
    context: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class NPCGoal(SQLModel, table=True):
    __tablename__ = "npc_goals"

    id: str = Field(primary_key=True)
    npc_id: str = Field(foreign_key="characters.id")
    goal_type: str = "long_term"  # long_term, short_term, immediate
    description: str
    priority: int = 5  # 1-10
    is_completed: bool = False
    progress: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class NPCSchedule(SQLModel, table=True):
    __tablename__ = "npc_schedules"

    id: str = Field(primary_key=True)
    npc_id: str = Field(foreign_key="characters.id")
    hour_start: int = 0  # 0-23
    hour_end: int = 0
    activity: str = ""
    location_id: str = ""
    day_of_week: str = "*"  # *, monday, tuesday, ...


# ──────────────────────────────────────────────
# Events & World State
# ──────────────────────────────────────────────


class Event(SQLModel, table=True):
    __tablename__ = "events"

    id: str = Field(primary_key=True)
    event_type: str  # combat, interaction, environment, quest, social, economy
    source_id: str = ""
    target_id: str = ""
    location_id: str = ""
    description: str = ""
    data_json: str = "{}"
    turn: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    def get_data(self) -> dict[str, Any]:
        return json.loads(self.data_json)


class WorldEvent(SQLModel, table=True):
    __tablename__ = "world_events"

    id: str = Field(primary_key=True)
    event_type: str  # war, plague, festival, disaster, political
    description: str = ""
    region_id: str = ""
    severity: int = 1  # 1-10
    is_active: bool = True
    turn_started: int = 0
    turn_resolved: int | None = None
    data_json: str = "{}"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class StoryThread(SQLModel, table=True):
    __tablename__ = "story_threads"

    id: str = Field(primary_key=True)
    title: str
    description: str = ""
    thread_type: str = "main"  # main, side, personal
    status: str = "dormant"  # dormant, active, climax, resolved
    related_events_json: str = "[]"
    related_npcs_json: str = "[]"
    tension_level: int = 0  # 0-10
    turn_created: int = 0
    turn_last_updated: int = 0


class EconomyState(SQLModel, table=True):
    __tablename__ = "economy_state"

    id: str = Field(primary_key=True)
    location_id: str
    commodity: str
    base_price: float = 10.0
    current_price: float = 10.0
    supply: float = 100.0
    demand: float = 100.0
    last_updated_turn: int = 0


class WeatherState(SQLModel, table=True):
    __tablename__ = "weather_state"

    id: str = Field(primary_key=True)
    region_id: str
    current_weather: str = "clear"  # clear, cloudy, rain, storm, snow, fog
    temperature: float = 20.0
    wind_speed: float = 0.0
    season: str = "spring"
    turn: int = 0


# ──────────────────────────────────────────────
# Knowledge Graph
# ──────────────────────────────────────────────


class KnowledgeNode(SQLModel, table=True):
    __tablename__ = "knowledge_nodes"

    id: str = Field(primary_key=True)
    node_type: str  # character, item, location, faction, concept
    name: str
    attributes_json: str = "{}"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def get_attributes(self) -> dict[str, Any]:
        return json.loads(self.attributes_json)


class KnowledgeEdge(SQLModel, table=True):
    __tablename__ = "knowledge_edges"

    id: str = Field(primary_key=True)
    source_id: str = Field(foreign_key="knowledge_nodes.id")
    target_id: str = Field(foreign_key="knowledge_nodes.id")
    relation_type: str  # owns, likes, hates, allied_with, enemy_of, knows, owes
    weight: float = 1.0
    attributes_json: str = "{}"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def get_attributes(self) -> dict[str, Any]:
        return json.loads(self.attributes_json)


# ──────────────────────────────────────────────
# Memory
# ──────────────────────────────────────────────


class MemoryShort(SQLModel, table=True):
    __tablename__ = "memory_short"

    id: str = Field(primary_key=True)
    owner_id: str  # character ID or "player"
    event_id: str = ""
    description: str = ""
    importance: int = 5  # 1-10
    turn: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class MemoryLong(SQLModel, table=True):
    __tablename__ = "memory_long"

    id: str = Field(primary_key=True)
    owner_id: str
    memory_type: str = "general"  # reputation, relationship, historical, personal
    content: str
    source_event_ids_json: str = "[]"
    importance: int = 5
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_accessed: str = Field(default_factory=lambda: datetime.now().isoformat())

    def get_source_events(self) -> list[str]:
        return json.loads(self.source_event_ids_json)


# ──────────────────────────────────────────────
# Logs
# ──────────────────────────────────────────────


class ActionLog(SQLModel, table=True):
    __tablename__ = "action_logs"

    id: str = Field(primary_key=True)
    actor_id: str
    action_type: str
    action_data_json: str = "{}"
    result: str = ""  # success, failure, critical_success, critical_failure
    turn: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class RuleTrigger(SQLModel, table=True):
    __tablename__ = "rule_triggers"

    id: str = Field(primary_key=True)
    rule_name: str
    trigger_context_json: str = "{}"
    effects_json: str = "[]"
    chain_depth: int = 0
    turn: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# All model classes for table creation
ALL_MODELS = [
    Character, Item, Location, Region, Quest,
    Faction, Relationship, NPCGoal, NPCSchedule, Event,
    KnowledgeNode, KnowledgeEdge, WorldEvent, StoryThread,
    EconomyState, WeatherState, MemoryShort, MemoryLong,
    ActionLog, RuleTrigger,
]
