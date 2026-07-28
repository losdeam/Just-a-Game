"""跑团本数据模型：角色卡 / 知识书条目 / 剧情线 / 跑团本。

设计参考：
- SillyTavern 的角色卡（Character Card V2）与知识书（World Info / Lorebook），
  用关键词触发把世界设定注入主持人上下文，保证设定一致又不撑爆上下文。
- 环世界（RimWorld）的故事讲述者：用剧情线（PlotThread）追踪节奏与伏笔。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CharacterCard:
    """SillyTavern 风格角色卡（精简版）。玩家与 NPC 共用。"""

    name: str = ""
    role: str = ""                      # 身份/职业，如「酒馆老板」「冒险者」
    description: str = ""               # 外貌与背景
    personality: str = "neutral"        # friendly/stern/curious/charming/neutral
    scenario: str = ""                  # 此角色当下的处境
    goals: str = ""                     # 动机/目标
    location: str = ""                  # 所在地点
    first_message: str = ""             # 开场可用的台词（NPC 专用，可选）
    is_player: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "personality": self.personality,
            "scenario": self.scenario,
            "goals": self.goals,
            "location": self.location,
            "first_message": self.first_message,
            "is_player": self.is_player,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CharacterCard:
        return cls(
            name=d.get("name", ""),
            role=d.get("role", ""),
            description=d.get("description", ""),
            personality=d.get("personality", "neutral"),
            scenario=d.get("scenario", ""),
            goals=d.get("goals", ""),
            location=d.get("location", ""),
            first_message=d.get("first_message", ""),
            is_player=d.get("is_player", False),
        )


@dataclass
class LorebookEntry:
    """知识书条目：当玩家输入 / 当前场景命中关键词时注入主持人上下文。"""

    keywords: list[str] = field(default_factory=list)
    content: str = ""
    priority: int = 0                   # 数值越大越优先注入
    enabled: bool = True

    def matches(self, text: str) -> bool:
        if not self.enabled or not text:
            return False
        low = text.lower()
        return any(k and k.lower() in low for k in self.keywords)

    def to_dict(self) -> dict[str, Any]:
        return {
            "keywords": list(self.keywords),
            "content": self.content,
            "priority": self.priority,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LorebookEntry:
        return cls(
            keywords=list(d.get("keywords", [])),
            content=d.get("content", ""),
            priority=d.get("priority", 0),
            enabled=d.get("enabled", True),
        )


@dataclass
class PlotThread:
    """剧情线：跑团本的剧本钩子，交给 StoryDirector 维持节奏与连贯。"""

    title: str = ""
    description: str = ""
    status: str = "active"              # active | climax | resolved | dormant

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "description": self.description, "status": self.status}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PlotThread:
        return cls(
            title=d.get("title", ""),
            description=d.get("description", ""),
            status=d.get("status", "active"),
        )


@dataclass
class CampaignBook:
    """跑团本：一桌单人跑团所需的完整剧本。

    「创建世界观」即生成一份 CampaignBook：设定、角色卡、知识书、剧情线、
    以及主持人（AI GM）的开场场景。运行时由 NarrativeGenerator 以 GM 声线演绎。
    """

    title: str = ""                     # 跑团本名称
    logline: str = ""                   # 一句话概要
    premise: str = ""                   # 序章 / 背景设定
    tone: str = ""                      # 基调与风格
    ruleset: str = ""                   # 规则说明（D20 检定等）
    setting: dict[str, Any] = field(default_factory=dict)   # 世界观（沿用 lore 结构）
    player_card: CharacterCard = field(default_factory=CharacterCard)
    npc_cards: list[CharacterCard] = field(default_factory=list)
    lorebook: list[LorebookEntry] = field(default_factory=list)
    plot_threads: list[PlotThread] = field(default_factory=list)
    opening_scene: str = ""             # 主持人开场独白
    tags: dict[str, Any] = field(default_factory=dict)
    method: str = "template"            # template | llm | demo

    # ── 上下文构造（供主持人 prompt 使用）──────────────────────

    def lookup_lorebook(self, text: str, limit: int = 6) -> list[LorebookEntry]:
        """根据文本命中关键词，返回需要注入的知识书条目（按优先级降序）。"""
        hits = [e for e in self.lorebook if e.matches(text)]
        hits.sort(key=lambda e: e.priority, reverse=True)
        return hits[:limit]

    def npc_card_at(self, location: str) -> list[CharacterCard]:
        """返回位于某地点的 NPC 角色卡。"""
        return [c for c in self.npc_cards if c.location == location]

    def find_npc_card(self, name: str) -> CharacterCard | None:
        low = (name or "").lower()
        for c in self.npc_cards:
            if low and (c.name.lower() == low or c.role.lower() == low):
                return c
        return None

    # ── 序列化 ─────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "logline": self.logline,
            "premise": self.premise,
            "tone": self.tone,
            "ruleset": self.ruleset,
            "setting": dict(self.setting),
            "player_card": self.player_card.to_dict(),
            "npc_cards": [c.to_dict() for c in self.npc_cards],
            "lorebook": [e.to_dict() for e in self.lorebook],
            "plot_threads": [t.to_dict() for t in self.plot_threads],
            "opening_scene": self.opening_scene,
            "tags": dict(self.tags),
            "method": self.method,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CampaignBook:
        return cls(
            title=d.get("title", ""),
            logline=d.get("logline", ""),
            premise=d.get("premise", ""),
            tone=d.get("tone", ""),
            ruleset=d.get("ruleset", ""),
            setting=dict(d.get("setting", {})),
            player_card=CharacterCard.from_dict(d.get("player_card", {})),
            npc_cards=[CharacterCard.from_dict(c) for c in d.get("npc_cards", [])],
            lorebook=[LorebookEntry.from_dict(e) for e in d.get("lorebook", [])],
            plot_threads=[PlotThread.from_dict(t) for t in d.get("plot_threads", [])],
            opening_scene=d.get("opening_scene", ""),
            tags=dict(d.get("tags", {})),
            method=d.get("method", "template"),
        )
