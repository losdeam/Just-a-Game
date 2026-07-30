"""Structured output models for the Director."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """A single tool invocation the Director wants to execute."""

    tool: str = Field(description="要调用的工具名")
    args: dict[str, Any] = Field(default_factory=dict, description="工具参数（键值对）")


class DirectorDecision(BaseModel):
    """The Director's decision for a single player action.

    - thoughts: 导演的内部构思（不展示给玩家），用于推理情节走向
    - narrative: 展示给玩家的叙事文本（沉浸式第二人称描述）
    - tool_calls: 要执行的工具调用列表，用于固化对世界/NPC/玩家状态的影响
    - suggested_options: 可选的后续行动建议（最多3条）
    """

    thoughts: str = Field(default="", description="导演的内部构思与情节推理（不展示给玩家）")
    narrative: str = Field(description="展示给玩家的叙事文本")
    tool_calls: list[ToolCall] = Field(default_factory=list, description="要执行的工具调用")
    suggested_options: list[str] = Field(default_factory=list, description="后续行动建议")


class OpeningDecision(BaseModel):
    """The Director's opening narration for a freshly created world."""

    narrative: str = Field(description="开场叙事文本，介绍世界与玩家处境")
    suggested_options: list[str] = Field(default_factory=list, description="初始行动建议")
