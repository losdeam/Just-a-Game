"""NPC agent: autonomous behavior with Observe→Think→Plan→Act cycle."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from jag.agents.llm import LLMProvider
from jag.world.npc import NPC
from jag.world.world import WorldState

logger = logging.getLogger(__name__)


class NPCActionModel(BaseModel):
    """Structured NPC action decision from LLM."""

    action_type: str = Field(default="idle", description="Action: move, interact, work, rest, trade, patrol, socialize, flee, idle")
    target: str = Field(default="", description="Target entity or location ID")
    reason: str = Field(default="", description="Why the NPC chose this action")
    dialogue: str = Field(default="", description="Optional dialogue if NPC speaks")
    params: dict[str, Any] = Field(default_factory=dict, description="Additional parameters")


NPC_SYSTEM_PROMPT = """You are controlling an NPC in an open-world RPG.
Given the NPC's personality, current state, and observations of the world,
decide what the NPC should do this turn.

NPC behaviors should be:
- Consistent with their personality and goals
- Reactive to their environment (time of day, weather, nearby entities)
- Following their schedule when appropriate
- Self-preserving (eat when hungry, rest when tired)

Available actions:
- move: go to a different location
- interact: interact with an object or entity
- work: perform job/duty
- rest: rest to recover energy
- trade: buy or sell goods
- patrol: walk around guard duty
- socialize: talk to nearby NPCs
- flee: run from danger
- idle: do nothing

Respond with the most appropriate action.
"""


@dataclass
class NPCObservation:
    """NPC's observation of the world."""

    location_id: str = ""
    location_name: str = ""
    time_of_day: str = ""
    hour: int = 0
    nearby_characters: list[str] = None  # type: ignore
    nearby_items: list[str] = None  # type: ignore
    energy: float = 1.0
    hunger: float = 0.0
    mood: str = "neutral"
    schedule_activity: str = ""
    schedule_location: str = ""

    def __post_init__(self) -> None:
        if self.nearby_characters is None:
            self.nearby_characters = []
        if self.nearby_items is None:
            self.nearby_items = []


class NPCAgent:
    """NPC autonomous behavior agent.

    Uses Observe→Think→Plan→Act cycle.
    Falls back to rule-based behavior when LLM is unavailable.
    """

    def __init__(self, llm: LLMProvider | None = None, use_llm: bool = True) -> None:
        self.llm = llm
        self.use_llm = use_llm and llm is not None

    async def decide(
        self, npc: NPC, world: WorldState, observation: dict[str, Any]
    ) -> dict[str, Any]:
        """Decide NPC action for one tick.

        Returns action dict compatible with TickEngine._apply_npc_action().
        """
        obs = self._build_observation(npc, observation)

        # Think: update internal state
        self._think(npc, obs)

        if self.use_llm:
            try:
                return await self._llm_decide(npc, obs)
            except Exception as e:
                logger.warning("NPC %s LLM decision failed: %s, using rules", npc.id, e)

        return self._rule_decide(npc, obs)

    def _build_observation(self, npc: NPC, obs_data: dict[str, Any]) -> NPCObservation:
        """Build structured observation from raw data."""
        loc_data = obs_data.get("location", {})
        schedule = obs_data.get("schedule", {})
        self_state = obs_data.get("self_state", {})

        return NPCObservation(
            location_id=self_state.get("location", npc.location_id),
            location_name=loc_data.get("name", "") if isinstance(loc_data, dict) else "",
            time_of_day=obs_data.get("time", ""),
            hour=obs_data.get("hour", 0),
            nearby_characters=obs_data.get("nearby_characters", []),
            nearby_items=obs_data.get("nearby_items", []),
            energy=self_state.get("energy", npc.state.energy),
            hunger=self_state.get("hunger", npc.state.hunger),
            mood=self_state.get("mood", npc.state.mood),
            schedule_activity=schedule.get("activity", ""),
            schedule_location=schedule.get("location", ""),
        )

    def _think(self, npc: NPC, obs: NPCObservation) -> None:
        """Update NPC internal state based on observations."""
        # Mood adjustment based on conditions
        if obs.energy < 0.2:
            npc.state.mood = "sad"
        elif obs.hunger > 0.8:
            npc.state.mood = "sad"
        elif obs.energy > 0.7 and obs.hunger < 0.3:
            npc.state.mood = "happy"

        # Check for threats (nearby characters with negative relationships)
        for char_id in obs.nearby_characters:
            rel = npc.relationships.get(char_id, 0)
            if rel < -50:
                npc.state.mood = "fearful"
                break

    async def _llm_decide(self, npc: NPC, obs: NPCObservation) -> dict[str, Any]:
        """Use LLM to decide NPC action."""
        assert self.llm is not None

        prompt = (
            f"NPC: {npc.name}\n"
            f"Personality: {npc.personality}\n"
            f"Goal: {npc.goal}\n"
            f"Desires: {', '.join(npc.desires)}\n"
            f"Fears: {', '.join(npc.fears)}\n"
            f"\nCurrent State:\n"
            f"  Mood: {obs.mood}, Energy: {obs.energy:.1f}, Hunger: {obs.hunger:.1f}\n"
            f"  Location: {obs.location_name} ({obs.location_id})\n"
            f"  Time: {obs.time_of_day} (hour {obs.hour})\n"
            f"  Nearby: {', '.join(obs.nearby_characters) or 'nobody'}\n"
            f"  Items: {', '.join(obs.nearby_items) or 'nothing'}\n"
        )
        if obs.schedule_activity:
            prompt += f"  Schedule: {obs.schedule_activity} at {obs.schedule_location}\n"

        prompt += "\nDecide what this NPC should do this turn."

        decision = await self.llm.structured(
            prompt=prompt,
            response_model=NPCActionModel,
            system=NPC_SYSTEM_PROMPT,
        )

        action = {
            "type": decision.action_type,
            "target": decision.target,
            "description": decision.reason or f"{npc.name} {decision.action_type}s",
            "params": decision.params,
        }
        if decision.dialogue:
            action["dialogue"] = decision.dialogue
            action["description"] += f' — "{decision.dialogue}"'

        return action

    def _rule_decide(self, npc: NPC, obs: NPCObservation) -> dict[str, Any]:
        """Rule-based NPC decision making (fallback)."""
        # Priority 1: Self-preservation
        if obs.energy < 0.15:
            return {
                "type": "rest",
                "target": obs.location_id,
                "description": f"{npc.name} is exhausted and rests",
            }

        if obs.hunger > 0.85:
            return {
                "type": "interact",
                "target": "food",
                "description": f"{npc.name} looks for food",
            }

        # Priority 2: Fear response
        if obs.mood == "fearful":
            return {
                "type": "flee",
                "target": "",
                "description": f"{npc.name} tries to flee from danger",
            }

        # Priority 3: Schedule adherence
        if obs.schedule_activity and obs.schedule_location:
            if obs.location_id != obs.schedule_location:
                return {
                    "type": "move",
                    "target": obs.schedule_location,
                    "description": f"{npc.name} heads to {obs.schedule_location} for {obs.schedule_activity}",
                }
            return {
                "type": "work",
                "target": obs.schedule_location,
                "description": f"{npc.name} is {obs.schedule_activity}",
            }

        # Priority 4: Social behavior
        if obs.nearby_characters and npc.personality in ("friendly", "social"):
            target = obs.nearby_characters[0]
            return {
                "type": "socialize",
                "target": target,
                "description": f"{npc.name} chats with {target}",
            }

        # Default: idle
        return {
            "type": "idle",
            "target": "",
            "description": f"{npc.name} looks around",
        }
