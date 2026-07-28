"""Narrative generator: world state → immersive narrative text via LLM.

当挂载了跑团本（CampaignBook）时，叙述者切换为「AI 主持人（Game Master）」声线：
以桌跑团 GM 的口吻演绎场景、扮演 NPC、点名检定，并把角色卡与知识书
（关键词触发的世界设定）注入上下文，保证设定一致又不撑爆上下文。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from jag.agents.llm import LLMProvider
from jag.core.perception import PerceptionFilter
from jag.world.tick import TickResult
from jag.world.world import WorldState

if TYPE_CHECKING:
    from jag.campaign.book import CampaignBook

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


GM_VOICE_PROMPT = """你是这桌单人跑团的主持人（Game Master / DM）。你同时是世界、所有 NPC 与命运的代言人。
所有输出使用简体中文，以第二人称「你」称呼玩家。

你的职责（参考 SillyTavern 的角色扮演与环世界的故事讲述者）：
1. 场景演绎：用电影感、带感官细节的笔触描述玩家所处的场景与行动结果，展现而非陈述。
2. 扮演 NPC：当玩家与 NPC 互动时，以该 NPC 的性格与目标即兴说出他们的台词与反应，用「」包裹对白。
3. 点名检定：当玩家行动存在风险或悬念时，明确宣布需要何种检定（属性 + DC），例如「请进行一次【力量 DC12】检定」。
   若本回合已给出骰子结果，则依据结果演绎成功/失败/大成功/大失败。
4. 推进剧情：抓住伏笔与剧情线，在合适时机抛出钩子、制造张力，但把选择权交给玩家。
5. 设定一致：严格遵循下方「跑团本设定」「角色卡」「知识书」中的世界规则，不要凭空捏造与之冲突的设定。

风格：
- 简洁有力，单次回应 120-260 字，不堆砌形容词。
- 不打破第四面墙，不提及「系统/模型/骰子代码」等机制词。
- 只有在玩家与 NPC 互动、或 NPC 有值得注意的行动时才让 NPC 出场。
"""


class NarrativeGenerator:
    """Generate immersive narrative text from tick results.

    Features:
    - LLM-powered narrative generation
    - Perception filtering (only narrate what the player can perceive)
    - Style consistency via system prompt
    - Fallback to template-based narration
    - 跑团本（CampaignBook）模式下切换为 AI 主持人声线
    """

    def __init__(
        self,
        llm: LLMProvider | None = None,
        perception_filter: PerceptionFilter | None = None,
    ) -> None:
        self.llm = llm
        self.perception_filter = perception_filter
        # 跑团本：挂载后即以 AI 主持人声线演绎
        self.campaign: CampaignBook | None = None

    def set_campaign(self, campaign: CampaignBook | None) -> None:
        self.campaign = campaign

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
                if self.campaign is not None:
                    narrative = await self._gm_narrate(context, tick_result)
                else:
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

    async def _gm_narrate(
        self, context: dict[str, Any], result: TickResult
    ) -> str:
        """AI 主持人声线：注入跑团本设定 / 角色卡 / 知识书后演绎场景。"""
        assert self.llm is not None and self.campaign is not None
        camp = self.campaign

        # 关键词触发：用玩家行动 + 地点名匹配知识书条目
        action = context.get("player_action", {}) or {}
        trigger_text = " ".join(filter(None, [
            action.get("text", ""),
            action.get("target", ""),
            action.get("intent", ""),
            context["location"]["name"],
        ]))
        lore_hits = camp.lookup_lorebook(trigger_text)

        # 现场角色卡：玩家 + 同地点 NPC
        loc_name = context["location"]["name"]
        npc_cards = [c for c in camp.npc_cards if c.location == action.get("target") or c.location == loc_name or c.name in trigger_text]
        if not npc_cards:
            npc_cards = camp.npc_cards[:3]

        parts: list[str] = []
        parts.append("【跑团本设定】")
        parts.append(f"名称：{camp.title}　基调：{camp.tone}")
        parts.append(f"概要：{camp.logline}")
        parts.append(f"世界设定：{camp.setting.get('description','')}")
        if camp.setting.get("main_quest"):
            parts.append(f"主线：{camp.setting['main_quest']}")
        if camp.ruleset:
            parts.append(f"规则：{camp.ruleset}")
        if camp.plot_threads:
            active = [t for t in camp.plot_threads if t.status == "active"]
            if active:
                parts.append("剧情线：" + "；".join(f"{t.title}（{t.description}）" for t in active[:3]))

        parts.append("\n【角色卡】")
        parts.append(f"玩家：{camp.player_card.name}（{camp.player_card.role}）— {camp.player_card.description} 性格：{camp.player_card.personality}。")
        for c in npc_cards[:4]:
            parts.append(f"NPC：{c.name}（{c.role}）— {c.description} 性格：{c.personality}，目标：{c.goals}。")

        if lore_hits:
            parts.append("\n【知识书（命中）】")
            for e in lore_hits:
                parts.append(f"- {e.content}")

        parts.append("\n【本回合事件】")
        parts.append(f"时间: {context['time']}，第{context['day']}天，{context['season']}")
        parts.append(f"地点: {context['location']['name']}（{context['location']['description']}）")
        if action:
            parts.append(f"玩家行动: {action.get('type','act')} — 「{action.get('text', action.get('intent',''))}」")
        if context["dice_result"]:
            d = context["dice_result"]
            parts.append(f"骰子: {d['summary']}（{d['result']}）")
        if context["npc_actions"]:
            parts.append("NPC 行动:")
            for na in context["npc_actions"]:
                parts.append(f"  - {na.get('description','')}")
        if context["world_events"]:
            parts.append("世界事件:")
            for evt in context["world_events"]:
                parts.append(f"  - {evt['description']}")
        if context["story_beats"]:
            parts.append("剧情发展:")
            for beat in context["story_beats"]:
                parts.append(f"  - {beat.get('description','')}")
        if context["new_quests"]:
            parts.append("新任务:")
            for q in context["new_quests"]:
                parts.append(f"  - {q['title']}：{q['description']}")

        parts.append("\n请以主持人身份演绎本回合（120-260字）。若玩家行动有风险而本回合尚无骰子结果，请点名要求检定。")
        prompt = "\n".join(parts)
        narrative = await self.llm.complete(
            prompt=prompt,
            system=GM_VOICE_PROMPT,
            max_tokens=500,
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
