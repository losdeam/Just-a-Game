"""Narrative generator: world state → immersive narrative text via LLM."""

from __future__ import annotations

import logging
from typing import Any

from jag.agents.llm import LLMProvider
from jag.core.perception import PerceptionFilter
from jag.world.tick import TickResult
from jag.world.world import WorldState

logger = logging.getLogger(__name__)


NARRATOR_SYSTEM_PROMPT = """你是一个沉浸式开放世界RPG的叙事者。
根据游戏事件生成生动、有氛围的叙事文本。
所有输出必须使用简体中文。

风格指南：
- 用第二人称（“你”）描述玩家行动
- 描述性但简洁（每段叙事2-4句）
- 包含感官细节（视觉、声音、气味）
- 保持一致的奇幻风格语调
- 不要打破第四面墙
- 自然地引用NPC名字和地名
- 展现而非叙述：描述结果而非陈述机制

涉及骰子检定时：
- 大成功：描述一次精湛的、令人印象深刻的行动
- 成功：描述一次熟练的、有效的行动
- 失败：描述出了什么问题，但保持趣味性
- 大失败：描述一次戏剧性的、令人难忘的失误
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
        parts.append(f"时间: {context['time']}，第{context['day']}天，{context['season']}")
        parts.append(f"地点: {context['location']['name']}（{context['location']['description']}）")

        if context["player_action"]:
            action = context["player_action"]
            parts.append(f"\nPlayer attempted: {action.get('type', 'act')} — \"{action.get('text', action.get('intent', ''))}\"")

        if context["dice_result"]:
            parts.append(f"骰子结果: {context['dice_result']['summary']}")

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
        parts.append(f"【{time_str}】你在{loc_name}。")

        # Player action
        action = context.get("player_action", {})
        if action:
            action_type = action.get("type", "")
            target = action.get("target", "")

            if action_type == "move":
                parts.append(f"你前往{target}。")
            elif action_type == "attack":
                parts.append(f"你攻击了{target}。")
            elif action_type == "interact":
                parts.append(f"你与{target}互动。")
            elif action_type == "speak":
                parts.append(f"你与{target}交谈。")
            elif action_type == "take":
                parts.append(f"你拾取了{target}。")
            elif action_type == "examine":
                parts.append(f"你仔细检查了{target}。")
            elif action_type == "rest":
                parts.append("你稍作休息。")
            else:
                parts.append(f"你执行了{action_type}。")

        # Dice result
        dice = context.get("dice_result")
        if dice:
            dice_result = dice.get("result", "")
            if dice_result == "critical_success":
                parts.append("一次不可思议的大成功！")
            elif dice_result == "success":
                parts.append("你的尝试成功了。")
            elif dice_result == "failure":
                parts.append("你的尝试失败了。")
            elif dice_result == "critical_failure":
                parts.append("一场灾难性的大失败！")

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
            parts.append(f"★ 新任务：{q['title']}")

        return " ".join(parts)
