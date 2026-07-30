"""Tools for solidifying Inventory module changes."""

from __future__ import annotations

from typing import Any

from jag.modules.inventory import ItemData

from .base import Tool, ToolParam, ToolResult


class AddItemTool(Tool):
    name = "add_item"
    description = "给玩家背包添加物品（拾取、获得战利品、购买等）。"
    params = [
        ToolParam("id", "str", "物品ID（英文，如 iron_sword）"),
        ToolParam("name", "str", "物品名称（中文）"),
        ToolParam("description", "str", "物品描述", required=False, default=""),
        ToolParam("quantity", "int", "数量", required=False, default=1),
        ToolParam("item_type", "str", "物品类型", required=False, default="misc",
                  enum=["weapon", "armor", "consumable", "misc", "quest"]),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        inv = game.modules["inventory"]
        item = ItemData(
            id=args.get("id", ""),
            name=args.get("name", ""),
            description=args.get("description", ""),
            quantity=int(args.get("quantity", 1)),
            item_type=args.get("item_type", "misc"),
        )
        inv.add(item)
        return ToolResult(ok=True, message=f"获得物品: {item.name}")


class RemoveItemTool(Tool):
    name = "remove_item"
    description = "从玩家背包移除物品（使用、消耗、丢弃、出售等）。"
    params = [
        ToolParam("item_id", "str", "物品ID"),
        ToolParam("quantity", "int", "数量", required=False, default=1),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        inv = game.modules["inventory"]
        item_id = args.get("item_id", "")
        qty = int(args.get("quantity", 1))
        if not inv.remove(item_id, qty):
            return ToolResult(ok=False, message=f"背包中没有 {item_id} 或数量不足")
        return ToolResult(ok=True, message=f"失去物品: {item_id} x{qty}")


class EquipItemTool(Tool):
    name = "equip_item"
    description = "装备一件武器或防具（同类型会自动替换）。"
    params = [
        ToolParam("item_id", "str", "物品ID"),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        inv = game.modules["inventory"]
        item_id = args.get("item_id", "")
        if not inv.equip(item_id):
            return ToolResult(ok=False, message=f"无法装备 {item_id}（不存在或非装备）")
        return ToolResult(ok=True, message=f"已装备: {item_id}")


class UpdateGoldTool(Tool):
    name = "update_gold"
    description = "改变玩家金币（收入为正，支出为负）。不能为负。"
    params = [
        ToolParam("delta", "int", "金币变化量"),
    ]

    def execute(self, args: dict[str, Any], game) -> ToolResult:
        inv = game.modules["inventory"]
        try:
            delta = int(args.get("delta", 0))
        except ValueError:
            return ToolResult(ok=False, message="delta 需要数字")
        if inv.gold + delta < 0:
            return ToolResult(ok=False, message=f"金币不足（现有 {inv.gold}）")
        inv.gold += delta
        return ToolResult(ok=True, message=f"金币变化 {delta:+d}（现 {inv.gold}）")


INVENTORY_TOOLS: list[Tool] = [
    AddItemTool(),
    RemoveItemTool(),
    EquipItemTool(),
    UpdateGoldTool(),
]
