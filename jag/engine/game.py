"""The Game coordinator: the central facade replacing GameMaster.

The new architecture is deliberately simple:

    Player input
        │
        ▼
    ┌─────────┐   module prompts (dynamic)   ┌──────────┐
    │  Game   │ ───────────────────────────▶ │ Director │
    │ (coord) │ ◀───── DirectorDecision ──── │  (LLM)   │
    └────┬────┘                               └──────────┘
         │ executes tool_calls
         ▼
    ┌─────────────────────────────────────┐
    │ modules: worldview/location/npc/     │
    │          self_state/inventory        │
    └─────────────────────────────────────┘

- The five modules are the single source of truth for all state.
- The Director conceives plot and emits tool calls; tools mutate modules.
- There is no tick pipeline: one player action → one Director decision →
  tool solidification → time advance → narrative. World simulation that used to
  live in tick steps (weather/economy/faction) is now folded into the Director's
  judgment, which can advance time and change modules via tools as the plot
  demands. This keeps the whole flow prompt-driven and transparent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jag.config import GameConfig, load_config
from jag.director import Director, tool_results_of
from jag.llm import LLMFactory, LLMProvider, build_factory
from jag.modules import (
    InventoryModule,
    LocationModule,
    NPCModule,
    SelfStateModule,
    WorldviewModule,
)
from jag.tools import ToolRegistry, build_default_registry


class Game:
    """Central coordinator: holds modules, the Director, and orchestration logic."""

    def __init__(self, config: GameConfig | None = None) -> None:
        self.config: GameConfig = config or load_config()
        self._factory: LLMFactory = build_factory(self.config)

        # The five information modules
        self.modules: dict[str, Any] = {
            "worldview": WorldviewModule(),
            "location": LocationModule(),
            "npc": NPCModule(),
            "self_state": SelfStateModule(),
            "inventory": InventoryModule(),
        }

        # Tools + Director
        self.tool_registry: ToolRegistry = build_default_registry()
        self.director: Director = Director(self._get_llm(), self.tool_registry)

        # Narrative history (input + outcome)
        self.history: list[dict[str, Any]] = []

    # ── LLM access ──────────────────────────────────────────────────────

    def _get_llm(self, module: str = "default") -> LLMProvider:
        return self._factory.get(module)

    @property
    def llm(self) -> LLMProvider:
        return self._factory.get("default")

    def reinit_llm(self) -> None:
        """Rebuild LLM providers after a config change."""
        self._factory = build_factory(self.config)
        self.director.llm = self._factory.get("default")

    # ── Module accessors (convenience) ──────────────────────────────────

    @property
    def worldview(self) -> WorldviewModule:
        return self.modules["worldview"]

    @property
    def location(self) -> LocationModule:
        return self.modules["location"]

    @property
    def npc(self) -> NPCModule:
        return self.modules["npc"]

    @property
    def self_state(self) -> SelfStateModule:
        return self.modules["self_state"]

    @property
    def inventory(self) -> InventoryModule:
        return self.modules["inventory"]

    # ── World lifecycle ─────────────────────────────────────────────────

    def has_world(self) -> bool:
        return not self.worldview.is_empty()

    def clear_world(self) -> None:
        # Rebuild fresh empty modules so all state is reset cleanly.
        self.modules = {
            "worldview": WorldviewModule(),
            "location": LocationModule(),
            "npc": NPCModule(),
            "self_state": SelfStateModule(),
            "inventory": InventoryModule(),
        }
        self.history.clear()
        self._last_options = []

    # ── Core gameplay ───────────────────────────────────────────────────

    async def generate_opening(self) -> str:
        """Have the Director narrate the opening and return the text."""
        narrative, options = await self.director.generate_opening(self)
        self._last_options = options
        return narrative

    async def process_action(self, player_input: str) -> dict[str, Any]:
        """Process a player action. Returns a result dict with narrative + status.

        Flow: Director conceives → tools solidify → time advances → narrate.
        """
        decision = await self.director.process_action(player_input, self)
        tool_results = tool_results_of(decision)

        # Advance time by 1 turn per action (the Director may also advance_time)
        self.self_state.advance_time(1)

        # Record history
        self.history.append({
            "turn": self.self_state.turn,
            "input": player_input,
            "narrative": decision.narrative,
            "tool_results": tool_results,
        })
        self._last_options = decision.suggested_options

        return {
            "narrative": decision.narrative,
            "thoughts": decision.thoughts,
            "tool_results": tool_results,
            "status": self.get_status(),
            "suggested_options": self.get_suggested_options(),
        }

    async def advance_world(self, turns: int = 1) -> dict[str, Any]:
        """Advance time without an explicit player action (a 'wait')."""
        narratives: list[str] = []
        ss = self.self_state
        for _ in range(max(1, turns)):
            ss.advance_time(1)
            loc = self.location.get(ss.current_location_id)
            loc_name = loc.name if loc else "某处"
            narratives.append(
                f"时间流逝。你静待片刻，此时已是第{ss.day}天 {ss.time_display()}，"
                f"你仍在{loc_name}。"
            )
        self._last_options = ["继续等待", "环顾四周", "采取行动"]
        return {
            "narratives": narratives,
            "status": self.get_status(),
            "suggested_options": self.get_suggested_options(),
        }

    def get_suggested_options(self) -> list[dict[str, Any]]:
        """Return the last suggested options as UI-friendly dicts."""
        opts = getattr(self, "_last_options", []) or []
        return [{"label": o, "risk": "low"} for o in opts]

    # ── Status for UI ───────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        ss = self.self_state
        loc = self.location.get(ss.current_location_id)
        nearby = [n.name for n in self.npc.at_location(ss.current_location_id)]
        inv_names = [it.name for it in self.inventory.items]
        return {
            "turn": ss.turn,
            "time": ss.time_display(),
            "day": ss.day,
            "season": ss.season,
            "location": loc.name if loc else "未知",
            "location_description": loc.description if loc else "",
            "inventory": inv_names,
            "health": ss.health,
            "max_health": ss.max_health,
            "equipment": [it.name for it in self.inventory.items if it.equipped],
            "nearby_npcs": [n.id for n in self.npc.at_location(ss.current_location_id)],
            "nearby_entities": nearby,
            "active_threads": 0,
            "active_quests": 0,
        }

    def get_locations_view(self) -> list[dict[str, Any]]:
        """Locations list for the /api/locations UI endpoint."""
        out = []
        for l in self.location.locations.values():
            out.append({
                "id": l.id,
                "name": l.name,
                "type": l.location_type,
                "description": l.description,
                "connected": list(l.connected),
                "entities": [n.name for n in self.npc.at_location(l.id)],
                "items": [],
                "light_level": l.light_level,
                "danger_level": l.danger_level,
            })
        return out

    def get_npcs_view(self) -> list[dict[str, Any]]:
        """NPCs list for the /api/npcs UI endpoint."""
        return [
            {
                "id": n.id,
                "name": n.name,
                "description": n.description,
                "mood": n.mood,
                "energy": n.energy,
                "location_id": n.location_id,
                "personality": n.personality,
                "relationship": n.relationship,
            }
            for n in self.npc.npcs.values()
        ]

    def get_inventory_view(self) -> dict[str, Any]:
        return {
            "items": [
                {
                    "id": it.id, "name": it.name, "description": it.description,
                    "quantity": it.quantity, "item_type": it.item_type, "equipped": it.equipped,
                }
                for it in self.inventory.items
            ],
            "gold": self.inventory.gold,
        }

    def get_lore_view(self) -> dict[str, Any]:
        """Lore for the /api/lore UI endpoint (mirrors frontend expectations)."""
        wv = self.worldview
        npcs = [
            {"name": n.name, "role": n.goal or n.personality,
             "location": (self.location.get(n.location_id).name if self.location.get(n.location_id) else n.location_id)}
            for n in self.npc.npcs.values()
        ]
        locs = [
            {"name": l.name, "danger": l.danger_level, "description": l.description}
            for l in self.location.locations.values()
        ]
        return {
            "world_name": wv.world_name,
            "genre": wv.genre,
            "era": wv.era,
            "atmosphere": wv.atmosphere,
            "terrain": wv.terrain,
            "magic_level": wv.magic_level,
            "danger_level": wv.danger_level,
            "description": wv.description,
            "history": wv.history,
            "main_quest": wv.main_quest,
            "npcs": npcs,
            "locations": locs,
        }

    # ── Persistence (JSON snapshot of all modules) ──────────────────────

    def save_game(self, path: str = "savegame.json") -> None:
        data = {
            "version": 2,
            "config": self.config.model_dump(),
            "modules": {name: m.snapshot() for name, m in self.modules.items()},
            "history": self.history,
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_game(self, path: str = "savegame.json") -> bool:
        p = Path(path)
        if not p.exists():
            return False
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False
        modules_data = data.get("modules", {})
        for name, m in self.modules.items():
            if name in modules_data:
                m.restore(modules_data[name])
        self.history = data.get("history", [])
        self._last_options = []
        return True


def create_game(config: GameConfig | None = None) -> Game:
    """Convenience factory."""
    return Game(config)
