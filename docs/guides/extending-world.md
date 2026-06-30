# 世界数据扩展指南

本指南介绍如何创建和加载自定义世界数据，扩展 Just-a-Game 的游戏世界。

## 目录

1. [创建新世界数据 YAML](#创建新世界数据-yaml)
2. [世界数据格式说明](#世界数据格式说明)
3. [如何加载世界数据](#如何加载世界数据)

---

## 创建新世界数据 YAML

### 文件结构

世界数据可以组织为以下 YAML 文件：

| 文件名 | 说明 |
|--------|------|
| `world_data.yaml` | 世界元数据、区域和地点（推荐合并文件） |
| `regions.yaml` | 区域数据（可选，可合并到 world_data.yaml） |
| `locations.yaml` | 地点数据（可选，可合并到 world_data.yaml） |
| `npcs.yaml` | NPC 数据 |
| `items.yaml` | 物品数据 |
| `factions.yaml` | 派系数据和关系 |
| `rules.yaml` | 游戏规则 |

**推荐做法**：将 `regions` 和 `locations` 合并到 `world_data.yaml` 中，保持文件组织清晰。

### 示例：创建一个新世界

以下是一个完整的奇幻世界示例，文件放置在 `data/my_world/` 目录下。

#### world_data.yaml

```yaml
# 新世界：翡翠王国

regions:
  - id: emerald_capital
    name: 翡翠城
    description: 翡翠王国的首都，繁华的商业与文化中心。
    region_type: city
    danger_level: 1

  - id: crystal_forest
    name: 水晶森林
    description: 传说中精灵居住的神秘森林，树木如水晶般透明。
    region_type: wilderness
    danger_level: 4

locations:
  # 翡翠城
  - id: city_square
    name: 中央广场
    description: 翡翠城的心脏，巨大的翡翠雕像矗立中央。
    region_id: emerald_capital
    location_type: outdoor
    light_level: 9
    danger_level: 0
    connected: [royal_palace, magic_shop, city_gate]
    tags: [social, trade]

  - id: royal_palace
    name: 皇家宫殿
    description: 王室的居所，金碧辉煌的宫殿建筑群。
    region_id: emerald_capital
    location_type: indoor
    light_level: 8
    danger_level: 0
    connected: [city_square]
    tags: [government, restricted]

  - id: magic_shop
    name: 奇术工坊
    description: 各种魔法道具和卷轴的专卖店。
    region_id: emerald_capital
    location_type: indoor
    light_level: 6
    danger_level: 0
    connected: [city_square]
    tags: [trade, magic]

  - id: city_gate
    name: 城门
    description: 连接城市与森林的宏伟石门。
    region_id: emerald_capital
    location_type: outdoor
    light_level: 7
    danger_level: 1
    connected: [city_square, forest_entrance]
    tags: [transition]

  # 水晶森林
  - id: forest_entrance
    name: 森林入口
    description: 进入水晶森林的边界，光线开始变得奇异。
    region_id: crystal_forest
    location_type: outdoor
    light_level: 5
    danger_level: 2
    connected: [city_gate, elf_village]
    tags: [wilderness]

  - id: elf_village
    name: 精灵村落
    description: 隐藏在水晶树之间的精灵聚居地。
    region_id: crystal_forest
    location_type: outdoor
    light_level: 4
    danger_level: 1
    connected: [forest_entrance, ancient_tree]
    tags: [social, hidden]

  - id: ancient_tree
    name: 世界之树
    description: 森林深处最古老的水晶巨树，据说蕴含强大魔力。
    region_id: crystal_forest
    location_type: outdoor
    light_level: 3
    danger_level: 5
    connected: [elf_village]
    tags: [ancient, magic]
```

---

## 世界数据格式说明

### regions.yaml / world_data.yaml 中的 regions

区域定义世界的宏观地理单元。

```yaml
regions:
  - id: region_id          # 必填：唯一标识符
    name: 区域名称          # 必填：显示名称
    description: 区域描述   # 可选：详细描述
    region_type: settlement # 可选：类型（settlement, wilderness, kingdom 等）
    danger_level: 1         # 可选：危险等级 (0-10)
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 区域的唯一标识符 |
| `name` | string | 是 | 区域显示名称 |
| `description` | string | 否 | 区域描述文本 |
| `region_type` | string | 否 | 区域类型，如 `settlement`、`wilderness`、`kingdom`、`city` |
| `danger_level` | int | 否 | 整体危险等级，范围 0-10 |

---

### locations.yaml / world_data.yaml 中的 locations

地点定义区域内的具体位置。

```yaml
locations:
  - id: location_id           # 必填：唯一标识符
    name: 地点名称             # 必填：显示名称
    description: 地点描述      # 可选：详细描述
    region_id: region_id      # 必填：所属区域 ID
    location_type: outdoor    # 可选：类型（indoor/outdoor）
    light_level: 8            # 可选：光照等级 (1-10)
    danger_level: 0           # 可选：危险等级 (0-10)
    connected: [other_loc]    # 必填：连接的地点 ID 列表
    tags: [social, trade]     # 可选：标签列表
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 地点的唯一标识符 |
| `name` | string | 是 | 地点显示名称 |
| `description` | string | 否 | 地点描述文本 |
| `region_id` | string | 是 | 所属区域 ID |
| `location_type` | string | 否 | `indoor` 或 `outdoor` |
| `light_level` | int | 否 | 光照等级，1（黑暗）到 10（明亮） |
| `danger_level` | int | 否 | 危险等级，0（安全）到 10（致命） |
| `connected` | list | 是 | 可通行的连接地点 ID 列表 |
| `tags` | list | 否 | 功能标签，如 `social`、`trade`、`rest`、`dungeon` |

---

### npcs.yaml

NPC 定义世界中的非玩家角色。

```yaml
npcs:
  - id: npc_id                  # 必填：唯一标识符
    name: NPC名称               # 必填：显示名称
    description: NPC描述        # 可选：详细描述
    location_id: tavern         # 必填：初始位置 ID
    personality: friendly       # 可选：性格类型
    goal: NPC的目标             # 可选：主要目标
    desires: ["愿望1", "愿望2"]  # 可选：渴望列表
    fears: ["恐惧1", "恐惧2"]   # 可选：恐惧列表
    attributes:                 # 可选：属性值
      STR: 10
      DEX: 14
      CON: 12
      INT: 16
      WIS: 12
      CHA: 15
    resources:                  # 可选：资源
      gold: 50
    schedule:                   # 可选：日程安排
      - hour_start: 6
        hour_end: 18
        activity: 工作
        location_id: workplace
      - hour_start: 18
        hour_end: 22
        activity: 休闲
        location_id: tavern
      - hour_start: 22
        hour_end: 6
        activity: 睡觉
        location_id: home
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | NPC 的唯一标识符 |
| `name` | string | 是 | NPC 显示名称 |
| `description` | string | 否 | NPC 外貌与背景描述 |
| `location_id` | string | 是 | 初始所在地点 ID |
| `personality` | string | 否 | 性格类型：`friendly`、`stern`、`curious`、`charming`、`neutral`、`gruff`、`cautious`、`cunning`、`mysterious` |
| `goal` | string | 否 | NPC 的主要目标 |
| `desires` | list | 否 | NPC 渴望的事物 |
| `fears` | string | 否 | NPC 恐惧的事物 |
| `attributes` | dict | 否 | 六维属性：STR/DEX/CON/INT/WIS/CHA (值范围 3-18) |
| `resources` | dict | 否 | 拥有的资源，如 `gold` |
| `schedule` | list | 否 | 日程安排条目列表 |

**schedule 条目格式**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `hour_start` | int | 开始时间（0-24） |
| `hour_end` | int | 结束时间（0-24） |
| `activity` | string | 活动描述 |
| `location_id` | string | 该时段所在地点 ID |

---

### items.yaml

物品定义世界中可交互的对象。

```yaml
items:
  - id: item_id              # 必填：唯一标识符
    name: 物品名称            # 必填：显示名称
    description: 物品描述     # 可选：详细描述
    location_id: tavern      # 可选：所在位置（或 owner_id）
    properties:              # 可选：物品属性
      light_source: true     # 光源
      flammable: true        # 可燃
      weapon: true           # 武器
      sharp: true            # 锋利
      metallic: true         # 金属
      portable: true         # 可携带
      container: true        # 容器
      consumable: true       # 可消耗
      healing: true          # 治疗
      liquid: true           # 液体
      valuable: true         # 有价值
      readable: true         # 可阅读
      tool: true             # 工具
      climbable: true        # 可攀爬
    value: 25                # 可选：价值（金币）
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 物品的唯一标识符 |
| `name` | string | 是 | 物品显示名称 |
| `description` | string | 否 | 物品描述文本 |
| `location_id` | string | 否 | 所在地点 ID（或 `owner_id` 表示持有者） |
| `properties` | dict | 否 | 物品属性标签 |
| `value` | int | 否 | 物品价值（金币） |

**常用 properties 属性**：

- `light_source` - 光源物品（油灯、火把）
- `flammable` - 可燃物品
- `weapon` - 武器
- `sharp` - 锋利物品
- `metallic` - 金属物品
- `portable` - 可携带
- `container` - 容器
- `consumable` / `food` - 可消耗/食物
- `healing` - 治疗物品
- `liquid` - 液体
- `valuable` - 高价值物品
- `readable` - 可阅读（书籍、地图）
- `tool` - 工具
- `climbable` / `flexible` - 可攀爬/柔韧（绳索）

---

### factions.yaml

派系定义世界中的组织和势力关系。

```yaml
factions:
  - id: faction_id             # 必填：唯一标识符
    name: 派系名称              # 必填：显示名称
    description: 派系描述       # 可选：详细描述
    faction_type: organization # 可选：类型
    leader_id: npc_id         # 可选：首领 NPC ID
    members: [npc1, npc2]     # 可选：成员 NPC ID 列表
    goals: [目标1, 目标2]      # 可选：派系目标
    resources:                # 可选：派系资源
      gold: 500
      influence: 20

relations:
  - faction_a: faction1
    faction_b: faction2
    relation: friendly        # 关系类型
```

**派系字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 派系的唯一标识符 |
| `name` | string | 是 | 派系显示名称 |
| `description` | string | 否 | 派系描述文本 |
| `faction_type` | string | 否 | 派系类型：`community`、`organization`、`criminal`、`guild` |
| `leader_id` | string | 否 | 首领 NPC 的 ID |
| `members` | list | 否 | 成员 NPC ID 列表 |
| `goals` | list | 否 | 派系的集体目标 |
| `resources` | dict | 否 | 拥有的资源（如 `gold`、`influence`） |

**关系类型**：

| 值 | 说明 |
|------|------|
| `friendly` | 友好关系 |
| `neutral` | 中立关系 |
| `hostile` | 敌对关系 |
| `alliance` | 结盟关系 |

---

### rules.yaml

规则定义世界中的因果逻辑和游戏机制。

```yaml
- name: 规则名称
  conditions:
    - attribute: source.type    # 检查的属性路径
      operator: eq              # 比较运算符
      value: fire               # 目标值
  effects:
    - action: set_state         # 执行的动作
      target: target.on_fire
      value: true
  probability: 0.7              # 触发概率
  priority: 10                  # 执行优先级
  tags: [fire, environment]     # 规则标签
```

**条件运算符**：

| 运算符 | 说明 |
|--------|------|
| `eq` | 等于 |
| `ne` | 不等于 |
| `gt` | 大于 |
| `lt` | 小于 |
| `gte` | 大于等于 |
| `lte` | 小于等于 |
| `has_property` | 拥有属性 |
| `contains` | 包含（列表） |

**动作类型**：

| 动作 | 说明 |
|------|------|
| `set_state` | 设置状态值 |
| `modify_attribute` | 修改属性值 |
| `emit_event` | 发送事件 |

---

### world_data.yaml 元数据

除了 regions 和 locations，还可以在 world_data.yaml 中添加世界元数据：

```yaml
# 世界元数据
world_name: 翡翠王国
description: 一个魔法与荣耀交织的奇幻世界。
genre: fantasy                  # 类型：fantasy/scifi/postapoc/wuxia/mystery/steampunk/horror
era: medieval                   # 时代：ancient/medieval/renaissance/industrial/modern/future
magic_level: medium             # 魔法等级：none/low/medium/high
danger_level: moderate          # 危险等级：safe/moderate/dangerous/deadly

# 区域和地点数据...
regions:
  ...

locations:
  ...
```

---

## 如何加载世界数据

### WorldLoader 类

使用 `jag.demo.WorldLoader` 类加载 YAML 世界数据：

```python
from pathlib import Path
from jag.demo import WorldLoader

# 指定世界数据目录
world_dir = Path("data/my_world")
loader = WorldLoader(world_dir)

# 加载所有数据
data = loader.load_all()

# 返回的数据结构：
# {
#     "regions": [WorldRegion, ...],
#     "locations": [WorldLocation, ...],
#     "npcs": [NPC, ...],
#     "items": [GameItem, ...],
#     "factions": [Faction, ...],
#     "relations": [{"faction_a": ..., "faction_b": ..., "relation": ...}, ...]
# }
```

### 单独加载各部分数据

```python
from jag.demo import (
    load_regions,
    load_locations,
    load_npcs,
    load_items,
    load_factions,
)

# 加载区域
regions = load_regions()  # 从 world_data.yaml 加载

# 加载地点
locations = load_locations()  # 从 world_data.yaml 加载

# 加载 NPC
npcs = load_npcs()  # 从 npcs.yaml 加载

# 加载物品
items = load_items()  # 从 items.yaml 加载

# 加载派系和关系
factions, relations = load_factions()  # 从 factions.yaml 加载
```

### 使用 GameMaster 加载世界

将加载的数据传入 `GameMaster.setup_world()` 方法：

```python
from jag.agents.game_master import GameMaster
from jag.demo import WorldLoader

# 创建 GameMaster
gm = GameMaster()

# 加载世界数据
loader = WorldLoader(Path("data/my_world"))
data = loader.load_all()

# 验证数据完整性
errors = loader.validate(data)
if errors:
    for err in errors:
        print(f"验证错误: {err}")
    return

# 设置世界
gm.setup_world(
    regions=data["regions"],
    locations=data["locations"],
    npcs=data["npcs"],
    player_data={
        "location_id": "city_square",  # 玩家初始位置
        "inventory": ["铁剑", "皮甲", "面包", "20金币"],
        "name": "冒险者",
        "type": "player",
    },
    lore={
        "world_name": "翡翠王国",
        "description": "一个魔法与荣耀交织的奇幻世界。",
        "main_quest": "寻找传说中的翡翠宝石，拯救王国于危难。",
    },
)

# 添加物品到世界
for item in data["items"]:
    gm.world.add_item(item)

# 注册派系
for faction in data["factions"]:
    gm.faction.add_faction(faction)

# 设置派系关系
for rel in data["relations"]:
    gm.faction.set_relation(rel["faction_a"], rel["faction_b"], rel["relation"])
```

### 使用 WorldBuilder 创建世界

`WorldBuilder` 支持基于标签的自动化世界生成：

```python
from jag.agents.game_master import GameMaster
from jag.world.world_builder import WorldBuilder

gm = GameMaster()
builder = WorldBuilder(gm)

# 使用标签生成世界
result = builder.build_from_tags(
    world_name="暗影王国",
    tags={
        "genre": ["fantasy"],
        "era": ["medieval"],
        "atmosphere": ["dark", "epic"],
        "terrain": ["forest", "mountain"],
        "magic": ["high"],
        "danger": ["dangerous"],
    },
    description="一个被黑暗笼罩的王国，英雄必须拯救它。",
)

print(f"世界 '{result['world_name']}' 已创建")
print(f"地点数: {result['locations']}")
print(f"NPC数: {result['npcs']}")
```

### 使用 LLM 生成世界

```python
import asyncio
from jag.agents.game_master import GameMaster
from jag.world.world_builder import WorldBuilder

async def create_world():
    gm = GameMaster()
    builder = WorldBuilder(gm)

    result = await builder.build_with_llm(
        world_name="神秘都市",
        tags={
            "genre": ["mystery"],
            "era": ["modern"],
            "atmosphere": ["dark", "mystery"],
        },
        description="一个充满阴谋与谜团的现代都市。",
    )

    return result

# 运行
result = asyncio.run(create_world())
```

---

## 数据验证

使用 `WorldLoader.validate()` 方法检查数据完整性：

```python
loader = WorldLoader(Path("data/my_world"))
data = loader.load_all()

errors = loader.validate(data)

# 检查项：
# - 区域是否存在
# - 地点是否引用有效区域
# - NPC 是否引用有效地点
# - 日程地点是否有效
# - 连接地点是否存在

if errors:
    print("数据验证失败:")
    for err in errors:
        print(f"  - {err}")
else:
    print("数据验证通过")
```

---

## 参考文件

实际示例请参考 `jag/demo/` 目录下的 YAML 文件：

- `world_data.yaml` - 灰石村与暗影森林示例
- `npcs.yaml` - NPC 数据示例
- `items.yaml` - 物品数据示例
- `factions.yaml` - 派系数据示例
- `rules.yaml` - 规则数据示例