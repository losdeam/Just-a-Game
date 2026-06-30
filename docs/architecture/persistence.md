# Persistence 模块架构文档

## 1. 模块职责

Persistence 模块是 JAG（Just-a-Game）项目的数据持久化层，负责：

- **数据存储**：提供可靠的数据持久化机制
- **数据访问抽象**：通过 Repository 模式隔离业务逻辑与数据访问实现
- **模型定义**：定义游戏世界中的所有数据实体
- **多后端支持**：支持 SQLite 文件数据库和内存数据库

模块位置：`jag/persistence/`

---

## 2. Repository 模式

### 2.1 设计理念

Repository 模式为数据访问提供统一的抽象接口，使得业务层无需关心底层存储实现细节。这种设计带来以下优势：

- **解耦**：业务逻辑与数据访问实现分离
- **可测试**：测试时可轻松替换为内存数据库
- **可扩展**：未来可支持其他数据库后端

### 2.2 Repository 协议

定义于 `repository.py`，提供以下核心操作：

| 方法 | 说明 |
|------|------|
| `save(entity)` | 保存实体（插入或更新） |
| `find(model, entity_id)` | 根据 ID 查找实体 |
| `find_all(model, **filters)` | 根据条件查找所有匹配实体 |
| `delete(entity)` | 删除实体 |
| `update(entity)` | 更新实体 |

### 2.3 SQLiteRepository 实现

定义于 `sqlite_backend.py`，提供完整的 SQLite 数据访问实现：

```python
class SQLiteRepository:
    def __init__(self, engine: Engine) -> None
    def save(self, entity: SQLModel) -> None
    def find(self, model: type[T], entity_id: str) -> T | None
    def find_all(self, model: type[T], **filters: Any) -> list[T]
    def delete(self, entity: SQLModel) -> None
    def update(self, entity: SQLModel) -> None
    def save_batch(self, entities: list[SQLModel]) -> None  # 批量保存
    def query(self, model: type[T], conditions: dict[str, Any]) -> list[T]
    def count(self, model: type[T], **filters: Any) -> int
```

**特性**：
- 使用 SQLModel ORM 进行数据映射
- 支持过滤条件查询（包括 `in` 查询）
- 支持批量操作，在单事务中完成

---

## 3. 数据库配置

### 3.1 Database 协议

定义于 `database.py`，规定数据库实现必须提供的接口：

```python
class Database(Protocol):
    @property
    def engine(self) -> Engine: ...
    def create_tables(self) -> None: ...
    def close(self) -> None: ...
```

### 3.2 支持的数据库类型

#### SQLiteDatabase

基于文件的 SQLite 数据库，适用于生产环境：

```python
db = SQLiteDatabase(path="jag_world.db")
db.create_tables()
```

**配置参数**：
- `path`: 数据库文件路径，默认为 `jag_world.db`

#### InMemoryDatabase

内存数据库，适用于测试环境：

```python
db = InMemoryDatabase()
db.create_tables()
```

**特点**：
- 数据存储在内存中，进程结束后数据丢失
- 无需文件 I/O，测试速度更快
- 完全隔离的数据库实例

### 3.3 使用示例

```python
from jag.persistence.database import SQLiteDatabase
from jag.persistence.sqlite_backend import SQLiteRepository
from jag.persistence.models import Character

# 初始化数据库
db = SQLiteDatabase("game_world.db")
db.create_tables()

# 创建 Repository
repo = SQLiteRepository(db.engine)

# 数据操作
character = Character(id="hero_001", name="Hero")
repo.save(character)

# 查询
found = repo.find(Character, "hero_001")
all_alive = repo.find_all(Character, is_alive=True)

# 清理
db.close()
```

---

## 4. 数据模型

Persistence 模块定义了 **20 张数据表**，涵盖游戏世界的完整状态。

### 4.1 核心实体

| 表名 | 类名 | 说明 |
|------|------|------|
| `characters` | Character | 游戏角色（NPC、玩家、生物） |
| `items` | Item | 物品（武器、护甲、消耗品、工具） |
| `locations` | Location | 地点（房间、建筑、户外、地牢） |
| `regions` | Region | 区域（定居点、荒野、地牢、城市） |

#### Character 核心字段
- `character_type`: 角色类型（npc/player/creature）
- `hp`, `max_hp`: 生命值
- `attributes_json`: 属性（STR/DEX 等）
- `skills_json`: 技能
- `status_effects_json`: 状态效果

#### Item 核心字段
- `item_type`: 物品类型（weapon/armor/consumable/tool/misc）
- `properties_json`: 物品属性（可燃/锋利等）
- `quantity`, `value`, `weight`: 数量、价值、重量

#### Location 核心字段
- `location_type`: 地点类型（room/building/outdoor/dungeon）
- `connected_locations_json`: 相连地点列表
- `light_level`, `danger_level`: 光照等级、危险等级

### 4.2 任务系统

| 表名 | 类名 | 说明 |
|------|------|------|
| `quests` | Quest | 任务（主线、支线、个人、派系） |

#### Quest 核心字段
- `quest_type`: 任务类型（main/side/personal/faction）
- `status`: 状态（available/active/completed/failed）
- `objectives_json`: 目标列表
- `rewards_json`: 奖励（经验、金币、物品）
- `source`: 任务来源（npc_need/faction_conflict/world_event/player_action）

### 4.3 派系与关系

| 表名 | 类名 | 说明 |
|------|------|------|
| `factions` | Faction | 派系（组织、公会、王国、部落） |
| `relationships` | Relationship | 实体间关系 |
| `npc_goals` | NPCGoal | NPC 目标（长期、短期、即时） |
| `npc_schedules` | NPCSchedule | NPC 日程安排 |

#### Faction 核心字段
- `faction_type`: 派系类型（organization/guild/kingdom/tribe）
- `member_ids_json`: 成员 ID 列表
- `goals_json`: 派系目标
- `resources_json`: 资源（金币、影响力）
- `reputation`: 玩家声望

#### Relationship 核心字段
- `relation_type`: 关系类型（friendly/neutral/hostile/allied/enemy）
- `value`: 关系值（-100 到 100）

### 4.4 事件与世界状态

| 表名 | 类名 | 说明 |
|------|------|------|
| `events` | Event | 游戏事件（战斗、交互、环境等） |
| `world_events` | WorldEvent | 世界级事件（战争、瘟疫、节日、灾难） |
| `story_threads` | StoryThread | 故事线 |
| `economy_state` | EconomyState | 经济状态（商品价格、供需） |
| `weather_state` | WeatherState | 天气状态 |

#### Event 核心字段
- `event_type`: 事件类型（combat/interaction/environment/quest/social/economy）
- `turn`: 发生回合
- `data_json`: 事件详情

#### WorldEvent 核心字段
- `event_type`: 世界事件类型（war/plague/festival/disaster/political）
- `severity`: 严重程度（1-10）
- `turn_started`, `turn_resolved`: 开始和解决回合

#### StoryThread 核心字段
- `thread_type`: 故事线类型（main/side/personal）
- `status`: 状态（dormant/active/climax/resolved）
- `tension_level`: 紧张程度（0-10）

### 4.5 知识图谱

| 表名 | 类名 | 说明 |
|------|------|------|
| `knowledge_nodes` | KnowledgeNode | 知识节点（角色、物品、地点、派系、概念） |
| `knowledge_edges` | KnowledgeEdge | 知识边（实体间关系） |

#### KnowledgeNode 核心字段
- `node_type`: 节点类型（character/item/location/faction/concept）
- `attributes_json`: 节点属性

#### KnowledgeEdge 核心字段
- `relation_type`: 关系类型（owns/likes/hates/allied_with/enemy_of/knows/owes）
- `weight`: 关系权重

### 4.6 记忆系统

| 表名 | 类名 | 说明 |
|------|------|------|
| `memory_short` | MemoryShort | 短期记忆 |
| `memory_long` | MemoryLong | 长期记忆 |

#### MemoryShort 核心字段
- `owner_id`: 记忆所有者（角色 ID 或 "player"）
- `event_id`: 关联事件 ID
- `importance`: 重要性（1-10）
- `turn`: 发生回合

#### MemoryLong 核心字段
- `memory_type`: 记忆类型（reputation/relationship/historical/personal）
- `source_event_ids_json`: 来源事件列表
- `last_accessed`: 最后访问时间

### 4.7 日志系统

| 表名 | 类名 | 说明 |
|------|------|------|
| `action_logs` | ActionLog | 行动日志 |
| `rule_triggers` | RuleTrigger | 规则触发记录 |

#### ActionLog 核心字段
- `action_type`: 行动类型
- `action_data_json`: 行动数据
- `result`: 结果（success/failure/critical_success/critical_failure）

#### RuleTrigger 核心字段
- `rule_name`: 规则名称
- `trigger_context_json`: 触发上下文
- `effects_json`: 效果列表
- `chain_depth`: 链式触发深度

---

## 5. 表关系图

```
Region (区域)
  └── Location (地点) [region_id]
        ├── Character (角色) [location_id]
        │     ├── NPCGoal (NPC目标) [npc_id]
        │     ├── NPCSchedule (NPC日程) [npc_id]
        │     └── MemoryShort/MemoryLong (记忆) [owner_id]
        └── Item (物品) [location_id / owner_id]

Faction (派系)
  └── Character (角色) [leader_id / member_ids]

Character (角色)
  ├── Relationship (关系) [source_id → target_id]
  └── Quest (任务) [giver_id]

KnowledgeNode (知识节点)
  └── KnowledgeEdge (知识边) [source_id → target_id]

Event (事件)
  └── MemoryShort (短期记忆) [event_id]

WorldEvent (世界事件)
  └── Region (区域) [region_id]

StoryThread (故事线)
  ├── related_events_json
  └── related_npcs_json

EconomyState (经济状态)
  └── Location (地点) [location_id]

WeatherState (天气状态)
  └── Region (区域) [region_id]
```

---

## 6. 模块文件结构

```
jag/persistence/
├── __init__.py        # 模块初始化，导出公共接口
├── database.py        # Database 协议与实现（SQLiteDatabase、InMemoryDatabase）
├── models.py          # 20 张数据表的模型定义
├── repository.py      # Repository 协议定义
└── sqlite_backend.py  # SQLiteRepository 实现
```

---

## 7. 设计决策

### 7.1 为什么使用 JSON 字段？

部分字段（如 `attributes_json`、`objectives_json`）采用 JSON 字符串存储，原因：

- **灵活性**：支持动态属性，无需修改表结构
- **简单性**：SQLite 原生支持不复杂嵌套查询，JSON 存储足够
- **便捷方法**：模型类提供 `get_*` / `set_*` 方法简化访问

### 7.2 为什么使用 Protocol 而非抽象类？

- **鸭子类型**：Python 的 Protocol 支持结构子类型
- **低耦合**：实现类无需显式继承
- **易于测试**：可轻松创建 Mock 实现

### 7.3 时间戳字段

多个表包含 `created_at` 和 `updated_at` 字段，使用 ISO 8601 格式字符串存储：
- 格式：`datetime.now().isoformat()`
- 示例：`2024-01-15T10:30:45.123456`