"""Tools for solidifying Location module changes."""

from __future__ import annotations

from typing import Any

from jag.modules.location import LocationData, RegionData

from .base import Tool, ToolParam, ToolResult


class AddLocationTool(Tool):
    name = "add_location"
    description = "在世界中新增一个地点，并可选地连接到玩家当前位置或指定地点。"
    params = [
        ToolParam("id", "str", "地点唯一ID（英文，如 dark_cave）"),
        ToolParam("name", "str", "地点名称（中文）"),
        ToolParam("description", "str", "地点描述"),
        ToolParam("location_type", "str", "地点类型", required=False, default="outdoor",
                  enum=["room", "building", "outdoor", "dungeon"]),
        ToolParam("light_level", "int", "光照等级 0-10", required=False, default=5),
        ToolParam("danger_level", "int", "危险等级 0-10", required=False, default=0),
        ToolParam("connect_to", "str", "要连接到的已有地点ID（通常为当前位置）", required=False, default=""),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        loc_mod = game.modules["location"]
        loc_id = args.get("id", "")
        if not loc_id:
            return ToolResult(ok=False, message="地点ID不能为空")
        if loc_id in loc_mod.locations:
            return ToolResult(ok=False, message=f"地点 {loc_id} 已存在")
        loc = LocationData(
            id=loc_id,
            name=args.get("name", loc_id),
            description=args.get("description", ""),
            location_type=args.get("location_type", "outdoor"),
            light_level=int(args.get("light_level", 5)),
            danger_level=int(args.get("danger_level", 0)),
        )
        loc_mod.add_location(loc)
        connect_to = args.get("connect_to", "")
        if connect_to:
            loc_mod.connect(loc_id, connect_to)
        return ToolResult(ok=True, message=f"地点 {loc.name} 已建立" + (f"，并连接到 {connect_to}" if connect_to else ""))


class MovePlayerTool(Tool):
    name = "move_player"
    description = "将玩家移动到另一个已连接/可达的地点。用于玩家移动、传送等。"
    params = [
        ToolParam("location_id", "str", "目标地点ID"),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        loc_mod = game.modules["location"]
        ss = game.modules["self_state"]
        target_id = args.get("location_id", "")
        target = loc_mod.get(target_id)
        if not target:
            return ToolResult(ok=False, message=f"地点 {target_id} 不存在")
        old = ss.current_location_id
        ss.current_location_id = target_id
        return ToolResult(ok=True, message=f"玩家从 {old or '原地'} 移动到 {target.name}")


class UpdateLocationTool(Tool):
    name = "update_location"
    description = "更新某地点的描述或属性（如改变危险度、补充描述）。"
    params = [
        ToolParam("location_id", "str", "地点ID"),
        ToolParam("field", "str", "字段名", enum=["name", "description", "location_type", "light_level", "danger_level"]),
        ToolParam("value", "str", "新值（数值字段传字符串数字）"),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        loc_mod = game.modules["location"]
        loc = loc_mod.get(args.get("location_id", ""))
        if not loc:
            return ToolResult(ok=False, message=f"地点 {args.get('location_id')} 不存在")
        field_name = args.get("field", "")
        value = args.get("value", "")
        if field_name in ("light_level", "danger_level"):
            try:
                setattr(loc, field_name, max(0, min(10, int(value))))
            except ValueError:
                return ToolResult(ok=False, message=f"{field_name} 需要数字")
        elif hasattr(loc, field_name):
            setattr(loc, field_name, value)
        else:
            return ToolResult(ok=False, message=f"无效字段: {field_name}")
        return ToolResult(ok=True, message=f"地点 {loc.name}[{field_name}]已更新")


class ConnectLocationsTool(Tool):
    name = "connect_locations"
    description = "在两个已存在的地点之间建立双向连接。"
    params = [
        ToolParam("a", "str", "地点A的ID"),
        ToolParam("b", "str", "地点B的ID"),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        loc_mod = game.modules["location"]
        a, b = args.get("a", ""), args.get("b", "")
        if not loc_mod.get(a) or not loc_mod.get(b):
            return ToolResult(ok=False, message="其中一个地点不存在")
        loc_mod.connect(a, b)
        return ToolResult(ok=True, message=f"{a} 与 {b} 已建立连接")


LOCATION_TOOLS: list[Tool] = [
    AddLocationTool(),
    MovePlayerTool(),
    UpdateLocationTool(),
    ConnectLocationsTool(),
]
