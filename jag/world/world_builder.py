"""World builder: tag-driven compositional world generation."""

from __future__ import annotations

import hashlib
import logging
import random
from typing import Any

from jag.agents.game_master import GameMaster
from jag.world.dynamic_npc_generator import DynamicNPCGenerator
from jag.world.npc import NPC, ScheduleEntry
from jag.world.world import WorldLocation, WorldRegion

logger = logging.getLogger(__name__)

# ── Tag Categories (frontend) ───────────────────────────────────────────

TAG_CATEGORIES: list[dict[str, Any]] = [
    {"id": "genre", "name": "类型", "icon": "📖", "multi": False, "tags": [
        {"id": "fantasy", "name": "奇幻", "desc": "剑与魔法的经典奇幻世界"},
        {"id": "scifi", "name": "科幻", "desc": "星际旅行与高科技的未来世界"},
        {"id": "postapoc", "name": "末日废土", "desc": "文明崩溃后的荒芜世界"},
        {"id": "wuxia", "name": "武侠仙侠", "desc": "江湖恩怨与修仙问道"},
        {"id": "mystery", "name": "现代悬疑", "desc": "充满谜团的现代都市"},
        {"id": "steampunk", "name": "蒸汽朋克", "desc": "蒸汽动力与齿轮的维多利亚时代"},
        {"id": "horror", "name": "克苏鲁恐怖", "desc": "不可名状的恐惧与疯狂"},
    ]},
    {"id": "era", "name": "时代", "icon": "⏳", "multi": False, "tags": [
        {"id": "ancient", "name": "远古", "desc": "文明初生的蛮荒时代"},
        {"id": "medieval", "name": "中世纪", "desc": "封建领主与骑士的时代"},
        {"id": "renaissance", "name": "文艺复兴", "desc": "艺术与科学萌芽的时代"},
        {"id": "industrial", "name": "工业革命", "desc": "机器取代手工的变革时代"},
        {"id": "modern", "name": "现代", "desc": "信息与技术高度发达"},
        {"id": "future", "name": "未来", "desc": "超越想象的遥远未来"},
    ]},
    {"id": "atmosphere", "name": "氛围", "icon": "🌅", "multi": True, "tags": [
        {"id": "light", "name": "轻松愉快", "desc": "欢乐与冒险并存的明快世界"},
        {"id": "dark", "name": "黑暗残酷", "desc": "生存不易的冷酷世界"},
        {"id": "epic", "name": "史诗恢弘", "desc": "命运交织的宏大叙事"},
        {"id": "mystery", "name": "神秘诡谲", "desc": "处处隐藏秘密与阴谋"},
        {"id": "peaceful", "name": "宁静祥和", "desc": "和平为主旋律的田园世界"},
        {"id": "chaotic", "name": "混乱动荡", "desc": "势力割据、冲突不断"},
    ]},
    {"id": "terrain", "name": "地形", "icon": "🏔", "multi": True, "tags": [
        {"id": "forest", "name": "密林", "desc": "广袤的森林与丛林"},
        {"id": "desert", "name": "荒漠", "desc": "黄沙万里的不毛之地"},
        {"id": "ocean", "name": "海洋群岛", "desc": "碧波万顷与星罗棋布的岛屿"},
        {"id": "mountain", "name": "高山", "desc": "巍峨险峻的崇山峻岭"},
        {"id": "city", "name": "都市", "desc": "繁华的城市与建筑群"},
        {"id": "underground", "name": "地下城", "desc": "深邃的地下洞穴与遗迹"},
        {"id": "swamp", "name": "沼泽", "desc": "毒雾弥漫的危险湿地"},
        {"id": "plains", "name": "草原", "desc": "一望无际的辽阔草原"},
    ]},
    {"id": "magic", "name": "魔法等级", "icon": "✨", "multi": False, "tags": [
        {"id": "none", "name": "无魔法", "desc": "纯粹的物理世界"},
        {"id": "low", "name": "低魔", "desc": "魔法稀少且被质疑"},
        {"id": "medium", "name": "中魔", "desc": "魔法存在但受限制"},
        {"id": "high", "name": "高魔", "desc": "魔法充斥每个角落"},
    ]},
    {"id": "danger", "name": "危险等级", "icon": "⚔", "multi": False, "tags": [
        {"id": "safe", "name": "安全", "desc": "以探索与社交为主"},
        {"id": "moderate", "name": "适中", "desc": "偶有危险的冒险"},
        {"id": "dangerous", "name": "危险", "desc": "步步惊心的生存挑战"},
        {"id": "deadly", "name": "致命", "desc": "随时可能丧命的绝境"},
    ]},
]


def get_all_tags() -> list[dict[str, Any]]:
    return TAG_CATEGORIES


# ════════════════════════════════════════════════════════════════════════
#  COMPOSITIONAL DATA POOLS
# ════════════════════════════════════════════════════════════════════════

# ── Genre data ─────────────────────────────────────────────────────────
# Each genre: hub/tavern names & descriptions, NPC roles, inventory

_GENRE: dict[str, dict[str, Any]] = {
    "fantasy": {
        "region_default": "艾尔文大陆", "region_type": "kingdom",
        "hub_names": ["村庄广场", "城镇中心", "集市路口", "石桥镇头"],
        "hub_descs": [
            "石板路交织的聚落，炊烟从茅草屋顶升起，旅人们在此交换消息。",
            "木质围墙内的定居点，广场上矗立着古老的守护雕像。",
            "道路交汇处的热闹集镇，商贩的叫卖声此起彼伏。",
        ],
        "tavern": ("旅者酒馆", [
            "温暖的壁炉映照着木质吧台，墙上挂着冒险者留下的旧盾。",
            "推开厚重的橡木门，麦酒的醇香扑面而来，角落里有人在低声吟唱。",
        ]),
        "npc_roles": ["酒馆老板", "流浪法师", "游侠", "铁匠", "草药师", "吟游诗人", "骑士队长"],
        "inventory": ["铁剑", "皮甲", "面包", "10枚金币"],
    },
    "scifi": {
        "region_default": "新星空间站", "region_type": "station",
        "hub_names": ["中央枢纽", "主控制室", "中转大厅", "对接平台"],
        "hub_descs": [
            "全息指示牌闪烁的交通枢纽，各色物种的旅客匆匆穿行。",
            "环形走廊交汇的核心区域，人工重力稳定运转，数据流在空中交织。",
            "巨大的透明穹顶下，星舰起降的蓝光映照着忙碌的人群。",
        ],
        "tavern": ("星际酒吧", [
            "合成饮品和全息娱乐设施供各物种放松，低频音乐在空气中震荡。",
            "霓虹灯光下，形形色色的外星种族举杯对饮，交易在暗处进行。",
        ]),
        "npc_roles": ["酒吧老板", "科学家", "走私客", "机械师", "AI管理员", "星际商人", "陆战队老兵"],
        "inventory": ["激光手枪", "防护服", "营养棒", "100信用点"],
    },
    "postapoc": {
        "region_default": "废土荒原", "region_type": "wasteland",
        "hub_names": ["避难所入口", "营地中心", "物资交换点", "废铁镇"],
        "hub_descs": [
            "幸存者们用废料搭建的安全区，铁丝网围出了脆弱的文明。",
            "废弃加油站改造的聚居点，篝火旁摆着换来的物资。",
            "地铁站改建的避难所出口，幸存者在此进行物物交换。",
        ],
        "tavern": ("废墟酒吧", [
            "零件拼凑的吧台后，劣质烈酒是最受欢迎的交易品。",
            "用油桶和钢板搭建的小酒吧，发电机嗡嗡作响，灯光忽明忽暗。",
        ]),
        "npc_roles": ["营地首领", "拾荒者", "变异医生", "武器商", "流浪战士", "技师"],
        "inventory": ["生锈的管子", "破旧的防毒面具", "罐头", "净水片"],
    },
    "wuxia": {
        "region_default": "云梦江湖", "region_type": "jianghu",
        "hub_names": ["清风镇", "渡口码头", "官道驿站", "落雁城"],
        "hub_descs": [
            "山脚下的热闹小镇，客栈茶楼鳞次栉比，来往的江湖人络绎不绝。",
            "连接各门各派的必经之地，石桥横跨碧水，柳絮随风飘扬。",
            "官道旁的古老驿站，快马扬尘，刀光剑影的故事在此流传。",
        ],
        "tavern": ("醉仙楼", [
            "镇上最好的酒楼，据说掌柜的曾是某大门派弟子，好酒配好故事。",
            "三层木楼酒香四溢，二楼凭栏可望远山，江湖传闻在这里比酒更烈。",
        ]),
        "npc_roles": ["酒楼掌柜", "独行剑客", "僧人", "药铺老板", "门派长老", "女侠"],
        "inventory": ["青铜剑", "粗布衣", "银两", "伤药"],
    },
    "mystery": {
        "region_default": "迷雾都市", "region_type": "city",
        "hub_names": ["中央广场", "地铁站", "市中心", "老城区"],
        "hub_descs": [
            "高楼间车水马龙的繁华地带，监控摄像头无声记录着一切。",
            "人流密集的换乘站，每个出口都通向不同的秘密。",
            "霓虹闪烁的都市中心，真相藏在每一扇亮着灯的窗户背后。",
        ],
        "tavern": ("深夜咖啡馆", [
            "凌晨两点仍有灯光的温暖角落，失眠者和线人各怀心事。",
            "复古装潢的小店，浓缩咖啡的苦涩混合着未解的谜团。",
        ]),
        "npc_roles": ["私家侦探", "黑客", "酒吧老板", "记者", "退休警察", "神秘委托人"],
        "inventory": ["笔记本", "手电筒", "手机", "证件"],
    },
    "steampunk": {
        "region_default": "齿轮城", "region_type": "industrial",
        "hub_names": ["中央钟楼", "蒸汽枢纽", "齿轮广场", "铜管街"],
        "hub_descs": [
            "巨大齿轮和管道构成的城市中心，蒸汽机车在头顶的铁轨上呼啸。",
            "黄铜铸就的钟楼广场，整点的汽笛声回荡在整座城市。",
            "铆钉密布的圆形广场，蒸汽管道从地面延伸向四面八方。",
        ],
        "tavern": ("铜壶酒馆", [
            "机械侍者端上冒着泡沫的蒸馏酒，齿轮装饰在墙上缓慢转动。",
            "铜管和风琴构成的奇异空间，每杯酒都带着蒸汽的灼热。",
        ]),
        "npc_roles": ["发明家", "机械师", "贵族", "飞艇船长", "炼金术士", "工会头目"],
        "inventory": ["蒸汽手枪", "护目镜", "齿轮工具包", "英镑"],
    },
    "horror": {
        "region_default": "阿卡姆镇", "region_type": "cursed_land",
        "hub_names": ["镇中心", "教堂废墟", "码头", "学院广场"],
        "hub_descs": [
            "居民回避彼此目光的小镇，空气中弥漫着不祥的低语。",
            "残存的秩序之地，但理智在此地是稀缺品。",
            "雾气笼罩的沿海小镇，渔船从不出海太远，因为……没人说得清原因。",
        ],
        "tavern": ("黑猫旅社", [
            "角落里总有低语声，但没人敢确认来源，旅客们紧握着各自的护身符。",
            "昏暗的油灯下，每个人都在假装没注意到墙上缓慢移动的影子。",
        ]),
        "npc_roles": ["图书管理员", "疯癫教授", "酒吧老板", "神秘猎人", "牧师", "流浪记者"],
        "inventory": ["手电筒", "日记本", "旧钥匙", "镇静剂"],
    },
}

# ── Terrain location pools ─────────────────────────────────────────────
# Descriptions are pre-composed (no {adj} placeholder), each location has
# rich text that works across genres.  Genre/era/atmosphere influence the
# light/danger numbers and NPC composition instead.

_TERRAIN_LOCS: dict[str, list[dict[str, Any]]] = {
    "forest": [
        {"id": "deep_forest", "name": "密林深处", "desc": "参天古树遮天蔽日，粗壮的藤蔓缠绕其间，远处传来不明生物的低吼声。", "type": "outdoor", "light": 3, "danger": 4},
        {"id": "forest_clearing", "name": "林中空地", "desc": "阳光透过树冠洒落，地面上散落着营火遗迹和不知名的足迹。", "type": "outdoor", "light": 6, "danger": 2},
        {"id": "ancient_tree", "name": "巨树", "desc": "一棵无法估量年龄的巨树拔地而起，树根延伸数十米，树洞深处似有微光闪烁。", "type": "outdoor", "light": 4, "danger": 3},
    ],
    "desert": [
        {"id": "oasis", "name": "绿洲", "desc": "荒漠中珍贵的水源地，几棵棕榈树投下唯一的阴凉，旅人在此短暂歇息。", "type": "outdoor", "light": 9, "danger": 2},
        {"id": "sandstorm_pass", "name": "风暴隘口", "desc": "沙暴频繁肆虐的狭窄通道，能见度极低，风声如同哀嚎。", "type": "outdoor", "light": 7, "danger": 5},
        {"id": "buried_temple", "name": "沙埋神殿", "desc": "半埋在黄沙中的远古遗迹，入口处风沙呼啸，壁画在剥落的墙壁上若隐若现。", "type": "indoor", "light": 2, "danger": 6},
    ],
    "ocean": [
        {"id": "harbor", "name": "港口", "desc": "繁忙的码头，各色船只来来往往，海风中混合着盐味和朗姆酒的气息。", "type": "outdoor", "light": 8, "danger": 1},
        {"id": "island", "name": "孤岛", "desc": "远离航线的小岛，据说藏有海盗的宝藏和不可告人的秘密。", "type": "outdoor", "light": 7, "danger": 4},
        {"id": "underwater_ruins", "name": "海底遗迹", "desc": "退潮时露出水面的建筑残骸，墙面上的符文至今无人能解。", "type": "indoor", "light": 3, "danger": 6},
    ],
    "mountain": [
        {"id": "mountain_path", "name": "山间栈道", "desc": "凿刻在悬崖上的窄路，一侧是万丈深渊，碎石不断滑落。", "type": "outdoor", "light": 7, "danger": 4},
        {"id": "peak", "name": "绝顶", "desc": "云雾缭绕的山巅，传说站在此处可以看见世界的尽头，风声如泣如诉。", "type": "outdoor", "light": 8, "danger": 5},
        {"id": "hermit_cave", "name": "隐修洞", "desc": "山腰处的隐秘洞穴，有人长期在此居住修行，石壁上刻满了文字。", "type": "indoor", "light": 3, "danger": 2},
    ],
    "city": [
        {"id": "market_district", "name": "商业区", "desc": "拥挤繁华的街区，各色摊位和商铺鳞次栉比，叫卖声不绝于耳。", "type": "outdoor", "light": 7, "danger": 1},
        {"id": "back_alley", "name": "暗巷", "desc": "贫民区的窄巷，阳光难以到达，可疑的身影在阴影中出没。", "type": "outdoor", "light": 3, "danger": 4},
        {"id": "tower_building", "name": "高塔", "desc": "矗立在城市中心的标志性建筑，从顶端可以俯瞰整个城区。", "type": "indoor", "light": 6, "danger": 2},
    ],
    "underground": [
        {"id": "tunnel", "name": "隧道", "desc": "向地底延伸的通道，空气阴冷潮湿，每一步的回声都令人不安。", "type": "indoor", "light": 2, "danger": 4},
        {"id": "underground_lake", "name": "地下暗湖", "desc": "幽蓝的水面在黑暗中微微发光，水下似乎有什么东西在缓慢游动。", "type": "indoor", "light": 2, "danger": 5},
        {"id": "lost_vault", "name": "失落宝库", "desc": "被遗忘的金库，厚重的铁门已被某种力量从内部破开，宝藏散落一地。", "type": "indoor", "light": 1, "danger": 7},
    ],
    "swamp": [
        {"id": "swamp_path", "name": "沼泽小径", "desc": "泥泞的小路蜿蜒前行，每走一步都可能陷入没膝的淤泥，蚊虫嗡嗡作响。", "type": "outdoor", "light": 4, "danger": 4},
        {"id": "witch_hut", "name": "沼泽小屋", "desc": "歪歪斜斜的木屋，门前挂满了干燥的草药和不明动物的骨头。", "type": "indoor", "light": 4, "danger": 3},
        {"id": "poison_pool", "name": "毒潭", "desc": "冒着气泡的浑浊水潭，空气中弥漫着令人窒息的硫磺味，寸草不生。", "type": "outdoor", "light": 3, "danger": 6},
    ],
    "plains": [
        {"id": "crossroads", "name": "十字路口", "desc": "一望无际的平原上唯一的标识，四条路通向未知的远方，风卷起尘土。", "type": "outdoor", "light": 9, "danger": 2},
        {"id": "nomad_camp", "name": "游牧营地", "desc": "游牧民族的临时营地，帐篷在风中猎猎作响，篝火旁飘着肉香。", "type": "outdoor", "light": 8, "danger": 1},
        {"id": "standing_stones", "name": "石柱阵", "desc": "草原上突兀矗立的巨石阵，据说在满月之夜会发出不明的嗡鸣声。", "type": "outdoor", "light": 7, "danger": 3},
    ],
}

# ── Magic level extra locations ────────────────────────────────────────

_MAGIC_LOCS: dict[str, list[dict[str, Any]]] = {
    "none": [],
    "low": [
        {"id": "old_shrine", "name": "废弃神龛", "desc": "残破的小神龛，香火已灭，但偶尔有人声称在此感受到异样的气息。", "type": "indoor", "light": 4, "danger": 2},
    ],
    "medium": [
        {"id": "shrine", "name": "神殿", "desc": "祭祀场所，石台上残留着微弱的光芒，祈祷者在此寻求启示。", "type": "indoor", "light": 4, "danger": 3},
    ],
    "high": [
        {"id": "magic_academy", "name": "魔法学院", "desc": "宏伟的建筑群内，学徒们在半空中练习咒语，各色魔法光芒交织闪烁。", "type": "indoor", "light": 6, "danger": 2},
        {"id": "ley_line", "name": "灵脉节点", "desc": "能量汇聚之处，空气中闪烁着肉眼可见的魔力粒子，令人头皮发麻。", "type": "outdoor", "light": 5, "danger": 4},
    ],
}

# ── NPC role pools by genre ────────────────────────────────────────────

_NPC_ROLES: dict[str, list[dict[str, Any]]] = {
    "fantasy": [
        {"id": "tavern_owner", "role": "酒馆老板", "personality": "friendly", "goal": "让每位旅客都感到宾至如归", "activity": "照看吧台"},
        {"id": "wandering_mage", "role": "流浪法师", "personality": "curious", "goal": "寻找失落的远古魔法典籍", "activity": "研究魔法"},
        {"id": "ranger", "role": "游侠", "personality": "stern", "goal": "守护这片土地免受侵害", "activity": "巡逻边境"},
        {"id": "blacksmith", "role": "铁匠", "personality": "friendly", "goal": "锻造出传说中的神兵利器", "activity": "打铁铸剑"},
        {"id": "herbalist", "role": "草药师", "personality": "neutral", "goal": "收集稀有草药治愈伤员", "activity": "采药炼膏"},
        {"id": "bard", "role": "吟游诗人", "personality": "charming", "goal": "谱写流传千古的英雄史诗", "activity": "弹琴吟唱"},
        {"id": "knight", "role": "骑士队长", "personality": "stern", "goal": "维护秩序与正义", "activity": "操练士兵"},
        {"id": "thief", "role": "盗贼", "personality": "charming", "goal": "偷到世间最珍贵的宝物", "activity": "潜行探查"},
    ],
    "scifi": [
        {"id": "bar_owner", "role": "酒吧老板", "personality": "friendly", "goal": "在这混乱的星域保持中立地位", "activity": "调酒"},
        {"id": "scientist", "role": "科学家", "personality": "curious", "goal": "完成改变历史的突破性研究", "activity": "进行实验"},
        {"id": "smuggler", "role": "走私客", "personality": "charming", "goal": "攒够信用点金盆洗手", "activity": "秘密交易"},
        {"id": "mechanic", "role": "机械师", "personality": "friendly", "goal": "修复那台传说中的远古机器", "activity": "维修飞船"},
        {"id": "ai_admin", "role": "AI管理员", "personality": "neutral", "goal": "确保所有系统稳定运行", "activity": "监控数据"},
        {"id": "trader", "role": "星际商人", "personality": "charming", "goal": "垄断稀有矿物的贸易航线", "activity": "谈生意"},
        {"id": "veteran", "role": "退役老兵", "personality": "stern", "goal": "忘掉过去的星际战争", "activity": "训练"},
        {"id": "hacker", "role": "黑客", "personality": "curious", "goal": "破解最高级别的安全防火墙", "activity": "入侵网络"},
    ],
    "postapoc": [
        {"id": "camp_leader", "role": "营地首领", "personality": "stern", "goal": "让所有人在这片废土上活下去", "activity": "管理营地"},
        {"id": "scavenger", "role": "拾荒者", "personality": "curious", "goal": "找到传说中的旧世界物资库", "activity": "搜索废墟"},
        {"id": "doctor", "role": "变异医生", "personality": "friendly", "goal": "研制抗辐射血清拯救变异者", "activity": "救治伤员"},
        {"id": "arms_dealer", "role": "武器商", "personality": "charming", "goal": "成为废土最大的军火供应商", "activity": "交易武器"},
        {"id": "warrior", "role": "流浪战士", "personality": "stern", "goal": "为死去的同伴复仇", "activity": "战斗训练"},
        {"id": "tech", "role": "技师", "personality": "curious", "goal": "修好通讯设备联系其他幸存者据点", "activity": "修理设备"},
    ],
    "wuxia": [
        {"id": "innkeeper", "role": "酒楼掌柜", "personality": "friendly", "goal": "守护门派的最后传承", "activity": "经营酒楼"},
        {"id": "swordsman", "role": "独行剑客", "personality": "stern", "goal": "寻找值得拔剑的对手", "activity": "练剑悟道"},
        {"id": "monk", "role": "僧人", "personality": "neutral", "goal": "度化有缘人脱离苦海", "activity": "诵经参禅"},
        {"id": "apothecary", "role": "药铺老板", "personality": "friendly", "goal": "炼制传说中的仙丹妙药", "activity": "采药炼丹"},
        {"id": "elder", "role": "门派长老", "personality": "stern", "goal": "重振门派昔日荣光", "activity": "教授弟子"},
        {"id": "swordswoman", "role": "女侠", "personality": "curious", "goal": "查明灭门惨案的幕后真凶", "activity": "行侠仗义"},
        {"id": "beggar", "role": "乞丐帮主", "personality": "charming", "goal": "搜集江湖上所有情报", "activity": "打探消息"},
    ],
    "mystery": [
        {"id": "detective", "role": "私家侦探", "personality": "curious", "goal": "破解那桩悬而未决的连环案", "activity": "调查线索"},
        {"id": "hacker", "role": "黑客", "personality": "neutral", "goal": "揭露隐藏在权力背后的阴谋", "activity": "编程破解"},
        {"id": "bar_owner", "role": "酒吧老板", "personality": "friendly", "goal": "守住自己不可告人的秘密", "activity": "擦杯子"},
        {"id": "journalist", "role": "记者", "personality": "curious", "goal": "发表轰动全国的独家报道", "activity": "采访调查"},
        {"id": "ex_cop", "role": "退休警察", "personality": "stern", "goal": "在体制之外继续追查旧案", "activity": "翻阅卷宗"},
        {"id": "client", "role": "神秘委托人", "personality": "charming", "goal": "找到失踪的亲人", "activity": "等待回音"},
    ],
    "steampunk": [
        {"id": "inventor", "role": "发明家", "personality": "curious", "goal": "完成足以改变世界的永动机", "activity": "发明创造"},
        {"id": "mechanic", "role": "机械师", "personality": "friendly", "goal": "维护城市赖以运转的蒸汽核心", "activity": "维修管道"},
        {"id": "noble", "role": "贵族", "personality": "charming", "goal": "扩大家族的势力版图", "activity": "社交斡旋"},
        {"id": "airship_captain", "role": "飞艇船长", "personality": "stern", "goal": "发现传说中的新大陆", "activity": "驾驶飞艇"},
        {"id": "alchemist", "role": "炼金术士", "personality": "curious", "goal": "破解贤者之石的终极配方", "activity": "化学实验"},
        {"id": "union_boss", "role": "工会头目", "personality": "stern", "goal": "为底层工人争取应有的权益", "activity": "组织工人"},
    ],
    "horror": [
        {"id": "librarian", "role": "图书管理员", "personality": "neutral", "goal": "保管那些不该被阅读的禁书", "activity": "整理书架"},
        {"id": "professor", "role": "疯癫教授", "personality": "curious", "goal": "理解那些不该被理解的禁忌知识", "activity": "疯狂研究"},
        {"id": "bar_owner", "role": "酒吧老板", "personality": "friendly", "goal": "在天亮之前保持清醒", "activity": "擦拭吧台"},
        {"id": "hunter", "role": "神秘猎人", "personality": "stern", "goal": "猎杀那些不可名状的存在", "activity": "追踪异象"},
        {"id": "priest", "role": "牧师", "personality": "neutral", "goal": "用信仰对抗侵蚀理智的黑暗", "activity": "祈祷守望"},
        {"id": "reporter", "role": "流浪记者", "personality": "curious", "goal": "记录下真相——哪怕没人会相信", "activity": "写日记"},
    ],
}

# NPC name pools by genre
_NPC_NAMES: dict[str, list[str]] = {
    "fantasy": ["艾琳", "索林", "贝拉", "贾维斯", "格里芬", "莉娜", "老麦克", "铁锤汤姆", "梅丽莎", "奥丁"],
    "scifi": ["泽克", "林博士", "影子", "诺娃", "铁壁", "星辰", "幽灵", "老K", "阿尔法", "维加"],
    "postapoc": ["老铁", "疤痕", "灰烬", "独眼", "小刀", "老鼠", "铁锈", "毒蛇", "火花", "断指"],
    "wuxia": ["醉道人", "独孤", "空明", "药婆婆", "青鸾", "寒霜", "铁掌", "玉面", "飞燕", "断水"],
    "mystery": ["陈探长", "黑影", "李薇", "老赵", "K先生", "阿雪", "刀疤", "眼镜", "午夜", "方记者"],
    "steampunk": ["阿奇博尔德", "维多利亚", "齿轮杰克", "铜夫人", "蒸汽比尔", "铆钉", "勋爵", "发条", "黄铜", "烟囱"],
    "horror": ["阿卡姆教授", "暗影", "赫伯特", "老管家", "梦游者", "低语", "黑袍", "苍白", "密典", "无名"],
}

# ── Atmosphere modifiers ───────────────────────────────────────────────

_ATMO_MOD: dict[str, dict[str, Any]] = {
    "light":    {"tone": "阳光明媚，处处生机。", "light_mod": 2, "danger_mod": -1},
    "dark":     {"tone": "阴影笼罩，危机四伏。", "light_mod": -2, "danger_mod": 2},
    "epic":     {"tone": "恢弘的气势弥漫在空气中，命运的齿轮正在转动。", "light_mod": 0, "danger_mod": 1},
    "mystery":  {"tone": "每个角落都藏着秘密，真相扑朔迷离。", "light_mod": -1, "danger_mod": 0},
    "peaceful": {"tone": "宁静祥和，岁月静好。", "light_mod": 1, "danger_mod": -2},
    "chaotic":  {"tone": "混乱与冲突无处不在，秩序已然崩塌。", "light_mod": -1, "danger_mod": 3},
}

# ── Era metadata ───────────────────────────────────────────────────────

_ERA_INFO: dict[str, dict[str, Any]] = {
    "ancient":     {"label": "远古蛮荒时代", "light_mod": -1},
    "medieval":    {"label": "封建中世纪", "light_mod": 0},
    "renaissance": {"label": "启蒙时代", "light_mod": 0},
    "industrial":  {"label": "蒸汽工业时代", "light_mod": 1},
    "modern":      {"label": "信息时代", "light_mod": 2},
    "future":      {"label": "超维未来时代", "light_mod": 2},
}

# ── Danger base modifier ──────────────────────────────────────────────

_DANGER_BASE: dict[str, int] = {"safe": -2, "moderate": 0, "dangerous": 3, "deadly": 5}

# ── Starting inventory ─────────────────────────────────────────────────

_INVENTORIES: dict[str, list[str]] = {
    "fantasy": ["铁剑", "皮甲", "面包", "10枚金币"],
    "scifi": ["激光手枪", "防护服", "营养棒", "100信用点"],
    "postapoc": ["生锈的管子", "破旧的防毒面具", "罐头", "净水片"],
    "wuxia": ["青铜剑", "粗布衣", "银两", "伤药"],
    "mystery": ["笔记本", "手电筒", "手机", "证件"],
    "steampunk": ["蒸汽手枪", "护目镜", "齿轮工具包", "英镑"],
    "horror": ["手电筒", "日记本", "旧钥匙", "镇静剂"],
}

# ════════════════════════════════════════════════════════════════════════
#  WORLD BUILDER
# ════════════════════════════════════════════════════════════════════════

class WorldBuilder:
    """Build custom worlds compositionally from tags and descriptions."""

    def __init__(self, gm: GameMaster) -> None:
        self.gm = gm
        self._state: dict[str, Any] = {}

    def build_from_tags(
        self,
        world_name: str = "",
        tags: dict[str, list[str]] | None = None,
        description: str = "",
        background_npc_count: int = 0,
        background_npc_seed: int | None = None,
    ) -> dict[str, Any]:
        self._parse_tags(world_name, tags, description)
        self.build_step_region()
        step_locs = self.build_step_locations()
        # Default: 2 background NPCs per location if count not specified
        if background_npc_count == 0 and step_locs.get("count", 0) > 0:
            background_npc_count = step_locs["count"] * 2
        self.build_step_npcs(
            background_npc_count=background_npc_count,
            background_npc_seed=background_npc_seed,
        )
        step_lore = self.build_step_lore()
        result = self.build_step_finalize(step_lore.get("lore"))
        return result

    # ── Step-by-step build (for progressive UI) ─────────────────────

    def _parse_tags(
        self,
        world_name: str = "",
        tags: dict[str, list[str]] | None = None,
        description: str = "",
    ) -> None:
        self.gm.clear_world()
        tags = tags or {}
        genre = (tags.get("genre", ["fantasy"]) or ["fantasy"])[0]
        era = (tags.get("era", ["medieval"]) or ["medieval"])[0]
        atmosphere = tags.get("atmosphere", [])
        terrain = tags.get("terrain", [])
        magic = (tags.get("magic", ["medium"]) or ["medium"])[0]
        danger = (tags.get("danger", ["moderate"]) or ["moderate"])[0]

        g = _GENRE.get(genre, _GENRE["fantasy"])
        rng = self._tag_rng(tags)
        era_info = _ERA_INFO.get(era, _ERA_INFO["medieval"])
        danger_base = _DANGER_BASE.get(danger, 0)
        atmo_light = sum(_ATMO_MOD.get(a, {}).get("light_mod", 0) for a in atmosphere)
        atmo_danger = sum(_ATMO_MOD.get(a, {}).get("danger_mod", 0) for a in atmosphere)
        era_light = era_info.get("light_mod", 0)

        self._state = {
            "world_name": world_name,
            "description": description,
            "genre": genre, "era": era,
            "atmosphere": atmosphere, "terrain": terrain,
            "magic": magic, "danger": danger,
            "g": g, "rng": rng,
            "era_info": era_info,
            "danger_base": danger_base,
            "atmo_light": atmo_light,
            "atmo_danger": atmo_danger,
            "era_light": era_light,
            "region_name": world_name or g["region_default"],
        }

    def build_step_region(self) -> dict[str, Any]:
        """Step 1: Create the region."""
        s = self._state
        g = s["g"]
        atmo_tones = " ".join(_ATMO_MOD.get(a, {}).get("tone", "") for a in s["atmosphere"])
        desc_parts = [p for p in [s["description"], atmo_tones, s["era_info"].get("label", "")] if p]
        region_desc = " ".join(desc_parts) if desc_parts else "由玩家创建的世界。"

        region = WorldRegion(
            id="main_region", name=s["region_name"],
            description=region_desc,
            region_type=g.get("region_type", "kingdom"),
        )
        self.gm.world.add_region(region)
        self.gm.weather.add_region(region.id)
        s["region"] = region
        return {"step": "region", "name": region.name, "description": region.description}

    def build_step_locations(self) -> dict[str, Any]:
        """Step 2: Create locations."""
        s = self._state
        g = s["g"]
        loc_defs: list[dict[str, Any]] = []

        hub_name = g["hub_names"][0]
        hub_desc = g["hub_descs"][0]
        loc_defs.append({"id": "hub", "name": hub_name, "desc": hub_desc,
                         "type": "outdoor", "light": 8, "danger": 0})

        tav_name, tav_descs = g["tavern"]
        loc_defs.append({"id": "tavern", "name": tav_name, "desc": tav_descs[0],
                         "type": "indoor", "light": 6, "danger": 0})

        terrain = s["terrain"]
        if not terrain:
            terrain = ["city", "forest"]
        for t in terrain:
            for loc in _TERRAIN_LOCS.get(t, []):
                loc_defs.append({"id": loc["id"], "name": loc["name"],
                                 "desc": loc["desc"], "type": loc["type"],
                                 "light": loc["light"], "danger": loc["danger"]})

        for loc in _MAGIC_LOCS.get(s["magic"], []):
            loc_defs.append({"id": loc["id"], "name": loc["name"],
                             "desc": loc["desc"], "type": loc["type"],
                             "light": loc["light"], "danger": loc["danger"]})

        locations: list[WorldLocation] = []
        for ld in loc_defs:
            is_safe = ld["id"] in ("hub", "tavern")
            light = max(1, min(10, ld["light"] + s["era_light"] + (s["atmo_light"] if not is_safe else 0)))
            dng = ld["danger"]
            if not is_safe:
                dng = max(0, min(10, ld["danger"] + s["danger_base"] + s["atmo_danger"]))
            locations.append(WorldLocation(
                id=ld["id"], name=ld["name"], description=ld["desc"],
                region_id="main_region", location_type=ld["type"],
                light_level=light, danger_level=dng,
            ))

        self._build_connections(locations)
        for loc in locations:
            self.gm.world.add_location(loc)
        s["locations"] = locations
        return {"step": "locations", "count": len(locations), "names": [l.name for l in locations]}

    def build_step_npcs(
        self,
        background_npc_count: int = 0,
        background_npc_seed: int | None = None,
    ) -> dict[str, Any]:
        """Step 3: Create NPCs.

        Uses hybrid strategy:
        - Core NPCs (tavern_owner, knight, blacksmith): template-based for consistency
        - Background NPCs: dynamically generated via DynamicNPCGenerator for quantity

        Args:
            background_npc_count: Number of extra background NPCs to generate (0 = disabled)
            background_npc_seed: Random seed for reproducible background NPC generation
        """
        s = self._state
        genre = s["genre"]
        rng = s["rng"]
        locations = s.get("locations", [])

        # ── Core (template-based) NPCs ─────────────────────────────
        npc_pool = list(_NPC_ROLES.get(genre, _NPC_ROLES["fantasy"]))
        fixed_ids = ["tavern_owner", "knight", "blacksmith"]
        genre_fixed_map = {
            "fantasy": {"tavern_owner": "tavern_owner", "knight": "knight", "blacksmith": "blacksmith"},
            "scifi": {"tavern_owner": "bar_owner", "knight": "veteran", "blacksmith": "mechanic"},
            "postapoc": {"tavern_owner": "camp_leader", "knight": "warrior", "blacksmith": "tech"},
            "wuxia": {"tavern_owner": "innkeeper", "knight": "swordsman", "blacksmith": "apothecary"},
            "mystery": {"tavern_owner": "bar_owner", "knight": "ex_cop", "blacksmith": "detective"},
            "steampunk": {"tavern_owner": "inventor", "knight": "airship_captain", "blacksmith": "mechanic"},
            "horror": {"tavern_owner": "bar_owner", "knight": "hunter", "blacksmith": "librarian"},
        }
        fixed_map = genre_fixed_map.get(genre, genre_fixed_map["fantasy"])
        fixed_npcs = []
        for fixed_id in fixed_ids:
            role_id = fixed_map.get(fixed_id)
            match = [n for n in npc_pool if n["id"] == role_id]
            if match:
                fixed_npcs.append(match[0])
                npc_pool.remove(match[0])

        rng.shuffle(npc_pool)
        sorted_locs = sorted(locations, key=lambda l: l.danger_level)
        half = len(sorted_locs) // 2 + 1
        npc_loc_pool = sorted_locs[:half]
        extras_needed = max(0, min(len(npc_pool), max(1, len(npc_loc_pool) - len(fixed_npcs))))
        selected_extras = npc_pool[:extras_needed]
        all_selected = fixed_npcs + selected_extras

        name_pool = list(_NPC_NAMES.get(genre, _NPC_NAMES["fantasy"]))
        rng.shuffle(name_pool)

        npcs: list[NPC] = []
        npc_info = []
        for i, npc_def in enumerate(all_selected):
            if i == 0:
                loc_id = "tavern"
            elif i == 1:
                loc_id = "hub"
            else:
                loc_id = npc_loc_pool[(i - 2) % len(npc_loc_pool)].id
            name = name_pool[i] if i < len(name_pool) else f"NPC_{i}"
            npcs.append(NPC(
                id=npc_def["id"], name=name,
                description=f"{npc_def['role']}。{npc_def['goal']}。",
                location_id=loc_id,
                personality=npc_def["personality"],
                goal=npc_def["goal"],
                schedule=[
                    ScheduleEntry(hour_start=6, hour_end=22, activity=npc_def["activity"], location_id=loc_id),
                    ScheduleEntry(hour_start=22, hour_end=6, activity="休息", location_id=loc_id),
                ],
            ))
            npc_info.append({"Name": name, "role": npc_def["role"], "location_id": loc_id})

        # ── Background (dynamically generated) NPCs ────────────────
        bg_npc_count = 0
        if background_npc_count > 0:
            bg_gen = DynamicNPCGenerator(
                genre=genre,
                seed=background_npc_seed,
                min_traits=2,
                max_traits=4,
            )
            loc_ids = [loc.id for loc in locations]
            bg_batch = bg_gen.generate_batch(background_npc_count, loc_ids)

            for g in bg_batch:
                npcs.append(g.npc)
                npc_info.append({
                    "name": g.npc.name,
                    "role": g.role["name"],
                    "location_id": g.npc.location_id,
                    "traits": [t["name"] for t in g.traits],
                })
            bg_npc_count = len(bg_batch)

        # Register all NPCs
        for npc in npcs:
            self.gm.world.add_character(npc.id, {
                "location_id": npc.location_id, "name": npc.name, "type": "npc",
            })
            self.gm.tick_engine.register_npc(npc)
        s["npcs"] = npcs

        return {
            "step": "npcs",
            "count": len(npcs),
            "core_count": len(fixed_npcs) + extras_needed,
            "background_count": bg_npc_count,
            "npcs": npc_info,
        }

    def build_step_lore(self) -> dict[str, Any]:
        """Step 4: Generate lore."""
        s = self._state
        locations = s.get("locations", [])
        npcs = s.get("npcs", [])
        lore = self._generate_lore(
            s["genre"], s["era"], s["atmosphere"], s["terrain"],
            s["magic"], s["danger"], s["region_name"],
            locations, npcs,
        )
        s["lore"] = lore
        return {"step": "lore", "lore": lore}

    def build_step_finalize(self, lore: dict[str, Any] | None = None) -> dict[str, Any]:
        """Step 5: Finalize - add player and store lore."""
        s = self._state
        lore = lore or s.get("lore", {})
        genre = s["genre"]
        player_loc = "hub" if "hub" in self.gm.world.locations else next(iter(self.gm.world.locations), "")
        self.gm.world.add_character(self.gm.player_id, {
            "location_id": player_loc,
            "inventory": _INVENTORIES.get(genre, _INVENTORIES["fantasy"]),
            "name": "冒险者", "type": "player",
        })
        if lore:
            self.gm.world_lore = lore
        return {
            "ok": True, "world_name": s["region_name"],
            "locations": len(self.gm.world.locations),
            "npcs": len(self.gm.tick_engine._npcs),
            "genre": genre, "description": s["description"],
            "tags_applied": {"genre": s["genre"], "era": s["era"],
                             "atmosphere": s["atmosphere"], "terrain": s["terrain"],
                             "magic": s["magic"], "danger": s["danger"]},
        }

    def _build_connections(self, locations: list[WorldLocation]) -> None:
        if len(locations) < 2:
            return
        loc_map = {l.id: l for l in locations}
        ids = [l.id for l in locations]

        # Hub connects to tavern + first 2 other locations
        hub = loc_map["hub"]
        hub_conns = ["tavern"]
        for lid in ids:
            if lid not in ("hub", "tavern") and len(hub_conns) < 3:
                hub_conns.append(lid)
        hub.connected = hub_conns

        # Tavern connects to hub
        loc_map["tavern"].connected = ["hub"]

        # Chain remaining locations
        non_hub = [l for l in locations if l.id not in ("hub", "tavern")]
        for i, loc in enumerate(non_hub):
            conns: list[str] = []
            if i == 0 and "hub" not in conns:
                conns.append("hub")
            if i > 0:
                conns.append(non_hub[i - 1].id)
            if i < len(non_hub) - 1:
                conns.append(non_hub[i + 1].id)
            loc.connected = conns

        # Tavern connects to first non-hub
        if non_hub and non_hub[0].id not in loc_map["tavern"].connected:
            loc_map["tavern"].connected.append(non_hub[0].id)
            if "tavern" not in non_hub[0].connected:
                non_hub[0].connected.append("tavern")

    # ── Deterministic RNG ──────────────────────────────────────────────

    def _tag_rng(self, tags: dict) -> random.Random:
        seed = int(hashlib.md5(str(sorted(tags.items())).encode()).hexdigest()[:8], 16)
        return random.Random(seed)

    # ── Lore generation ─────────────────────────────────────────────────

    def _generate_lore(
        self, genre: str, era: str, atmosphere: list[str], terrain: list[str],
        magic: str, danger: str, region_name: str,
        locations: list[WorldLocation], npcs: list[NPC],
    ) -> dict[str, Any]:
        g = _GENRE.get(genre, _GENRE["fantasy"])
        era_info = _ERA_INFO.get(era, _ERA_INFO["medieval"])
        atmo_tones = " ".join(_ATMO_MOD.get(a, {}).get("tone", "") for a in atmosphere)
        terrain_names = "、".join(
            next((t["name"] for cat in TAG_CATEGORIES if cat["id"] == "terrain"
                  for t in cat["tags"] if t["id"] == ter), ter)
            for ter in terrain
        ) if terrain else "多样"

        magic_name = next(
            (t["name"] for cat in TAG_CATEGORIES if cat["id"] == "magic"
             for t in cat["tags"] if t["id"] == magic), magic)
        danger_name = next(
            (t["name"] for cat in TAG_CATEGORIES if cat["id"] == "danger"
             for t in cat["tags"] if t["id"] == danger), danger)

        # Main quest: derive from genre
        main_quests = {
            "fantasy": "传说中的黑暗领主正在集结大军，你必须找到传说中的神器，联合各势力，在末日降临前阻止他。",
            "scifi": "星区核心的能源站即将失控，整个星系面临毁灭。你需要找到故障源头，修复或摧毁它。",
            "postapoc": "废土深处有一座传说中完好无损的旧世界避难所，那里有重建文明的希望。找到它。",
            "wuxia": "武林秘籍《天机卷》重现江湖，各门派蠢蠢欲动。你必须抢在阴谋得逞前揭开背后的真相。",
            "mystery": "一连串离奇的失踪案指向城市最深处的秘密组织。真相就藏在阴影中，但你每接近一步，危险就增加一分。",
            "steampunk": "蒸汽核心的稳定性正在崩溃，整座城市随时可能爆炸。你必须找到传说中的远古蓝图来修复它。",
            "horror": "古老的邪恶正在苏醒，理智在恐惧中逐渐瓦解。你必须找到封印它的方法——在它彻底降临之前。",
        }

        lore = {
            "world_name": region_name,
            "genre": genre,
            "era": era_info.get("label", ""),
            "atmosphere": atmo_tones,
            "terrain": terrain_names,
            "magic_level": magic_name,
            "danger_level": danger_name,
            "description": f"这是一个{g.get('region_default', '未知')}风格的世界。{atmo_tones}",
            "history": f"这片土地在{era_info.get('label', '远古')}时期便有人类活动的痕迹。历经无数变迁，如今形成了以{region_name}为中心的格局。{atmo_tones}",
            "factions": [],
            "main_quest": main_quests.get(genre, "探索这个世界，发现隐藏的秘密。"),
            "npcs": [
                {"name": n.name, "role": n.goal, "location": next(
                    (l.name for l in locations if l.id == n.location_id), n.location_id)}
                for n in npcs
            ],
            "locations": [
                {"name": l.name, "description": l.description, "danger": l.danger_level}
                for l in locations
            ],
        }
        return lore

    # ── LLM generation ─────────────────────────────────────────────────

    async def build_with_llm(
        self, world_name: str = "", tags: dict[str, list[str]] | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        self.gm.clear_world()
        tags = tags or {}
        llm_cfg = self.gm.config.llm.default
        if not llm_cfg.api_key or llm_cfg.api_key == "your-api-key-here":
            logger.info("LLM not configured, falling back to tag-based generation")
            return self.build_from_tags(world_name, tags, description)

        try:
            llm = self.gm._get_llm("narrator")
            genre = (tags.get("genre", ["fantasy"]) or ["fantasy"])[0]
            era = (tags.get("era", ["medieval"]) or ["medieval"])[0]
            atmosphere = tags.get("atmosphere", [])
            terrain = tags.get("terrain", [])
            magic = (tags.get("magic", ["medium"]) or ["medium"])[0]
            danger = (tags.get("danger", ["moderate"]) or ["moderate"])[0]

            tag_names = {}
            for cat in TAG_CATEGORIES:
                for t in cat["tags"]:
                    tag_names[t["id"]] = t["name"]

            prompt = f"""请用JSON格式创建一个RPG游戏世界，要求如下：

世界名称: {world_name or '由AI生成'}
类型: {tag_names.get(genre, genre)}
时代: {tag_names.get(era, era)}
氛围: {'、'.join(tag_names.get(a, a) for a in atmosphere) or '适中'}
地形: {'、'.join(tag_names.get(t, t) for t in terrain) or '多样'}
魔法等级: {tag_names.get(magic, magic)}
危险等级: {tag_names.get(danger, danger)}
玩家额外描述: {description or '无特别要求'}

请输出以下JSON结构（所有文字使用中文）:
{{
  "region_name": "区域名称",
  "region_description": "区域描述",
  "locations": [
    {{"id": "英文id", "name": "地点名称", "description": "地点描述", "type": "indoor或outdoor", "light_level": 1-10, "danger_level": 0-10}}
  ],
  "connections": {{"地点id": ["连接的地点id"]}},
  "npcs": [
    {{"id": "英文id", "name": "NPC名称", "description": "NPC描述", "location_id": "地点id", "personality": "friendly/stern/curious/charming/neutral", "goal": "NPC目标"}}
  ]
}}

要求：创建6-8个地点（第一个id=hub为安全中心），4-6个NPC分散在不同地点。只输出JSON。"""

            response = await llm.complete(prompt, system="你是一个专业的RPG世界设计师。严格按照JSON格式输出。")
            text = response.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
            import json
            world_data = json.loads(text)
            return self._apply_llm_world(world_name, world_data, tags)
        except Exception as e:
            logger.warning("LLM world generation failed: %s, falling back", e)
            return self.build_from_tags(world_name, tags, description)

    async def build_with_llm_step_by_step(
        self, world_name: str = "", tags: dict[str, list[str]] | None = None,
        description: str = "",
        progress_callback: Any = None,
    ) -> dict[str, Any]:
        """Build world with LLM step by step, with progress callbacks.
        
        Args:
            world_name: Name of the world
            tags: World tags
            description: Player's description
            progress_callback: Async callback function(step, data) for progress updates
        """
        self.gm.clear_world()
        tags = tags or {}
        llm_cfg = self.gm.config.llm.default
        if not llm_cfg.api_key or llm_cfg.api_key == "your-api-key-here":
            logger.info("LLM not configured, falling back to tag-based generation")
            if progress_callback:
                await progress_callback("fallback", {"message": "LLM未配置，使用模板生成"})
            return self.build_from_tags(world_name, tags, description)

        async def _report(step: str, data: dict[str, Any]) -> None:
            if progress_callback:
                try:
                    await progress_callback(step, data)
                except Exception:
                    pass

        try:
            llm = self.gm._get_llm("narrator")
            genre = (tags.get("genre", ["fantasy"]) or ["fantasy"])[0]
            era = (tags.get("era", ["medieval"]) or ["medieval"])[0]
            atmosphere = tags.get("atmosphere", [])
            terrain = tags.get("terrain", [])
            magic = (tags.get("magic", ["medium"]) or ["medium"])[0]
            danger = (tags.get("danger", ["moderate"]) or ["moderate"])[0]

            tag_names = {}
            for cat in TAG_CATEGORIES:
                for t in cat["tags"]:
                    tag_names[t["id"]] = t["name"]

            # Step 1: Generate region and locations
            await _report("generating_locations", {
                "message": "AI正在构思世界区域和地点...",
                "step": 1,
                "total": 4,
            })

            loc_prompt = f"""请用JSON格式创建RPG游戏世界的区域和地点，要求如下：

世界名称: {world_name or '由AI生成'}
类型: {tag_names.get(genre, genre)}
时代: {tag_names.get(era, era)}
氛围: {'、'.join(tag_names.get(a, a) for a in atmosphere) or '适中'}
地形: {'、'.join(tag_names.get(t, t) for t in terrain) or '多样'}
魔法等级: {tag_names.get(magic, magic)}
危险等级: {tag_names.get(danger, danger)}
玩家额外描述: {description or '无特别要求'}

请输出以下JSON结构（所有文字使用中文）:
{{
  "region_name": "区域名称",
  "region_description": "区域整体描述（2-3句话）",
  "locations": [
    {{"id": "英文id", "name": "地点名称", "description": "地点描述（1-2句话）", "type": "indoor或outdoor", "light_level": 1-10, "danger_level": 0-10}}
  ],
  "connections": {{"地点id": ["连接的地点id"]}}
}}

要求：创建6-8个地点（第一个id=hub为安全中心，是城镇广场或类似的枢纽地点）。地点类型要多样，包括室内和室外。只输出JSON。"""

            loc_response = await llm.complete(loc_prompt, system="你是一个专业的RPG世界设计师。严格按照JSON格式输出。")
            loc_text = loc_response.strip()
            if loc_text.startswith("```"):
                lines = loc_text.split("\n")
                loc_text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
            import json
            loc_data = json.loads(loc_text)

            # Apply region and locations
            region = WorldRegion(
                id="main_region",
                name=loc_data.get("region_name", world_name or "AI World"),
                description=loc_data.get("region_description", ""),
                region_type="kingdom",
            )
            self.gm.world.add_region(region)
            self.gm.weather.add_region(region.id)

            locations = []
            for loc in loc_data.get("locations", []):
                locations.append(WorldLocation(
                    id=loc["id"], name=loc["name"],
                    description=loc.get("description", ""),
                    region_id="main_region",
                    location_type=loc.get("type", "outdoor"),
                    light_level=loc.get("light_level", 5),
                    danger_level=loc.get("danger_level", 0),
                ))
            conns = loc_data.get("connections", {})
            for loc in locations:
                if loc.id in conns:
                    loc.connected = conns[loc.id]
            for loc in locations:
                self.gm.world.add_location(loc)

            self._state = {
                "region": region,
                "locations": locations,
                "region_name": region.name,
            }

            await _report("locations_done", {
                "message": f"已生成 {len(locations)} 个地点",
                "step": 1,
                "total": 4,
                "locations": [l.name for l in locations],
                "region_name": region.name,
            })

            # Step 2: Generate NPCs
            await _report("generating_npcs", {
                "message": "AI正在设计世界中的角色...",
                "step": 2,
                "total": 4,
            })

            loc_names_str = "、".join(f"{l.id}({l.name})" for l in locations)
            npc_prompt = f"""请用JSON格式为RPG游戏世界创建NPC角色，要求如下：

区域: {region.name}
地点列表: {loc_names_str}
类型: {tag_names.get(genre, genre)}
时代: {tag_names.get(era, era)}
氛围: {'、'.join(tag_names.get(a, a) for a in atmosphere) or '适中'}
玩家额外描述: {description or '无特别要求'}

请输出以下JSON结构（所有文字使用中文）:
{{
  "npcs": [
    {{
      "id": "英文id（如npc_blacksmith）",
      "name": "NPC名称",
      "description": "NPC外貌和背景描述（1-2句话）",
      "location_id": "所在地点id（从上面的地点列表中选）",
      "personality": "friendly/stern/curious/charming/neutral 中的一个",
      "goal": "NPC的当前目标或动机"
    }}
  ]
}}

要求：创建4-6个NPC，分散在不同地点，角色类型多样（如商人、铁匠、守卫、酒馆老板、神秘人等）。只输出JSON。"""

            npc_response = await llm.complete(npc_prompt, system="你是一个专业的RPG世界设计师。严格按照JSON格式输出。")
            npc_text = npc_response.strip()
            if npc_text.startswith("```"):
                lines = npc_text.split("\n")
                npc_text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
            npc_data = json.loads(npc_text)

            npcs = []
            for nd in npc_data.get("npcs", []):
                lid = nd.get("location_id", locations[0].id if locations else "")
                npcs.append(NPC(
                    id=nd["id"], name=nd["name"],
                    description=nd.get("description", ""),
                    location_id=lid,
                    personality=nd.get("personality", "neutral"),
                    goal=nd.get("goal", ""),
                    schedule=[
                        ScheduleEntry(hour_start=6, hour_end=22, activity="日常活动", location_id=lid),
                        ScheduleEntry(hour_start=22, hour_end=6, activity="休息", location_id=lid),
                    ],
                ))
            for npc in npcs:
                self.gm.tick_engine.register_npc(npc)
                npc_data_dict = {
                    "location_id": npc.location_id,
                    "name": npc.name,
                    "type": "npc",
                    "health": 100,
                    "max_health": 100,
                }
                self.gm.world.add_character(npc.id, npc_data_dict)

            self._state["npcs"] = npcs

            await _report("npcs_done", {
                "message": f"已生成 {len(npcs)} 个NPC",
                "step": 2,
                "total": 4,
                "npcs": [{"name": n.name, "location": next((l.name for l in locations if l.id == n.location_id), "")} for n in npcs],
            })

            # Step 3: Generate lore
            await _report("generating_lore", {
                "message": "AI正在编织世界观设定...",
                "step": 3,
                "total": 4,
            })

            first_loc_id = "hub" if any(l.id == "hub" for l in locations) else (locations[0].id if locations else "")
            self.gm.world.add_character(self.gm.player_id, {
                "location_id": first_loc_id,
                "inventory": _INVENTORIES.get(genre, _INVENTORIES["fantasy"]),
                "name": "冒险者",
                "type": "player",
                "health": 100,
                "max_health": 100,
            })

            lore_prompt = f"""请为这个RPG游戏世界生成世界观设定和主线任务，要求如下：

世界名称: {region.name}
世界描述: {region.description}
类型: {tag_names.get(genre, genre)}
时代: {tag_names.get(era, era)}
氛围: {'、'.join(tag_names.get(a, a) for a in atmosphere) or '适中'}
地点: {'、'.join(l.name for l in locations)}
NPC: {'、'.join(n.name for n in npcs)}
玩家额外描述: {description or '无特别要求'}

请输出以下JSON结构（所有文字使用中文）:
{{
  "world_description": "世界整体背景设定（3-5句话，描述这个世界的历史、现状、主要势力）",
  "main_quest": "主线任务描述（2-3句话，玩家的终极目标是什么）",
  "factions": ["主要势力1", "主要势力2"],
  "secrets": ["隐藏的秘密1", "隐藏的秘密2"]
}}

只输出JSON。"""

            lore_response = await llm.complete(lore_prompt, system="你是一个专业的RPG游戏世界观设计师。严格按照JSON格式输出。")
            lore_text = lore_response.strip()
            if lore_text.startswith("```"):
                lines = lore_text.split("\n")
                lore_text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
            lore_ai = json.loads(lore_text)

            era_info = _ERA_INFO.get(era, _ERA_INFO["medieval"])
            atmo_tones = " ".join(_ATMO_MOD.get(a, {}).get("tone", "") for a in atmosphere)
            terrain_names = "、".join(
                next((t["name"] for cat in TAG_CATEGORIES if cat["id"] == "terrain"
                      for t in cat["tags"] if t["id"] == ter), ter)
                for ter in terrain
            ) if terrain else "多样"
            magic_name = next(
                (t["name"] for cat in TAG_CATEGORIES if cat["id"] == "magic"
                 for t in cat["tags"] if t["id"] == magic), magic)
            danger_name = next(
                (t["name"] for cat in TAG_CATEGORIES if cat["id"] == "danger"
                 for t in cat["tags"] if t["id"] == danger), danger)

            lore = {
                "world_name": region.name,
                "genre": tag_names.get(genre, genre),
                "era": era_info.get("label", ""),
                "atmosphere": atmo_tones,
                "terrain": terrain_names,
                "magic_level": magic_name,
                "danger_level": danger_name,
                "description": lore_ai.get("world_description", ""),
                "main_quest": lore_ai.get("main_quest", ""),
                "factions": lore_ai.get("factions", []),
                "secrets": lore_ai.get("secrets", []),
                "npc_summaries": {n.id: n.description for n in npcs},
                "location_summaries": {l.id: l.description for l in locations},
            }
            self.gm.world_lore = lore

            await _report("lore_done", {
                "message": "世界观设定已完成",
                "step": 3,
                "total": 4,
                "lore": {
                    "main_quest": lore.get("main_quest", ""),
                    "factions": lore.get("factions", []),
                },
            })

            # Step 4: Finalize
            await _report("finalizing", {
                "message": "正在整合世界数据...",
                "step": 4,
                "total": 4,
            })

            result = {
                "ok": True,
                "world_name": region.name,
                "locations": len(locations),
                "npcs": len(npcs),
                "genre": genre,
                "method": "llm",
            }

            await _report("complete", {
                "message": "世界生成完成！",
                "step": 4,
                "total": 4,
                "result": result,
            })

            return result

        except Exception as e:
            logger.warning("LLM world generation failed: %s, falling back", e)
            if progress_callback:
                try:
                    await progress_callback("fallback", {
                        "message": f"AI生成失败，使用模板生成: {e}",
                    })
                except Exception:
                    pass
            return self.build_from_tags(world_name, tags, description)

    def _apply_llm_world(self, world_name: str, data: dict, tags: dict) -> dict[str, Any]:
        region = WorldRegion(
            id="main_region", name=data.get("region_name", world_name or "AI World"),
            description=data.get("region_description", ""), region_type="kingdom",
        )
        locations = []
        for loc in data.get("locations", []):
            locations.append(WorldLocation(
                id=loc["id"], name=loc["name"], description=loc.get("description", ""),
                region_id="main_region", location_type=loc.get("type", "outdoor"),
                light_level=loc.get("light_level", 5), danger_level=loc.get("danger_level", 0),
            ))
        conns = data.get("connections", {})
        for loc in locations:
            if loc.id in conns:
                loc.connected = conns[loc.id]
        npcs = []
        for nd in data.get("npcs", []):
            lid = nd.get("location_id", locations[0].id if locations else "")
            npcs.append(NPC(
                id=nd["id"], name=nd["name"], description=nd.get("description", ""),
                location_id=lid, personality=nd.get("personality", "neutral"),
                goal=nd.get("goal", ""),
                schedule=[
                    ScheduleEntry(hour_start=6, hour_end=22, activity="日常活动", location_id=lid),
                    ScheduleEntry(hour_start=22, hour_end=6, activity="休息", location_id=lid),
                ],
            ))
        genre = (tags.get("genre", ["fantasy"]) or ["fantasy"])[0]
        first = "hub" if any(l.id == "hub" for l in locations) else (locations[0].id if locations else "")
        lore = self._generate_lore(genre, tags.get("era", ["medieval"])[0] if tags.get("era") else "medieval",
                                    tags.get("atmosphere", []), tags.get("terrain", []),
                                    tags.get("magic", ["medium"])[0] if tags.get("magic") else "medium",
                                    tags.get("danger", ["moderate"])[0] if tags.get("danger") else "moderate",
                                    region.name, locations, npcs)
        self.gm.setup_world(
            regions=[region], locations=locations, npcs=npcs,
            player_data={"location_id": first, "inventory": _INVENTORIES.get(genre, _INVENTORIES["fantasy"]),
                         "name": "冒险者", "type": "player"},
            lore=lore,
        )
        return {"ok": True, "world_name": region.name, "locations": len(locations),
                "npcs": len(npcs), "genre": genre, "method": "llm"}
