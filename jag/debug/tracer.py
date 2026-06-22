"""Pipeline tracer: records timing and debug info for each tick step."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

# Step names in the tick pipeline
STEP_NAMES = [
    "action_plan",
    "rules",
    "dice",
    "world_update",
    "npc_tick",
    "world_sim",
    "quest_gen",
    "story",
    "memory",
    "knowledge",
    "persist",
    "narrative",
]

STEP_DISPLAY_NAMES = {
    "action_plan": "行动规划",
    "rules": "规则评估",
    "dice": "骰子检定",
    "world_update": "世界更新",
    "npc_tick": "NPC回合",
    "world_sim": "世界模拟",
    "quest_gen": "任务生成",
    "story": "故事处理",
    "memory": "记忆维护",
    "knowledge": "知识图谱",
    "persist": "状态持久化",
    "narrative": "叙事生成",
}


@dataclass
class StepTrace:
    """Trace data for a single pipeline step."""

    name: str
    display_name: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    success: bool = True
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "duration_ms": round(self.duration_ms, 2),
            "success": self.success,
            "error": self.error,
            "details": self.details,
        }


@dataclass
class TickTrace:
    """Complete trace for one game tick."""

    turn: int = 0
    player_input: str = ""
    steps: list[StepTrace] = field(default_factory=list)
    total_duration_ms: float = 0.0
    start_time: float = 0.0
    end_time: float = 0.0
    # Summary fields extracted after tick
    narrative: str = ""
    dice_summary: str = ""
    action_type: str = ""
    npc_count: int = 0
    event_count: int = 0
    quest_count: int = 0
    story_beat_count: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn": self.turn,
            "player_input": self.player_input,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "steps": [s.to_dict() for s in self.steps],
            "narrative": self.narrative,
            "dice_summary": self.dice_summary,
            "action_type": self.action_type,
            "npc_count": self.npc_count,
            "event_count": self.event_count,
            "quest_count": self.quest_count,
            "story_beat_count": self.story_beat_count,
            "errors": self.errors,
            "timestamp": time.time(),
        }


# Type for subscribers that receive trace data
TraceSubscriber = Callable[[TickTrace], Awaitable[None] | None]


class PipelineTracer:
    """Records and distributes tick pipeline traces.

    Usage:
        tracer = PipelineTracer()
        trace = tracer.start_tick(turn=1, player_input="explore forest")
        step = tracer.start_step("action_plan")
        # ... run action plan ...
        tracer.end_step(step, details={"action_type": "move"})
        # ... more steps ...
        tracer.end_tick(trace, narrative="...", tick_result=result)
    """

    def __init__(self, history_size: int = 100) -> None:
        self._history: deque[TickTrace] = deque(maxlen=history_size)
        self._subscribers: list[TraceSubscriber] = []

    def subscribe(self, subscriber: TraceSubscriber) -> None:
        """Add a subscriber that will be called on each tick completion."""
        self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber: TraceSubscriber) -> None:
        """Remove a subscriber."""
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    def start_tick(self, turn: int, player_input: str = "") -> TickTrace:
        """Begin tracing a new tick."""
        trace = TickTrace(
            turn=turn,
            player_input=player_input,
            start_time=time.perf_counter(),
        )
        return trace

    def start_step(self, name: str) -> StepTrace:
        """Begin tracing a pipeline step."""
        return StepTrace(
            name=name,
            display_name=STEP_DISPLAY_NAMES.get(name, name),
            start_time=time.perf_counter(),
        )

    def end_step(
        self,
        step: StepTrace,
        success: bool = True,
        error: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Finish tracing a pipeline step."""
        step.end_time = time.perf_counter()
        step.duration_ms = (step.end_time - step.start_time) * 1000
        step.success = success
        step.error = error
        if details:
            step.details = details

    def end_tick(self, trace: TickTrace) -> None:
        """Finish tracing the tick and notify subscribers."""
        trace.end_time = time.perf_counter()
        trace.total_duration_ms = (trace.end_time - trace.start_time) * 1000
        self._history.append(trace)

    async def notify(self, trace: TickTrace) -> None:
        """Notify all subscribers of a completed trace."""
        for subscriber in self._subscribers:
            try:
                result = subscriber(trace)
                import asyncio
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent trace history as dicts."""
        items = list(self._history)[-limit:]
        return [t.to_dict() for t in items]

    def get_last(self) -> dict[str, Any] | None:
        """Get the most recent trace."""
        if self._history:
            return self._history[-1].to_dict()
        return None
