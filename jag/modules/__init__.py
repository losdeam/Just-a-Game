"""The five information modules package.

Modules:
  - worldview:  world setting / lore
  - location:   the map of places
  - npc:        the cast of characters
  - self_state: the player's vitals + time
  - inventory:  the player's possessions

Each module renders a prompt fragment via `to_prompt()`. The Director consumes
these fragments; tools mutate the modules to solidify changes.
"""

from __future__ import annotations

from .base import ModuleBase
from .worldview import Faction, WorldviewModule
from .location import LocationData, LocationModule, RegionData
from .npc import NPCData, NPCModule
from .self_state import SelfStateModule, StatusEffect
from .inventory import InventoryModule, ItemData

__all__ = [
    "ModuleBase",
    "WorldviewModule",
    "Faction",
    "LocationModule",
    "LocationData",
    "RegionData",
    "NPCModule",
    "NPCData",
    "SelfStateModule",
    "StatusEffect",
    "InventoryModule",
    "ItemData",
]
