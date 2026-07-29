"""Skill 注册表：支持按名称动态调度各生成 Skill。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from jag.skills.base import Skill, SkillContext, SkillResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SkillRegistry:
    """全局 Skill 注册表（单例）。

    用法::

        registry = SkillRegistry.instance()
        registry.register_defaults()
        result = await registry.execute("world_generation", context)
    """

    _instance: "SkillRegistry | None" = None

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    @classmethod
    def instance(cls) -> "SkillRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── 注册 / 查询 ────────────────────────────────────────────

    def register(self, skill: Skill) -> None:
        """注册一个 Skill 实例。"""
        if not skill.name:
            raise ValueError("Skill 必须有 name 属性")
        self._skills[skill.name] = skill
        logger.debug("已注册 skill: %s", skill.name)

    def unregister(self, name: str) -> None:
        self._skills.pop(name, None)

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_skills(self) -> list[dict[str, str]]:
        """返回所有已注册 skill 的摘要，便于调度方选择。"""
        return [
            {"name": s.name, "description": s.description, "category": s.category}
            for s in self._skills.values()
        ]

    def has(self, name: str) -> bool:
        return name in self._skills

    # ── 执行 ────────────────────────────────────────────────────

    async def execute(self, name: str, context: SkillContext) -> SkillResult:
        """按名称动态调度执行一个 skill。

        Args:
            name: skill 名称。
            context: 执行上下文。

        Returns:
            SkillResult；若 skill 不存在则返回失败结果。
        """
        skill = self._skills.get(name)
        if skill is None:
            logger.warning("未注册的 skill: %s", name)
            return SkillResult(success=False, error=f"未注册的 skill: {name}")
        try:
            result = await skill.run(context)
            # 执行成功后自动调用持久化钩子
            if result.success:
                skill.persist(context, result)
            return result
        except Exception as e:  # noqa: BLE001 - 调度层需吞掉异常
            logger.exception("skill %s 执行失败", name)
            return SkillResult(success=False, error=str(e))

    # ── 默认 skill 集合 ──────────────────────────────────────────

    def register_defaults(self) -> None:
        """注册框架内置的 5 个生成 skill。"""
        from jag.skills.world_generation import WorldGenerationSkill
        from jag.skills.director import DirectorSkill
        from jag.skills.character_generation import CharacterGenerationSkill
        from jag.skills.location_generation import LocationGenerationSkill
        from jag.skills.quest_generation import QuestGenerationSkill

        for skill_cls in (
            WorldGenerationSkill,
            DirectorSkill,
            CharacterGenerationSkill,
            LocationGenerationSkill,
            QuestGenerationSkill,
        ):
            inst = skill_cls()
            if not self.has(inst.name):
                self.register(inst)
