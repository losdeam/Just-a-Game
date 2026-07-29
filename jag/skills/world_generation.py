"""世界观生成 Skill。

根据用户选择的词条（tags）组合生成完整世界观，并将世界观设定
持久化保存至当前剧本（存档），作为后续导演 / 叙事 / NPC 生成的提示词。
"""

from __future__ import annotations

import logging
from typing import Any

from jag.skills.base import Skill, SkillContext, SkillResult
from jag.world.world_builder import WorldBuilder

logger = logging.getLogger(__name__)


class WorldGenerationSkill(Skill):
    """根据用户词条生成世界观，并持久化到剧本作为提示词。"""

    name = "world_generation"
    description = "根据用户选择的词条（类型/时代/氛围/地形/魔法/危险）生成世界观，持久化保存至当前剧本作为提示词"
    category = "generation"

    async def run(self, context: SkillContext) -> SkillResult:
        gm = context.gm
        params = context.params

        world_name: str = params.get("world_name", "")
        tags: dict[str, list[str]] = params.get("tags", {})
        description: str = params.get("description", "")
        use_llm: bool = params.get("use_llm", False)

        builder = WorldBuilder(gm)

        if use_llm:
            world = await builder.build_with_llm(world_name, tags, description)
        else:
            world = builder.build_from_tags(world_name, tags, description)

        # 将世界观设定固化为「剧本提示词」，供导演 / 叙事后续读取
        prompts = self._build_world_prompts(gm, world_name, tags, description)

        # 构建与原 WorldBuilder.build_from_tags 兼容的返回结构
        # 原结构包含 ok, world_name, locations, npcs, genre, description, tags_applied
        result_data = {
            "ok": True,
            "world_name": world.get("world_name", world_name),
            "locations": world.get("locations", len(gm.world.locations)),
            "npcs": world.get("npcs", len(gm.tick_engine._npcs)),
            "genre": world.get("genre", ""),
            "description": world.get("description", description),
            "tags_applied": world.get("tags_applied", tags),
            # 额外扩展：Skill 特有字段
            "world_lore": gm.world_lore,
            "prompts": prompts,
            "regions": len(gm.world.regions),
        }

        result = SkillResult(
            success=True,
            data=result_data,
            messages=[f"已生成世界观「{world_name or gm.world_lore.get('name', '未命名')}」"],
        )
        return result

    def persist(self, context: SkillContext, result: SkillResult) -> None:
        """将世界观（含提示词）持久化到当前剧本（存档 JSON）。"""
        gm = context.gm
        path = context.params.get("save_path", "savegame.json")
        try:
            gm.save_game(path)
            logger.info("世界观已持久化到剧本: %s", path)
            result.messages.append(f"世界观已保存到剧本 {path}，可作为后续生成提示词")
        except Exception as e:  # noqa: BLE001
            logger.error("持久化世界观失败: %s", e)
            result.messages.append(f"持久化失败: {e}")

    # ── 内部：构建剧本提示词 ─────────────────────────────────────

    def _build_world_prompts(
        self,
        gm: Any,
        world_name: str,
        tags: dict[str, list[str]],
        description: str,
    ) -> dict[str, Any]:
        """把世界设定整理为结构化提示词，存入 gm.world_lore 供导演/叙事读取。"""
        lore = gm.world_lore
        prompts: dict[str, Any] = {
            "world_name": world_name or lore.get("name", "未命名世界"),
            "description": description or lore.get("description", ""),
            "tags": tags,
            "genre": lore.get("genre", tags.get("genre", ["fantasy"])[0] if tags.get("genre") else "fantasy"),
            "era": lore.get("era", ""),
            "atmosphere": tags.get("atmosphere", []),
            "main_quest": lore.get("main_quest", ""),
            "regions": [
                {"id": r.id, "name": r.name, "description": r.description, "type": r.region_type}
                for r in gm.world.regions.values()
            ],
            "locations": [
                {
                    "id": loc.id, "name": loc.name, "description": loc.description,
                    "type": loc.location_type, "danger": loc.danger_level,
                }
                for loc in gm.world.locations.values()
            ],
        }
        # 写回 world_lore，使叙事/导演在后续 tick 中能读取作为提示上下文
        gm.world_lore.setdefault("prompts", prompts)
        return prompts
