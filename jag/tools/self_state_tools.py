"""Tools for solidifying SelfState module changes."""

from __future__ import annotations

from typing import Any

from jag.modules.self_state import StatusEffect

from .base import Tool, ToolParam, ToolResult


class UpdateHealthTool(Tool):
    name = "update_health"
    description = "改变玩家生命值（伤害为负，治疗为正）。会自动限制在0与上限之间。"
    params = [
        ToolParam("delta", "int", "生命值变化量"),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        ss = game.modules["self_state"]
        try:
            delta = int(args.get("delta", 0))
        except ValueError:
            return ToolResult(ok=False, message="delta 需要数字")
        ss.health = max(0, min(ss.max_health, ss.health + delta))
        return ToolResult(ok=True, message=f"玩家生命变化 {delta:+d}（现 {ss.health}/{ss.max_health}）")


class SetStatusEffectTool(Tool):
    name = "add_status_effect"
    description = "给玩家添加一个状态效果（如中毒、祝福、受伤）。"
    params = [
        ToolParam("name", "str", "效果名称"),
        ToolParam("description", "str", "效果描述", required=False, default=""),
        ToolParam("duration", "int", "持续回合数（0表示持续到被移除）", required=False, default=0),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        ss = game.modules["self_state"]
        name = args.get("name", "")
        if any(e.name == name for e in ss.status_effects):
            return ToolResult(ok=False, message=f"状态效果 {name} 已存在")
        ss.status_effects.append(StatusEffect(
            name=name,
            description=args.get("description", ""),
            duration=int(args.get("duration", 0)),
        ))
        return ToolResult(ok=True, message=f"玩家获得状态: {name}")


class RemoveStatusEffectTool(Tool):
    name = "remove_status_effect"
    description = "移除玩家身上的一个状态效果。"
    params = [
        ToolParam("name", "str", "效果名称"),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        ss = game.modules["self_state"]
        name = args.get("name", "")
        before = len(ss.status_effects)
        ss.status_effects = [e for e in ss.status_effects if e.name != name]
        if len(ss.status_effects) == before:
            return ToolResult(ok=False, message=f"未找到状态效果: {name}")
        return ToolResult(ok=True, message=f"状态效果 {name} 已移除")


class AdvanceTimeTool(Tool):
    name = "advance_time"
    description = "推进游戏时间若干小时（用于休息、长途旅行、等待等）。1小时=1回合。"
    params = [
        ToolParam("hours", "int", "推进的小时数", required=False, default=1),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        ss = game.modules["self_state"]
        try:
            hours = max(1, int(args.get("hours", 1)))
        except ValueError:
            hours = 1
        ss.advance_time(hours)
        return ToolResult(ok=True, message=f"时间推进 {hours} 小时（现 第{ss.day}天 {ss.time_display()}）")


SELF_STATE_TOOLS: list[Tool] = [
    UpdateHealthTool(),
    SetStatusEffectTool(),
    RemoveStatusEffectTool(),
    AdvanceTimeTool(),
]
