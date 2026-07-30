"""Module layer: the five information modules.

Each module is a self-contained state store that can:
  - render its current state as a prompt fragment for the Director (`to_prompt`)
  - snapshot/restore itself for persistence
  - expose typed data for the Web/UI layer

The five modules are: worldview, location, npc, self_state, inventory.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ModuleBase(ABC):
    """Base class for all information modules.

    A module holds part of the game state and knows how to describe itself to the
    Director as a prompt fragment. Tools mutate modules; the Director only reads
    their prompts.
    """

    name: str = "module"

    @abstractmethod
    def to_prompt(self) -> str:
        """Render the current state as a prompt fragment for the Director."""
        ...

    @abstractmethod
    def snapshot(self) -> dict[str, Any]:
        """Serialize the module state for persistence."""
        ...

    @abstractmethod
    def restore(self, data: dict[str, Any]) -> None:
        """Restore the module state from a snapshot."""
        ...

    def is_empty(self) -> bool:
        """Whether the module has no meaningful content yet (e.g. no world created)."""
        return False
