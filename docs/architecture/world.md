# World 模块架构文档

## 模块职责

World 模块是 Just-a-Game 的世界模拟器核心，负责管理游戏世界的整体状态与动态演化。模块职责包括：

- **世界状态管理**：管理区域、地点、角色、物品等世界元素的状态存储与查询
- **NPC 系统**：定义 NPC 属性、状态、日程安排，支持自主行为决策
- **经济模拟**：基于供需关系的商品价格波动模拟
- **派系模拟**：派系关系矩阵与玩家声誉管理
- **天气模拟**：基于马尔可夫链的季节性天气变化系统
- **任务生成**：根据世界事件动态生成任务
- **时间系统**：游戏回合、昼夜、季节的时间推进

模块位于 `jag/world/` 目录下，由 TickEngine（见 `tick-engine.md`）统一调度执行。

---

## 主要类介绍

### WorldState：世界状态管理

**文件位置**：`jag/world/world.py`

WorldState 是世界状态的核心容器，管理所有世界元素的数据存储与查询。

#### 核心属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `time` | TimeState | 游戏时间状态 |
| `regions` | dict[str, WorldRegion] | 区域字典，key 为区域 ID |
| `locations` | dict[str, WorldLocation] | 地点字典，key 为地点 ID |
| `characters` | dict[str, dict] | 角色数据字典 |
| `items` | dict[str, dict] | 物品数据字典 |
| `global_flags` | dict[str, Any] | 全局标志位 |

#### TimeState 时间状态

```python
@dataclass
class TimeState:
    turn: int = 0          # 回合数
    hour: int = 8          # 当前小时 (0-23)
    day: int = 1           # 当前日期
    season: str = "spring" # 季节：spring/summer/autumn/winter
```

时间推进规则：
- 1 回合 ≈ 1 小时
- 24 小时后进入新的一天
- 30 天后季节轮换
- 提供 `time_of_day()` 方法返回时段：morning/afternoon/evening/night
- `is_dark()` 判断是否为黑暗时段（hour < 6 或 hour >= 20）

#### WorldLocation 地点

```python
@dataclass
class WorldLocation:
    id: str                          # 地点唯一标识
    name: str                        # 地点名称
    description: str                 # 地点描述
    region_id: str                   # 所属区域 ID
    location_type: str               # 类型：room/outdoor/indoor 等
    light_level: int                 # 光照等级 (1-10)
    danger_level: int                # 危险等级 (0-10)
    connected: list[str]             # 连通的地点 ID 列表
    entities: list[str]              # 当前位置的实体 ID 列表
    items: list[str]                 # 当前位置的物品 ID 列表
    tags: list[str]                  # 地点标签
```

#### WorldRegion 区域

```python
@dataclass
class WorldRegion:
    id: str                          # 区域唯一标识
    name: str                        # 区域名称
    description: str                 # 区域描述
    region_type: str                 # 类型：settlement/kingdom 等
    danger_level: int                # 区域危险等级
    locations: list[str]             # 区域内的地点 ID 列表
```

#### 核心方法

| 方法 | 说明 |
|------|------|
| `add_region(region)` | 添加区域到世界 |
| `add_location(location)` | 添加地点并关联到区域 |
| `add_character(char_id, data)` | 添加角色并放置到地点 |
| `add_item(item_id, data)` | 添加物品并放置到地点 |
| `move_character(char_id, from_loc, to_loc)` | 移动角色到新地点 |
| `get_location_entities(location_id)` | 获取地点内的所有实体 |
| `get_location_items(location_id)` | 获取地点内的所有物品 |
| `advance_time(turns)` | 推进时间并更新光照等级 |
| `snapshot()` | 获取世界状态快照 |
| `is_dangerous_location(location_id)` | 判断地点是否危险（danger_level >= 5） |
| `get_hostile_characters_at(location_id)` | 获取地点内的敌对角色 |
| `generate_npc_at(location_id, npc_type)` | 根据模板动态生成 NPC |

---

### NPC 系统

**文件位置**：`jag/world/npc.py`

NPC 模块定义了非玩家角色的完整数据模型，支持自主行为、记忆系统和社会关系。

#### NPC 类

```python
@dataclass
class NPC:
    id: str                          # NPC 唯一标识
    name: str                        # NPC 名称
    description: str                 # NPC 描述
    location_id: str                 # 所在地点 ID
    
    # 性格属性
    goal: str                        # 主要目标
    desires: list[str]               # 欲望列表
    fears: list[str]                 # 恐惧列表
    personality: str                 # 性格类型：friendly/stern/curious/charming/neutral
    
    # 运行状态
    state: NPCState                  # 当前状态
    
    # 记忆系统
    memory: MemoryStore              # 记忆存储（来自 knowledge 模块）
    
    # 社交关系
    relationships: dict[str, float]  # 与其他角色的关系值 (-100..100)
    
    # 资源
    resources: dict[str, int]        # 资源数量，如 {"gold": 10}
    inventory: list[str]             # 物品列表
    
    # 日程安排
    schedule: list[ScheduleEntry]    # 日常活动日程
    
    # 属性值
    attributes: dict[str, int]       # 六维属性：STR/DEX/CON/INT/WIS/CHA
```

#### NPCState 运行状态

```python
@dataclass
class NPCState:
    mood: str = "neutral"            # 情绪：happy/neutral/sad/angry/fearful
    energy: float = 1.0              # 精力值 (0.0-1.0)
    hunger: float = 0.0              # 饥饿值 (0.0-1.0)
    current_action: str = ""         # 当前行为描述
    current_location_id: str = ""    # 当前位置
```

状态衰减机制（由 TickEngine 驱动）：
- 每回合精力 -0.02
- 每回合饥饿 +0.03

#### ScheduleEntry 日程条目

```python
@dataclass
class ScheduleEntry:
    hour_start: int                  # 开始小时
    hour_end: int                    # 结束小时
    activity: str                    # 活动描述
    location_id: str                 # 活动地点
```

NPC 通过 `get_current_schedule(hour)` 方法获取当前时段应执行的日程。

#### 核心方法

| 方法 | 说明 |
|------|------|
| `get_current_schedule(hour)` | 获取当前小时的日程条目 |
| `update_relationship(char_id, delta)` | 更新与某角色的关系值（范围限制 -100..100） |
| `get_observation(world_data)` | 构建 NPC 对世界的感知数据 |
| `record_memory(content, importance, turn)` | 记录一条记忆 |

#### 观察系统

NPC 通过 `get_observation()` 获取局部感知，包含：
- 当前地点信息
- 附近角色列表
- 附近物品列表
- 当前时间
- 自身状态（情绪、精力、饥饿、位置）

---

## 模拟器说明

### EconomySimulator：供需经济模拟

**文件位置**：`jag/world/economy.py`

经济模拟器基于供需关系驱动商品价格波动，支持多地点独立市场。

#### Commodity 商品

```python
@dataclass
class Commodity:
    id: str                          # 商品标识
    name: str                        # 商品名称
    base_price: float                # 基准价格
    current_price: float             # 当前价格
    supply: float                    # 供应量
    demand: float                    # 需求量
```

#### Market 市场

```python
@dataclass
class Market:
    location_id: str                 # 市场所在地点
    commodities: dict[str, Commodity] # 该地点的商品字典
```

#### EconomySimulator 类

```python
class EconomySimulator:
    markets: dict[str, Market]       # 所有市场
    volatility: float                # 价格波动系数 (默认 0.1)
    transactions: list[dict]         # 交易记录
```

#### 价格计算公式

```python
ratio = demand / supply              # 供需比
noise = 1.0 + random(-volatility, volatility)
current_price = base_price * ratio * noise
```

当供应量为 0 时，ratio 默认为 2.0（价格翻倍）。

#### 交易方法

| 方法 | 说明 |
|------|------|
| `buy(location_id, commodity_id, quantity, buyer_id)` | 购买商品，返回总花费，减少供应、增加需求 |
| `sell(location_id, commodity_id, quantity, seller_id)` | 出售商品，返回总收入（按 80% 价格），增加供应、减少需求 |

购买会触发需求 +0.5*quantity，出售会触发需求 -0.3*quantity。

#### Tick 执行

每回合 `tick()` 方法：
1. 遍历所有市场的所有商品
2. 根据供需比和波动系数重新计算价格
3. 当价格偏离基准价超过 50% 时，生成 `price_shift` 事件

---

### FactionSimulator：派系关系矩阵

**文件位置**：`jag/world/faction.py`

派系模拟器管理世界中的组织势力及其相互关系，支持玩家声誉系统。

#### Faction 派系

```python
@dataclass
class Faction:
    id: str                          # 派系唯一标识
    name: str                        # 派系名称
    description: str                 # 派系描述
    faction_type: str                # 类型：organization/guild/cult 等
    leader_id: str                   # 领导者 ID
    members: list[str]               # 成员 ID 列表
    goals: list[str]                 # 派系目标列表
    resources: dict[str, int]        # 资源：{"gold": 100, "influence": 10}
    player_reputation: int           # 玩家声誉 (-100..100)
```

#### FactionSimulator 类

```python
class FactionSimulator:
    factions: dict[str, Faction]     # 所有派系
    relations: dict[tuple, str]      # 派系关系矩阵
```

#### 关系类型

| 关系值 | 说明 |
|--------|------|
| `hostile` | 敌对状态 |
| `neutral` | 中立状态 |
| `friendly` | 友好状态 |
| `allied` | 同盟状态 |

关系存储使用排序后的派系 ID 元组作为 key，确保对称性：
```python
key = tuple(sorted([faction_a, faction_b]))
```

#### 核心方法

| 方法 | 说明 |
|------|------|
| `add_faction(faction)` | 添加派系 |
| `set_relation(faction_a, faction_b, relation)` | 设置两个派系的关系 |
| `get_relation(faction_a, faction_b)` | 获取两个派系的关系（默认 neutral） |
| `modify_reputation(faction_id, delta)` | 修改玩家对某派系的声誉 |

#### Tick 执行

每回合 `tick()` 方法检查敌对派系对，生成 `faction_tension` 事件：
```python
{
    "type": "faction_tension",
    "factions": [faction_ids],
    "description": "派系间的紧张关系描述"
}
```

---

### WeatherSimulator：马尔可夫链天气

**文件位置**：`jag/world/weather.py`

天气模拟器使用马尔可夫链实现季节性天气变化，每个区域独立维护天气状态。

#### 天气状态

```python
WEATHER_STATES = ["clear", "cloudy", "rain", "storm", "snow", "fog"]
```

#### WeatherState 天气状态

```python
@dataclass
class WeatherState:
    region_id: str                   # 区域 ID
    current: str                     # 当前天气状态
    temperature: float               # 温度
    wind_speed: float                # 风速
```

#### 季节转移概率矩阵

每个季节定义独立的转移概率矩阵，格式为：
```python
{
    season: {
        current_weather: {
            next_weather: probability
        }
    }
}
```

例如春季的雨天转移概率：
```python
"spring": {
    "rain": {
        "cloudy": 0.4,
        "rain": 0.4,
        "storm": 0.1,
        "clear": 0.1
    }
}
```

夏季晴天有更高的保持概率（0.7），冬季有雪的概率显著提升。

#### 天气效果

不同天气对游戏机制的影响：

| 天气 | 感知修正 | 移动修正 | 战斗修正 |
|------|----------|----------|----------|
| clear | 1.0 | 1.0 | 1.0 |
| cloudy | 0.9 | 1.0 | 1.0 |
| rain | 0.7 | 0.8 | 0.9 |
| storm | 0.4 | 0.5 | 0.7 |
| snow | 0.6 | 0.6 | 0.8 |
| fog | 0.3 | 0.7 | 0.9 |

通过 `get_effects(region_id)` 获取当前天气的效果修正。

#### Tick 执行

每回合 `tick(season)` 方法：
1. 遍历所有区域的天气状态
2. 根据季节和当前天气查询转移概率矩阵
3. 使用加权随机选择下一天气状态
4. 根据季节和天气更新温度（平滑过渡）
5. 天气变化时生成 `weather_change` 事件

温度计算：
```python
base_temps = {"spring": 15, "summer": 25, "autumn": 12, "winter": 0}
target = base_temp + weather_modifier
temperature += (target - temperature) * 0.3  # 平滑过渡
```

---

## 任务生成系统

**文件位置**：`jag/world/quest.py`

任务生成器根据世界事件动态生成任务，使用模板匹配机制。

### Quest 数据结构

```python
@dataclass
class Quest:
    id: str                          # 任务唯一标识
    title: str                       # 任务标题
    description: str                 # 任务描述
    quest_type: str                  # 类型：main/side
    status: str                      # 状态：available/active/completed
    giver_id: str                    # 任务发布者 ID
    objectives: list[QuestObjective] # 任务目标列表
    rewards: dict                    # 奖励：{"xp": 50, "gold": 20}
    source: str                      # 事件来源类型
```

```python
@dataclass
class QuestObjective:
    description: str                 # 目标描述
    completed: bool = False          # 是否完成
```

### QuestTemplate 任务模板

```python
@dataclass
class QuestTemplate:
    name: str                        # 模板名称
    title_template: str              # 标题模板（支持占位符）
    description_template: str        # 描述模板
    quest_type: str                  # 任务类型
    trigger_conditions: dict         # 触发条件
    objectives: list[str]            # 目标模板列表
    rewards: dict                    # 奖励模板
```

### 默认任务模板

| 模板名 | 触发条件 | 示例标题 |
|--------|----------|----------|
| escort | `npc_need: safety` | 护送 {npc_name} 到 {location} |
| eliminate | `threat_nearby` | 消灭 {location} 的 {threat} |
| delivery | `npc_need: item` | 将 {item} 送到 {npc_name} |
| investigate | `world_event` | 调查 {location} 的 {event} |

模板使用 `{placeholder}` 占位符，从事件数据中提取填充。

### QuestGenerator 类

```python
class QuestGenerator:
    templates: list[QuestTemplate]   # 任务模板列表
    active_quests: dict[str, Quest]  # 活跃任务字典
```

#### 核心方法

| 方法 | 说明 |
|------|------|
| `check(world_state, events)` | 检查事件并生成匹配的任务 |
| `add_template(template)` | 添加自定义任务模板 |
| `complete_objective(quest_id, objective_index)` | 标记任务目标完成 |

#### 生成流程

1. `check()` 接收世界事件列表
2. 遍历每个事件，匹配模板的触发条件
3. 使用事件数据填充模板占位符
4. 生成 Quest 对象并加入活跃任务池
5. 当所有目标完成时，自动将任务标记为 completed

#### 触发条件匹配

```python
# 条件匹配逻辑
all(event.get(k) == v for k, v in conditions.items() if k != "need")
```

条件为字典形式，支持任意字段匹配。

---

## 世界构建器

**文件位置**：`jag/world/world_builder.py`

WorldBuilder 提供基于标签组合的世界生成能力，支持纯代码生成和 LLM 辅助生成两种模式。

### 标签系统

#### 标签分类

| 分类 | 说明 | 可选值 |
|------|------|--------|
| genre | 类型 | fantasy/scifi/postapoc/wuxia/mystery/steampunk/horror |
| era | 时代 | ancient/medieval/renaissance/industrial/modern/future |
| atmosphere | 氛围（可多选） | light/dark/epic/mystery/peaceful/chaotic |
| terrain | 地形（可多选） | forest/desert/ocean/mountain/city/underground/swamp/plains |
| magic | 魔法等级 | none/low/medium/high |
| danger | 危险等级 | safe/moderate/dangerous/deadly |

每个类型都有预设的数据池：
- 区域名称和描述
- 中心枢纽地点
- 酒馆/休息地点
- NPC 角色池和名称池
- 初始物品列表
- 地点描述库

### 生成流程

```python
def build_from_tags(world_name, tags, description):
    1. _parse_tags()      # 解析标签，初始化状态
    2. build_step_region()    # 创建区域
    3. build_step_locations() # 创建地点（枢纽+酒馆+地形+魔法地点）
    4. build_step_npcs()      # 创建 NPC（固定角色+随机角色）
    5. build_step_lore()      # 生成世界背景故事
    6. build_step_finalize()  # 添加玩家，完成构建
```

### 地点生成逻辑

1. **枢纽地点**（hub）：安全中心，光照 8，危险 0
2. **酒馆地点**（tavern）：休息场所，光照 6，危险 0
3. **地形地点**：根据 terrain 标签从 `_TERRAIN_LOCS` 池选取
4. **魔法地点**：根据 magic 标签从 `_MAGIC_LOCS` 池选取

光照和危险等级会根据氛围、时代、危险标签进行修正：
```python
light = base_light + era_light + atmosphere_light
danger = base_danger + danger_base + atmosphere_danger
```

### NPC 生成逻辑

每个类型有固定的 NPC 角色池和映射：
- 酒馆老板（总是生成在 tavern）
- 战士/骑士（生成在 hub）
- 其他角色（随机分配到低危险地点）

NPC 自动生成日程：
```python
[
    ScheduleEntry(6, 22, "日常活动", location_id),
    ScheduleEntry(22, 6, "休息", location_id)
]
```

### LLM 辅助生成

`build_with_llm()` 方法支持使用 LLM 生成自定义世界：
1. 构建提示词，包含标签信息
2. 请求 LLM 返回 JSON 格式的世界数据
3. 解析 JSON 并应用到 WorldState
4. 若 LLM 失败，回退到纯代码生成

---

## 与其他模块的关系

| 模块 | 关系 |
|------|------|
| `core/events` | 通过 EventBus 发布世界事件 |
| `core/rules` | 通过 RuleEngine 评估规则变更 |
| `core/dice` | 通过 DiceRoller 解析行动结果 |
| `knowledge/memory` | NPC 使用 MemoryStore 存储记忆 |
| `knowledge/graph` | TickEngine 更新知识图谱 |
| `agents/game_master` | GameMaster 持有 WorldBuilder 和 WorldState |

---

## 设计要点

1. **数据驱动**：所有预设数据以常量字典形式存储，便于扩展
2. **确定性生成**：使用标签哈希作为随机种子，相同标签生成相同世界
3. **事件驱动**：世界变化通过事件传播，支持订阅机制
4. **并发处理**：NPC Tick 使用 Semaphore 控制并发度
5. **渐进构建**：WorldBuilder 支持分步构建，适合 UI 交互展示进度