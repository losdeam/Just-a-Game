"""Narrative generator: world state → immersive narrative text via LLM."""

from __future__ import annotations

import logging
from typing import Any

from jag.agents.llm import LLMProvider
from jag.core.perception import PerceptionFilter
from jag.world.tick import TickResult
from jag.world.world import WorldState

logger = logging.getLogger(__name__)


NARRATOR_SYSTEM_PROMPT = """You are a narrator for an immersive open-world RPG.
Generate vivid, atmospheric narrative text based on game events.

Style guidelines:
- Use second person ("You") for player actions
- Be descriptive but concise (2-4 sentences per narrative)
- Include sensory details (sights, sounds, smells)
- Maintain a consistent fantasy tone
- Don't break the fourth wall
- Reference NPC names and locations naturally
- Show don't tell: describe outcomes rather than stating mechanics

When dice rolls are involved:
- Critical success: Describe a masterful, impressive action
- Success: Describe a competent, effective action
- Failure: Describe what went wrong, but keep it interesting
- Critical failure: Describe a dramatic, memorable mishap
"""


class NarrativeGenerator:
    """Generate immersive narrative text from tick results.

    Features:
    - LLM-powered narrative generation
    - Perception filtering (only narrate what the player can perceive)
    - Style consistency via system prompt
    - Fallback to template-based narration
    """

    def __init__(
        self,
        llm: LLMProvider | None = None,
        perception_filter: PerceptionFilter | None = None,
    ) -> None:
        self.llm = llm
        self.perception_filter = perception_filter

    async def narrate(self, tick_result: TickResult, world: WorldState) -> str:
        """Generate narrative text for a tick result.

        Args:
            tick_result: The result of a game tick
            world: Current world state

        Returns:
            Narrative text string
        """
        context = self._build_narrative_context(tick_result, world)

        if self.llm:
            try:
                narrative = await self._llm_narrate(context, tick_result)
                return narrative
            except Exception as e:
                logger.warning("LLM narration failed: %s, using fallback", e)

        return self._fallback_narrate(context, tick_result)

    def _build_narrative_context(
        self, result: TickResult, world: WorldState
    ) -> dict[str, Any]:
        """Build context for narrative generation."""
        player_id = result.player_action.get("player_id", "player")
        player = world.characters.get(player_id, {})
        loc_id = player.get("location_id", "")
        location = world.locations.get(loc_id)

        # Gather visible events (filtered by perception if available)
        visible_events = []
        for event in result.world_events:
            # If event is at player's location, always visible
            if event.location_id == loc_id or not event.location_id:
                visible_events.append(event)

        context: dict[str, Any] = {
            "time": f"{world.time.time_of_day()} (hour {world.time.hour})",
            "day": world.time.day,
            "season": world.time.season,
            "location": {
                "name": location.name if location else "unknown",
                "type": location.location_type if location else "room",
                "description": location.description if location else "",
                "light_level": location.light_level if location else 5,
            },
            "player_action": result.player_action,
            "dice_result": {
                "total": result.dice_result.total,
                "result": result.dice_result.result.value,
                "summary": result.dice_result.summary(),
            } if result.dice_result else None,
            "npc_actions": result.npc_actions[:5],
            "world_events": [
                {"description": e.description, "type": e.event_type.value}
                for e in visible_events[:5]
            ],
            "new_quests": [
                {"title": q.title, "description": q.description}
                for q in result.new_quests[:3]
            ],
            "story_beats": result.story_beats[:3],
        }
        return context

    async def _llm_narrate(
        self, context: dict[str, Any], result: TickResult
    ) -> str:
        """Generate narrative via LLM."""
        assert self.llm is not None

        parts = []
        parts.append(f"Time: {context['time']}, Day {context['day']}, {context['season']}")
        parts.append(f"Location: {context['location']['name']} ({context['location']['description']})")

        if context["player_action"]:
            action = context["player_action"]
            parts.append(f"\nPlayer attempted: {action.get('type', 'act')} — \"{action.get('text', action.get('intent', ''))}\"")

        if context["dice_result"]:
            parts.append(f"Dice result: {context['dice_result']['summary']}")

        if context["npc_actions"]:
            parts.append("\nNPC actions:")
            for npc_act in context["npc_actions"]:
                parts.append(f"  - {npc_act.get('description', '')}")

        if context["world_events"]:
            parts.append("\nWorld events:")
            for evt in context["world_events"]:
                parts.append(f"  - {evt['description']}")

        if context["new_quests"]:
            parts.append("\nNew quests available:")
            for q in context["new_quests"]:
                parts.append(f"  - {q['title']}: {q['description']}")

        if context["story_beats"]:
            parts.append("\nStory developments:")
            for beat in context["story_beats"]:
                parts.append(f"  - {beat.get('description', '')}")

        prompt = "\n".join(parts)
        narrative = await self.llm.complete(
            prompt=prompt,
            system=NARRATOR_SYSTEM_PROMPT,
            max_tokens=300,
        )

        return narrative.strip() if narrative else self._fallback_narrate(context, result)

    def _fallback_narrate(
        self, context: dict[str, Any], result: TickResult
    ) -> str:
        """Template-based fallback narration."""
        parts = []

        # Time and location
        loc_name = context["location"]["name"]
        time_str = context["time"]
        parts.append(f"[{time_str}] You are at {loc_name}.")

        # Player action
        action = context.get("player_action", {})
        if action:
            action_type = action.get("type", "")
            target = action.get("target", "")

            if action_type == "move":
                parts.append(f"You travel to {target}.")
            elif action_type == "attack":
                parts.append(f"You attack {target}.")
            elif action_type == "interact":
                parts.append(f"You interact with {target}.")
            elif action_type == "speak":
                parts.append(f"You speak to {target}.")
            elif action_type == "take":
                parts.append(f"You pick up {target}.")
            elif action_type == "examine":
                parts.append(f"You examine {target} closely.")
            elif action_type == "rest":
                parts.append("You take a moment to rest.")
            else:
                parts.append(f"You {action_type}.")

        # Dice result
        dice = context.get("dice_result")
        if dice:
            dice_result = dice.get("result", "")
            if dice_result == "critical_success":
                parts.append("An incredible success!")
            elif dice_result == "success":
                parts.append("Your attempt succeeds.")
            elif dice_result == "failure":
                parts.append("Your attempt fails.")
            elif dice_result == "critical_failure":
                parts.append("A disastrous failure!")

        # NPC actions
        for npc_act in context.get("npc_actions", [])[:3]:
            desc = npc_act.get("description", "")
            if desc:
                parts.append(desc)

        # World events
        for evt in context.get("world_events", [])[:3]:
            desc = evt.get("description", "")
            if desc:
                parts.append(desc)

        # Quests
        for q in context.get("new_quests", []):
            parts.append(f"★ New quest: {q['title']}")

        return " ".join(parts)
