"""任务生成 Skill。

封装 QuestGenerator，根据世界事件触发任务模板，或根据显式参数生成自定义任务。
"""

from __future__ import annotations

import logging
from typing import Any

from jag.skills.base import Skill, SkillContext, SkillResult
from jag.world.quest import Quest, QuestObjective, QuestTemplate

logger = logging.getLogger(__name__)


class QuestGenerationSkill(Skill):
    """根据世界事件或显式参数生成任务。"""

    name = "quest_generation"
    description = "根据世界事件触发任务模板，或根据标题/目标/奖励参数生成自定义任务"
    category = "generation"

    async def run(self, context: SkillContext) -> SkillResult:
        gm = context.gm
        params = context.params

        custom = params.get("custom_quest")
        if custom:
            return self._generate_custom(gm, custom)

        events = params.get("events", [])
        sim_events = self._normalize_events(events)
        new_quests = gm.quest_gen.check(gm.world, sim_events)

        return SkillResult(
            success=True,
            data={
                "new_quests": [self._quest_summary(q) for q in new_quests],
                "active_quests": [self._quest_summary(q) for q in gm.quest_gen.active_quests.values()],
                "count": len(new_quests),
            },
            messages=[f"生成 {len(new_quests)} 个新任务，当前活跃任务 {len(gm.quest_gen.active_quests)} 个"],
        )

    # ── 自定义任务 ───────────────────────────────────────────────

    def _generate_custom(self, gm: Any, spec: dict[str, Any]) -> SkillResult:
        import uuid

        quest = Quest(
            id=f"quest_custom_{uuid.uuid4().hex[:8]}",
            title=spec.get("title", "自定义任务"),
            description=spec.get("description", ""),
            quest_type=spec.get("quest_type", "side"),
            status="available",
            giver_id=spec.get("giver_id", ""),
            objectives=[QuestObjective(description=o) for o in spec.get("objectives", [])],
            rewards=spec.get("rewards", {}),
            source="custom",
        )
        gm.quest_gen.active_quests[quest.id] = quest
        return SkillResult(
            success=True,
            data={"new_quests": [self._quest_summary(quest)], "count": 1},
            messages=[f"已生成自定义任务「{quest.title}」"],
        )

    # ── 工具 ─────────────────────────────────────────────────────

    def _normalize_events(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        for ev in events:
            if isinstance(ev, dict):
                normalized.append(ev)
        return normalized

    def _quest_summary(self, q: Quest) -> dict[str, Any]:
        return {
            "id": q.id,
            "title": q.title,
            "description": q.description,
            "quest_type": q.quest_type,
            "status": q.status,
            "giver_id": q.giver_id,
            "objectives": [{"description": o.description, "completed": o.completed} for o in q.objectives],
            "rewards": q.rewards,
            "source": q.source,
        }
