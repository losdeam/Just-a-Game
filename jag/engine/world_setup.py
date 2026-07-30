"""World setup: populate the five modules with demo / tag-based content.

Kept separate from the engine so the engine stays pure orchestration. The demo
world ("阿尔多利亚王国") mirrors the old setup_demo_world content, but wired
into the new module structure.
"""

from __future__ import annotations

from typing import Any

from jag.modules import (
    Faction,
    InventoryModule,
    ItemData,
    LocationData,
    LocationModule,
    NPCData,
    NPCModule,
    RegionData,
    SelfStateModule,
    WorldviewModule,
)


def load_demo_world(
    worldview: WorldviewModule,
    location: LocationModule,
    npc: NPCModule,
    self_state: SelfStateModule,
    inventory: InventoryModule,
) -> None:
    """Populate modules with the 阿尔多利亚 demo world."""
    # ── Worldview ──
    worldview.world_name = "阿尔多利亚王国"
    worldview.genre = "fantasy"
    worldview.era = "封建中世纪"
    worldview.atmosphere = "阳光明媚，处处生机。"
    worldview.terrain = "城镇、森林"
    worldview.magic_level = "中魔"
    worldview.danger_level = "适中"
    worldview.description = "一个位于荒野边缘的和平王国，剑与魔法的经典奇幻世界。"
    worldview.history = (
        "阿尔多利亚王国曾是古代精灵帝国的一部分，人类在精灵隐退后建立了自己的文明。"
        "如今王国边境的黑暗森林中，古老的遗迹正散发出不祥的气息。"
    )
    worldview.main_quest = (
        "传说中的黑暗领主正在集结大军，你必须找到传说中的神器，"
        "联合各势力，在末日降临前阻止他。"
    )
    worldview.factions = [
        Faction(name="王国守卫军", description="守护城镇的卫队", relationship="ally"),
        Faction(name="暗影教会", description="潜伏在遗迹中的邪教", relationship="hostile"),
    ]

    # ── Location ──
    location.regions.clear()
    location.locations.clear()
    location.add_region(RegionData(
        id="kingdom", name="阿尔多利亚王国",
        description="一个位于荒野边缘的和平王国。", region_type="kingdom",
    ))
    locs = [
        LocationData("town_square", "城镇广场", "阿尔多利亚繁华的中心。商贩们吆喝着叫卖，市民们忙碌地穿梭往来。",
                     "kingdom", "outdoor", 8, 0),
        LocationData("tavern", "金色酒壶", "一家温暖的酒馆，弥漫着麦芽酒和烤肉的气味。冒险者们围坐在炉火旁分享故事。",
                     "kingdom", "indoor", 6, 0),
        LocationData("market", "集市街", "一条长长的街道，两旁摆满了摊位，从新鲜农产品到异域工艺品应有尽有。",
                     "kingdom", "outdoor", 8, 0),
        LocationData("forest_edge", "森林边缘", "文明世界与黑暗森林的交界处。扭曲的树木在前方投下阴影。",
                     "kingdom", "outdoor", 4, 3),
        LocationData("darkwood", "暗木小径", "一条穿过古老森林的狭窄小径。诡异的声响在林间回荡。",
                     "kingdom", "outdoor", 2, 5),
        LocationData("ruins", "远古遗迹", "布满青苔和藤蔓的石制建筑。阴影中有东西在闪烁。",
                     "kingdom", "outdoor", 3, 7),
    ]
    for l in locs:
        location.add_location(l)
    # connections
    location.connect("town_square", "tavern")
    location.connect("town_square", "market")
    location.connect("town_square", "forest_edge")
    location.connect("forest_edge", "darkwood")
    location.connect("darkwood", "ruins")

    # ── NPC ──
    npc.npcs.clear()
    npc.add(NPCData(
        id="innkeeper", name="贝尔塔",
        description="一位眼神和善的健壮妇女，经营着这家酒馆。",
        location_id="tavern", personality="friendly",
        goal="让酒馆生意兴隆，顾客满意",
        desires=["好故事", "美酒"], mood="happy", relationship=20.0,
        status="正在擦拭酒杯",
    ))
    npc.add(NPCData(
        id="guard_captain", name="阿尔德里克爵士",
        description="一位身披旧铠的沧桑骑士，城镇卫队的队长。",
        location_id="town_square", personality="stern",
        goal="保护城镇免受威胁", fears=["辜负职责"],
        mood="neutral", relationship=0.0, status="正在巡逻",
    ))
    npc.add(NPCData(
        id="merchant", name="泽菲尔",
        description="一位走南闯北的商人，眼光毒辣，口才了得。",
        location_id="market", personality="charming",
        goal="通过贸易积累财富", desires=["稀有文物", "金币"],
        mood="happy", relationship=10.0, status="正在叫卖货物",
    ))

    # ── Self state ──
    self_state.name = "冒险者"
    self_state.health = 100
    self_state.max_health = 100
    self_state.attributes = {"力量": 12, "敏捷": 10, "体质": 11, "智力": 10, "感知": 10, "魅力": 10}
    self_state.status_effects.clear()
    self_state.current_location_id = "town_square"
    self_state.current_action = ""
    self_state.turn = 0
    self_state.hour = 8
    self_state.day = 1
    self_state.season = "春季"

    # ── Inventory ──
    inventory.items.clear()
    inventory.gold = 10
    inventory.add(ItemData("rusty_sword", "生锈的铁剑", "一把有些年头但依然锋利的剑。", 1, "weapon", True))
    inventory.add(ItemData("leather_armor", "皮甲", "简陋的皮革护甲，聊胜于无。", 1, "armor", True))
    inventory.add(ItemData("bread", "面包", "能填饱肚子的干粮。", 2, "consumable"))
    inventory.add(ItemData("torch", "火把", "能在黑暗中照明。", 1, "misc"))


# ── Tag-based world creation (used by the world builder UI) ──────────────

TAG_CATALOG: list[dict[str, Any]] = [
    {
        "id": "type", "name": "世界类型", "icon": "🌍", "multi": False,
        "tags": [
            {"id": "fantasy", "name": "奇幻", "desc": "剑与魔法的中世纪世界"},
            {"id": "scifi", "name": "科幻", "desc": "未来科技与星际探索"},
            {"id": "postapoc", "name": "末日", "desc": "文明毁灭后的废土"},
            {"id": "wuxia", "name": "武侠", "desc": "江湖恩怨与武学争锋"},
            {"id": "horror", "name": "恐怖", "desc": "诡异与未知的惊悚"},
        ],
    },
    {
        "id": "era", "name": "时代", "icon": "⏳", "multi": False,
        "tags": [
            {"id": "medieval", "name": "中世纪", "desc": "封建王国与冷兵器"},
            {"id": "ancient", "name": "古代", "desc": "远古文明的辉煌"},
            {"id": "modern", "name": "现代", "desc": "当代都市背景"},
            {"id": "future", "name": "未来", "desc": "高度发达的科技时代"},
        ],
    },
    {
        "id": "atmosphere", "name": "氛围", "icon": "🌫️", "multi": True,
        "tags": [
            {"id": "bright", "name": "明亮", "desc": "阳光、希望、生机"},
            {"id": "dark", "name": "黑暗", "desc": "压抑、阴森、绝望"},
            {"id": "mysterious", "name": "神秘", "desc": "迷雾、未知、谜团"},
            {"id": "chaotic", "name": "混乱", "desc": "战乱、无序、动荡"},
        ],
    },
    {
        "id": "terrain", "name": "地形", "icon": "🏞️", "multi": True,
        "tags": [
            {"id": "town", "name": "城镇", "desc": "人类聚居地"},
            {"id": "forest", "name": "森林", "desc": "茂密的林地"},
            {"id": "desert", "name": "沙漠", "desc": "干旱的荒原"},
            {"id": "mountain", "name": "山脉", "desc": "高耸的山峰"},
            {"id": "sea", "name": "海洋", "desc": "无垠的水域"},
            {"id": "underground", "name": "地下", "desc": "洞穴与地城"},
        ],
    },
    {
        "id": "magic", "name": "魔法等级", "icon": "✨", "multi": False,
        "tags": [
            {"id": "low", "name": "低魔", "desc": "魔法稀有而神秘"},
            {"id": "mid", "name": "中魔", "desc": "魔法常见但非普遍"},
            {"id": "high", "name": "高魔", "desc": "魔法无处不在"},
        ],
    },
    {
        "id": "danger", "name": "危险等级", "icon": "⚔️", "multi": False,
        "tags": [
            {"id": "low", "name": "低", "desc": "相对安全"},
            {"id": "mid", "name": "中", "desc": "危机四伏"},
            {"id": "high", "name": "高", "desc": "步步杀机"},
        ],
    },
]

_TYPE_NAME = {"fantasy": "奇幻", "scifi": "科幻", "postapoc": "末日", "wuxia": "武侠", "horror": "恐怖"}
_ERA_NAME = {"medieval": "封建中世纪", "ancient": "远古时代", "modern": "现代", "future": "未来纪元"}
_MAGIC_NAME = {"low": "低魔", "mid": "中魔", "high": "高魔"}
_DANGER_NAME = {"low": "较低", "mid": "适中", "high": "极高"}
_ATMO_NAME = {"bright": "阳光明媚，处处生机", "dark": "阴云密布，暗流涌动",
              "mysterious": "迷雾笼罩，神秘莫测", "chaotic": "动荡不安，烽烟四起"}
_TERRAIN_NAME = {"town": "城镇", "forest": "森林", "desert": "沙漠",
                 "mountain": "山脉", "sea": "海洋", "underground": "地下"}


def create_world_from_tags(
    tags: dict[str, list[str]],
    custom_description: str,
    worldview: WorldviewModule,
    location: LocationModule,
    npc: NPCModule,
    self_state: SelfStateModule,
    inventory: InventoryModule,
) -> dict[str, Any]:
    """Build a world from selected tags (template-based, LLM-agnostic).

    Returns a summary dict with counts for the UI.
    """
    wtype = (tags.get("type") or ["fantasy"])[0]
    era = (tags.get("era") or ["medieval"])[0]
    atmo = tags.get("atmosphere") or ["bright"]
    terrain = tags.get("terrain") or ["town"]
    magic = (tags.get("magic") or ["mid"])[0]
    danger = (tags.get("danger") or ["mid"])[0]

    wname = custom_description.strip()[:20] if custom_description.strip() else f"{_TYPE_NAME.get(wtype,'未知')}世界"

    # ── Worldview ──
    worldview.world_name = wname
    worldview.genre = _TYPE_NAME.get(wtype, wtype)
    worldview.era = _ERA_NAME.get(era, era)
    worldview.atmosphere = "、".join(_ATMO_NAME.get(a, a) for a in atmo)
    worldview.terrain = "、".join(_TERRAIN_NAME.get(t, t) for t in terrain)
    worldview.magic_level = _MAGIC_NAME.get(magic, magic)
    worldview.danger_level = _DANGER_NAME.get(danger, danger)
    worldview.description = custom_description.strip() or f"一个{worldview.atmosphere}的{worldview.genre}世界。"
    worldview.history = ""
    worldview.main_quest = "探索这片土地，揭开它隐藏的秘密。"
    worldview.factions = []

    # ── Location: a small map derived from terrain tags ──
    location.regions.clear()
    location.locations.clear()
    location.add_region(RegionData(id="start_region", name="起始之地", description=worldview.description, region_type="settlement"))

    base_danger = {"low": 1, "mid": 4, "high": 7}[danger]
    locs = [LocationData("town_center", "中心广场", "一切冒险的起点，人来人往。", "start_region", "outdoor", 8, 0)]
    terrain_locs = {
        "town": LocationData("market", "集市", "贩卖各种物资的喧闹集市。", "start_region", "outdoor", 8, 0),
        "forest": LocationData("forest", "幽暗森林", "林木遮天，潜藏未知生物。", "start_region", "outdoor", 4, base_danger),
        "desert": LocationData("desert", "荒芜沙漠", "黄沙漫天，寸步难行。", "start_region", "outdoor", 9, base_danger),
        "mountain": LocationData("mountain", "险峻山脉", "陡峭的山峰直插云霄。", "start_region", "outdoor", 7, base_danger),
        "sea": LocationData("harbor", "港口", "停泊着各式船只的海港。", "start_region", "outdoor", 8, 1),
        "underground": LocationData("cave", "幽深洞穴", "黑暗深处的地下世界。", "start_region", "dungeon", 2, base_danger + 1),
    }
    for t in terrain:
        if t in terrain_locs and terrain_locs[t].id not in location.locations:
            locs.append(terrain_locs[t])
    # a dangerous deep location
    locs.append(LocationData("depths", "未知深处", "据说藏有传说之物的地方。", "start_region", "dungeon", 1, min(10, base_danger + 3)))

    for l in locs:
        location.add_location(l)
    for l in locs[1:]:
        location.connect("town_center", l.id)
    location.connect(locs[1].id if len(locs) > 1 else "town_center", "depths")

    # ── NPC ──
    npc.npcs.clear()
    npc.add(NPCData("guide", "向导", "一位熟悉此地的引路人。", "town_center",
                    "friendly", "指引新人了解世界", mood="happy", relationship=15.0, status="正在等待旅人"))
    npc.add(NPCData("merchant0", "流浪商人", "到处兜售货物的小贩。", "town_center",
                    "charming", "赚取利润", mood="happy", relationship=0.0, status="正在摆摊"))

    # ── Self state ──
    self_state.name = "冒险者"
    self_state.health = 100
    self_state.max_health = 100
    self_state.attributes = {"力量": 10, "敏捷": 10, "体质": 10, "智力": 10, "感知": 10, "魅力": 10}
    self_state.status_effects.clear()
    self_state.current_location_id = "town_center"
    self_state.current_action = ""
    self_state.turn = 0
    self_state.hour = 8
    self_state.day = 1
    self_state.season = "春季"

    # ── Inventory ──
    inventory.items.clear()
    inventory.gold = 20
    inventory.add(ItemData("starter_weapon", "新手武器", "一把趁手的武器。", 1, "weapon", True))
    inventory.add(ItemData("bread", "面包", "干粮。", 3, "consumable"))
    inventory.add(ItemData("torch", "火把", "照明用。", 2, "misc"))

    return {
        "method": "tags",
        "world_name": wname,
        "locations": len(location.locations),
        "npcs": len(npc.npcs),
    }
