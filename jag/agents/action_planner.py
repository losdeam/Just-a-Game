"""Action planner: natural language → structured ActionPlan via LLM."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from jag.agents.llm import LLMProvider
from jag.world.world import WorldState

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class SuggestedOption(BaseModel):
    """Suggested player option."""
    
    text: str = Field(description="The natural language text of the option")
    description: str = Field(description="Brief description of what this action does")
    risk: RiskLevel = Field(default=RiskLevel.LOW, description="Risk level of this option")


class SuggestedOptionsModel(BaseModel):
    """Container for suggested options."""
    
    options: list[SuggestedOption] = Field(default_factory=list, description="3 suggested actions for the player")


class ActionPlanModel(BaseModel):
    """Structured action plan output from LLM."""

    action_type: str = Field(default="interact", description="Action type: move, attack, interact, use, take, drop, examine, rest, craft, speak")
    target: str = Field(default="", description="Target entity or location ID")
    intent: str = Field(default="", description="Player's intent in natural language")
    risk: RiskLevel = Field(default=RiskLevel.LOW, description="Risk level of the action")
    estimated_effects: list[str] = Field(default_factory=list, description="Expected effects of the action")
    attribute: str = Field(default="", description="Primary attribute used (STR, DEX, CON, INT, WIS, CHA)")
    dc: int = Field(default=10, description="Difficulty class for the action check")
    params: dict[str, Any] = Field(default_factory=dict, description="Additional action parameters")


# Attribute name mapping
ATTRIBUTE_MAP = {
    "strength": "STR", "str": "STR",
    "dexterity": "DEX", "dex": "DEX",
    "constitution": "CON", "con": "CON",
    "intelligence": "INT", "int": "INT",
    "wisdom": "WIS", "wis": "WIS",
    "charisma": "CHA", "cha": "CHA",
}

# DC suggestions per risk level
DC_BY_RISK = {
    RiskLevel.LOW: 8,
    RiskLevel.MEDIUM: 12,
    RiskLevel.HIGH: 16,
    RiskLevel.EXTREME: 20,
}


PLANNER_SYSTEM_PROMPT = """你是一个开放世界RPG游戏的行动规划器。
根据玩家的自然语言输入和当前世界上下文，将行动解析为结构化计划。
所有输出内容请使用简体中文。

可用行动类型：
- move: 前往某个地点
- attack: 攻击某个实体
- interact: 与某个实体或物品互动
- use: 使用某个物品
- take: 拾取物品
- drop: 丢弃物品
- examine: 仔细检查某物
- rest: 休息恢复
- craft: 用材料制作
- speak: 与NPC对话

属性：STR（力量）、DEX（敏捷）、CON（体质）、INT（智力）、WIS（感知）、CHA（魅力）
根据难度设定DC：简单=8、中等=12、困难=16、极难=20

合理评估风险和DC：
- 纯社交或被动行为，风险应为LOW，DC为8
- 涉及危险或复杂性的行为，相应提高风险和DC
"""

OPTIONS_SYSTEM_PROMPT = """你是一个开放世界RPG游戏的引导助手。
根据当前世界上下文，生成3个适合玩家的自然语言行动建议。
所有输出内容请使用简体中文。

建议原则：
1. 提供不同类型的选择（例如：探索、社交、互动）
2. 根据当前地点和附近实体生成有意义的选项
3. 包含1个低风险、1个中等风险、1个高风险选项
4. 每个选项要简短，符合RPG游戏的行动描述
5. 不要提及机制性词汇（如DC、属性），只描述玩家可以做什么
"""


def build_world_context(player_id: str, world: WorldState) -> str:
    """Build a compact world context string for the LLM prompt."""
    player = world.characters.get(player_id, {})
    loc_id = player.get("location_id", "")
    location = world.locations.get(loc_id)

    parts = [f"时间: {world.time.time_of_day()}（{world.time.hour}时），第{world.time.day}天，{world.time.season}"]

    if location:
        parts.append(f"地点: {location.name}（{location.location_type}）")
        parts.append(f"  描述: {location.description}")
        nearby = [e for e in location.entities if e != player_id]
        if nearby:
            parts.append(f"  附近: {', '.join(nearby[:5])}{'...' if len(nearby) > 5 else ''}")
        items = location.items
        if items:
            parts.append(f"  物品: {', '.join(items[:5])}{'...' if len(items) > 5 else ''}")

    inventory = player.get("inventory", [])
    if inventory:
        parts.append(f"背包: {', '.join(inventory[:8])}{'...' if len(inventory) > 8 else ''}")

    return "\n".join(parts)


class ActionPlanner:
    """Parse natural language player input into structured action plans."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def suggest_options(
        self, player_id: str, world: WorldState
    ) -> list[dict[str, Any]]:
        """Suggest 3 possible actions for the player based on current context.
        
        Returns list of suggested options with text, description, and risk.
        """
        world_context = build_world_context(player_id, world)

        prompt = (
            f"World Context:\n{world_context}\n\n"
            "请根据当前环境生成3个不同的行动建议，给玩家选择。"
        )

        try:
            result = await self.llm.structured(
                prompt=prompt,
                response_model=SuggestedOptionsModel,
                system=OPTIONS_SYSTEM_PROMPT,
                max_tokens=512,
            )
            
            # Convert to dicts and ensure exactly 3 options
            options = []
            for opt in result.options[:3]:
                options.append({
                    "text": opt.text,
                    "description": opt.description,
                    "risk": opt.risk.value if isinstance(opt.risk, RiskLevel) else str(opt.risk),
                })
            
            # Fill with fallback options if needed
            while len(options) < 3:
                fallback_suggestions = self._fallback_suggestions()
                if len(options) < len(fallback_suggestions):
                    options.append(fallback_suggestions[len(options)])
                else:
                    options.append(fallback_suggestions[0])
            
            return options
        except Exception as e:
            logger.warning("LLM option suggestion failed: %s, using fallback", e)
            return self._fallback_suggestions(3)

    def _fallback_suggestions(self, count: int = 3) -> list[dict[str, Any]]:
        """Generate fallback suggestions when LLM fails."""
        suggestions = [
            {"text": "仔细观察周围环境", "description": "观察当前地点的细节", "risk": "low"},
            {"text": "与附近的NPC交谈", "description": "与附近的角色互动", "risk": "low"},
            {"text": "检查背包里的物品", "description": "查看并管理你的装备", "risk": "low"},
            {"text": "前往下一个地点", "description": "移动到相邻的区域", "risk": "medium"},
            {"text": "休息恢复体力", "description": "原地休息恢复状态", "risk": "low"},
        ]
        return suggestions[:count]

    async def plan(
        self, action_text: str, player_id: str, world: WorldState
    ) -> dict[str, Any]:
        """Plan an action from natural language input.

        Returns a dict compatible with TickEngine.tick() player_action parameter.
        """
        world_context = build_world_context(player_id, world)

        prompt = (
            f"World Context:\n{world_context}\n\n"
            f"Player says: \"{action_text}\"\n\n"
            f"Parse this into a structured action plan."
        )

        try:
            plan = await self.llm.structured(
                prompt=prompt,
                response_model=ActionPlanModel,
                system=PLANNER_SYSTEM_PROMPT,
                max_tokens=512,
            )
            return self._to_action_dict(plan, player_id, action_text)
        except Exception as e:
            logger.warning("LLM action planning failed: %s, using fallback", e)
            return self._fallback_plan(action_text, player_id, world)

    def _to_action_dict(
        self, plan: ActionPlanModel, player_id: str, original_text: str
    ) -> dict[str, Any]:
        """Convert ActionPlanModel to action dict for TickEngine."""
        attribute_mod = 0
        attr_name = ATTRIBUTE_MAP.get(plan.attribute.lower(), "")
        if attr_name:
            # Will be resolved by dice step; pass the attribute name
            pass

        return {
            "type": plan.action_type,
            "target": plan.target,
            "player_id": player_id,
            "text": original_text,
            "intent": plan.intent,
            "risk": plan.risk.value if isinstance(plan.risk, RiskLevel) else str(plan.risk),
            "dc": plan.dc,
            "attribute": attr_name,
            "attribute_mod": attribute_mod,
            "estimated_effects": plan.estimated_effects,
            "params": plan.params,
        }

    def _fallback_plan(self, action_text: str, player_id: str, world: Any | None = None) -> dict[str, Any]:
        """Generate a fallback action plan when LLM fails.

        Uses keyword matching to determine action type and target.
        """
        text = action_text.lower()

        keywords = {
            "move": ["go ", "walk", "travel", "run", "head", "move", "去", "前往", "走到", "去", "前往", "走到"],
            "attack": ["attack", "fight", "hit", "strike", "kill", "slash", "攻击", "打", "杀", "砍", "揍"],
            "take": ["take", "grab", "pick", "loot", "steal", "拿", "捡", "拾取", "拿取", "偷"],
            "drop": ["drop", "discard", "throw", "丢弃", "扔", "放下"],
            "use": ["use", "drink", "eat", "equip", "apply", "使用", "喝", "吃", "装备", "用"],
            "examine": ["examine", "look", "inspect", "search", "investigate", "检查", "看", "观察", "搜索", "调查"],
            "speak": ["talk", "speak", "ask", "tell", "greet", "交谈", "说话", "聊", "问", "打招呼", "与", "跟"],
            "rest": ["rest", "sleep", "camp", "nap", "休息", "睡觉", "睡", "扎营", "小憩"],
            "craft": ["craft", "make", "build", "forge", "制作", "打造", "建造", "锻造"],
        }

        detected_type = "interact"
        for action_type, words in keywords.items():
            if any(w in text for w in words):
                detected_type = action_type
                break

        target = ""
        if world and detected_type in ("speak", "interact", "attack"):
            target = self._find_nearest_npc(action_text, world)

        return {
            "type": detected_type,
            "target": target,
            "player_id": player_id,
            "text": action_text,
            "intent": action_text,
            "risk": "low",
            "dc": 10,
            "attribute": "",
            "attribute_mod": 0,
            "estimated_effects": [],
            "params": {},
        }

    def _find_nearest_npc(self, action_text: str, world: Any) -> str:
        """Find the nearest NPC matching action text, or first nearby NPC."""
        player_data = world.characters.get("player", {})
        loc_id = player_data.get("location_id", "")
        if not loc_id:
            return ""

        nearby_npcs = [
            (cid, c.get("name", ""))
            for cid, c in world.characters.items()
            if c.get("location_id") == loc_id and c.get("type") == "npc"
        ]
        if not nearby_npcs:
            return ""

        text = action_text.lower()
        for cid, name in nearby_npcs:
            if name and name in action_text:
                return cid

        return nearby_npcs[0][0]
