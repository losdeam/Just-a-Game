"""GameMaster: central orchestrator holding all subsystem references."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from jag.agents.action_planner import ActionPlanner
from jag.agents.llm import LLMConfig, LLMFactory, LLMProvider
from jag.agents.narrative import NarrativeGenerator
from jag.agents.npc_agent import NPCAgent
from jag.agents.story_director import StoryDirector
from jag.config import GameConfig, load_config
from jag.core.dice import DiceRoller
from jag.core.events import EventBus, EventType, GameEvent
from jag.core.rules import RuleEngine
from jag.debug.tracer import PipelineTracer
from jag.knowledge.compression import MemoryCompressor, RuleBasedCompressor
from jag.knowledge.graph import KnowledgeGraph
from jag.knowledge.memory import MemoryStore
from jag.world.economy import EconomySimulator
from jag.world.faction import FactionSimulator
from jag.world.npc import NPC
from jag.world.quest import QuestGenerator
from jag.world.tick import TickEngine, TickResult
from jag.world.weather import WeatherSimulator
from jag.world.world import WorldLocation, WorldRegion, WorldState

logger = logging.getLogger(__name__)


class GameMaster:
    """Central game orchestrator.

    Holds references to all subsystems and provides the main game loop interface.
    """

    def __init__(self, config: GameConfig | None = None) -> None:
        self.config = config or GameConfig()

        # Core systems
        self.world = WorldState()
        self.event_bus = EventBus()
        self.rule_engine = RuleEngine(self.event_bus, max_chain_depth=self.config.max_chain_depth)
        self.dice = DiceRoller()
        self.knowledge = KnowledgeGraph()

        # Simulators
        self.weather = WeatherSimulator()
        self.economy = EconomySimulator()
        self.faction = FactionSimulator()
        self.quest_gen = QuestGenerator()

        # LLM
        self._init_llm()

        # Agents
        self.action_planner = ActionPlanner(llm=self._get_llm("action_planner"))
        self.npc_agent = NPCAgent(llm=self._get_llm("npc_agent"))
        self.story_director = StoryDirector(
            llm=self._get_llm("story_director"),
            event_bus=self.event_bus,
        )
        self.narrator = NarrativeGenerator(llm=self._get_llm("narrator"))

        # Debug tracer (must be created before TickEngine)
        self.tracer = PipelineTracer()

        # Tick engine
        self.tick_engine = TickEngine(
            world=self.world,
            event_bus=self.event_bus,
            rule_engine=self.rule_engine,
            dice=self.dice,
            weather=self.weather,
            economy=self.economy,
            faction=self.faction,
            quest_gen=self.quest_gen,
            knowledge=self.knowledge,
            action_planner=self.action_planner,
            story_director=self.story_director,
            narrator=self.narrator,
            npc_agent=self.npc_agent,
            npc_concurrency=self.config.npc_concurrency,
            tracer=self.tracer,
        )

        # Player state
        self.player_id = "player"
        self._player_memory = MemoryStore(self.player_id)

        # Game state
        self._running = False
        self._turn_count = 0
        self.world_lore: dict[str, Any] = {}

    def _is_valid_api_key(self, api_key: str) -> bool:
        """Check if an API key is valid (not empty and not a placeholder)."""
        if not api_key:
            return False
        placeholders = [
            "your-api-key-here", "your_api_key_here", "sk-xxxx", "sk-xxx",
            "placeholder", "example", "test", "demo", "changeme",
        ]
        normalized = api_key.strip().lower()
        if normalized in placeholders:
            return False
        if normalized.startswith("your-") or normalized.startswith("your_"):
            return False
        return True

    def _init_llm(self) -> None:
        """Initialize LLM factory from config."""
        default_cfg = self.config.llm.default
        if default_cfg.provider == "mock" or not self._is_valid_api_key(default_cfg.api_key):
            default_llm_config = LLMConfig(provider="mock")
        else:
            default_llm_config = LLMConfig(
                provider="litellm",
                upstream_provider=default_cfg.provider,
                model=default_cfg.model,
                api_key=default_cfg.api_key,
                api_base=default_cfg.api_base,
                temperature=default_cfg.temperature,
                max_tokens=default_cfg.max_tokens,
                disable_thinking=default_cfg.disable_thinking,
            )
        module_configs = {}
        for name, mod_cfg in self.config.llm.modules.items():
            if mod_cfg.provider == "mock" or not self._is_valid_api_key(mod_cfg.api_key):
                module_configs[name] = LLMConfig(provider="mock")
            else:
                module_configs[name] = LLMConfig(
                    provider="litellm",
                    upstream_provider=mod_cfg.provider,
                    model=mod_cfg.model,
                    api_key=mod_cfg.api_key,
                    api_base=mod_cfg.api_base,
                    temperature=mod_cfg.temperature,
                    max_tokens=mod_cfg.max_tokens,
                    disable_thinking=mod_cfg.disable_thinking,
                )
        self._llm_factory = LLMFactory(
            default_config=default_llm_config,
            module_configs=module_configs,
        )

    def _get_llm(self, module: str) -> LLMProvider:
        """Get LLM provider for a module."""
        return self._llm_factory.get(module)

    def refresh_llm(self) -> None:
        """Reinitialize LLM factory and all LLM-based components.
        
        Call this after updating config.llm to apply changes.
        """
        self._init_llm()
        # Re-create LLM-dependent agents with new providers
        self.action_planner = ActionPlanner(llm=self._get_llm("action_planner"))
        self.npc_agent = NPCAgent(llm=self._get_llm("npc_agent"))
        self.story_director = StoryDirector(
            llm=self._get_llm("story_director"),
            event_bus=self.event_bus,
        )
        self.narrator = NarrativeGenerator(llm=self._get_llm("narrator"))
        # Update TickEngine's references so it uses the new agents
        self.tick_engine.action_planner = self.action_planner
        self.tick_engine.npc_agent = self.npc_agent
        self.tick_engine.narrator = self.narrator
        self.tick_engine.story_director = self.story_director
        logger.info("LLM components refreshed")

    # ── World setup ──────────────────────────────────────────────

    def setup_world(
        self,
        regions: list[WorldRegion] | None = None,
        locations: list[WorldLocation] | None = None,
        npcs: list[NPC] | None = None,
        player_data: dict[str, Any] | None = None,
        lore: dict[str, Any] | None = None,
    ) -> None:
        """Set up the game world with regions, locations, NPCs, and player."""
        for region in regions or []:
            self.world.add_region(region)
            self.weather.add_region(region.id)

        for location in locations or []:
            self.world.add_location(location)

        for npc in npcs or []:
            npc_data = {
                "location_id": npc.location_id,
                "name": npc.name,
                "type": "npc",
                "health": 100,
                "max_health": 100,
            }
            self.world.add_character(npc.id, npc_data)
            self.tick_engine.register_npc(npc)

        # Add player
        if player_data:
            # Ensure player has health fields
            if "health" not in player_data:
                player_data["health"] = 100
            if "max_health" not in player_data:
                player_data["max_health"] = 100
            self.world.add_character(self.player_id, player_data)
        else:
            # Default: place player at first location
            first_loc = next(iter(self.world.locations), "")
            self.world.add_character(self.player_id, {
                "location_id": first_loc,
                "inventory": [],
                "name": "Player",
                "type": "player",
                "health": 100,
                "max_health": 100,
            })

        # Store lore
        if lore:
            self.world_lore = lore

    def clear_world(self) -> None:
        """Clear all world state for a fresh rebuild."""
        self.world = WorldState()
        self.world_lore = {}
        self._turn_count = 0
        self.tick_engine.clear_npcs()
        self.knowledge = KnowledgeGraph()
        self.quest_gen = QuestGenerator()
        self.event_bus = EventBus()
        self.rule_engine = RuleEngine(self.event_bus, max_chain_depth=self.config.max_chain_depth)

    # ── Game loop ────────────────────────────────────────────────

    async def generate_opening(self) -> str:
        """Generate an immersive opening narration for the player."""
        player = self.world.characters.get(self.player_id, {})
        loc_id = player.get("location_id", "")
        location = self.world.locations.get(loc_id)

        if self.narrator and self.narrator.llm:
            try:
                inv = player.get("inventory", [])
                context = {
                    "location": {
                        "name": location.name if location else "unknown",
                        "description": location.description[:200] if location else "",
                        "type": location.location_type if location else "outdoor",
                    },
                    "time": f"{self.world.time.time_of_day()} (hour {self.world.time.hour})",
                    "day": self.world.time.day,
                    "season": self.world.time.season,
                    "inventory": inv[:8],
                }
                prompt = (
                    f"地点: {context['location']['name']}（{context['location']['description']}）\n"
                    f"时间: {context['time']}，第{context['day']}天，{context['season']}\n"
                    f"背包: {'、'.join(context['inventory']) if context['inventory'] else '空'}\n\n"
                    "请以第二人称「你」写一段沉浸式的开场白，描述玩家初次来到这个世界时的所见所感。"
                    "包括环境氛围、感官细节，暗示前方的冒险。不要提及具体NPC。3-5句。"
                )
                opening = await asyncio.wait_for(
                    self.narrator.llm.complete(
                        prompt=prompt,
                        system="你是一个沉浸式开放世界RPG的叙事者。所有输出使用简体中文。",
                        max_tokens=300,
                    ),
                    timeout=10.0,
                )
                return opening.strip()
            except asyncio.TimeoutError:
                logger.warning("generate_opening timed out after 10 seconds")
            except Exception:
                pass

        # Fallback
        loc_name = location.name if location else "未知之地"
        loc_desc = location.description if location else ""
        inv = player.get("inventory", [])
        inv_str = f"你的背包里有{'、'.join(inv)}。" if inv else "你的背包空空如也。"
        return (
            f"你睁开双眼，发现自己身处{loc_name}。{loc_desc}\n"
            f"{inv_str}\n"
            f"一场伟大的冒险正等待着你……"
        )

    async def process_action(self, player_input: str) -> tuple[str, list[dict[str, Any]]]:
        """Process a player action and return narrative text and suggested options.

        Args:
            player_input: Natural language player input

        Returns:
            Tuple of (narrative text, suggested options list)
        """
        action = {
            "text": player_input,
            "player_id": self.player_id,
        }

        result = await self.tick_engine.tick(action)
        self._turn_count += 1

        # Record to player memory
        self._player_memory.record(
            f"Turn {result.turn}: {player_input}",
            importance=5,
            turn=result.turn,
        )

        # Get suggested options after action
        options = await self.get_suggested_options()

        return (result.narrative or f"Turn {result.turn} complete.", options)

    async def advance_world(self, turns: int = 1) -> tuple[list[str], list[dict[str, Any]]]:
        """Advance the world without player action.

        Returns tuple of (list of narrative texts, suggested options).
        """
        narratives = []
        for _ in range(turns):
            result = await self.tick_engine.tick(None)
            self._turn_count += 1
            if result.narrative:
                narratives.append(result.narrative)
            else:
                narratives.append(f"Time passes... (Turn {result.turn})")
        
        # Get suggested options after advance
        options = await self.get_suggested_options()
        return (narratives, options)

    async def get_suggested_options(self) -> list[dict[str, Any]]:
        """Get suggested actions for the player."""
        try:
            return await asyncio.wait_for(
                self.action_planner.suggest_options(self.player_id, self.world),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            logger.warning("get_suggested_options timed out after 10 seconds")
            return self.action_planner._fallback_suggestions(3)

    def get_status(self) -> dict[str, Any]:
        """Get current game status."""
        player = self.world.characters.get(self.player_id, {})
        loc_id = player.get("location_id", "")
        location = self.world.locations.get(loc_id)

        # Only count NPCs at the player's location
        nearby_npcs = [
            cid for cid, c in self.world.characters.items()
            if c.get("location_id") == loc_id and c.get("type") == "npc"
        ]
        
        # Get nearby entities from location
        nearby_entities = []
        if location:
            nearby_entities = [e for e in location.entities if e != self.player_id]

        return {
            "turn": self.world.time.turn,
            "time": f"{self.world.time.hour:02d}:00（{self.world.time.time_of_day_display()}）",
            "day": self.world.time.day,
            "season": self.world.time.season_display(),
            "location": location.name if location else "unknown",
            "location_description": location.description if location else "",
            "inventory": player.get("inventory", []),
            "health": player.get("health", 100),
            "max_health": player.get("max_health", 100),
            "equipment": player.get("equipment", []),
            "nearby_npcs": nearby_npcs,
            "nearby_entities": nearby_entities,
            "active_threads": len(self.story_director.get_active_threads()),
            "active_quests": len(self.quest_gen.active_quests),
        }

    # ── Save/Load ────────────────────────────────────────────────

    def save_game(self, path: str = "savegame.json") -> None:
        """Save current game state to JSON."""
        regions_data = {
            rid: {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "region_type": r.region_type,
                "danger_level": r.danger_level,
                "locations": r.locations,
            }
            for rid, r in self.world.regions.items()
        }

        locations_data = {
            lid: {
                "id": l.id,
                "name": l.name,
                "description": l.description,
                "region_id": l.region_id,
                "location_type": l.location_type,
                "light_level": l.light_level,
                "danger_level": l.danger_level,
                "connected": l.connected,
                "entities": l.entities,
                "items": l.items,
                "tags": l.tags,
            }
            for lid, l in self.world.locations.items()
        }

        npc_states = {}
        for npc_id, npc in self.tick_engine._npcs.items():
            npc_states[npc_id] = {
                "id": npc.id,
                "name": npc.name,
                "description": npc.description,
                "personality": npc.personality,
                "goal": npc.goal,
                "schedule": [
                    {"hour_start": s.hour_start, "hour_end": s.hour_end,
                     "activity": s.activity, "location_id": s.location_id}
                    for s in npc.schedule
                ],
                "state": {
                    "current_location_id": npc.state.current_location_id,
                    "mood": npc.state.mood,
                    "energy": npc.state.energy,
                    "hunger": npc.state.hunger,
                    "current_action": npc.state.current_action,
                },
            }

        state = {
            "version": 1,
            "time": {
                "turn": self.world.time.turn,
                "hour": self.world.time.hour,
                "day": self.world.time.day,
                "season": self.world.time.season,
            },
            "regions": regions_data,
            "locations": locations_data,
            "characters": self.world.characters,
            "items": self.world.items,
            "global_flags": self.world.global_flags,
            "npcs": npc_states,
            "lore": self.world_lore,
            "turn_count": self._turn_count,
            "knowledge": self.knowledge.to_dict(),
            "active_quests": [q.to_dict() if hasattr(q, "to_dict") else str(q) for q in self.quest_gen.active_quests]
            if hasattr(self.quest_gen, "active_quests") else [],
        }

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        logger.info("Game saved to %s", path)

    def load_game(self, path: str = "savegame.json") -> bool:
        """Load game state from JSON. Returns True on success."""
        p = Path(path)
        if not p.exists():
            logger.warning("Save file not found: %s", path)
            return False

        try:
            with open(p, encoding="utf-8") as f:
                state = json.load(f)

            self.clear_world()

            # Restore regions
            for rid, rdata in state.get("regions", {}).items():
                region = WorldRegion(
                    id=rdata["id"],
                    name=rdata["name"],
                    description=rdata.get("description", ""),
                    region_type=rdata.get("region_type", "settlement"),
                    danger_level=rdata.get("danger_level", 0),
                    locations=rdata.get("locations", []),
                )
                self.world.add_region(region)
                self.weather.add_region(region.id)

            # Restore locations
            for lid, ldata in state.get("locations", {}).items():
                location = WorldLocation(
                    id=ldata["id"],
                    name=ldata["name"],
                    description=ldata.get("description", ""),
                    region_id=ldata.get("region_id", ""),
                    location_type=ldata.get("location_type", "room"),
                    light_level=ldata.get("light_level", 5),
                    danger_level=ldata.get("danger_level", 0),
                    connected=ldata.get("connected", []),
                    entities=ldata.get("entities", []),
                    items=ldata.get("items", []),
                    tags=ldata.get("tags", []),
                )
                self.world.add_location(location)

            # Restore characters
            for cid, cdata in state.get("characters", {}).items():
                self.world.characters[cid] = cdata

            # Restore items
            for iid, idata in state.get("items", {}).items():
                self.world.items[iid] = idata

            # Restore time
            time_data = state.get("time", {})
            self.world.time.turn = time_data.get("turn", 0)
            self.world.time.hour = time_data.get("hour", 8)
            self.world.time.day = time_data.get("day", 1)
            self.world.time.season = time_data.get("season", "spring")
            self._turn_count = state.get("turn_count", 0)

            # Restore global flags
            self.world.global_flags = state.get("global_flags", {})

            # Restore NPCs
            from jag.world.npc import NPC, ScheduleEntry
            for npc_id, ndata in state.get("npcs", {}).items():
                schedule = [
                    ScheduleEntry(
                        hour_start=s["hour_start"],
                        hour_end=s["hour_end"],
                        activity=s["activity"],
                        location_id=s["location_id"],
                    )
                    for s in ndata.get("schedule", [])
                ]
                npc = NPC(
                    id=ndata["id"],
                    name=ndata["name"],
                    description=ndata.get("description", ""),
                    location_id=ndata.get("state", {}).get("current_location_id", ""),
                    personality=ndata.get("personality", "neutral"),
                    goal=ndata.get("goal", ""),
                    schedule=schedule,
                )
                if "state" in ndata:
                    st = ndata["state"]
                    npc.state.current_location_id = st.get("current_location_id", npc.state.current_location_id)
                    npc.state.mood = st.get("mood", npc.state.mood)
                    npc.state.energy = st.get("energy", npc.state.energy)
                    npc.state.hunger = st.get("hunger", npc.state.hunger)
                    npc.state.current_action = st.get("current_action", npc.state.current_action)
                self.tick_engine.register_npc(npc)

            # Restore lore
            self.world_lore = state.get("lore", {})

            # Restore knowledge graph
            kg_data = state.get("knowledge", {})
            if kg_data:
                self.knowledge.from_dict(kg_data)

            logger.info("Game loaded from %s", path)
            return True
        except Exception as e:
            logger.error("Failed to load game: %s", e)
            return False
