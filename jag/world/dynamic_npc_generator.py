"""Dynamic NPC generator — pure code + random, no LLM.

Generates NPCs with:
- Random traits (personality) drawn from a pool (n >= 2)
- Dynamic ability scores based on role/age/genre
- Social relationships (friendship, rivalry, family)
- Daily schedules tied to role

Can be used directly by world_builder for fast NPC spawning,
especially when scaling NPC count (10-50+) without LLM latency.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from jag.world.npc import NPC, ScheduleEntry


# ── Data pools ───────────────────────────────────────────────────────

TRAIT_POOL: list[dict[str, Any]] = [
    # Positive
    {"id": "brave", "name": "勇敢", "desc": "面对危险时毫不退缩",
     "mods": {"STR": 2, "CHA": 1, "WIS": -1}, "mood_bias": 0.1},
    {"id": "kind", "name": "善良", "desc": "乐于助人，富有同情心",
     "mods": {"CHA": 2, "WIS": 1, "STR": -1}, "mood_bias": 0.15},
    {"id": "wise", "name": "睿智", "desc": "见识广博，善于思考",
     "mods": {"INT": 2, "WIS": 2, "DEX": -1}, "mood_bias": 0.05},
    {"id": "cheerful", "name": "开朗", "desc": "总是乐观向上",
     "mods": {"CHA": 2, "CON": 1, "INT": -1}, "mood_bias": 0.2},
    {"id": "diligent", "name": "勤勉", "desc": "工作认真负责",
     "mods": {"CON": 2, "STR": 1, "CHA": -1}, "mood_bias": 0.05},
    {"id": "curious", "name": "好奇", "desc": "对未知充满探索欲",
     "mods": {"INT": 2, "DEX": 1, "WIS": -1}, "mood_bias": 0.05},
    {"id": "calm", "name": "冷静", "desc": "遇事沉着不慌乱",
     "mods": {"WIS": 2, "INT": 1, "CHA": -1}, "mood_bias": 0.0},
    {"id": "generous", "name": "慷慨", "desc": "乐于分享自己的所有",
     "mods": {"CHA": 2, "WIS": 1, "STR": -1}, "mood_bias": 0.1},
    {"id": "honest", "name": "诚实", "desc": "从不说谎，信守承诺",
     "mods": {"WIS": 2, "CHA": 1, "DEX": -1}, "mood_bias": 0.05},
    {"id": "creative", "name": "创意", "desc": "思维活跃，常有新奇想法",
     "mods": {"INT": 2, "CHA": 1, "CON": -1}, "mood_bias": 0.05},
    # Neutral
    {"id": "cautious", "name": "谨慎", "desc": "做决定前会反复权衡",
     "mods": {"WIS": 1, "DEX": 1, "STR": -1}, "mood_bias": -0.05},
    {"id": "ambitious", "name": "野心", "desc": "对权力和地位有强烈渴望",
     "mods": {"CHA": 1, "INT": 1, "WIS": -1}, "mood_bias": 0.0},
    {"id": "proud", "name": "骄傲", "desc": "自尊心强，不愿低头",
     "mods": {"STR": 1, "CHA": 1, "WIS": -1}, "mood_bias": 0.0},
    {"id": "quiet", "name": "沉默", "desc": "不善言辞，喜欢独处",
     "mods": {"INT": 1, "WIS": 1, "CHA": -2}, "mood_bias": -0.05},
    {"id": "thrifty", "name": "节俭", "desc": "精打细算，不浪费资源",
     "mods": {"WIS": 1, "INT": 1, "CHA": -1}, "mood_bias": 0.0},
    # Negative
    {"id": "greedy", "name": "贪婪", "desc": "对金钱和财物极度渴望",
     "mods": {"DEX": 1, "INT": 1, "CHA": -2}, "mood_bias": -0.1},
    {"id": "lazy", "name": "懒惰", "desc": "逃避劳动，贪图安逸",
     "mods": {"CHA": 1, "WIS": 1, "STR": -2, "CON": -1}, "mood_bias": 0.05},
    {"id": "hot_tempered", "name": "暴躁", "desc": "易怒，容易冲动",
     "mods": {"STR": 2, "CON": 1, "WIS": -2, "INT": -1}, "mood_bias": -0.15},
    {"id": "cowardly", "name": "懦弱", "desc": "面对威胁容易退缩",
     "mods": {"DEX": 1, "WIS": 1, "STR": -2}, "mood_bias": -0.15},
    {"id": "jealous", "name": "嫉妒", "desc": "容易嫉妒他人的成就",
     "mods": {"INT": 1, "CHA": -2, "WIS": -1}, "mood_bias": -0.1},
]

ROLE_POOL: dict[str, list[dict[str, Any]]] = {
    "fantasy": [
        {"id": "tavern_owner", "name": "酒馆老板", "base_attr": {"CHA": 12, "WIS": 11, "CON": 10},
         "activities": ["打理酒馆", "接待客人", "算账"]},
        {"id": "blacksmith", "name": "铁匠", "base_attr": {"STR": 14, "CON": 13, "DEX": 10},
         "activities": ["打铁", "修理装备", "采买材料"]},
        {"id": "knight", "name": "骑士", "base_attr": {"STR": 13, "CON": 12, "WIS": 10},
         "activities": ["巡逻", "训练", "执行任务"]},
        {"id": "merchant", "name": "商人", "base_attr": {"CHA": 13, "INT": 11, "DEX": 10},
         "activities": ["摆摊", "进货", "谈生意"]},
        {"id": "mage", "name": "法师", "base_attr": {"INT": 14, "WIS": 12, "CON": 9},
         "activities": ["研究魔法", "配制药水", "冥想"]},
        {"id": "priest", "name": "牧师", "base_attr": {"WIS": 13, "CHA": 12, "STR": 9},
         "activities": ["主持仪式", "医治病患", "祈祷"]},
        {"id": "guard", "name": "卫兵", "base_attr": {"STR": 12, "CON": 12, "DEX": 10},
         "activities": ["站岗", "巡逻", "维持秩序"]},
        {"id": "farmer", "name": "农夫", "base_attr": {"STR": 12, "CON": 13, "WIS": 9},
         "activities": ["耕田", "饲养牲畜", "赶集"]},
        {"id": "thief", "name": "盗贼", "base_attr": {"DEX": 13, "CHA": 10, "INT": 10},
         "activities": ["踩点", "行窃", "销赃"]},
        {"id": "bard", "name": "吟游诗人", "base_attr": {"CHA": 14, "DEX": 11, "INT": 10},
         "activities": ["表演", "收集故事", "传递消息"]},
    ],
    "scifi": [
        {"id": "pilot", "name": "飞行员", "base_attr": {"DEX": 13, "INT": 12, "WIS": 10},
         "activities": ["驾驶飞船", "检修设备", "规划航线"]},
        {"id": "engineer", "name": "工程师", "base_attr": {"INT": 14, "DEX": 11, "STR": 10},
         "activities": ["维修设备", "设计方案", "调试系统"]},
        {"id": "scientist", "name": "科学家", "base_attr": {"INT": 14, "WIS": 12, "CON": 9},
         "activities": ["做实验", "分析数据", "撰写论文"]},
        {"id": "mercenary", "name": "雇佣兵", "base_attr": {"STR": 13, "DEX": 12, "WIS": 10},
         "activities": ["执行任务", "训练", "等待委托"]},
        {"id": "trader", "name": "星际商人", "base_attr": {"CHA": 13, "INT": 12, "WIS": 10},
         "activities": ["交易货物", "打探行情", "维护客户"]},
        {"id": "medic", "name": "医疗官", "base_attr": {"WIS": 13, "INT": 12, "DEX": 11},
         "activities": ["治疗病患", "配药", "体检"]},
        {"id": "hacker", "name": "黑客", "base_attr": {"INT": 14, "DEX": 11, "CON": 9},
         "activities": ["破解系统", "收集情报", "编写程序"]},
        {"id": "diplomat", "name": "外交官", "base_attr": {"CHA": 14, "INT": 12, "WIS": 11},
         "activities": ["谈判", "出席宴会", "撰写报告"]},
    ],
    "postapoc": [
        {"id": "scavenger", "name": "拾荒者", "base_attr": {"DEX": 12, "CON": 13, "PER": 10},
         "activities": ["搜索物资", "修理装备", "交易废品"]},
        {"id": "raider", "name": "掠夺者", "base_attr": {"STR": 13, "DEX": 11, "CON": 12},
         "activities": ["抢劫", "巡逻", "分赃"]},
        {"id": "medic", "name": "游医", "base_attr": {"WIS": 12, "DEX": 11, "INT": 11},
         "activities": ["治疗", "采药", "制作药剂"]},
        {"id": "trader", "name": "商人", "base_attr": {"CHA": 12, "INT": 11, "WIS": 11},
         "activities": ["以物易物", "收集情报", "迁徙"]},
        {"id": "mechanic", "name": "机修工", "base_attr": {"INT": 12, "DEX": 12, "STR": 10},
         "activities": ["修理机器", "改装装备", "收集零件"]},
        {"id": "farmer", "name": "种植者", "base_attr": {"STR": 12, "CON": 13, "WIS": 10},
         "activities": ["种植", "狩猎", "保护庄稼"]},
    ],
    "wuxia": [
        {"id": "swordsman", "name": "剑客", "base_attr": {"DEX": 13, "STR": 12, "CON": 11},
         "activities": ["练剑", "行走江湖", "切磋"]},
        {"id": "scholar", "name": "书生", "base_attr": {"INT": 14, "WIS": 12, "STR": 8},
         "activities": ["读书", "写字", "游学"]},
        {"id": "doctor", "name": "郎中", "base_attr": {"WIS": 13, "INT": 12, "DEX": 10},
         "activities": ["诊脉", "抓药", "行医"]},
        {"id": "merchant", "name": "商贾", "base_attr": {"CHA": 13, "INT": 11, "WIS": 11},
         "activities": ["经商", "收账", "宴客"]},
        {"id": "monk", "name": "僧人", "base_attr": {"WIS": 13, "CON": 12, "STR": 10},
         "activities": ["打坐", "化缘", "习武"]},
        {"id": "innkeeper", "name": "客栈老板", "base_attr": {"CHA": 13, "WIS": 11, "CON": 10},
         "activities": ["招呼客人", "算账", "打探消息"]},
        {"id": "guard", "name": "镖师", "base_attr": {"STR": 12, "DEX": 11, "WIS": 10},
         "activities": ["保镖", "练武", "赶路"]},
    ],
    "mystery": [
        {"id": "detective", "name": "侦探", "base_attr": {"INT": 14, "WIS": 12, "PER": 11},
         "activities": ["调查案件", "收集证据", "询问证人"]},
        {"id": "journalist", "name": "记者", "base_attr": {"CHA": 13, "INT": 12, "DEX": 10},
         "activities": ["采访", "写稿", "打探消息"]},
        {"id": "bartender", "name": "酒保", "base_attr": {"CHA": 12, "WIS": 12, "DEX": 11},
         "activities": ["调酒", "听客人倾诉", "打扫"]},
        {"id": "lawyer", "name": "律师", "base_attr": {"INT": 13, "CHA": 12, "WIS": 11},
         "activities": ["研究卷宗", "出庭", "见客户"]},
        {"id": "doctor", "name": "医生", "base_attr": {"INT": 13, "WIS": 12, "DEX": 11},
         "activities": ["看病", "做手术", "写病历"]},
        {"id": "police", "name": "警察", "base_attr": {"STR": 12, "DEX": 11, "WIS": 11},
         "activities": ["巡逻", "办案", "写报告"]},
    ],
    "steampunk": [
        {"id": "inventor", "name": "发明家", "base_attr": {"INT": 14, "DEX": 12, "STR": 9},
         "activities": ["搞发明", "调试机器", "绘制图纸"]},
        {"id": "airship_captain", "name": "飞空艇船长", "base_attr": {"STR": 11, "DEX": 12, "CHA": 12, "WIS": 11},
         "activities": ["驾驶飞艇", "指挥船员", "规划航线"]},
        {"id": "mechanic", "name": "机修师", "base_attr": {"STR": 12, "DEX": 12, "INT": 11},
         "activities": ["修理引擎", "维护设备", "改装"]},
        {"id": "noble", "name": "贵族", "base_attr": {"CHA": 13, "INT": 11, "WIS": 11, "STR": 9},
         "activities": ["参加舞会", "处理政务", "收租"]},
        {"id": "merchant", "name": "富商", "base_attr": {"CHA": 13, "INT": 12, "WIS": 10},
         "activities": ["谈生意", "参加宴会", "巡视店铺"]},
        {"id": "clockmaker", "name": "钟表匠", "base_attr": {"DEX": 14, "INT": 12, "WIS": 10},
         "activities": ["钟表制作", "修理齿轮", "校准时间"]},
    ],
    "horror": [
        {"id": "hunter", "name": "猎人", "base_attr": {"STR": 12, "DEX": 13, "WIS": 11},
         "activities": ["追踪", "狩猎", "布陷阱"]},
        {"id": "librarian", "name": "图书管理员", "base_attr": {"INT": 14, "WIS": 12, "DEX": 9},
         "activities": ["整理书籍", "查阅古籍", "守夜"]},
        {"id": "bartender", "name": "酒吧老板", "base_attr": {"CHA": 12, "WIS": 12, "STR": 10},
         "activities": ["调酒", "听故事", "打烊"]},
        {"id": "professor", "name": "教授", "base_attr": {"INT": 14, "WIS": 12, "CON": 9},
         "activities": ["研究", "授课", "做实验"]},
        {"id": "priest", "name": "神父", "base_attr": {"WIS": 13, "CHA": 12, "STR": 9},
         "activities": ["布道", "驱魔", "祈祷"]},
        {"id": "cop", "name": "警员", "base_attr": {"STR": 12, "DEX": 11, "WIS": 10},
         "activities": ["巡逻", "办案", "写报告"]},
    ],
}

NAME_POOLS: dict[str, list[str]] = {
    "fantasy": [
        "阿尔文", "菲奥娜", "格雷戈尔", "伊莎贝拉", "罗兰", "塞琳娜",
        "提里安", "莫甘娜", "芬里尔", "伊莲娜", "索恩", "莉莉丝",
        "奥古斯丁", "薇拉", "卡斯帕", "艾琳", "鲁珀特", "格蕾丝",
        "埃德蒙", "索菲亚", "马库斯", "娜奥米", "西奥多", "艾米莉亚",
    ],
    "scifi": [
        "凯尔", "诺娃", "马库斯", "艾琳娜", "赞恩", "奥利维亚",
        "罗曼", "阿丽亚", "维克多", "索菲亚", "亚当", "莉娜",
        "伊森", "玛雅", "雷克斯", "露娜", "凯恩", "艾娃",
    ],
    "postapoc": [
        "野狼", "灰烬", "铁皮", "荆棘", "老烟", "锈钉",
        "飞鹰", "碎骨", "铁匠", "瞎子", "快腿", "哑女",
        "铁头", "瘦猴", "酒鬼", "医生", "狐狸", "蛇眼",
    ],
    "wuxia": [
        "李慕白", "周芷若", "张无忌", "黄蓉", "杨过", "小龙女",
        "令狐冲", "任盈盈", "乔峰", "王语嫣", "段誉", "木婉清",
        "郭靖", "梅超风", "陈玄风", "程英", "陆无双", "公孙绿萼",
    ],
    "mystery": [
        "陈默", "林婉清", "王建国", "李美玲", "张伟", "周雪",
        "刘浩然", "赵雅琴", "孙志远", "吴晓燕", "郑海涛", "冯佳怡",
        "钱文博", "朱梦琪", "徐明辉", "何静怡",
    ],
    "steampunk": [
        "塞缪尔", "维多利亚", "阿奇博尔德", "约瑟芬", "威廉", "伊丽莎白",
        "珀西瓦尔", "凯瑟琳", "埃德加", "伊莎多拉", "阿方斯", "克莱拉",
        "尼古拉斯", "玛格丽特",
    ],
    "horror": [
        "霍华德", "安娜贝尔", "文森特", "玛格丽特", "约瑟夫", "艾米丽",
        "查尔斯", "伊迪丝", "亨利", "埃莉诺", "托马斯", "罗莎琳",
        "亚瑟", "格蕾丝",
    ],
}

RELATIONSHIP_TYPES: list[dict[str, Any]] = [
    {"type": "friends", "label": "朋友", "range": (40, 80), "weight": 3},
    {"type": "close_friends", "label": "挚友", "range": (70, 95), "weight": 2},
    {"type": "rivals", "label": "对手", "range": (-60, -20), "weight": 2},
    {"type": "enemies", "label": "仇敌", "range": (-90, -50), "weight": 1},
    {"type": "family", "label": "家人", "range": (60, 90), "weight": 2},
    {"type": "mentor_student", "label": "师徒", "range": (50, 85), "weight": 1},
    {"type": "lovers", "label": "恋人", "range": (75, 100), "weight": 1},
    {"type": "acquaintances", "label": "熟人", "range": (10, 35), "weight": 3},
    {"type": "business", "label": "生意伙伴", "range": (20, 50), "weight": 2},
]


# ── Generator class ─────────────────────────────────────────────────

@dataclass
class GeneratedNPC:
    """Result of dynamic NPC generation."""
    npc: NPC
    traits: list[dict[str, Any]]
    role: dict[str, Any]
    age: int


class DynamicNPCGenerator:
    """Generates NPCs dynamically using pure random logic (no LLM).

    Speed comparison (estimated):
    - LLM-based: 3-10 seconds per NPC (API latency + token generation)
    - This generator: < 1ms per NPC (pure Python + random)

    So for 10 NPCs: LLM ~30-100s, this generator ~10ms — ~1000x faster.
    """

    def __init__(
        self,
        genre: str = "fantasy",
        seed: int | None = None,
        min_traits: int = 2,
        max_traits: int = 4,
    ) -> None:
        self.genre = genre if genre in ROLE_POOL else "fantasy"
        self.rng = random.Random(seed)
        self.min_traits = min_traits
        self.max_traits = max_traits
        self._used_names: set[str] = set()

    def generate_npc(
        self,
        npc_id: str,
        location_id: str,
        role_id: str | None = None,
        age: int | None = None,
    ) -> GeneratedNPC:
        """Generate a single NPC."""
        roles = ROLE_POOL[self.genre]

        if role_id:
            role = next((r for r in roles if r["id"] == role_id), roles[0])
        else:
            role = self.rng.choice(roles)

        if age is None:
            age = self.rng.randint(16, 65)

        traits = self._pick_traits()
        name = self._pick_name()
        attributes = self._calc_attributes(role, traits, age)

        schedule = self._build_schedule(role, location_id)

        # Build description from traits + role
        trait_names = "、".join(t["name"] for t in traits)
        desc = f"{role['name']}。性格{trait_names}。"

        npc = NPC(
            id=npc_id,
            name=name,
            description=desc,
            location_id=location_id,
            personality=traits[0]["id"] if traits else "neutral",
            goal=self._generate_goal(role, traits),
            schedule=schedule,
            attributes=attributes,
            resources={"gold": self.rng.randint(5, 200)},
        )

        return GeneratedNPC(npc=npc, traits=traits, role=role, age=age)

    def generate_batch(
        self,
        count: int,
        locations: list[str],
        role_ids: list[str] | None = None,
    ) -> list[GeneratedNPC]:
        """Generate N NPCs distributed across given locations."""
        results: list[GeneratedNPC] = []
        roles = ROLE_POOL[self.genre]

        if role_ids:
            available_roles = [r for r in roles if r["id"] in role_ids]
        else:
            available_roles = list(roles)

        for i in range(count):
            npc_id = f"npc_dyn_{i}"
            loc = locations[i % len(locations)] if locations else "unknown"
            role = available_roles[i % len(available_roles)] if available_roles else roles[0]
            g = self.generate_npc(npc_id=npc_id, location_id=loc, role_id=role["id"])
            results.append(g)

        self._generate_relationships(results)
        return results

    # ── internal methods ─────────────────────────────────────────

    def _pick_traits(self) -> list[dict[str, Any]]:
        n = self.rng.randint(self.min_traits, self.max_traits)
        pool = list(TRAIT_POOL)
        self.rng.shuffle(pool)
        selected = pool[:n]
        return sorted(selected, key=lambda t: t["name"])

    def _pick_name(self) -> str:
        names = NAME_POOLS.get(self.genre, NAME_POOLS["fantasy"])
        available = [n for n in names if n not in self._used_names]
        if not available:
            # Fallback: just append a number
            base = self.rng.choice(names)
            i = 2
            while f"{base}{i}" in self._used_names:
                i += 1
            name = f"{base}{i}"
        else:
            name = self.rng.choice(available)
        self._used_names.add(name)
        return name

    def _calc_attributes(
        self,
        role: dict[str, Any],
        traits: list[dict[str, Any]],
        age: int,
    ) -> dict[str, int]:
        attrs = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}

        base = role.get("base_attr", {})
        for k, v in base.items():
            if k in attrs:
                attrs[k] = v

        for trait in traits:
            for k, v in trait.get("mods", {}).items():
                if k in attrs:
                    attrs[k] += v

        # Age adjustments
        if age < 18:
            for k in attrs:
                attrs[k] -= 2
            attrs["STR"] -= 1
        elif age > 50:
            attrs["STR"] -= 2
            attrs["DEX"] -= 2
            attrs["CON"] -= 1
            attrs["WIS"] += 1
            attrs["INT"] += 1

        # Small random variance
        for k in attrs:
            attrs[k] += self.rng.randint(-1, 1)

        # Clamp to 3-20 range (D&D-style bounds)
        for k in attrs:
            attrs[k] = max(3, min(20, attrs[k]))

        return attrs

    def _build_schedule(
        self,
        role: dict[str, Any],
        location_id: str,
    ) -> list[ScheduleEntry]:
        activities = role.get("activities", ["工作"])
        main_activity = activities[0] if activities else "工作"

        # Simple schedule: work daytime, rest nighttime
        # Add small variation per NPC
        start_hour = self.rng.choice([6, 7, 8, 9])
        end_hour = self.rng.choice([20, 21, 22, 23])

        schedule = [
            ScheduleEntry(
                hour_start=start_hour,
                hour_end=end_hour,
                activity=main_activity,
                location_id=location_id,
            ),
            ScheduleEntry(
                hour_start=end_hour,
                hour_end=start_hour,
                activity="休息",
                location_id=location_id,
            ),
        ]

        # Add midday break for some
        if self.rng.random() < 0.5 and end_hour - start_hour > 8:
            midday = (start_hour + end_hour) // 2
            schedule = [
                ScheduleEntry(hour_start=start_hour, hour_end=midday,
                              activity=main_activity, location_id=location_id),
                ScheduleEntry(hour_start=midday, hour_end=midday + 1,
                              activity="午休", location_id=location_id),
                ScheduleEntry(hour_start=midday + 1, hour_end=end_hour,
                              activity=main_activity, location_id=location_id),
                ScheduleEntry(hour_start=end_hour, hour_end=start_hour,
                              activity="休息", location_id=location_id),
            ]

        return schedule

    def _generate_goal(self, role: dict[str, Any], traits: dict[str, Any]) -> str:
        goals_by_role = {
            "tavern_owner": "经营好酒馆，让每位客人都满意而归",
            "blacksmith": "打造出传世的神兵利器",
            "knight": "守护这片土地的和平与正义",
            "merchant": "积累财富，成为最富有的商人",
            "mage": "探索魔法的终极奥秘",
            "priest": "传播神的福音，救助苦难之人",
            "guard": "尽职尽责保护居民安全",
            "farmer": "种出最好的庄稼，让家人衣食无忧",
            "thief": "偷取最值钱的宝物而不被发现",
            "bard": "游遍天下，收集最动人的故事",
        }
        goal = goals_by_role.get(role["id"], f"做好{role['name']}的本职工作")

        # Add trait-influenced flavor
        if any(t["id"] == "ambitious" for t in traits):
            goal = "出人头地，" + goal
        elif any(t["id"] == "greedy" for t in traits):
            goal = "赚更多的钱，" + goal

        return goal

    def _generate_relationships(self, npcs: list[GeneratedNPC]) -> None:
        """Generate relationships between NPCs in the batch."""
        if len(npcs) < 2:
            return

        n = len(npcs)
        # Each NPC has ~30% chance of relationship with each other NPC
        for i in range(n):
            for j in range(i + 1, n):
                if self.rng.random() < 0.3:
                    rel_type = self._weighted_choice(RELATIONSHIP_TYPES)
                    lo, hi = rel_type["range"]
                    value = float(self.rng.randint(lo, hi))

                    npc_a = npcs[i].npc
                    npc_b = npcs[j].npc

                    npc_a.relationships[npc_b.id] = value
                    npc_b.relationships[npc_a.id] = value

    def _weighted_choice(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        total = sum(item.get("weight", 1) for item in items)
        r = self.rng.uniform(0, total)
        for item in items:
            r -= item.get("weight", 1)
            if r <= 0:
                return item
        return items[0]


# ── Analysis utilities ──────────────────────────────────────────────

def analyze_performance(
    genre: str = "fantasy",
    npc_counts: list[int] | None = None,
) -> dict[str, Any]:
    """Analyze performance impact of dynamic NPC generation.

    Returns estimated time comparisons and resource usage.
    """
    import time

    if npc_counts is None:
        npc_counts = [5, 10, 25, 50, 100]

    gen = DynamicNPCGenerator(genre=genre, seed=42)
    locations = [f"loc_{i}" for i in range(10)]

    results: dict[str, Any] = {"counts": {}, "summary": {}}

    for count in npc_counts:
        start = time.perf_counter()
        batch = gen.generate_batch(count, locations)
        elapsed = time.perf_counter() - start

        # Calculate stats
        total_relationships = sum(len(g.npc.relationships) for g in batch)
        avg_attrs = {}
        for g in batch:
            for k, v in g.npc.attributes.items():
                avg_attrs[k] = avg_attrs.get(k, 0) + v
        avg_attrs = {k: round(v / count, 1) for k, v in avg_attrs.items()}

        # LLM estimate (3-8s per NPC, conservative)
        llm_low_estimate = count * 3.0
        llm_high_estimate = count * 8.0

        results["counts"][str(count)] = {
            "gen_time_seconds": round(elapsed, 4),
            "per_npc_ms": round(elapsed / count * 1000, 2),
            "total_relationships": total_relationships,
            "avg_attributes": avg_attrs,
            "llm_estimate_low_seconds": llm_low_estimate,
            "llm_estimate_high_seconds": llm_high_estimate,
            "speedup_vs_llm_lowx": round(llm_low_estimate / max(elapsed, 0.0001), 1),
            "speedup_vs_llm_highx": round(llm_high_estimate / max(elapsed, 0.0001), 1),
        }

    # Summary
    results["summary"] = {
        "method": "纯代码随机生成（无 LLM）",
        "trait_pool_size": len(TRAIT_POOL),
        "role_pool_size": len(ROLE_POOL.get(genre, [])),
        "min_traits_per_npc": gen.min_traits,
        "max_traits_per_npc": gen.max_traits,
        "attributes_per_npc": 6,
        "relationship_types": len(RELATIONSHIP_TYPES),
        "pros": [
            "极快的生成速度（毫秒级）",
            "可大规模生成 NPC（100+ 也毫无压力）",
            "游戏初始化几乎无等待",
            "不消耗 API 费用",
            "离线可用，不依赖网络",
            "可预测、可调试、可复现（通过 seed）",
        ],
        "cons": [
            "缺乏 LLM 生成的深度和创意",
            "对话内容需要模板或单独生成",
            "人物背景故事相对简单",
            "需要手动维护 trait/role 池子",
        ],
        "recommendation": (
            "建议混合使用：核心 NPC（如任务相关、关键角色）"
            "用 LLM 生成获得深度，背景 NPC（路人、卫兵、普通村民）"
            "用此动态生成器快速填充，兼顾质量与数量。"
        ),
    }

    return results


# ── CLI entry point ─────────────────────────────────────────────────

def main() -> None:
    """Demo: generate NPCs and print analysis."""
    import json
    import sys

    genre = sys.argv[1] if len(sys.argv) > 1 else "fantasy"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    print(f"=== Dynamic NPC Generator Demo ===")
    print(f"Genre: {genre}")
    print(f"Count: {count}")
    print()

    gen = DynamicNPCGenerator(genre=genre, seed=42)
    locations = ["tavern", "market", "plaza", "forge", "temple"]
    batch = gen.generate_batch(count, locations)

    print(f"Generated {len(batch)} NPCs:")
    for g in batch[:10]:
        traits = "/".join(t["name"] for t in g.traits)
        print(f"  {g.npc.name} ({g.role['name']}, {g.age}岁) [{traits}]")
    if len(batch) > 10:
        print(f"  ... and {len(batch) - 10} more")
    print()

    # Relationship summary
    total_rels = sum(len(g.npc.relationships) for g in batch)
    print(f"Total relationships: {total_rels}")
    print()

    # Sample attributes
    sample = batch[0]
    print(f"Sample: {sample.npc.name} attributes:")
    for k, v in sorted(sample.npc.attributes.items()):
        bar = "█" * (v // 2) + "░" * (10 - v // 2)
        print(f"  {k:4s} {v:2d} {bar}")
    print()

    # Performance analysis
    print("=== Performance Analysis ===")
    analysis = analyze_performance(genre=genre)
    print(json.dumps(analysis["summary"], ensure_ascii=False, indent=2))
    print()
    print("Time comparison:")
    print(f"{'Count':>6} | {'Gen time':>10} | {'Per NPC':>10} | {'LLM est.':>12} | {'Speedup':>12}")
    print("-" * 60)
    for cnt_str in sorted(analysis["counts"].keys(), key=lambda x: int(x)):
        data = analysis["counts"][cnt_str]
        speedup = f"{data['speedup_vs_llm_lowx']:.0f}-{data['speedup_vs_llm_highx']:.0f}x"
        print(f"{cnt_str:>6} | {data['gen_time_seconds']:>8.4f}s | {data['per_npc_ms']:>8.2f}ms | "
              f"{data['llm_estimate_low_seconds']:>6.0f}-{data['llm_estimate_high_seconds']:>4.0f}s | {speedup:>12}")


if __name__ == "__main__":
    main()
