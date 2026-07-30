"""导演系统 Skill。

综合当前场景、人物、情况调度相关信息进行生成。
封装 StoryDirector + GameMaster 编排能力，支持两种调度模式：

1. ``mode="develop"``：根据当前世界状态生成故事发展（故事节拍/剧情线）。
2. ``mode="action"``：处理玩家动作，走完整 tick 管道并返回叙事 + 建议选项。
"""

from __future__ import annotations

import logging
from typing import Any

from jag.core.events import GameEvent
from jag.skills.base import Skill, SkillContext, SkillResult

logger = logging.getLogger(__name__)


class DirectorSkill(Skill):
    """综合场景/人物/情况调度信息进行生成的导演系统。"""

    name = "director"
    description = "综合当前场景、人物、情况调度相关信息进行生成（故事节拍 / 剧情线 / 叙事）"
    category = "orchestration"

    async def run(self, context: SkillContext) -> SkillResult:
        gm = context.gm
        params = context.params
        mode: str = params.get("mode", "develop")

        if mode == "action":
            return await self._run_action(gm, params)
        return await self._run_develop(gm, params)

    # ── 模式一：故事发展（节拍 / 剧情线）─────────────────────────

    async def _run_develop(self, gm: Any, params: dict[str, Any]) -> SkillResult:
        # 收集当前场景 / 人物 / 情况，构建事件输入
        events = self._collect_context_events(gm, params)
        beats = await gm.story_director.process(events, gm.world)
        threads = [
            {
                "id": t.id, "title": t.title, "description": t.description,
                "status": t.status, "involved_entities": t.involved_entities,
            }
            for t in gm.story_director.get_active_threads()
        ]
        return SkillResult(
            success=True,
            data={
                "story_beats": beats,
                "active_threads": threads,
                "scene": self._scene_summary(gm),
            },
            messages=[f"生成 {len(beats)} 个故事节拍，活跃剧情线 {len(threads)} 条"],
        )

    # ── 模式二：玩家动作 ────────────────────────────────────────

    async def _run_action(self, gm: Any, params: dict[str, Any]) -> SkillResult:
        player_input: str = params.get("action", "")
        narrative, options = await gm.process_action(player_input)
        return SkillResult(
            success=True,
            data={
                "narrative": narrative,
                "suggested_options": options,
                "status": gm.get_status(),
            },
            messages=[f"已处理动作「{player_input}」"],
        )

    # ── 上下文聚合 ───────────────────────────────────────────────

    def _collect_context_events(self, gm: Any, params: dict[str, Any]) -> list[GameEvent]:
        """聚合当前场景、人物、情况为 GameEvent 列表供导演处理。"""
        from jag.core.events import EventType, GameEvent

        def _to_event_type(value: str) -> EventType:
            """将字符串映射为 EventType 枚举，未知类型回退为 WORLD。"""
            try:
                return EventType(value)
            except ValueError:
                return EventType.WORLD

        events: list[GameEvent] = []
        # 显式传入的情况事件
        for ev in params.get("events", []):
            events.append(GameEvent(
                event_type=_to_event_type(ev.get("type", "world")),
                source_id=ev.get("source_id", ""),
                target_id=ev.get("target_id", ""),
                location_id=ev.get("location_id", ""),
                data=ev.get("data", {}),
            ))
        # 若无显式事件，根据玩家所在场景构造一个观察事件
        if not events:
            player = gm.world.characters.get(gm.player_id, {})
            loc_id = player.get("location_id", "")
            loc = gm.world.locations.get(loc_id)
            events.append(GameEvent(
                event_type=EventType.WORLD,
                source_id=gm.player_id,
                location_id=loc_id,
                data={"scene": loc.name if loc else "未知", "situation": params.get("situation", "")},
            ))
        return events

    def _scene_summary(self, gm: Any) -> dict[str, Any]:
        player = gm.world.characters.get(gm.player_id, {})
        loc_id = player.get("location_id", "")
        loc = gm.world.locations.get(loc_id)
        nearby = [
            {"id": cid, "name": c.get("name", cid)}
            for cid, c in gm.world.characters.items()
            if c.get("location_id") == loc_id and cid != gm.player_id
        ]
        return {
            "location": loc.name if loc else "未知",
            "location_description": loc.description if loc else "",
            "nearby_characters": nearby,
            "time": f"{gm.world.time.hour:02d}:00（{gm.world.time.time_of_day_display()}）",
            "season": gm.world.time.season_display(),
        }
