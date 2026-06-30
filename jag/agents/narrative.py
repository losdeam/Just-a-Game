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
- 用第二人称（"你"）描述玩家行动
- 描述性但简洁（每段叙事2-4句）
- 包含感官细节（视觉、声音、气味）
- 保持一致的奇幻风格语调
- 不要打破第四面墙
- 自然地引用NPC名字和地名
- 展现而非叙述：描述结果而非陈述机制
- 只有当玩家主动与NPC互动或NPC做出值得注意的行动时，才描述NPC
- 不要仅仅因为NPC存在就描述他们

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

        # Only include NPC actions at the player's location
        visible_npc_actions = []
        for npc_act in result.npc_actions:
            if npc_act.get("location_id") == loc_id:
                visible_npc_actions.append(npc_act)

        context: dict[str, Any] = {
            "time": f"{world.time.time_of_day()} (hour {world.time.hour})",
            "day": world.time.day,
            "season": world.time.season,
            "location": {
                "name": location.name if location else "unknown",
                "type": location.location_type if location else "room",
                "description": (location.description[:200] + "...") if location and len(location.description) > 200 else (location.description if location else ""),
                "light_level": location.light_level if location else 5,
            },
            "player_action": result.player_action,
            "dice_result": {
                "total": result.dice_result.total,
                "result": result.dice_result.result.value,
                "summary": result.dice_result.summary(),
            } if result.dice_result else None,
            "npc_actions": visible_npc_actions[:5],
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

        loc_name = context["location"]["name"]
        if loc_name == "unknown":
            loc_name = "此地"
        time_str = context["time"]

        action = context.get("player_action", {})
        if action:
            action_type = action.get("type", "")
            target = action.get("target", "")
            action_text = action.get("text", "")

            if action_type == "move" and target:
                loc = None
                if hasattr(result, 'world'):
                    loc = result.world.locations.get(target)
                if not loc:
                    loc_name = target
                else:
                    loc_name = loc.name if hasattr(loc, 'name') else target
                parts.append(f"你动身前往{loc_name}。")
            elif action_type == "speak":
                npc_name = ""
                npc_desc = ""
                if target and result:
                    if isinstance(result, object) and hasattr(result, 'npc_actions'):
                        for na in result.npc_actions:
                            if na.get("npc_id") == target:
                                npc_name = na.get("npc_name", "")
                                npc_desc = na.get("description", "")
                                break
                if not npc_name:
                    npc_name = target or "附近的人"
                parts.append(f"你走向{npc_name}，开始与对方交谈。")
                
                if not npc_desc:
                    import random
                    dialogues = [
                        f"{npc_name}抬起头，微笑着说：'你好，旅行者。有什么我可以帮你的吗？'",
                        f"{npc_name}看了你一眼：'哦，是外地人啊。这镇子最近可不太平。'",
                        f"'欢迎来到这里。'{npc_name}说道，'你是来做生意的，还是来冒险的？'",
                        f"{npc_name}放下手中的活计：'今天天气真不错，对吧？'",
                        f"'小心点，朋友。'{npc_name}压低声音，'最近夜里有奇怪的声音。'",
                    ]
                    parts.append(random.choice(dialogues))
                else:
                    parts.append(npc_desc)
            elif action_type == "interact" and target:
                npc_data = None
                if hasattr(result, 'world'):
                    npc_data = result.world.characters.get(target, {})
                if npc_data and npc_data.get('name'):
                    parts.append(f"你与{npc_data['name']}进行了互动。")
                else:
                    parts.append(f"你试着与{target}互动。")
            elif action_type == "attack" and target:
                parts.append(f"你向{target}发起攻击！")
            elif action_type == "rest":
                parts.append("你稍作休息，恢复体力。")
            elif action_type == "examine":
                if target:
                    parts.append(f"你仔细检查{target}。")
                else:
                    parts.append("你仔细观察周围的环境。")
            elif target:
                action_desc = {
                    "take": "拾取",
                    "drop": "丢弃",
                    "use": "使用",
                    "craft": "制作",
                }.get(action_type, action_type or "行动")
                parts.append(f"你尝试{action_desc}{target}。")
            elif action_text:
                parts.append(f"你尝试{action_text}。")
        else:
            parts.append(f"【{time_str}】你在{loc_name}。")

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

        for npc_act in context.get("npc_actions", [])[:3]:
            desc = npc_act.get("description", "")
            if desc:
                parts.append(desc)

        for evt in context.get("world_events", [])[:2]:
            desc = evt.get("description", "")
            if desc and "{" not in desc:
                parts.append(desc)

        for q in context.get("new_quests", []):
            parts.append(f"★ 新任务：{q['title']}")

        return " ".join(parts)
