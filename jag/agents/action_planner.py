"""Action planner: natural language → structured ActionPlan via LLM."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from jag.agents.llm import LLMProvider
from jag.world.world import WorldState

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class ActionPlanModel(BaseModel):
    """Structured action plan output from LLM."""

    action_type: str = Field(default="interact", description="Action type: move, attack, interact, use, take, drop, examine, rest, craft, speak")
    target: str = Field(default="", description="Target entity or location ID")
    intent: str = Field(default="", description="Player's intent in natural language")
    risk: RiskLevel = Field(default=RiskLevel.LOW, description="Risk level of the action")
    estimated_effects: list[str] = Field(default_factory=list, description="Expected effects of the action")
    attribute: str = Field(default="", description="Primary attribute used (STR, DEX, CON, INT, WIS, CHA)")
    dc: int = Field(default=10, description="Difficulty class for the action check")
    params: dict[str, Any] = Field(default_factory=dict, description="Additional action parameters")


# Attribute name mapping
ATTRIBUTE_MAP = {
    "strength": "STR", "str": "STR",
    "dexterity": "DEX", "dex": "DEX",
    "constitution": "CON", "con": "CON",
    "intelligence": "INT", "int": "INT",
    "wisdom": "WIS", "wis": "WIS",
    "charisma": "CHA", "cha": "CHA",
}

# DC suggestions per risk level
DC_BY_RISK = {
    RiskLevel.LOW: 8,
    RiskLevel.MEDIUM: 12,
    RiskLevel.HIGH: 16,
    RiskLevel.EXTREME: 20,
}


PLANNER_SYSTEM_PROMPT = """You are an action planner for an open-world RPG game.
Given a player's natural language input and the current world context,
parse the action into a structured plan.

Available action types:
- move: travel to a location
- attack: attack an entity
- interact: interact with an entity or object
- use: use an item
- take: pick up an item
- drop: drop an item
- examine: examine something closely
- rest: rest to recover
- craft: create something from materials
- speak: talk to an NPC

Attributes: STR, DEX, CON, INT, WIS, CHA
Set DC based on difficulty: easy=8, medium=12, hard=16, extreme=20

Be reasonable about risk and DC assignment.
If the action is purely social or passive, risk should be LOW with DC 8.
If the action involves danger or complexity, increase risk and DC accordingly.
"""


def build_world_context(player_id: str, world: WorldState) -> str:
    """Build a world context string for the LLM prompt."""
    player = world.characters.get(player_id, {})
    loc_id = player.get("location_id", "")
    location = world.locations.get(loc_id)

    parts = [f"Time: {world.time.time_of_day()} (hour {world.time.hour}), Day {world.time.day}, {world.time.season}"]

    if location:
        parts.append(f"Location: {location.name} ({location.location_type})")
        parts.append(f"  Description: {location.description}")
        nearby = [e for e in location.entities if e != player_id]
        if nearby:
            parts.append(f"  Nearby: {', '.join(nearby)}")
        items = location.items
        if items:
            parts.append(f"  Items here: {', '.join(items)}")

    inventory = player.get("inventory", [])
    if inventory:
        parts.append(f"Inventory: {', '.join(inventory)}")

    return "\n".join(parts)


class ActionPlanner:
    """Parse natural language player input into structured action plans."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def plan(
        self, action_text: str, player_id: str, world: WorldState
    ) -> dict[str, Any]:
        """Plan an action from natural language input.

        Returns a dict compatible with TickEngine.tick() player_action parameter.
        """
        world_context = build_world_context(player_id, world)

        prompt = (
            f"World Context:\n{world_context}\n\n"
            f"Player says: \"{action_text}\"\n\n"
            f"Parse this into a structured action plan."
        )

        try:
            plan = await self.llm.structured(
                prompt=prompt,
                response_model=ActionPlanModel,
                system=PLANNER_SYSTEM_PROMPT,
            )
            return self._to_action_dict(plan, player_id, action_text)
        except Exception as e:
            logger.warning("LLM action planning failed: %s, using fallback", e)
            return self._fallback_plan(action_text, player_id)

    def _to_action_dict(
        self, plan: ActionPlanModel, player_id: str, original_text: str
    ) -> dict[str, Any]:
        """Convert ActionPlanModel to action dict for TickEngine."""
        attribute_mod = 0
        attr_name = ATTRIBUTE_MAP.get(plan.attribute.lower(), "")
        if attr_name:
            # Will be resolved by dice step; pass the attribute name
            pass

        return {
            "type": plan.action_type,
            "target": plan.target,
            "player_id": player_id,
            "text": original_text,
            "intent": plan.intent,
            "risk": plan.risk.value if isinstance(plan.risk, RiskLevel) else str(plan.risk),
            "dc": plan.dc,
            "attribute": attr_name,
            "attribute_mod": attribute_mod,
            "estimated_effects": plan.estimated_effects,
            "params": plan.params,
        }

    def _fallback_plan(self, action_text: str, player_id: str) -> dict[str, Any]:
        """Generate a fallback action plan when LLM fails.

        Uses keyword matching to determine action type.
        """
        text = action_text.lower()

        # Keyword-based action detection
        keywords = {
            "move": ["go", "walk", "travel", "run", "head", "move"],
            "attack": ["attack", "fight", "hit", "strike", "kill", "slash"],
            "take": ["take", "grab", "pick", "loot", "steal"],
            "drop": ["drop", "discard", "throw"],
            "use": ["use", "drink", "eat", "equip", "apply"],
            "examine": ["examine", "look", "inspect", "search", "investigate"],
            "speak": ["talk", "speak", "ask", "tell", "greet"],
            "rest": ["rest", "sleep", "camp", "nap"],
            "craft": ["craft", "make", "build", "forge"],
            "interact": ["interact", "open", "close", "pull", "push", "touch"],
        }

        detected_type = "interact"
        for action_type, words in keywords.items():
            if any(w in text for w in words):
                detected_type = action_type
                break

        return {
            "type": detected_type,
            "target": "",
            "player_id": player_id,
            "text": action_text,
            "intent": action_text,
            "risk": "low",
            "dc": 10,
            "attribute": "",
            "attribute_mod": 0,
            "estimated_effects": [],
            "params": {},
        }
