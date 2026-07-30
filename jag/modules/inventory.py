"""Inventory module: the player's possessions.

Holds items (with quantity/type/equipped flag) and gold. The prompt lists what
the player carries so the Director can reference and consume items naturally.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import ModuleBase


@dataclass
class ItemData:
    id: str
    name: str
    description: str = ""
    quantity: int = 1
    item_type: str = "misc"  # weapon/armor/consumable/misc/quest/...
    equipped: bool = False

    def display(self) -> str:
        suffix = ""
        if self.quantity > 1:
            suffix = f" x{self.quantity}"
        flag = " [已装备]" if self.equipped else ""
        return f"{self.name}{suffix}{flag}"


class InventoryModule(ModuleBase):
    name = "inventory"

    def __init__(self) -> None:
        self.items: list[ItemData] = []
        self.gold: int = 0

    def is_empty(self) -> bool:
        return not self.items and self.gold == 0

    def add(self, item: ItemData) -> None:
        # stack if same id
        existing = next((i for i in self.items if i.id == item.id), None)
        if existing and item.item_type != "weapon" and item.item_type != "armor":
            existing.quantity += item.quantity
        else:
            self.items.append(item)

    def remove(self, item_id: str, quantity: int = 1) -> bool:
        item = next((i for i in self.items if i.id == item_id), None)
        if not item or item.quantity < quantity:
            return False
        item.quantity -= quantity
        if item.quantity <= 0:
            self.items.remove(item)
        return True

    def has(self, item_id: str) -> bool:
        return any(i.id == item_id for i in self.items)

    def equip(self, item_id: str) -> bool:
        item = next((i for i in self.items if i.id == item_id), None)
        if not item or item.item_type not in ("weapon", "armor"):
            return False
        # unequip others of same type
        for other in self.items:
            if other.item_type == item.item_type:
                other.equipped = False
        item.equipped = True
        return True

    def to_prompt(self) -> str:
        lines = ["【背包】"]
        lines.append(f"金币: {self.gold}")
        if self.items:
            for it in self.items:
                desc = it.display()
                if it.description:
                    desc += f" — {it.description}"
                lines.append(f"- {desc}")
        else:
            lines.append("(空)")
        return "\n".join(lines)

    def snapshot(self) -> dict[str, Any]:
        return {
            "items": [
                {
                    "id": i.id,
                    "name": i.name,
                    "description": i.description,
                    "quantity": i.quantity,
                    "item_type": i.item_type,
                    "equipped": i.equipped,
                }
                for i in self.items
            ],
            "gold": self.gold,
        }

    def restore(self, data: dict[str, Any]) -> None:
        self.items = [
            ItemData(
                id=i["id"],
                name=i.get("name", ""),
                description=i.get("description", ""),
                quantity=i.get("quantity", 1),
                item_type=i.get("item_type", "misc"),
                equipped=i.get("equipped", False),
            )
            for i in data.get("items", [])
        ]
        self.gold = data.get("gold", 0)
