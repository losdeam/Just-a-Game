"""Tool layer: the interface the Director uses to solidify changes into modules.

A Tool is a named, described operation that mutates one or more modules. The
Director decides what should happen (plot-wise), then emits tool calls; the
engine executes those calls against the live modules. This keeps the Director
as a pure "conceiver" and the modules as the single source of truth — every
change goes through a tool, so state is always consistent and inspectable.

Tools are described to the Director as a plain-text schema in the system prompt
(no native function-calling required), which keeps the design LLM-agnostic and
works with the mock provider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from jag.engine.game import Game


@dataclass
class ToolParam:
    name: str
    type: str  # str/int/float/bool
    description: str
    required: bool = True
    default: Any = None
    enum: list[str] | None = None


@dataclass
class ToolResult:
    ok: bool
    message: str


class Tool(ABC):
    """Base class for all director tools."""

    name: str = ""
    description: str = ""
    params: list[ToolParam] = field(default_factory=list)

    @abstractmethod
    def execute(self, args: dict[str, Any], game: "Game") -> ToolResult:
        """Execute the tool against the game's modules."""
        ...

    def schema_text(self) -> str:
        """Render the tool's schema as plain text for the Director prompt."""
        parts = [f"- {self.name}: {self.description}"]
        if self.params:
            pspecs = []
            for p in self.params:
                spec = f"{p.name}"
                if p.enum:
                    spec += f"({'|'.join(p.enum)})"
                else:
                    spec += f":{p.type}"
                if not p.required:
                    spec += "[可选]"
                spec += f" — {p.description}"
                pspecs.append(spec)
            parts.append("  参数: " + "; ".join(pspecs))
        return "\n".join(parts)


class ToolRegistry:
    """Registry of available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def execute(self, name: str, args: dict[str, Any], game: "Game") -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(ok=False, message=f"未知工具: {name}")
        try:
            # fill defaults
            full_args = dict(args)
            for p in tool.params:
                if p.name not in full_args and not p.required:
                    full_args[p.name] = p.default
            return tool.execute(full_args, game)
        except Exception as e:  # noqa: BLE001
            return ToolResult(ok=False, message=f"工具 {name} 执行失败: {e}")

    def describe_all(self) -> str:
        """Render all tool schemas as a single text block for the Director prompt."""
        if not self._tools:
            return "(无可用工具)"
        return "\n".join(t.schema_text() for t in self._tools.values())

    def names(self) -> list[str]:
        return list(self._tools.keys())
