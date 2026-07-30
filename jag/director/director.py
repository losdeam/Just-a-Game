"""The Director: conceives plot and emits tool calls to solidify changes.

Flow per player action:
  1. The engine assembles module prompts into a context (see `context.py`).
  2. The Director calls the LLM with a system prompt (its role + tool catalog)
     and the context, asking for a structured `DirectorDecision`.
  3. The Director executes the returned `tool_calls` against the modules — this
     is the "solidify via tools" step. Modules are the single source of truth.
  4. The Director returns the narrative (and suggested options) to the engine.

If the LLM is unavailable or returns an empty narrative (e.g. the mock provider),
a rule-based fallback narrates the action from the current module state, so the
game is always playable offline.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from jag.llm import LLMProvider

from .context import build_action_context, build_opening_context
from .models import DirectorDecision, OpeningDecision

if TYPE_CHECKING:
    from jag.engine.game import Game
    from jag.tools import ToolRegistry


SYSTEM_PROMPT = """你是开放世界RPG的【导演】(Director)。你负责构思情节、推动故事发展，并以沉浸式的第二人称叙事回应玩家。

# 你的职责
1. 根据玩家的行动，构思合理的情节走向与后果。
2. 通过【工具调用】把对世界的影响固化下来——移动玩家、改变NPC好感、增减物品、推进时间、新增地点或NPC等。每一次实质影响都应通过工具落地，而不是只写在叙事里。
3. 输出给玩家的叙事文本(narrative)：第二人称、生动、有画面感，反映工具调用造成的变化。

# 当前世界信息
下方【玩家本次行动】之前的内容，是世界各模块以提示词形式动态传递给你的当前状态，包含：世界观、当前位置与可去之处、在场NPC、玩家自身状态(生命/时间/状态效果)、背包。请严格基于这些信息进行构思，保持一致性。

# 可用工具
你可以返回 tool_calls 列表来调用以下工具。工具会真实修改世界状态。参数以 JSON 键值对给出。仅在确实需要改变状态时才调用工具；纯对话/观察可不调用。

{tools}

# 输出要求
- thoughts: 简述你的情节构思与推理（不展示给玩家）。
- narrative: 给玩家的叙事（第二人称，中文，2-6句）。
- tool_calls: 要执行的工具调用（可空）。每个调用需给出 tool 名与 args。
- suggested_options: 2-3个后续行动建议（简短中文短语）。
"""


class Director:
    """The plot-conceiving agent. Stateless between turns — all state lives in modules."""

    def __init__(self, llm: LLMProvider, tool_registry: "ToolRegistry") -> None:
        self.llm = llm
        self.tool_registry = tool_registry

    def _system_prompt(self) -> str:
        return SYSTEM_PROMPT.format(tools=self.tool_registry.describe_all())

    async def process_action(self, player_input: str, game: "Game") -> DirectorDecision:
        """Conceive the outcome of a player action and solidify it via tools."""
        context = build_action_context(player_input, game)
        system = self._system_prompt()

        decision: DirectorDecision | None = None
        try:
            decision = await self.llm.structured(
                prompt=context, response_model=DirectorDecision, system=system
            )
        except Exception:  # noqa: BLE001
            decision = None

        # Fallback when LLM unavailable / mock returns empty narrative
        if decision is None or not decision.narrative.strip():
            decision = self._fallback_decision(player_input, game)

        # Solidify: execute tool calls against the modules
        results = []
        for tc in decision.tool_calls:
            result = self.tool_registry.execute(tc.tool, tc.args, game)
            results.append({"tool": tc.tool, "args": tc.args, "ok": result.ok, "message": result.message})

        # Stash execution results so the engine can surface/trace them
        decision.tool_calls  # keep for serialization
        object.__setattr__(decision, "_tool_results", results)
        return decision

    async def generate_opening(self, game: "Game") -> tuple[str, list[str]]:
        """Generate an opening narration for the current world state."""
        context = build_opening_context(game)
        system = (
            "你是开放世界RPG的导演。根据提供的世界信息，撰写一段开场叙事："
            "介绍世界背景、玩家处境与起点，引出主线。第二人称、中文、3-6句。"
        )
        try:
            opening = await self.llm.structured(
                prompt=context, response_model=OpeningDecision, system=system
            )
            if opening.narrative.strip():
                return opening.narrative, opening.suggested_options
        except Exception:  # noqa: BLE001
            pass
        # Fallback opening derived from modules
        return self._fallback_opening(game)

    # ── Fallbacks (offline / mock LLM) ──────────────────────────────────

    def _fallback_decision(self, player_input: str, game: "Game") -> DirectorDecision:
        """Rule-based fallback: mirror the action with a state-derived narration."""
        ss = game.modules["self_state"]
        loc = game.modules["location"].get(ss.current_location_id)
        loc_name = loc.name if loc else "未知之地"
        narrative = (
            f"你在{loc_name}采取了行动：{player_input}。"
            f"周围的环境静静回应着你的举动。（当前第{ss.day}天，{ss.time_display()}，"
            f"生命{ss.health}/{ss.max_health}。）"
        )
        return DirectorDecision(
            thoughts="（离线模式：LLM不可用，使用规则兜底）",
            narrative=narrative,
            tool_calls=[],
            suggested_options=["观察周围", "继续前进", "查看背包"],
        )

    def _fallback_opening(self, game: "Game") -> tuple[str, list[str]]:
        wv = game.modules["worldview"]
        ss = game.modules["self_state"]
        loc = game.modules["location"].get(ss.current_location_id)
        loc_name = loc.name if loc else "某处"
        name = wv.world_name or "这个世界"
        intro = wv.description or ""
        narrative = (
            f"欢迎来到{name}。{intro} "
            f"你此刻身处{loc_name}，新的冒险即将开始。"
        )
        return narrative, ["环顾四周", "查看自身状态", "前往相邻地点"]


def tool_results_of(decision: DirectorDecision) -> list[dict]:
    """Helper to extract tool execution results stashed on a decision."""
    return list(getattr(decision, "_tool_results", []))
