"""Tools for solidifying Worldview module changes."""

from __future__ import annotations

from typing import Any

from jag.modules.worldview import Faction

from .base import Tool, ToolParam, ToolResult


class UpdateWorldviewTool(Tool):
    name = "update_worldview"
    description = "更新或补充世界观设定（如氛围、历史、主线任务等）。仅修改指定字段。"
    params = [
        ToolParam("field", "str", "要修改的字段名", enum=[
            "world_name", "genre", "era", "atmosphere", "terrain",
            "magic_level", "danger_level", "description", "history", "main_quest",
        ]),
        ToolParam("value", "str", "字段的新内容（历史/简介/主线等可追加式扩展）"),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        field_name = args.get("field")
        value = args.get("value", "")
        wv = game.modules["worldview"]
        if not hasattr(wv, field_name) or field_name.startswith("_"):
            return ToolResult(ok=False, message=f"无效的世界观字段: {field_name}")
        old = getattr(wv, field_name)
        # for long text fields, allow append-style enrichment when not empty
        long_text = {"description", "history", "main_quest", "atmosphere"}
        if field_name in long_text and old and value not in old:
            setattr(wv, field_name, f"{old} {value}")
        else:
            setattr(wv, field_name, value)
        return ToolResult(ok=True, message=f"世界观[{field_name}]已更新")


class AddFactionTool(Tool):
    name = "add_faction"
    description = "在世界中新增一个势力/阵营，并设定其立场。"
    params = [
        ToolParam("name", "str", "势力名称"),
        ToolParam("description", "str", "势力简介", required=False, default=""),
        ToolParam("relationship", "str", "与玩家/主角势力的关系", required=False, default="neutral",
                  enum=["ally", "neutral", "hostile"]),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        wv = game.modules["worldview"]
        name = args.get("name", "")
        if any(f.name == name for f in wv.factions):
            return ToolResult(ok=False, message=f"势力 {name} 已存在")
        wv.factions.append(Faction(
            name=name,
            description=args.get("description", ""),
            relationship=args.get("relationship", "neutral"),
        ))
        return ToolResult(ok=True, message=f"势力 {name} 已加入世界")


WORLDVIEW_TOOLS: list[Tool] = [UpdateWorldviewTool(), AddFactionTool()]
