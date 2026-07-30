"""GameMaster: central orchestrator holding all subsystem references."""

from __future__ import annotations

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

    def _init_llm(self) -> None:
        """Initialize LLM factory from config."""
        default_cfg = self.config.llm.default
        if default_cfg.provider == "mock":
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
            if mod_cfg.provider == "mock":
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

    def reinit_llm(self) -> None:
        """Re-initialize LLM factory and all agent LLM providers after config update."""
        self._init_llm()
        self.action_planner.llm = self._get_llm("action_planner")
        self.npc_agent.llm = self._get_llm("npc_agent")
        self.story_director.llm = self._get_llm("story_director")
        self.narrator.llm = self._get_llm("narrator")
        logger.info("LLM providers re-initialized from updated config")

    def _get_llm(self, module: str) -> LLMProvider:
        """Get LLM provider for a module."""
        return self._llm_factory.get(module)

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
                opening = await self.narrator.llm.complete(
                    prompt=prompt,
                    system="你是一个沉浸式开放世界RPG的叙事者。所有输出使用简体中文。",
                    max_tokens=300,
                )
                return opening.strip()
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
        return await self.action_planner.suggest_options(self.player_id, self.world)

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
        """Save current game state to JSON.

        持久化范围：世界设定（world_lore，作为剧本提示词）、区域、地点、
        完整 NPC（含属性/日程/关系/记忆）、玩家角色、任务、剧情线、知识图谱。
        """
        state = {
            "world": self.world.snapshot(),
            "time": {
                "turn": self.world.time.turn,
                "hour": self.world.time.hour,
                "day": self.world.time.day,
                "season": self.world.time.season,
            },
            "world_lore": self.world_lore,
            "regions": [self._serialize_region(r) for r in self.world.regions.values()],
            "locations": [self._serialize_location(loc) for loc in self.world.locations.values()],
            "characters": {
                cid: {
                    "location_id": c.get("location_id", ""),
                    "inventory": c.get("inventory", []),
                    "name": c.get("name", ""),
                    "type": c.get("type", ""),
                    "health": c.get("health", 100),
                    "max_health": c.get("max_health", 100),
                }
                for cid, c in self.world.characters.items()
            },
            "npcs": [self._serialize_npc(npc) for npc in self.tick_engine._npcs.values()],
            "quests": [self._serialize_quest(q) for q in self.quest_gen.active_quests.values()],
            "story_threads": [self._serialize_thread(t) for t in self.story_director.threads.values()],
            "global_flags": self.world.global_flags,
            "knowledge": self.knowledge.to_dict(),
        }

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        logger.info("Game saved to %s (regions=%d locations=%d npcs=%d quests=%d)",
                    path, len(state["regions"]), len(state["locations"]),
                    len(state["npcs"]), len(state["quests"]))

    def load_game(self, path: str = "savegame.json") -> bool:
        """Load game state from JSON. Returns True on success."""
        p = Path(path)
        if not p.exists():
            logger.warning("Save file not found: %s", path)
            return False

        try:
            with open(p) as f:
                state = json.load(f)

            # 重新构建世界状态（避免残留旧数据）
            self.clear_world()

            # Restore time
            time_data = state.get("time", {})
            self.world.time.turn = time_data.get("turn", 0)
            self.world.time.hour = time_data.get("hour", 8)
            self.world.time.day = time_data.get("day", 1)
            self.world.time.season = time_data.get("season", "spring")

            # Restore world lore（剧本提示词）
            self.world_lore = state.get("world_lore", {})

            # Restore regions & locations
            for r in state.get("regions", []):
                self.world.add_region(self._deserialize_region(r))
                self.weather.add_region(r["id"])
            for loc in state.get("locations", []):
                self.world.add_location(self._deserialize_location(loc))

            # Restore characters
            for cid, c in state.get("characters", {}).items():
                self.world.add_character(cid, dict(c))

            # Restore NPCs（含属性/日程/关系/记忆）
            for npc_data in state.get("npcs", []):
                npc = self._deserialize_npc(npc_data)
                if npc:
                    self.tick_engine.register_npc(npc)
                    # 同步到 world.characters（若未在 characters 中）
                    if npc.id not in self.world.characters:
                        self.world.add_character(npc.id, {
                            "location_id": npc.location_id,
                            "name": npc.name, "type": "npc",
                            "health": 100, "max_health": 100,
                        })

            # Restore quests
            for q in state.get("quests", []):
                quest = self._deserialize_quest(q)
                if quest:
                    self.quest_gen.active_quests[quest.id] = quest

            # Restore story threads
            for t in state.get("story_threads", []):
                thread = self._deserialize_thread(t)
                if thread:
                    self.story_director.threads[thread.id] = thread

            # Restore global flags
            self.world.global_flags = state.get("global_flags", {})

            # Restore knowledge graph
            kg_data = state.get("knowledge", {})
            if kg_data:
                self.knowledge.from_dict(kg_data)

            logger.info("Game loaded from %s", path)
            return True
        except Exception as e:
            logger.error("Failed to load game: %s", e)
            return False

    # ── 序列化辅助 ──────────────────────────────────────────────

    @staticmethod
    def _serialize_region(r: WorldRegion) -> dict[str, Any]:
        return {
            "id": r.id, "name": r.name, "description": r.description,
            "region_type": r.region_type, "danger_level": r.danger_level,
            "locations": list(r.locations),
        }

    @staticmethod
    def _deserialize_region(data: dict[str, Any]) -> WorldRegion:
        return WorldRegion(
            id=data["id"], name=data.get("name", ""),
            description=data.get("description", ""),
            region_type=data.get("region_type", "settlement"),
            danger_level=data.get("danger_level", 0),
            locations=data.get("locations", []),
        )

    @staticmethod
    def _serialize_location(loc: WorldLocation) -> dict[str, Any]:
        return {
            "id": loc.id, "name": loc.name, "description": loc.description,
            "region_id": loc.region_id, "location_type": loc.location_type,
            "light_level": loc.light_level, "danger_level": loc.danger_level,
            "connected": list(loc.connected), "entities": list(loc.entities),
            "items": list(loc.items), "tags": list(loc.tags),
        }

    @staticmethod
    def _deserialize_location(data: dict[str, Any]) -> WorldLocation:
        return WorldLocation(
            id=data["id"], name=data.get("name", ""),
            description=data.get("description", ""),
            region_id=data.get("region_id", ""),
            location_type=data.get("location_type", "room"),
            light_level=data.get("light_level", 5),
            danger_level=data.get("danger_level", 0),
            connected=data.get("connected", []),
            entities=data.get("entities", []),
            items=data.get("items", []),
            tags=data.get("tags", []),
        )

    @staticmethod
    def _serialize_npc(npc: NPC) -> dict[str, Any]:
        from jag.world.npc import NPCState, ScheduleEntry
        return {
            "id": npc.id, "name": npc.name, "description": npc.description,
            "location_id": npc.location_id, "goal": npc.goal,
            "desires": list(npc.desires), "fears": list(npc.fears),
            "personality": npc.personality,
            "state": {
                "mood": npc.state.mood, "energy": npc.state.energy,
                "hunger": npc.state.hunger,
                "current_action": npc.state.current_action,
                "current_location_id": npc.state.current_location_id,
            },
            "relationships": dict(npc.relationships),
            "resources": dict(npc.resources),
            "inventory": list(npc.inventory),
            "schedule": [
                {"hour_start": s.hour_start, "hour_end": s.hour_end,
                 "activity": s.activity, "location_id": s.location_id}
                for s in npc.schedule
            ],
            "attributes": dict(npc.attributes),
            "memory": [
                {"content": m.content, "importance": m.importance, "turn": m.turn}
                for m in npc.memory.short_term.get_all()
            ],
        }

    @staticmethod
    def _deserialize_npc(data: dict[str, Any]) -> NPC | None:
        from jag.world.npc import NPC, NPCState, ScheduleEntry

        npc = NPC(
            id=data["id"], name=data.get("name", ""),
            description=data.get("description", ""),
            location_id=data.get("location_id", ""),
            goal=data.get("goal", ""),
            desires=data.get("desires", []),
            fears=data.get("fears", []),
            personality=data.get("personality", "neutral"),
            relationships=data.get("relationships", {}),
            resources=data.get("resources", {"gold": 10}),
            inventory=data.get("inventory", []),
            attributes=data.get("attributes", {}),
        )
        s = data.get("state", {})
        npc.state = NPCState(
            mood=s.get("mood", "neutral"), energy=s.get("energy", 1.0),
            hunger=s.get("hunger", 0.0), current_action=s.get("current_action", ""),
            current_location_id=s.get("current_location_id", npc.location_id),
        )
        npc.schedule = [
            ScheduleEntry(hour_start=sch["hour_start"], hour_end=sch["hour_end"],
                          activity=sch.get("activity", ""), location_id=sch.get("location_id", ""))
            for sch in data.get("schedule", [])
        ]
        for mem in data.get("memory", []):
            npc.memory.record(
                mem.get("content", ""), importance=mem.get("importance", 5),
                turn=mem.get("turn", 0),
            )
        return npc

    @staticmethod
    def _serialize_quest(q) -> dict[str, Any]:
        return {
            "id": q.id, "title": q.title, "description": q.description,
            "quest_type": q.quest_type, "status": q.status, "giver_id": q.giver_id,
            "objectives": [{"description": o.description, "completed": o.completed} for o in q.objectives],
            "rewards": dict(q.rewards), "source": q.source,
        }

    @staticmethod
    def _deserialize_quest(data: dict[str, Any]):
        from jag.world.quest import Quest, QuestObjective
        return Quest(
            id=data["id"], title=data.get("title", ""),
            description=data.get("description", ""),
            quest_type=data.get("quest_type", "side"),
            status=data.get("status", "available"),
            giver_id=data.get("giver_id", ""),
            objectives=[
                QuestObjective(description=o["description"], completed=o.get("completed", False))
                for o in data.get("objectives", [])
            ],
            rewards=data.get("rewards", {}),
            source=data.get("source", ""),
        )

    @staticmethod
    def _serialize_thread(t) -> dict[str, Any]:
        return {
            "id": t.id, "title": t.title, "description": t.description,
            "status": t.status, "events": list(t.events),
            "involved_entities": list(t.involved_entities),
            "turns_active": t.turns_active, "turns_since_event": t.turns_since_event,
        }

    @staticmethod
    def _deserialize_thread(data: dict[str, Any]):
        from jag.agents.story_director import StoryThread
        return StoryThread(
            id=data["id"], title=data.get("title", ""),
            description=data.get("description", ""),
            status=data.get("status", "active"),
            events=data.get("events", []),
            involved_entities=data.get("involved_entities", []),
            turns_active=data.get("turns_active", 0),
            turns_since_event=data.get("turns_since_event", 0),
        )
