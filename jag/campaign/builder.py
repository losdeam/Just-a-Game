"""跑团本生成器：在世界构建之上装配一桌单人跑团的完整剧本。

复用 WorldBuilder 已经搭好的世界骨架（地点 / NPC / lore），再叠加：
- 角色卡（玩家 + NPC，SillyTavern 风格）
- 知识书（关键词触发的世界设定条目）
- 剧情线（环世界式剧本钩子，交给 StoryDirector 维持节奏）
- 主持人开场独白（AI GM 声线）

「创建世界观」即「创建跑团本」。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from jag.campaign.book import (
    CampaignBook,
    CharacterCard,
    LorebookEntry,
    PlotThread,
)

if TYPE_CHECKING:  # 避免运行期循环导入
    from jag.agents.game_master import GameMaster

logger = logging.getLogger(__name__)


# ── 基调 / 规则模板 ──────────────────────────────────────────────

_TONE_BY_ATMOSPHERE: dict[str, str] = {
    "light": "明快轻松，鼓励玩家尽情冒险，失败也充满趣味。",
    "dark": "冷酷压抑，生存艰难，每一次抉择都代价沉重。",
    "epic": "恢弘史诗，命运交织，玩家是时代洪流中的关键人物。",
    "mystery": "悬疑诡谲，处处伏笔，真相藏在层层迷雾之后。",
    "peaceful": "宁静悠然，以探索与社交为主，偶有波澜。",
    "chaotic": "混乱动荡，势力割据，冲突一触即发。",
}

_RULESET_TEXT = (
    "采用 D20 检定系统：玩家宣告行动后，由主持人判定是否需要掷骰，"
    "并指定属性（力量STR/敏捷DEX/体质CON/智力INT/感知WIS/魅力CHA）与难度等级DC。"
    "d20+加值 ≥ DC 即为成功；自然20为大成功，自然1为大失败。"
    "主持人负责扮演所有 NPC、描述场景结果、推进剧情，并在关键时刻点名检定。"
)

# 各类型的开场母题与剧情线钩子
_GENRE_HOOKS: dict[str, dict[str, str]] = {
    "fantasy": {"hook": "一封来自远方的求助信，将你卷入黑暗领主复苏的阴谋。"},
    "scifi": {"hook": "空间站的警报骤然响起，核心能源站濒临失控。"},
    "postapoc": {"hook": "一张旧世界避难所的坐标，在废土幸存者间掀起暗流。"},
    "wuxia": {"hook": "一本失传秘籍重现江湖，各门派闻风而动，血案接踵而至。"},
    "mystery": {"hook": "一桩悬而未决的连环失踪案，把 you 拖向都市最深的阴影。"},
    "steampunk": {"hook": "蒸汽核心的异响预示着整座齿轮城即将崩毁。"},
    "horror": {"hook": "古老的低语在梦中响起，理智正被某种存在缓缓侵蚀。"},
}


class CampaignBuilder:
    """在世界之上装配跑团本。不重建世界，只读取 gm 当前状态。"""

    def __init__(self, gm: GameMaster) -> None:
        self.gm = gm

    # ── 主入口 ────────────────────────────────────────────────

    async def assemble(
        self,
        world_name: str = "",
        tags: dict[str, Any] | None = None,
        description: str = "",
        use_llm: bool = False,
        method: str = "template",
    ) -> CampaignBook:
        """读取 gm 当前世界状态，装配并返回跑团本（同时挂到 gm 上）。"""
        tags = tags or {}
        genre = self._first(tags.get("genre"), "fantasy")
        atmosphere = tags.get("atmosphere", []) or []

        setting = self._build_setting()
        player_card = self._build_player_card(genre)
        npc_cards = self._build_npc_cards()
        lorebook = self._build_lorebook(setting, npc_cards)
        plot_threads = self._build_plot_threads(genre, setting)

        # 叙事层：标题 / 概要 / 序章 / 基调 / 开场
        title = world_name or setting.get("world_name", "无名跑团本")
        tone = "；".join(_TONE_BY_ATMOSPHERE.get(a, "") for a in atmosphere if _TONE_BY_ATMOSPHERE.get(a)) \
            or "沉稳克制，注重氛围与抉择。"

        book = CampaignBook(
            title=title,
            tone=tone,
            ruleset=_RULESET_TEXT,
            setting=setting,
            player_card=player_card,
            npc_cards=npc_cards,
            lorebook=lorebook,
            plot_threads=plot_threads,
            tags=self._sanitize_tags(tags),
            method=method,
        )

        # 用 LLM 润色叙事层（失败回退模板）
        if use_llm and self._llm_ready():
            try:
                await self._llm_enrich(book, genre, description)
            except Exception as e:  # noqa: BLE001
                logger.warning("LLM 跑团本润色失败，回退模板: %s", e)
                self._template_enrich(book, genre, description)
        else:
            self._template_enrich(book, genre, description)

        self.gm.set_campaign(book)
        return book

    # ── 设定 / 角色卡 / 知识书 / 剧情线 ─────────────────────────

    def _build_setting(self) -> dict[str, Any]:
        lore = self.gm.world_lore or {}
        # 直接沿用 world_builder 产出的 lore 结构，补一个地点映射
        setting = dict(lore)
        locs = []
        for loc_id, loc in self.gm.world.locations.items():
            locs.append({
                "id": loc_id, "name": loc.name,
                "description": loc.description,
                "type": loc.location_type,
                "danger": loc.danger_level, "light": loc.light_level,
                "connected": list(loc.connected),
            })
        setting["locations"] = locs
        return setting

    def _build_player_card(self, genre: str) -> CharacterCard:
        player = self.gm.world.characters.get(self.gm.player_id, {})
        inv = player.get("inventory", [])
        return CharacterCard(
            name=player.get("name", "冒险者"),
            role="玩家角色",
            description=f"一名踏上{genre}之旅的冒险者，行囊中带着：{'、'.join(inv) if inv else '几件简单行装'}。",
            personality="curious",
            scenario="初来乍到，对这个世界一无所知，却已被卷入命运的漩涡。",
            goals="在这个世界中活下去，并揭开隐藏的真相。",
            location=player.get("location_id", ""),
            is_player=True,
        )

    def _build_npc_cards(self) -> list[CharacterCard]:
        cards: list[CharacterCard] = []
        for npc_id, npc in self.gm.tick_engine._npcs.items():
            loc_name = self._loc_name(npc.location_id)
            cards.append(CharacterCard(
                name=npc.name,
                role=self._role_from_desc(npc.description, npc_id),
                description=npc.description or f"出没于{loc_name}的角色。",
                personality=npc.personality,
                scenario=f"正于{loc_name}{'从事'+npc.goal if npc.goal else '活动'}。",
                goals=npc.goal or "维持自己的生活。",
                location=npc.location_id,
                first_message=self._first_line(npc),
            ))
        return cards

    def _build_lorebook(
        self, setting: dict[str, Any], npc_cards: list[CharacterCard],
    ) -> list[LorebookEntry]:
        entries: list[LorebookEntry] = []
        # 世界级设定
        if setting.get("main_quest"):
            entries.append(LorebookEntry(
                keywords=["任务", "主线", "quest", setting.get("world_name", "")],
                content=f"主线任务：{setting['main_quest']}", priority=10,
            ))
        if setting.get("magic_level"):
            entries.append(LorebookEntry(
                keywords=["魔法", "法术", "施法", "魔力", "magic"],
                content=f"魔法设定：{setting['magic_level']}", priority=5,
            ))
        if setting.get("history"):
            entries.append(LorebookEntry(
                keywords=["历史", "过去", "传说", "由来"],
                content=setting["history"], priority=3,
            ))
        # 地点条目（关键词=地点名）
        for loc in setting.get("locations", []):
            name = loc.get("name", "")
            if not name:
                continue
            entries.append(LorebookEntry(
                keywords=[name],
                content=f"{name}：{loc.get('description','')}（危险度 {loc.get('danger',0)}/10）",
                priority=4,
            ))
        # NPC 条目（关键词=NPC 名 + 职业）
        for c in npc_cards:
            kws = [c.name] if c.name else []
            if c.role and c.role != "NPC":
                kws.append(c.role)
            entries.append(LorebookEntry(
                keywords=kws,
                content=f"{c.name}（{c.role}）：{c.description} 目标：{c.goals}",
                priority=6,
            ))
        return entries

    def _build_plot_threads(self, genre: str, setting: dict[str, Any]) -> list[PlotThread]:
        hook = _GENRE_HOOKS.get(genre, {}).get("hook", "一个未知的契机将你卷入冒险。")
        threads = [PlotThread(
            title="主线：命运的召唤",
            description=setting.get("main_quest", hook),
            status="active",
        )]
        # 用首个非安全地点埋一条支线钩子
        for loc in setting.get("locations", []):
            if loc.get("danger", 0) >= 4:
                threads.append(PlotThread(
                    title=f"支线：{loc.get('name','未知之地')}的异象",
                    description=f"{loc.get('name','')}流传着不寻常的传闻，值得前往探查。",
                    status="dormant",
                ))
                break
        return threads

    # ── 叙事层填充 ─────────────────────────────────────────────

    def _template_enrich(self, book: CampaignBook, genre: str, description: str) -> None:
        hook = _GENRE_HOOKS.get(genre, {}).get("hook", "一个契机将你卷入冒险。")
        if not book.logline:
            book.logline = hook
        if not book.premise:
            extra = f" 玩家设想：{description}。" if description else ""
            book.premise = (
                f"{book.setting.get('description','这是一个等待被书写的世界。')}\n"
                f"{book.setting.get('history','')}\n{hook}{extra}"
            ).strip()
        if not book.opening_scene:
            book.opening_scene = self._template_opening(book, genre)

    def _template_opening(self, book: CampaignBook, genre: str) -> str:
        loc_name = self._loc_name(self.gm.world.characters.get(self.gm.player_id, {}).get("location_id", ""))
        inv = book.player_card.description
        return (
            f"（主持人）欢迎来到《{book.title}》。{book.logline}\n\n"
            f"你睁开双眼，发现自己身处「{loc_name}」。{book.setting.get('description','')}\n"
            f"{inv}\n\n"
            f"空气里弥漫着冒险的气息——你想做些什么？"
        )

    async def _llm_enrich(self, book: CampaignBook, genre: str, description: str) -> None:
        llm = self.gm._get_llm("narrator")
        npc_summary = "；".join(f"{c.name}({c.role})" for c in book.npc_cards[:6]) or "暂无"
        loc_summary = "；".join(l.get("name", "") for l in book.setting.get("locations", [])[:8]) or "未知"
        prompt = (
            f"你是一位经验丰富的桌跑团主持人，请为一桌单人跑团撰写剧本开篇。所有输出用简体中文。\n\n"
            f"跑团本名称：{book.title}\n"
            f"类型：{genre}　基调：{book.tone}\n"
            f"玩家描述：{description or '无特别要求'}\n"
            f"世界设定：{book.setting.get('description','')}\n"
            f"主线任务：{book.setting.get('main_quest','')}\n"
            f"关键地点：{loc_summary}\n"
            f"关键 NPC：{npc_summary}\n"
            f"玩家角色：{book.player_card.name}，{book.player_card.description}\n\n"
            f"请严格按以下格式输出（不要输出多余内容）：\n"
            f"【概要】一句话故事概要\n"
            f"【序章】2-4 句背景设定，交代世界现状与玩家处境\n"
            f"【开场】以主持人第二人称口吻写一段开场独白，描述玩家初次抵达「{self._loc_name(self.gm.world.characters.get(self.gm.player_id,{}).get('location_id',''))}」的所见所感，"
            f"含感官细节与悬念，结尾抛出一个开放式钩子引导玩家行动。150-250 字。"
        )
        text = (await llm.complete(prompt, system="你是一位资深桌跑团主持人与剧本作者。", max_tokens=600)).strip()
        logline, premise, opening = self._parse_llm_blocks(text)
        if logline:
            book.logline = logline
        if premise:
            book.premise = premise
        if opening:
            book.opening_scene = opening

    @staticmethod
    def _parse_llm_blocks(text: str) -> tuple[str, str, str]:
        import re
        def grab(label: str) -> str:
            m = re.search(rf"【{label}】\s*([\s\S]*?)(?=【|$)", text)
            return m.group(1).strip() if m else ""
        return grab("概要"), grab("序章"), grab("开场")

    # ── 工具 ───────────────────────────────────────────────────

    def _llm_ready(self) -> bool:
        cfg = self.gm.config.llm.default
        return bool(cfg.api_key and cfg.api_key != "your-api-key-here")

    @staticmethod
    def _first(seq: Any, default: str) -> str:
        if not seq:
            return default
        return seq[0] if isinstance(seq, list) else str(seq)

    def _loc_name(self, loc_id: str) -> str:
        loc = self.gm.world.locations.get(loc_id)
        return loc.name if loc else (loc_id or "未知之地")

    @staticmethod
    def _role_from_desc(desc: str, npc_id: str) -> str:
        # NPC.description 形如「酒馆老板。让每位旅客都感到宾至如归。」
        if desc:
            head = desc.split("。", 1)[0].strip()
            if head:
                return head
        return npc_id

    @staticmethod
    def _first_line(npc: Any) -> str:
        if not npc.goal:
            return ""
        # 极简开场台词，由 GM 在合适时机使用
        return ""

    @staticmethod
    def _sanitize_tags(tags: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in tags.items():
            out[k] = list(v) if isinstance(v, list) else v
        return out
