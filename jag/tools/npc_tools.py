"""Tools for solidifying NPC module changes."""

from __future__ import annotations

from typing import Any

from jag.modules.npc import NPCData

from .base import Tool, ToolParam, ToolResult


class AddNPCTool(Tool):
    name = "add_npc"
    description = "在世界中新增一个NPC，可放置在某地点。用于角色登场、召唤、生成怪物等。"
    params = [
        ToolParam("id", "str", "NPC唯一ID（英文）"),
        ToolParam("name", "str", "NPC名称（中文）"),
        ToolParam("description", "str", "NPC外貌/简介"),
        ToolParam("location_id", "str", "NPC所在地点ID", required=False, default=""),
        ToolParam("personality", "str", "性格", required=False, default="neutral",
                  enum=["friendly", "stern", "charming", "neutral", "mysterious", "aggressive"]),
        ToolParam("goal", "str", "NPC的目标", required=False, default=""),
        ToolParam("mood", "str", "初始心情", required=False, default="neutral",
                  enum=["happy", "sad", "angry", "fearful", "neutral"]),
        ToolParam("relationship", "int", "对玩家的初始好感度(-100到100)", required=False, default=0),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        npc_mod = game.modules["npc"]
        npc_id = args.get("id", "")
        if npc_id in npc_mod.npcs:
            return ToolResult(ok=False, message=f"NPC {npc_id} 已存在")
        npc = NPCData(
            id=npc_id,
            name=args.get("name", npc_id),
            description=args.get("description", ""),
            location_id=args.get("location_id", ""),
            personality=args.get("personality", "neutral"),
            goal=args.get("goal", ""),
            mood=args.get("mood", "neutral"),
            relationship=float(args.get("relationship", 0)),
        )
        npc_mod.add(npc)
        return ToolResult(ok=True, message=f"NPC {npc.name} 已登场")


class UpdateNPCTool(Tool):
    name = "update_npc"
    description = "更新NPC的状态（心情、状态文本、位置等）。"
    params = [
        ToolParam("npc_id", "str", "NPC的ID"),
        ToolParam("field", "str", "字段名", enum=["mood", "status", "location_id", "goal", "personality", "description"]),
        ToolParam("value", "str", "新值"),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        npc_mod = game.modules["npc"]
        npc = npc_mod.get(args.get("npc_id", ""))
        if not npc:
            return ToolResult(ok=False, message=f"NPC {args.get('npc_id')} 不存在")
        field_name = args.get("field", "")
        if hasattr(npc, field_name):
            setattr(npc, field_name, args.get("value", ""))
            return ToolResult(ok=True, message=f"{npc.name}[{field_name}]已更新")
        return ToolResult(ok=False, message=f"无效字段: {field_name}")


class UpdateRelationshipTool(Tool):
    name = "update_npc_relationship"
    description = "改变某NPC对玩家的好感度（如因帮助/冒犯）。delta为正负数。"
    params = [
        ToolParam("npc_id", "str", "NPC的ID"),
        ToolParam("delta", "int", "好感度变化量（正为提升，负为降低）"),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        npc_mod = game.modules["npc"]
        npc = npc_mod.get(args.get("npc_id", ""))
        if not npc:
            return ToolResult(ok=False, message=f"NPC {args.get('npc_id')} 不存在")
        try:
            delta = int(args.get("delta", 0))
        except ValueError:
            return ToolResult(ok=False, message="delta 需要数字")
        npc.relationship = max(-100, min(100, npc.relationship + delta))
        return ToolResult(ok=True, message=f"{npc.name} 对你好感度变化 {delta:+d}（现 {npc.relationship:.0f}）")


class RemoveNPCTool(Tool):
    name = "remove_npc"
    description = "让一个NPC离场（如死亡、离去）。从世界中移除。"
    params = [
        ToolParam("npc_id", "str", "NPC的ID"),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        npc_mod = game.modules["npc"]
        npc_id = args.get("npc_id", "")
        npc = npc_mod.get(npc_id)
        if not npc:
            return ToolResult(ok=False, message=f"NPC {npc_id} 不存在")
        del npc_mod.npcs[npc_id]
        return ToolResult(ok=True, message=f"{npc.name} 已离场")


NPC_TOOLS: list[Tool] = [
    AddNPCTool(),
    UpdateNPCTool(),
    UpdateRelationshipTool(),
    RemoveNPCTool(),
]
