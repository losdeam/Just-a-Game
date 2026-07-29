"""生成 Skill 包：世界观 / 导演 / 人物 / 地点 / 任务。

提供统一接口供动态调度::

    from jag.skills import SkillRegistry, SkillContext

    registry = SkillRegistry.instance()
    registry.register_defaults()
    result = await registry.execute(
        "world_generation",
        SkillContext(gm=gm, params={"world_name": "...", "tags": {...}}),
    )
"""

from jag.skills.base import Skill, SkillContext, SkillResult
from jag.skills.character_generation import CharacterGenerationSkill
from jag.skills.director import DirectorSkill
from jag.skills.location_generation import LocationGenerationSkill
from jag.skills.quest_generation import QuestGenerationSkill
from jag.skills.registry import SkillRegistry
from jag.skills.world_generation import WorldGenerationSkill

__all__ = [
    "Skill",
    "SkillContext",
    "SkillResult",
    "SkillRegistry",
    "WorldGenerationSkill",
    "DirectorSkill",
    "CharacterGenerationSkill",
    "LocationGenerationSkill",
    "QuestGenerationSkill",
]
