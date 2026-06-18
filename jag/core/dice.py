"""D20 dice system with modifiers and advantage/disadvantage."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto


class ModifierType(Enum):
    ATTRIBUTE = auto()
    PROFICIENCY = auto()
    ITEM = auto()
    STATUS = auto()


class RollResult(Enum):
    CRITICAL_SUCCESS = "critical_success"
    SUCCESS = "success"
    FAILURE = "failure"
    CRITICAL_FAILURE = "critical_failure"


@dataclass
class Modifier:
    """A modifier to apply to a dice roll."""

    mod_type: ModifierType
    value: int
    source: str = ""


@dataclass
class DiceResult:
    """Result of a dice roll."""

    base_roll: int
    modifiers: list[Modifier] = field(default_factory=list)
    total: int = 0
    result: RollResult = RollResult.FAILURE
    advantage: bool = False
    disadvantage: bool = False
    sides: int = 20

    @property
    def is_success(self) -> bool:
        return self.result in (RollResult.SUCCESS, RollResult.CRITICAL_SUCCESS)

    @property
    def is_critical(self) -> bool:
        return self.result in (RollResult.CRITICAL_SUCCESS, RollResult.CRITICAL_FAILURE)

    def summary(self) -> str:
        mod_str = ""
        if self.modifiers:
            parts = [f"{m.value:+d}" for m in self.modifiers]
            mod_str = f" ({' '.join(parts)})"
        return f"d{self.sides}: {self.base_roll}{mod_str} = {self.total} [{self.result.value}]"


class DiceRoller:
    """D20 dice roller with full modifier support."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def roll(
        self,
        sides: int = 20,
        count: int = 1,
        advantage: bool = False,
        disadvantage: bool = False,
        modifiers: list[Modifier] | None = None,
        dc: int = 10,
    ) -> DiceResult:
        """Roll dice with optional advantage/disadvantage and modifiers."""
        modifiers = modifiers or []

        if advantage and disadvantage:
            advantage = disadvantage = False  # cancel out

        if advantage or disadvantage:
            rolls = [self._rng.randint(1, sides) for _ in range(2)]
            base_roll = max(rolls) if advantage else min(rolls)
        else:
            rolls = [self._rng.randint(1, sides) for _ in range(count)]
            base_roll = sum(rolls)

        total = base_roll + sum(m.value for m in modifiers)

        # Determine result
        if base_roll == sides:  # natural 20 on d20
            result = RollResult.CRITICAL_SUCCESS
        elif base_roll == 1:
            result = RollResult.CRITICAL_FAILURE
        elif total >= dc:
            result = RollResult.SUCCESS
        else:
            result = RollResult.FAILURE

        return DiceResult(
            base_roll=base_roll,
            modifiers=modifiers,
            total=total,
            result=result,
            advantage=advantage,
            disadvantage=disadvantage,
            sides=sides,
        )

    def roll_check(
        self,
        attribute_mod: int = 0,
        proficiency_mod: int = 0,
        item_mod: int = 0,
        status_mod: int = 0,
        dc: int = 10,
        advantage: bool = False,
        disadvantage: bool = False,
    ) -> DiceResult:
        """Convenience method for ability checks."""
        modifiers = []
        if attribute_mod:
            modifiers.append(Modifier(ModifierType.ATTRIBUTE, attribute_mod, "attribute"))
        if proficiency_mod:
            modifiers.append(Modifier(ModifierType.PROFICIENCY, proficiency_mod, "proficiency"))
        if item_mod:
            modifiers.append(Modifier(ModifierType.ITEM, item_mod, "item"))
        if status_mod:
            modifiers.append(Modifier(ModifierType.STATUS, status_mod, "status"))

        return self.roll(
            modifiers=modifiers,
            dc=dc,
            advantage=advantage,
            disadvantage=disadvantage,
        )

    def roll_damage(self, dice_str: str) -> int:
        """Roll damage dice like '2d6+3'."""
        parts = dice_str.lower().split("d")
        if len(parts) != 2:
            return 0
        count = int(parts[0]) if parts[0] else 1
        rest = parts[1]

        bonus = 0
        sides_str = rest
        if "+" in rest:
            sides_str, bonus_str = rest.split("+")
            bonus = int(bonus_str)
        elif "-" in rest:
            sides_str, bonus_str = rest.split("-")
            bonus = -int(bonus_str)

        sides = int(sides_str)
        total = sum(self._rng.randint(1, sides) for _ in range(count)) + bonus
        return max(0, total)
