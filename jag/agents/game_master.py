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
        )

        # Player state
        self.player_id = "player"
        self._player_memory = MemoryStore(self.player_id)

        # Game state
        self._running = False
        self._turn_count = 0

    def _init_llm(self) -> None:
        """Initialize LLM factory from config."""
        default_cfg = self.config.llm.default
        default_llm_config = LLMConfig(
            provider=default_cfg.provider,
            model=default_cfg.model,
            api_key=default_cfg.api_key,
            api_base=default_cfg.api_base,
            temperature=default_cfg.temperature,
            max_tokens=default_cfg.max_tokens,
        )
        module_configs = {}
        for name, mod_cfg in self.config.llm.modules.items():
            module_configs[name] = LLMConfig(
                provider=mod_cfg.provider,
                model=mod_cfg.model,
                api_key=mod_cfg.api_key,
                api_base=mod_cfg.api_base,
                temperature=mod_cfg.temperature,
                max_tokens=mod_cfg.max_tokens,
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
    ) -> None:
        """Set up the game world with regions, locations, NPCs, and player."""
        for region in regions or []:
            self.world.add_region(region)
            self.weather.add_region(region.id)

        for location in locations or []:
            self.world.add_location(location)

        for npc in npcs or []:
            self.world.add_character(npc.id, {
                "location_id": npc.location_id,
                "name": npc.name,
                "type": "npc",
            })
            self.tick_engine.register_npc(npc)

        # Add player
        if player_data:
            self.world.add_character(self.player_id, player_data)
        else:
            # Default: place player at first location
            first_loc = next(iter(self.world.locations), "")
            self.world.add_character(self.player_id, {
                "location_id": first_loc,
                "inventory": [],
                "name": "Player",
                "type": "player",
            })

    # ── Game loop ────────────────────────────────────────────────

    async def process_action(self, player_input: str) -> str:
        """Process a player action and return narrative text.

        Args:
            player_input: Natural language player input

        Returns:
            Narrative text describing the result
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

        return result.narrative or f"Turn {result.turn} complete."

    async def advance_world(self, turns: int = 1) -> list[str]:
        """Advance the world without player action.

        Returns list of narrative texts for each turn.
        """
        narratives = []
        for _ in range(turns):
            result = await self.tick_engine.tick(None)
            self._turn_count += 1
            if result.narrative:
                narratives.append(result.narrative)
            else:
                narratives.append(f"Time passes... (Turn {result.turn})")
        return narratives

    def get_status(self) -> dict[str, Any]:
        """Get current game status."""
        player = self.world.characters.get(self.player_id, {})
        loc_id = player.get("location_id", "")
        location = self.world.locations.get(loc_id)

        return {
            "turn": self.world.time.turn,
            "time": f"{self.world.time.hour:02d}:00 ({self.world.time.time_of_day()})",
            "day": self.world.time.day,
            "season": self.world.time.season,
            "location": location.name if location else "unknown",
            "location_description": location.description if location else "",
            "inventory": player.get("inventory", []),
            "active_threads": len(self.story_director.get_active_threads()),
            "active_quests": len(self.quest_gen.active_quests),
            "npc_count": len(self.tick_engine._npcs),
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

            logger.info("Game loaded from %s", path)
            return True
        except Exception as e:
            logger.error("Failed to load game: %s", e)
            return False
