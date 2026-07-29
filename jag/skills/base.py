"""Skill 基础设施：统一接口，供动态调度使用。

每个 Skill 封装一类生成能力（世界观 / 导演 / 人物 / 地点 / 任务），
对外暴露统一的 ``run(context)`` 入口与可选的 ``persist`` 持久化钩子。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from jag.agents.game_master import GameMaster


@dataclass
class SkillContext:
    """传递给 Skill 执行的上下文。

    Attributes:
        gm: GameMaster 实例，提供对世界状态、子系统和 LLM 的访问。
        params: 调用方传入的参数（词条、地点 id、事件列表等）。
    """

    gm: "GameMaster"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    """Skill 执行结果。

    Attributes:
        success: 是否成功。
        data: 结构化输出（生成的世界/NPC/任务等）。
        messages: 人类可读的说明信息。
        error: 失败时的错误描述。
    """

    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)
    error: str | None = None


class Skill(ABC):
    """所有生成 Skill 的基类。

    子类需实现 :meth:`run`。可覆盖 :meth:`persist` 将产物写入剧本（存档）。
    """

    name: str = ""
    description: str = ""
    category: str = "generation"

    @abstractmethod
    async def run(self, context: SkillContext) -> SkillResult:
        """执行生成逻辑并返回结果。"""

    def persist(self, context: SkillContext, result: SkillResult) -> None:
        """将产物持久化到当前剧本（存档）。默认不做任何事，子类按需覆盖。"""
        return None

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<Skill {self.name}: {self.description}>"
