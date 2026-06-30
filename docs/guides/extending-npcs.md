# NPC 扩展指南

本指南介绍如何创建和配置 NPC（非玩家角色），包括 NPC 的数据模型、行为系统和日程安排。

## 目录

- [创建新 NPC](#创建新-npc)
- [配置 NPC 行为](#配置-npc-行为)
- [配置 NPC 日程](#配置-npc-日程)

---

## 创建新 NPC

### NPC 类的属性

`NPC` 类是游戏中所有 NPC 的核心数据模型，定义在 `jag/world/npc.py` 中。以下是主要属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | NPC 的唯一标识符 |
| `name` | `str` | NPC 的显示名称 |
| `description` | `str` | NPC 的详细描述 |
| `location_id` | `str` | NPC 的初始位置 ID |
| `attributes` | `dict[str, int]` | 角色属性，默认包含 STR/DEX/CON/INT/WIS/CHA |
| `personality` | `str` | 性格特征（如 friendly、gruff、cautious、mysterious、cunning） |
| `goal` | `str` | NPC 的主要目标 |
| `desires` | `list[str]` | NPC 的欲望列表 |
| `fears` | `list[str]` | NPC 的恐惧列表 |
| `memory` | `MemoryStore` | NPC 的记忆存储系统 |
| `relationships` | `dict[str, float]` | 与其他角色的关系（-100 到 100） |
| `resources` | `dict[str, int]` | NPC 拥有的资源（如金币） |
| `inventory` | `list[str]` | NPC 的物品清单 |
| `schedule` | `list[ScheduleEntry]` | NPC 的日程安排 |
| `state` | `NPCState` | NPC 的运行状态 |

### NPCState 运行状态

`NPCState` 定义了 NPC 的运行时状态：

```python
@dataclass
class NPCState:
    mood: str = "neutral"      # 情绪状态：happy, neutral, sad, angry, fearful
    energy: float = 1.0        # 精力值：0.0-1.0
    hunger: float = 0.0        # 饥饿度：0.0-1.0
    current_action: str = ""  # 当前行为描述
    current_location_id: str = ""  # 当前位置
```

### ScheduleEntry 日程条目

每个日程条目 `ScheduleEntry` 包含：

```python
@dataclass
class ScheduleEntry:
    hour_start: int = 0    # 开始时间（小时，0-23）
    hour_end: int = 0      # 结束时间（小时，0-23）
    activity: str = ""     # 活动描述
    location_id: str = ""  # 活动地点 ID
```

### 示例：创建一个 NPC

以下是在 YAML 配置文件中定义 NPC 的示例：

```yaml
npcs:
  - id: innkeeper_mara
    name: 玛拉
    description: 一位温暖慈祥的女性，经营着炉石客栈。她对村里每个人的事都了如指掌。
    location_id: tavern
    personality: friendly
    goal: 让客栈生意兴隆，保护客人安全
    desires: ["好评", "稳定收入"]
    fears: ["强盗", "火灾"]
    attributes:
      STR: 8
      DEX: 10
      CON: 12
      INT: 11
      WIS: 14
      CHA: 16
    resources:
      gold: 50
    schedule:
      - { hour_start: 5, hour_end: 22, activity: "经营客栈", location_id: tavern }
      - { hour_start: 22, hour_end: 5, activity: "睡觉", location_id: tavern }
```

---

## 配置 NPC 行为

### NPCAgent 的观察→思考→规划→行动循环

`NPCAgent` 类（定义在 `jag/agents/npc_agent.py`）实现了 NPC 的自主行为循环：

```
观察 (Observe) → 思考 (Think) → 规划 (Plan) → 行动 (Act)
```

#### 1. 观察 (Observe)

NPC 收集周围环境信息，构建 `NPCObservation` 对象：

```python
@dataclass
class NPCObservation:
    location_id: str           # 当前位置 ID
    location_name: str         # 当前位置名称
    time_of_day: str           # 时间描述
    hour: int                  # 当前小时
    nearby_characters: list[str]  # 附近的角色
    nearby_items: list[str]    # 附近的物品
    energy: float              # 精力值
    hunger: float              # 饥饿度
    mood: str                  # 情绪状态
    schedule_activity: str     # 当前日程活动
    schedule_location: str     # 日程地点
```

#### 2. 思考 (Think)

根据观察结果更新 NPC 的内部状态：

- 精力过低 (< 0.2) 或饥饿过高 (> 0.8) → 情绪变为 sad
- 精力充足且饥饿低 → 情绪变为 happy
- 附近有敌对关系角色 (关系 < -50) → 情绪变为 fearful

#### 3. 规划 (Plan) & 行动 (Act)

根据策略选择合适的行动类型：

| 行动类型 | 说明 |
|----------|------|
| `move` | 前往另一个地点 |
| `interact` | 与物体或实体互动 |
| `work` | 执行工作/职责 |
| `rest` | 休息恢复精力 |
| `trade` | 买卖商品 |
| `patrol` | 巡逻站岗 |
| `socialize` | 与附近 NPC 交谈 |
| `flee` | 逃离危险 |
| `idle` | 什么也不做 |

### 行为策略

#### LLM 策略

当 LLM 可用时，`NPCAgent` 使用结构化输出决定行为：

```python
class NPCActionModel(BaseModel):
    action_type: str      # 行动类型
    target: str           # 目标实体或位置 ID
    reason: str           # 选择该行动的原因
    dialogue: str         # 可选的对话内容
    params: dict[str, Any]  # 额外参数
```

LLM 会综合考虑：
- NPC 的性格、目标和欲望
- 当前状态（精力、饥饿、情绪）
- 环境信息（时间、地点、附近角色）
- 日程安排

#### 规则策略

当 LLM 不可用时，使用基于规则的决策系统，按优先级执行：

1. **自我保护**（最高优先级）
   - 精力 < 0.15 → 休息
   - 饥饿 > 0.85 → 寻找食物

2. **恐惧响应**
   - 情绪为 fearful → 逃离危险

3. **日程遵循**
   - 不在日程地点 → 移动到日程地点
   - 在日程地点 → 执行日程活动

4. **社交行为**
   - 附近有角色且性格为 friendly/social → 与其交谈

5. **默认行为**
   - 无所事事 → 空闲

### 目标系统

NPC 的目标通过以下属性配置：

- `goal`: 主要目标（字符串描述）
- `desires`: 欲望列表（驱动行为动机）
- `fears`: 恐惧列表（触发回避行为）

示例：

```yaml
goal: 保护村庄免受森林威胁
desires: ["和平", "稀有草药"]
fears: ["遗迹中的黑暗力量"]
```

---

## 配置 NPC 日程

### NPCSchedule 表结构

NPC 的日程通过 `schedule` 属性配置，是一个 `ScheduleEntry` 列表。

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `hour_start` | `int` | 活动开始时间（0-23） |
| `hour_end` | `int` | 活动结束时间（0-23） |
| `activity` | `str` | 活动描述 |
| `location_id` | `str` | 活动发生的地点 ID |

**注意**：时间可以跨越午夜，例如 `hour_start: 22, hour_end: 5` 表示从晚上 10 点到次日早上 5 点。

### 日程匹配逻辑

NPC 使用 `get_current_schedule(hour)` 方法获取当前小时的日程条目：

```python
def get_current_schedule(self, hour: int) -> ScheduleEntry | None:
    for entry in self.schedule:
        if entry.hour_start <= hour < entry.hour_end:
            return entry
    return None
```

### 示例：配置 NPC 日程

以下示例展示了几种典型的日程配置模式：

#### 1. 常规日程（旅馆老板）

```yaml
schedule:
  - { hour_start: 5, hour_end: 22, activity: "经营客栈", location_id: tavern }
  - { hour_start: 22, hour_end: 5, activity: "睡觉", location_id: tavern }
```

#### 2. 多地点日程（铁匠）

```yaml
schedule:
  - { hour_start: 6, hour_end: 18, activity: "锻造武器", location_id: blacksmith }
  - { hour_start: 18, hour_end: 22, activity: "在客栈喝酒", location_id: tavern }
  - { hour_start: 22, hour_end: 6, activity: "睡觉", location_id: blacksmith }
```

#### 3. 巡逻日程（猎人）

```yaml
schedule:
  - { hour_start: 5, hour_end: 12, activity: "巡逻森林边缘", location_id: village_gate }
  - { hour_start: 12, hour_end: 16, activity: "侦察森林", location_id: forest_path }
  - { hour_start: 16, hour_end: 20, activity: "向村庄汇报", location_id: village_square }
  - { hour_start: 20, hour_end: 5, activity: "睡觉", location_id: tavern }
```

#### 4. 隐秘日程（盗贼）

```yaml
schedule:
  - { hour_start: 6, hour_end: 18, activity: "伏击旅行者", location_id: forest_path }
  - { hour_start: 18, hour_end: 6, activity: "在营地休息", location_id: forest_camp }
```

---

## 完整示例

以下是一个完整的 NPC 配置示例：

```yaml
npcs:
  - id: hunter_lyra
    name: 莱拉
    description: 一位目光敏锐的精灵猎人，负责巡逻森林边缘。她行动无声，熟悉每一条小径。
    location_id: village_gate
    personality: cautious
    goal: 保护村庄免受森林威胁
    desires: ["和平", "稀有草药"]
    fears: ["遗迹中的黑暗力量"]
    attributes:
      STR: 10
      DEX: 16
      CON: 12
      INT: 12
      WIS: 15
      CHA: 10
    resources:
      gold: 20
    schedule:
      - { hour_start: 5, hour_end: 12, activity: "巡逻森林边缘", location_id: village_gate }
      - { hour_start: 12, hour_end: 16, activity: "侦察森林", location_id: forest_path }
      - { hour_start: 16, hour_end: 20, activity: "向村庄汇报", location_id: village_square }
      - { hour_start: 20, hour_end: 5, activity: "睡觉", location_id: tavern }
```

---

## 参考资料

- 源码：`jag/world/npc.py` - NPC 数据模型定义
- 源码：`jag/agents/npc_agent.py` - NPC 行为代理实现
- 示例：`jag/demo/npcs.yaml` - NPC 配置示例