"""地点生成 Skill。

复用 WorldBuilder 的地点组合逻辑，根据地形 / 魔法 / 氛围等词条生成地点，
并接入当前世界状态（含连通图与区域归属）。
"""

from __future__ import annotations

import logging
from typing import Any

from jag.skills.base import Skill, SkillContext, SkillResult
from jag.world.world import WorldLocation

logger = logging.getLogger(__name__)


class LocationGenerationSkill(Skill):
    """根据地形/魔法/氛围等词条生成地点，接入当前世界。"""

    name = "location_generation"
    description = "根据地形、魔法等级、氛围等词条生成地点，构建连通图并接入当前世界"
    category = "generation"

    async def run(self, context: SkillContext) -> SkillResult:
        gm = context.gm
        params = context.params

        terrain: list[str] = params.get("terrain", [])
        magic: str = params.get("magic", "medium")
        region_id: str = params.get("region_id", "main_region")
        atmosphere: list[str] = params.get("atmosphere", [])

        # 借用 WorldBuilder 的预制地点池生成
        from jag.world.world_builder import _TERRAIN_LOCS, _MAGIC_LOCS, _ATMO_MOD, _ERA_INFO

        era = params.get("era", "medieval")
        era_info = _ERA_INFO.get(era, _ERA_INFO["medieval"])
        atmo_light = sum(_ATMO_MOD.get(a, {}).get("light_mod", 0) for a in atmosphere)
        atmo_danger = sum(_ATMO_MOD.get(a, {}).get("danger_mod", 0) for a in atmosphere)
        danger_base = params.get("danger_base", 0)

        created: list[WorldLocation] = []
        for t in terrain or ["forest"]:
            for loc in _TERRAIN_LOCS.get(t, []):
                created.append(self._make_location(loc, region_id, era_info, atmo_light, atmo_danger, danger_base))

        for loc in _MAGIC_LOCS.get(magic, []):
            created.append(self._make_location(loc, region_id, era_info, atmo_light, atmo_danger, danger_base))

        # 注册到世界
        for loc in created:
            if loc.id not in gm.world.locations:
                gm.world.add_location(loc)

        # 构建连通图：链式 + 相邻
        self._connect(created)

        return SkillResult(
            success=True,
            data={
                "locations": [
                    {
                        "id": loc.id, "name": loc.name, "description": loc.description,
                        "type": loc.location_type, "light": loc.light_level,
                        "danger": loc.danger_level, "connected": loc.connected,
                    }
                    for loc in created
                ],
                "count": len(created),
            },
            messages=[f"已生成 {len(created)} 个地点并接入区域 {region_id}"],
        )

    # ── 内部 ─────────────────────────────────────────────────────

    def _make_location(
        self, loc_def: dict[str, Any], region_id: str,
        era_info: dict, atmo_light: int, atmo_danger: int, danger_base: int,
    ) -> WorldLocation:
        light = max(1, min(10, loc_def["light"] + era_info.get("light_mod", 0) + atmo_light))
        danger = max(0, min(10, loc_def["danger"] + danger_base + atmo_danger))
        return WorldLocation(
            id=loc_def["id"], name=loc_def["name"], description=loc_def["desc"],
            region_id=region_id, location_type=loc_def["type"],
            light_level=light, danger_level=danger,
        )

    def _connect(self, locations: list[WorldLocation]) -> None:
        if len(locations) < 2:
            return
        for i, loc in enumerate(locations):
            if i > 0:
                prev = locations[i - 1].id
                if prev not in loc.connected:
                    loc.connected.append(prev)
                if loc.id not in locations[i - 1].connected:
                    locations[i - 1].connected.append(loc.id)
