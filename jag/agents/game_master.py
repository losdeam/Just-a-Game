"""GameMaster: central orchestrator holding all subsystem references."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from jag.agents.action_planner import ActionPlanner
from jag.agents.llm import LLMConfig, LLMFactory, LLMProvider
from jag.agents.narrative import GM_VOICE_PROMPT, NarrativeGenerator
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
        # 跑团本：挂载后即由 AI 主持人声线驱动整场跑团
        self.campaign: Any = None

    def set_campaign(self, campaign: Any) -> None:
        """挂载跑团本，并同步给叙述器切换为 AI 主持人声线。"""
        self.campaign = campaign
        self.narrator.set_campaign(campaign)

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
        # 清理上一份跑团本与主持人声线
        self.campaign = None
        self.narrator.set_campaign(None)

    # ── Game loop ────────────────────────────────────────────────

    async def generate_opening(self) -> str:
        """Generate an immersive opening narration for the player.

        挂载跑团本时，优先使用 AI 主持人开场独白。
        """
        player = self.world.characters.get(self.player_id, {})
        loc_id = player.get("location_id", "")
        location = self.world.locations.get(loc_id)

        # 跑团本模式：用主持人开场独白（必要时由 LLM 现场生成）
        if self.campaign is not None:
            camp = self.campaign
            if getattr(camp, "opening_scene", "") and self.narrator and self.narrator.llm:
                # 已有开场独白时直接采用，保证剧本一致性
                return camp.opening_scene
            if self.narrator and self.narrator.llm:
                try:
                    opening = await self._gm_opening(player, location)
                    if opening:
                        return opening
                except Exception:
                    pass

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

    async def _gm_opening(self, player: dict[str, Any], location: Any) -> str:
        """跑团本模式下，用主持人声线现场生成开场独白。"""
        assert self.narrator is not None and self.narrator.llm is not None
        camp = self.campaign
        loc_name = location.name if location else "未知之地"
        inv = player.get("inventory", [])
        prompt = (
            f"你是这桌单人跑团的主持人。请用第二人称「你」写一段开场独白（150-250字）。\n"
            f"跑团本：{camp.title}　概要：{camp.logline}\n"
            f"基调：{camp.tone}\n"
            f"世界设定：{camp.setting.get('description','')}\n"
            f"主线：{camp.setting.get('main_quest','')}\n"
            f"玩家：{camp.player_card.name}，{camp.player_card.description}\n"
            f"开场地点：{loc_name}（{location.description[:160] if location else ''}）\n"
            f"背包：{'、'.join(inv) if inv else '空'}\n\n"
            f"要求：含感官细节与悬念，结尾抛出一个开放式钩子引导玩家行动。"
        )
        opening = await self.narrator.llm.complete(
            prompt=prompt,
            system=GM_VOICE_PROMPT,
            max_tokens=500,
        )
        text = opening.strip() if opening else ""
        if text:
            camp.opening_scene = text
        return text

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
            "campaign_title": getattr(self.campaign, "title", "") if self.campaign else "",
            "campaign_logline": getattr(self.campaign, "logline", "") if self.campaign else "",
            "has_campaign": self.campaign is not None,
        }

    # ── Save/Load ────────────────────────────────────────────────

    def save_game(self, path: str = "savegame.json") -> None:
        """Save current game state to JSON."""
        state = {
            "world": self.world.snapshot(),
            "time": {
                "turn": self.world.time.turn,
                "hour": self.world.time.hour,
                "day": self.world.time.day,
                "season": self.world.time.season,
            },
            "characters": {
                cid: {
                    "location_id": c.get("location_id", ""),
                    "inventory": c.get("inventory", []),
                    "name": c.get("name", ""),
                }
                for cid, c in self.world.characters.items()
            },
            "global_flags": self.world.global_flags,
            "knowledge": self.knowledge.to_dict(),
            "campaign": self.campaign.to_dict() if self.campaign else None,
        }

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        logger.info("Game saved to %s", path)

    def load_game(self, path: str = "savegame.json") -> bool:
        """Load game state from JSON. Returns True on success."""
        p = Path(path)
        if not p.exists():
            logger.warning("Save file not found: %s", path)
            return False

        try:
            with open(p) as f:
                state = json.load(f)

            # Restore time
            time_data = state.get("time", {})
            self.world.time.turn = time_data.get("turn", 0)
            self.world.time.hour = time_data.get("hour", 8)
            self.world.time.day = time_data.get("day", 1)
            self.world.time.season = time_data.get("season", "spring")

            # Restore global flags
            self.world.global_flags = state.get("global_flags", {})

            # Restore knowledge graph
            kg_data = state.get("knowledge", {})
            if kg_data:
                self.knowledge.from_dict(kg_data)

            # Restore campaign book（若存档中有）
            camp_data = state.get("campaign")
            if camp_data:
                try:
                    from jag.campaign.book import CampaignBook
                    self.set_campaign(CampaignBook.from_dict(camp_data))
                except Exception as e:  # noqa: BLE001
                    logger.warning("恢复跑团本失败: %s", e)

            logger.info("Game loaded from %s", path)
            return True
        except Exception as e:
            logger.error("Failed to load game: %s", e)
            return False
