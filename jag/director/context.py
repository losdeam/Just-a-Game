"""Context builder: assembles module prompts into a Director context.

This is the heart of the "module info is dynamically passed to the Director as
prompts" design. For each player action, the builder gathers every module's
`to_prompt()` fragment, plus location/NPC detail for the player's current
position, and packs them with the player's input into a single prompt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jag.engine.game import Game


def build_action_context(player_input: str, game: "Game") -> str:
    """Build the user prompt for a player action, injecting all module prompts."""
    ss = game.modules["self_state"]
    loc = game.modules["location"]
    npc = game.modules["npc"]

    parts: list[str] = []

    # Current-location-focused detail (more vivid than the global module prompt)
    current_id = ss.current_location_id
    parts.append(loc.prompt_for_location(current_id))
    parts.append(npc.prompt_for_location(current_id))
    parts.append("")

    # Full module prompts
    parts.append(game.modules["worldview"].to_prompt())
    parts.append("")
    parts.append(ss.to_prompt())
    parts.append("")
    parts.append(game.modules["inventory"].to_prompt())
    parts.append("")

    # Recent history (last few exchanges) for continuity
    if game.history:
        parts.append("【最近发生】")
        for h in game.history[-4:]:
            parts.append(f"回合{h['turn']} 玩家: {h['input']}")
            parts.append(f"  结果: {h['narrative'][:120]}")
        parts.append("")

    parts.append(f"【玩家本次行动】\n{player_input}")
    return "\n".join(parts)


def build_opening_context(game: "Game") -> str:
    """Build the prompt for generating an opening narration."""
    parts: list[str] = []
    parts.append(game.modules["worldview"].to_prompt())
    parts.append("")
    parts.append(game.modules["location"].to_prompt())
    parts.append("")
    parts.append(game.modules["npc"].to_prompt())
    parts.append("")
    ss = game.modules["self_state"]
    parts.append(ss.to_prompt())
    parts.append("")
    parts.append(game.modules["inventory"].to_prompt())
    parts.append("")
    parts.append("请为这个世界撰写一段开场叙事，介绍世界背景与玩家处境，并给出3个初始行动建议。")
    return "\n".join(parts)
