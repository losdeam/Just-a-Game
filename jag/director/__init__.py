"""Director package: the plot-conceiving agent.

The Director is the single LLM-driven agent in the new framework. It:
  - receives module prompts dynamically (assembled in `context.py`),
  - conceives the plot outcome of a player action,
  - emits tool calls (executed by the engine) to solidify changes into modules,
  - returns the narrative for the player.

There is no tick pipeline, no separate action-planner/narrator/npc-agent — the
Director is the sole decision maker, and modules + tools replace the old
scattered subsystems.
"""

from __future__ import annotations

from .context import build_action_context, build_opening_context
from .director import Director, tool_results_of
from .models import DirectorDecision, OpeningDecision, ToolCall

__all__ = [
    "Director",
    "DirectorDecision",
    "OpeningDecision",
    "ToolCall",
    "build_action_context",
    "build_opening_context",
    "tool_results_of",
]
