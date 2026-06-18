"""Item system with affordance properties and combination logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class ItemProperties:
    """Affordance properties for an item."""

    flammable: bool = False
    sharp: bool = False
    rope_like: bool = False
    stick_like: bool = False
    liquid: bool = False
    heavy: bool = False
    explosive: bool = False
    magical: bool = False
    edible: bool = False
    wearable: bool = False
    container: bool = False
    light_source: bool = False
    toxic: bool = False
    conductive: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: dict[str, bool]) -> ItemProperties:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class GameItem:
    """A game item with affordance properties."""

    id: str
    name: str
    description: str = ""
    item_type: str = "misc"
    properties: ItemProperties = field(default_factory=ItemProperties)
    quantity: int = 1
    value: int = 0
    weight: float = 0.0
    tags: list[str] = field(default_factory=list)
    state: str = "normal"  # normal, broken, on_fire, wet, etc.

    def has_property(self, prop_name: str) -> bool:
        """Check if item has a specific affordance property."""
        return getattr(self.properties, prop_name, False)

    def get_affordances(self) -> list[str]:
        """Get list of possible uses based on properties."""
        affordances = []
        if self.properties.sharp:
            affordances.extend(["cut", "stab", "slice"])
        if self.properties.stick_like:
            affordances.extend(["poke", "reach", "lever"])
        if self.properties.rope_like:
            affordances.extend(["tie", "climb", "bind"])
        if self.properties.flammable:
            affordances.extend(["burn", "fuel"])
        if self.properties.liquid:
            affordances.extend(["pour", "splash", "drink"])
        if self.properties.heavy:
            affordances.extend(["smash", "block", "weigh_down"])
        if self.properties.explosive:
            affordances.extend(["explode", "throw"])
        if self.properties.light_source:
            affordances.extend(["illuminate", "signal"])
        if self.properties.edible:
            affordances.extend(["eat", "feed"])
        if self.properties.container:
            affordances.extend(["store", "fill", "pour"])
        return affordances


@dataclass
class CombinationResult:
    """Result of combining two items."""

    success: bool
    result_item: GameItem | None = None
    consumed_items: list[str] = field(default_factory=list)
    description: str = ""


class ItemCombiner:
    """Combine items based on their affordance properties."""

    def __init__(self) -> None:
        self._combinations: list[dict[str, Any]] = []

    def load_combinations(self, path: str) -> None:
        """Load combination rules from YAML."""
        with open(path) as f:
            data = yaml.safe_load(f) or []
        self._combinations = data

    def add_combination(
        self,
        required_properties: list[str],
        result: dict[str, Any],
    ) -> None:
        """Add a combination rule."""
        self._combinations.append({
            "required_properties": required_properties,
            "result": result,
        })

    def try_combine(self, item_a: GameItem, item_b: GameItem) -> CombinationResult:
        """Try to combine two items."""
        all_props = set()
        for prop_name, value in item_a.properties.as_dict().items():
            if value:
                all_props.add(prop_name)
        for prop_name, value in item_b.properties.as_dict().items():
            if value:
                all_props.add(prop_name)

        for combo in self._combinations:
            required = set(combo.get("required_properties", []))
            if required.issubset(all_props):
                result_data = combo["result"]
                result_item = GameItem(
                    id=result_data.get("id", f"{item_a.id}_{item_b.id}"),
                    name=result_data.get("name", f"{item_a.name} + {item_b.name}"),
                    description=result_data.get("description", ""),
                    item_type=result_data.get("item_type", "misc"),
                    properties=ItemProperties.from_dict(
                        result_data.get("properties", {})
                    ),
                )
                return CombinationResult(
                    success=True,
                    result_item=result_item,
                    consumed_items=[item_a.id, item_b.id],
                    description=result_data.get("description", f"Combined {item_a.name} and {item_b.name}"),
                )

        return CombinationResult(
            success=False,
            description=f"Cannot combine {item_a.name} and {item_b.name}",
        )
