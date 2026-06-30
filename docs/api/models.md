# 数据模型文档

本文档描述了 JAG（Just a Game）项目中的所有 SQLModel 数据表结构。系统共包含 20 张数据表，分为核心实体、任务系统、派系关系、事件系统、知识图谱、记忆系统和日志系统七大模块。

## 目录

- [核心实体](#核心实体)
  - [Character（角色表）](#character角色表)
  - [Item（物品表）](#item物品表)
  - [Location（地点表）](#location地点表)
  - [Region（区域表）](#region区域表)
- [任务系统](#任务系统)
  - [Quest（任务表）](#quest任务表)
- [派系关系](#派系关系)
  - [Faction（派系表）](#faction派系表)
  - [Relationship（关系表）](#relationship关系表)
  - [NPCGoal（NPC 目标表）](#npcgoalnpc-目标表)
  - [NPCSchedule（NPC 日程表）](#npcschedulenpc-日程表)
- [事件系统](#事件系统)
  - [Event（事件表）](#event事件表)
  - [WorldEvent（世界事件表）](#worldevent世界事件表)
  - [StoryThread（故事线程表）](#storythread故事线程表)
  - [EconomyState（经济状态表）](#economystate经济状态表)
  - [WeatherState（天气状态表）](#weatherstate天气状态表)
- [知识图谱](#知识图谱)
  - [KnowledgeNode（知识节点表）](#knowledgenode知识节点表)
  - [KnowledgeEdge（知识边表）](#knowledgeedge知识边表)
- [记忆系统](#记忆系统)
  - [MemoryShort（短期记忆表）](#memoryshort短期记忆表)
  - [MemoryLong（长期记忆表）](#memorylong长期记忆表)
- [日志系统](#日志系统)
  - [ActionLog（行动日志表）](#actionlog行动日志表)
  - [RuleTrigger（规则触发表）](#ruletrigger规则触发表)
- [表关系](#表关系)
- [使用示例](#使用示例)

---

## 核心实体

### Character（角色表）

存储游戏中的所有角色信息，包括 NPC、玩家角色和生物。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，角色唯一标识 |
| `name` | str | - | 角色名称 |
| `description` | str | "" | 角色描述 |
| `character_type` | str | "npc" | 角色类型：`npc`、`player`、`creature` |
| `location_id` | str | "" | 外键，关联 `locations.id`，当前所在地点 |
| `hp` | int | 20 | 当前生命值 |
| `max_hp` | int | 20 | 最大生命值 |
| `level` | int | 1 | 等级 |
| `experience` | int | 0 | 经验值 |
| `attributes_json` | str | "{}" | JSON 格式的属性数据，如 `{"STR": 10, "DEX": 10}` |
| `skills_json` | str | "{}" | JSON 格式的技能数据 |
| `status_effects_json` | str | "[]" | JSON 数组格式的状态效果列表 |
| `is_alive` | bool | True | 是否存活 |
| `created_at` | str | 当前时间 | 创建时间 |
| `updated_at` | str | 当前时间 | 更新时间 |

**辅助方法：**
- `get_attributes()` -> dict：解析 `attributes_json` 返回字典
- `set_attributes(attrs: dict)` -> None：将属性字典保存为 JSON
- `get_status_effects()` -> list：解析 `status_effects_json` 返回列表

---

### Item（物品表）

存储游戏中的所有物品信息。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，物品唯一标识 |
| `name` | str | - | 物品名称 |
| `description` | str | "" | 物品描述 |
| `item_type` | str | "misc" | 物品类型：`weapon`、`armor`、`consumable`、`tool`、`misc` |
| `location_id` | str | "" | 所在地点 ID（若未被拾取） |
| `owner_id` | str | "" | 持有者 ID |
| `properties_json` | str | "{}" | JSON 格式的物品属性，如 `{"flammable": true, "sharp": false}` |
| `quantity` | int | 1 | 数量 |
| `value` | int | 0 | 金币价值 |
| `weight` | float | 0.0 | 重量 |
| `is_equipped` | bool | False | 是否已装备 |
| `created_at` | str | 当前时间 | 创建时间 |

**辅助方法：**
- `get_properties()` -> dict：解析 `properties_json` 返回字典
- `set_properties(props: dict)` -> None：将属性字典保存为 JSON

---

### Location（地点表）

存储游戏中的地点信息，地点是角色的活动场所。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，地点唯一标识 |
| `name` | str | - | 地点名称 |
| `description` | str | "" | 地点描述 |
| `region_id` | str | "" | 外键，关联 `regions.id`，所属区域 |
| `location_type` | str | "room" | 地点类型：`room`、`building`、`outdoor`、`dungeon` |
| `light_level` | int | 5 | 光照等级（0-10） |
| `danger_level` | int | 0 | 危险等级 |
| `is_accessible` | bool | True | 是否可进入 |
| `connected_locations_json` | str | "[]" | JSON 数组，存储相连地点的 ID 列表 |
| `tags_json` | str | "[]" | JSON 数组，存储标签列表 |
| `created_at` | str | 当前时间 | 创建时间 |

**辅助方法：**
- `get_connected_locations()` -> list：解析 `connected_locations_json` 返回列表

---

### Region（区域表）

存储游戏中的区域信息，区域包含多个地点。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，区域唯一标识 |
| `name` | str | - | 区域名称 |
| `description` | str | "" | 区域描述 |
| `region_type` | str | "settlement" | 区域类型：`settlement`、`wilderness`、`dungeon`、`city` |
| `danger_level` | int | 0 | 危险等级 |
| `weather_state` | str | "clear" | 天气状态 |
| `season` | str | "spring" | 季节 |
| `created_at` | str | 当前时间 | 创建时间 |

---

## 任务系统

### Quest（任务表）

存储游戏中的任务信息。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，任务唯一标识 |
| `title` | str | - | 任务标题 |
| `description` | str | "" | 任务描述 |
| `quest_type` | str | "main" | 任务类型：`main`、`side`、`personal`、`faction` |
| `status` | str | "available" | 任务状态：`available`、`active`、`completed`、`failed` |
| `giver_id` | str | "" | 任务发布者 NPC 的 ID |
| `objectives_json` | str | "[]" | JSON 数组，目标列表 `[{"desc": "...", "completed": false}]` |
| `rewards_json` | str | "{}" | JSON 对象，奖励信息 `{"xp": 100, "gold": 50, "items": [...]}` |
| `source` | str | "" | 任务来源：`npc_need`、`faction_conflict`、`world_event`、`player_action` |
| `created_at` | str | 当前时间 | 创建时间 |
| `updated_at` | str | 当前时间 | 更新时间 |

**辅助方法：**
- `get_objectives()` -> list：解析 `objectives_json` 返回目标列表

---

## 派系关系

### Faction（派系表）

存储游戏中的派系信息。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，派系唯一标识 |
| `name` | str | - | 派系名称 |
| `description` | str | "" | 派系描述 |
| `faction_type` | str | "organization" | 派系类型：`organization`、`guild`、`kingdom`、`tribe` |
| `leader_id` | str | "" | 领袖角色 ID |
| `member_ids_json` | str | "[]" | JSON 数组，成员 ID 列表 |
| `goals_json` | str | "[]" | JSON 数组，派系目标列表 |
| `resources_json` | str | "{}" | JSON 对象，资源信息 `{"gold": 1000, "influence": 50}` |
| `reputation` | int | 0 | 玩家与该派系的声望值 |
| `created_at` | str | 当前时间 | 创建时间 |

**辅助方法：**
- `get_members()` -> list：解析 `member_ids_json` 返回成员列表
- `get_goals()` -> list：解析 `goals_json` 返回目标列表

---

### Relationship（关系表）

存储角色之间的关系信息。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，关系唯一标识 |
| `source_id` | str | - | 关系发起方角色 ID |
| `target_id` | str | - | 关系目标方角色 ID |
| `relation_type` | str | "neutral" | 关系类型：`friendly`、`neutral`、`hostile`、`allied`、`enemy` |
| `value` | float | 0.0 | 关系值（-100 到 100） |
| `context` | str | "" | 关系上下文说明 |
| `created_at` | str | 当前时间 | 创建时间 |
| `updated_at` | str | 当前时间 | 更新时间 |

---

### NPCGoal（NPC 目标表）

存储 NPC 的目标信息。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，目标唯一标识 |
| `npc_id` | str | - | 外键，关联 `characters.id`，NPC ID |
| `goal_type` | str | "long_term" | 目标类型：`long_term`、`short_term`、`immediate` |
| `description` | str | - | 目标描述 |
| `priority` | int | 5 | 优先级（1-10） |
| `is_completed` | bool | False | 是否完成 |
| `progress` | float | 0.0 | 完成进度 |
| `created_at` | str | 当前时间 | 创建时间 |

---

### NPCSchedule（NPC 日程表）

存储 NPC 的日常日程安排。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，日程唯一标识 |
| `npc_id` | str | - | 外键，关联 `characters.id`，NPC ID |
| `hour_start` | int | 0 | 开始小时（0-23） |
| `hour_end` | int | 0 | 结束小时（0-23） |
| `activity` | str | "" | 活动内容 |
| `location_id` | str | "" | 活动地点 ID |
| `day_of_week` | str | "*" | 星期：`*` 表示每天，或 `monday`、`tuesday` 等 |

---

## 事件系统

### Event（事件表）

存储游戏中发生的各类事件。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，事件唯一标识 |
| `event_type` | str | - | 事件类型：`combat`、`interaction`、`environment`、`quest`、`social`、`economy` |
| `source_id` | str | "" | 事件发起方 ID |
| `target_id` | str | "" | 事件目标方 ID |
| `location_id` | str | "" | 事件发生地点 ID |
| `description` | str | "" | 事件描述 |
| `data_json` | str | "{}" | JSON 格式的附加数据 |
| `turn` | int | 0 | 游戏回合数 |
| `timestamp` | str | 当前时间 | 时间戳 |

**辅助方法：**
- `get_data()` -> dict：解析 `data_json` 返回字典

---

### WorldEvent（世界事件表）

存储影响整个游戏世界的大型事件。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，世界事件唯一标识 |
| `event_type` | str | - | 事件类型：`war`、`plague`、`festival`、`disaster`、`political` |
| `description` | str | "" | 事件描述 |
| `region_id` | str | "" | 影响的区域 ID |
| `severity` | int | 1 | 严重程度（1-10） |
| `is_active` | bool | True | 是否正在进行 |
| `turn_started` | int | 0 | 开始回合 |
| `turn_resolved` | int \| None | None | 结束回合（未结束时为 None） |
| `data_json` | str | "{}" | JSON 格式的附加数据 |
| `created_at` | str | 当前时间 | 创建时间 |

---

### StoryThread（故事线程表）

存储游戏中的故事线信息。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，故事线程唯一标识 |
| `title` | str | - | 故事线程标题 |
| `description` | str | "" | 故事线程描述 |
| `thread_type` | str | "main" | 线程类型：`main`、`side`、`personal` |
| `status` | str | "dormant" | 线程状态：`dormant`、`active`、`climax`、`resolved` |
| `related_events_json` | str | "[]" | JSON 数组，关联事件 ID 列表 |
| `related_npcs_json` | str | "[]" | JSON 数组，关联 NPC ID 列表 |
| `tension_level` | int | 0 | 紧张程度（0-10） |
| `turn_created` | int | 0 | 创建回合 |
| `turn_last_updated` | int | 0 | 最后更新回合 |

---

### EconomyState（经济状态表）

存储各地点的商品经济状态。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，经济状态唯一标识 |
| `location_id` | str | - | 地点 ID |
| `commodity` | str | - | 商品名称 |
| `base_price` | float | 10.0 | 基础价格 |
| `current_price` | float | 10.0 | 当前价格 |
| `supply` | float | 100.0 | 供应量 |
| `demand` | float | 100.0 | 需求量 |
| `last_updated_turn` | int | 0 | 最后更新回合 |

---

### WeatherState（天气状态表）

存储各区域的天气状态。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，天气状态唯一标识 |
| `region_id` | str | - | 区域 ID |
| `current_weather` | str | "clear" | 当前天气：`clear`、`cloudy`、`rain`、`storm`、`snow`、`fog` |
| `temperature` | float | 20.0 | 温度 |
| `wind_speed` | float | 0.0 | 风速 |
| `season` | str | "spring" | 季节 |
| `turn` | int | 0 | 游戏回合 |

---

## 知识图谱

### KnowledgeNode（知识节点表）

存储知识图谱中的节点信息。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，节点唯一标识 |
| `node_type` | str | - | 节点类型：`character`、`item`、`location`、`faction`、`concept` |
| `name` | str | - | 节点名称 |
| `attributes_json` | str | "{}" | JSON 格式的节点属性 |
| `created_at` | str | 当前时间 | 创建时间 |
| `updated_at` | str | 当前时间 | 更新时间 |

**辅助方法：**
- `get_attributes()` -> dict：解析 `attributes_json` 返回字典

---

### KnowledgeEdge（知识边表）

存储知识图谱中节点之间的关系。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，边唯一标识 |
| `source_id` | str | - | 外键，关联 `knowledge_nodes.id`，源节点 ID |
| `target_id` | str | - | 外键，关联 `knowledge_nodes.id`，目标节点 ID |
| `relation_type` | str | - | 关系类型：`owns`、`likes`、`hates`、`allied_with`、`enemy_of`、`knows`、`owes` |
| `weight` | float | 1.0 | 关系权重 |
| `attributes_json` | str | "{}" | JSON 格式的附加属性 |
| `created_at` | str | 当前时间 | 创建时间 |

**辅助方法：**
- `get_attributes()` -> dict：解析 `attributes_json` 返回字典

---

## 记忆系统

### MemoryShort（短期记忆表）

存储角色或玩家的短期记忆。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，记忆唯一标识 |
| `owner_id` | str | - | 记忆拥有者 ID（角色 ID 或 `"player"`） |
| `event_id` | str | "" | 关联的事件 ID |
| `description` | str | "" | 记忆描述 |
| `importance` | int | 5 | 重要程度（1-10） |
| `turn` | int | 0 | 游戏回合 |
| `created_at` | str | 当前时间 | 创建时间 |

---

### MemoryLong（长期记忆表）

存储角色或玩家的长期记忆。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，记忆唯一标识 |
| `owner_id` | str | - | 记忆拥有者 ID |
| `memory_type` | str | "general" | 记忆类型：`general`、`reputation`、`relationship`、`historical`、`personal` |
| `content` | str | - | 记忆内容 |
| `source_event_ids_json` | str | "[]" | JSON 数组，源事件 ID 列表 |
| `importance` | int | 5 | 重要程度（1-10） |
| `created_at` | str | 当前时间 | 创建时间 |
| `last_accessed` | str | 当前时间 | 最后访问时间 |

**辅助方法：**
- `get_source_events()` -> list：解析 `source_event_ids_json` 返回事件 ID 列表

---

## 日志系统

### ActionLog（行动日志表）

记录游戏中发生的所有行动。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，日志唯一标识 |
| `actor_id` | str | - | 行动者 ID |
| `action_type` | str | - | 行动类型 |
| `action_data_json` | str | "{}" | JSON 格式的行动数据 |
| `result` | str | "" | 行动结果：`success`、`failure`、`critical_success`、`critical_failure` |
| `turn` | int | 0 | 游戏回合 |
| `timestamp` | str | 当前时间 | 时间戳 |

---

### RuleTrigger（规则触发表）

记录游戏规则触发事件。

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | str | - | 主键，触发记录唯一标识 |
| `rule_name` | str | - | 规则名称 |
| `trigger_context_json` | str | "{}" | JSON 格式的触发上下文 |
| `effects_json` | str | "[]" | JSON 数组，产生的效果列表 |
| `chain_depth` | int | 0 | 触发链深度 |
| `turn` | int | 0 | 游戏回合 |
| `timestamp` | str | 当前时间 | 时间戳 |

---

## 表关系

### 外键关系图

```
Character (characters)
    ├── location_id → Location.id
    └── (referenced by)
        ├── NPCGoal.npc_id
        └── NPCSchedule.npc_id

Location (locations)
    ├── region_id → Region.id
    └── (referenced by)
        ├── Character.location_id
        ├── Event.location_id
        ├── EconomyState.location_id
        └── NPCSchedule.location_id

Region (regions)
    └── (referenced by)
        ├── Location.region_id
        ├── WorldEvent.region_id
        └── WeatherState.region_id

KnowledgeNode (knowledge_nodes)
    └── (referenced by)
        ├── KnowledgeEdge.source_id
        └── KnowledgeEdge.target_id
```

### 关系类型总结

| 从表 | 外键字段 | 关联到表 | 关联字段 | 关系类型 |
|------|----------|----------|----------|----------|
| `Character` | `location_id` | `Location` | `id` | 多对一 |
| `Location` | `region_id` | `Region` | `id` | 多对一 |
| `NPCGoal` | `npc_id` | `Character` | `id` | 多对一 |
| `NPCSchedule` | `npc_id` | `Character` | `id` | 多对一 |
| `KnowledgeEdge` | `source_id` | `KnowledgeNode` | `id` | 多对一 |
| `KnowledgeEdge` | `target_id` | `KnowledgeNode` | `id` | 多对一 |

---

## 使用示例

### 创建示例

#### 创建角色

```python
from jag.persistence.models import Character

# 创建一个 NPC 角色
character = Character(
    id="npc_001",
    name="艾莉丝",
    description="一位神秘的魔法师，来自遥远的东方",
    character_type="npc",
    location_id="loc_tavern",
    hp=30,
    max_hp=30,
    level=5,
    experience=1200
)

# 设置属性
character.set_attributes({"STR": 8, "DEX": 12, "INT": 16, "WIS": 14})

# 添加到数据库
session.add(character)
session.commit()
```

#### 创建物品

```python
from jag.persistence.models import Item

# 创建一把剑
sword = Item(
    id="item_sword_001",
    name="精钢长剑",
    description="一把锋利的精钢长剑",
    item_type="weapon",
    owner_id="npc_001",
    quantity=1,
    value=150,
    weight=3.5
)

# 设置物品属性
sword.set_properties({"sharp": True, "magical": False, "two_handed": False})

session.add(sword)
session.commit()
```

#### 创建地点和区域

```python
from jag.persistence.models import Region, Location

# 创建区域
region = Region(
    id="region_forest",
    name="迷雾森林",
    description="一片神秘的古老森林",
    region_type="wilderness",
    danger_level=3,
    weather_state="foggy",
    season="autumn"
)

# 创建地点
location = Location(
    id="loc_clearing",
    name="林间空地",
    description="森林中的一片开阔空地",
    region_id="region_forest",
    location_type="outdoor",
    light_level=6,
    danger_level=2
)

session.add(region)
session.add(location)
session.commit()
```

#### 创建任务

```python
from jag.persistence.models import Quest

quest = Quest(
    id="quest_001",
    title="失落的遗物",
    description="帮助村民找回被盗的传家宝",
    quest_type="side",
    status="available",
    giver_id="npc_villager",
    source="npc_need"
)

# 设置任务目标
quest.objectives_json = '[{"desc": "找到盗贼的藏身处", "completed": false}, {"desc": "取回传家宝", "completed": false}]'

# 设置奖励
quest.rewards_json = '{"xp": 200, "gold": 100, "items": ["item_healing_potion"]}'

session.add(quest)
session.commit()
```

#### 创建知识图谱节点和边

```python
from jag.persistence.models import KnowledgeNode, KnowledgeEdge

# 创建知识节点
node_alice = KnowledgeNode(
    id="kn_alice",
    node_type="character",
    name="艾莉丝"
)
node_alice.attributes_json = '{"role": "wizard", "level": 5}'

node_tavern = KnowledgeNode(
    id="kn_tavern",
    node_type="location",
    name="月光酒馆"
)

# 创建知识边（关系）
edge = KnowledgeEdge(
    id="ke_alice_tavern",
    source_id="kn_alice",
    target_id="kn_tavern",
    relation_type="knows",
    weight=0.8
)

session.add(node_alice)
session.add(node_tavern)
session.add(edge)
session.commit()
```

### 查询示例

#### 查询角色及其所在地点

```python
from sqlmodel import select
from jag.persistence.models import Character, Location

# 查询特定角色
character = session.exec(
    select(Character).where(Character.id == "npc_001")
).first()

# 查询角色所在地点
if character and character.location_id:
    location = session.exec(
        select(Location).where(Location.id == character.location_id)
    ).first()
    print(f"{character.name} 正在 {location.name}")
```

#### 查询区域内的所有地点

```python
from sqlmodel import select
from jag.persistence.models import Region, Location

# 查询特定区域
region = session.exec(
    select(Region).where(Region.id == "region_forest")
).first()

# 查询该区域内的所有地点
locations = session.exec(
    select(Location).where(Location.region_id == region.id)
).all()

for loc in locations:
    print(f"- {loc.name}: {loc.description}")
```

#### 查询 NPC 的目标和日程

```python
from sqlmodel import select
from jag.persistence.models import NPCGoal, NPCSchedule

npc_id = "npc_001"

# 查询 NPC 的目标
goals = session.exec(
    select(NPCGoal)
    .where(NPCGoal.npc_id == npc_id)
    .where(NPCGoal.is_completed == False)
    .order_by(NPCGoal.priority.desc())
).all()

for goal in goals:
    print(f"目标 [{goal.goal_type}]: {goal.description} (优先级: {goal.priority})")

# 查询 NPC 的日程
schedules = session.exec(
    select(NPCSchedule)
    .where(NPCSchedule.npc_id == npc_id)
    .order_by(NPCSchedule.hour_start)
).all()

for schedule in schedules:
    print(f"{schedule.hour_start}:00-{schedule.hour_end}:00 - {schedule.activity}")
```

#### 查询任务

```python
from sqlmodel import select
from jag.persistence.models import Quest

# 查询所有可接受的任务
available_quests = session.exec(
    select(Quest).where(Quest.status == "available")
).all()

# 查询特定玩家的活跃任务
active_quests = session.exec(
    select(Quest).where(Quest.status == "active")
).all()

# 查询主线任务
main_quests = session.exec(
    select(Quest)
    .where(Quest.quest_type == "main")
    .where(Quest.status != "failed")
).all()
```

#### 查询关系

```python
from sqlmodel import select
from jag.persistence.models import Relationship

# 查询两个角色之间的关系
relationship = session.exec(
    select(Relationship)
    .where(Relationship.source_id == "npc_001")
    .where(Relationship.target_id == "npc_002")
).first()

if relationship:
    print(f"关系类型: {relationship.relation_type}, 数值: {relationship.value}")

# 查询某角色的所有敌对关系
hostile_relations = session.exec(
    select(Relationship)
    .where(Relationship.source_id == "npc_001")
    .where(Relationship.relation_type == "hostile")
).all()
```

#### 查询记忆

```python
from sqlmodel import select
from jag.persistence.models import MemoryShort, MemoryLong

owner_id = "npc_001"

# 查询短期记忆（按重要性和时间排序）
short_memories = session.exec(
    select(MemoryShort)
    .where(MemoryShort.owner_id == owner_id)
    .order_by(MemoryShort.importance.desc())
    .order_by(MemoryShort.turn.desc())
    .limit(10)
).all()

# 查询长期记忆
long_memories = session.exec(
    select(MemoryLong)
    .where(MemoryLong.owner_id == owner_id)
    .order_by(MemoryLong.importance.desc())
).all()

for memory in long_memories:
    print(f"[{memory.memory_type}] {memory.content}")
```

#### 查询事件日志

```python
from sqlmodel import select
from jag.persistence.models import ActionLog

# 查询特定回合的所有行动
turn = 10
logs = session.exec(
    select(ActionLog)
    .where(ActionLog.turn == turn)
    .order_by(ActionLog.timestamp)
).all()

for log in logs:
    print(f"回合 {log.turn}: {log.actor_id} 执行 {log.action_type} -> {log.result}")

# 查询特定角色的行动历史
actor_logs = session.exec(
    select(ActionLog)
    .where(ActionLog.actor_id == "npc_001")
    .order_by(ActionLog.turn.desc())
    .limit(20)
).all()
```

---

## 数据模型导出

所有模型类都定义在 `jag.persistence.models` 模块中，并汇总在 `ALL_MODELS` 列表中：

```python
from jag.persistence.models import ALL_MODELS

# ALL_MODELS 包含所有 20 个模型类
# 可用于批量创建表
for model in ALL_MODELS:
    print(model.__tablename__)
```

---

## 数据库初始化

```python
from sqlmodel import SQLModel, create_engine
from jag.persistence.models import ALL_MODELS

# 创建数据库引擎
engine = create_engine("sqlite:///game.db")

# 创建所有表
SQLModel.metadata.create_all(engine)
```