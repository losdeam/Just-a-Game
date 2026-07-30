"""Tools package: the interface the Director uses to solidify module changes.

Tools are grouped by the module they primarily affect, but a single tool may
touch multiple modules (e.g. spawning an NPC touches both the npc module and,
indirectly, the location it appears in). The full toolset is registered by
`build_default_registry()`.
"""

from __future__ import annotations

from .base import Tool, ToolParam, ToolRegistry, ToolResult
from .worldview_tools import WORLDVIEW_TOOLS
from .location_tools import LOCATION_TOOLS
from .npc_tools import NPC_TOOLS
from .self_state_tools import SELF_STATE_TOOLS
from .inventory_tools import INVENTORY_TOOLS


def build_default_registry() -> ToolRegistry:
    """Build a registry preloaded with all default tools across the five modules."""
    registry = ToolRegistry()
    for tool in (
        WORLDVIEW_TOOLS
        + LOCATION_TOOLS
        + NPC_TOOLS
        + SELF_STATE_TOOLS
        + INVENTORY_TOOLS
    ):
        registry.register(tool)
    return registry


__all__ = [
    "Tool",
    "ToolParam",
    "ToolResult",
    "ToolRegistry",
    "build_default_registry",
]
