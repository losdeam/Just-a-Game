"""人物生成 Skill。

封装 DynamicNPCGenerator，根据类型/角色/性格生成 NPC，
并注册到当前世界的指定地点。
"""

from __future__ import annotations

import logging
from typing import Any

from jag.skills.base import Skill, SkillContext, SkillResult
from jag.world.dynamic_npc_generator import DynamicNPCGenerator
from jag.world.npc import NPC, ScheduleEntry

logger = logging.getLogger(__name__)


class CharacterGenerationSkill(Skill):
    """生成人物（NPC），可选批量与关系网络。"""

    name = "character_generation"
    description = "生成人物（NPC），支持指定角色/性格/地点，可批量生成并建立关系网络"
    category = "generation"

    async def run(self, context: SkillContext) -> SkillResult:
        gm = context.gm
        params = context.params

        count: int = int(params.get("count", 1))
        genre: str = params.get("genre", gm.world_lore.get("genre", "fantasy"))
        seed = params.get("seed")
        location_ids = params.get("location_ids") or self._default_locations(gm)
        role_ids = params.get("role_ids")

        generator = DynamicNPCGenerator(genre=genre, seed=seed)
        generated = generator.generate_batch(count, location_ids, role_ids=role_ids)

        # 注册到 GameMaster 世界与 tick 引擎
        registered: list[dict[str, Any]] = []
        for g in generated:
            npc = g.npc
            self._register_npc(gm, npc)
            registered.append(self._npc_summary(g.npc, g.traits, g.role, g.age))

        return SkillResult(
            success=True,
            data={
                "npcs": registered,
                "count": len(registered),
                "relationships": self._relationship_summary(generated),
            },
            messages=[f"已生成 {len(registered)} 个 NPC 并注册到世界"],
        )

    # ── 注册 ─────────────────────────────────────────────────────

    def _register_npc(self, gm: Any, npc: NPC) -> None:
        gm.world.add_character(npc.id, {
            "location_id": npc.location_id,
            "name": npc.name,
            "type": "npc",
            "health": 100,
            "max_health": 100,
            "hostile": False,
            "mood": npc.state.mood,
        })
        gm.tick_engine.register_npc(npc)

    # ── 摘要 ─────────────────────────────────────────────────────

    def _npc_summary(self, npc: NPC, traits: list[dict], role: dict, age: int) -> dict[str, Any]:
        return {
            "id": npc.id,
            "name": npc.name,
            "description": npc.description,
            "role": role.get("name", ""),
            "age": age,
            "traits": [t["name"] for t in traits],
            "goal": npc.goal,
            "personality": npc.personality,
            "location_id": npc.location_id,
            "attributes": npc.attributes,
            "resources": npc.resources,
        }

    def _relationship_summary(self, generated: list) -> list[dict[str, Any]]:
        rels: list[dict[str, Any]] = []
        for g in generated:
            for target, value in g.npc.relationships.items():
                rels.append({"from": g.npc.id, "to": target, "value": value})
        return rels

    def _default_locations(self, gm: Any) -> list[str]:
        locs = list(gm.world.locations.keys())
        return locs if locs else ["hub"]
