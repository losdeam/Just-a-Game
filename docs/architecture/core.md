# Core 模块架构文档

## 1. 模块概述

`jag.core` 是 Just-a-Game 的**基础机制层**，提供游戏运行所需的核心系统。该模块负责实现游戏规则的底层逻辑，为上层游戏系统提供稳定、可复用的基础设施。

**核心职责：**
- 骰子与随机性管理
- 事件驱动通信
- 规则评估与执行
- 物品属性与交互
- 环境感知与可见性

**模块结构：**
```
jag/core/
├── __init__.py      # 模块导出
├── dice.py          # D20骰子系统
├── events.py       # 事件总线与队列
├── rules.py        # 混合规则引擎
├── items.py        # 基于属性的物品系统
└── perception.py   # 环境感知过滤系统
```

---

## 2. Dice 系统（dice.py）

### 2.1 系统概述

Dice 系统实现了完整的 D20 骰子检定机制，支持优势/劣势、多种类型加值、暴击判定等功能，为游戏提供随机性和不确定性管理。

### 2.2 核心组件

#### 枚举类型

**ModifierType（加值类型）**
```python
class ModifierType(Enum):
    ATTRIBUTE = auto()    # 属性加值（如力量、敏捷）
    PROFICIENCY = auto()  # 熟练加值
    ITEM = auto()         # 物品加值
    STATUS = auto()       # 状态加值
```

**RollResult（检定结果）**
```python
class RollResult(Enum):
    CRITICAL_SUCCESS = "critical_success"  # 大成功（自然20）
    SUCCESS = "success"                    # 成功
    FAILURE = "failure"                    # 失败
    CRITICAL_FAILURE = "critical_failure"  # 大失败（自然1）
```

#### 数据类

**Modifier（加值）**
```python
@dataclass
class Modifier:
    mod_type: ModifierType  # 加值类型
    value: int              # 加值数值（可为负）
    source: str = ""        # 加值来源描述
```

**DiceResult（掷骰结果）**
```python
@dataclass
class DiceResult:
    base_roll: int              # 基础掷骰值
    modifiers: list[Modifier]   # 应用的加值列表
    total: int                  # 最终总值
    result: RollResult          # 检定结果
    advantage: bool             # 是否有优势
    disadvantage: bool          # 是否有劣势
    sides: int                  # 骰子面数
```

提供属性方法：
- `is_success`：判断是否成功
- `is_critical`：判断是否暴击
- `summary()`：生成人类可读的结果描述

### 2.3 核心类：DiceRoller

**初始化**
```python
def __init__(self, seed: int | None = None)
```
- 可选种子参数支持可重复的随机序列
- 内部使用 `random.Random` 实例保证独立性

**主要方法**

**1. roll() - 基础掷骰**
```python
def roll(
    self,
    sides: int = 20,                    # 骰子面数，默认D20
    count: int = 1,                     # 掷骰次数
    advantage: bool = False,            # 优势（取两次掷骰中的较高值）
    disadvantage: bool = False,         # 劣势（取两次掷骰中的较低值）
    modifiers: list[Modifier] | None,    # 加值列表
    dc: int = 10,                       # 难度等级
) -> DiceResult
```

**优势/劣势机制：**
- 同时存在优势与劣势时相互抵消，视为普通掷骰
- 优势：掷两个骰子，取较高值
- 劣势：掷两个骰子，取较低值
- 多骰掷骰（count > 1）：掷多个骰子并求和

**暴击判定：**
- 自然骰值为最大值（如 D20 的 20）：大成功
- 自然骰值为 1：大失败
- 其他情况：根据总值是否达到 DC 判定成功或失败

**2. roll_check() - 便捷检定方法**
```python
def roll_check(
    self,
    attribute_mod: int = 0,      # 属性加值
    proficiency_mod: int = 0,    # 熟练加值
    item_mod: int = 0,            # 物品加值
    status_mod: int = 0,          # 状态加值
    dc: int = 10,
    advantage: bool = False,
    disadvantage: bool = False,
) -> DiceResult
```
自动构造 Modifier 对象并调用 `roll()`

**3. roll_damage() - 伤害掷骰**
```python
def roll_damage(self, dice_str: str) -> int
```
解析骰子表达式并计算伤害：
- 格式：`"2d6+3"` （2个6面骰加3）
- 支持加值和减值
- 结果下限为 0

### 2.4 使用示例

```python
roller = DiceRoller(seed=42)

# 基础属性检定
result = roller.roll_check(
    attribute_mod=3,      # 力量+3
    proficiency_mod=2,   # 熟练加值+2
    dc=15,
    advantage=True       # 有优势
)
print(result.summary())  # "d20: 18 (+3 +2) = 23 [success]"

# 伤害掷骰
damage = roller.roll_damage("2d6+4")
```

---

## 3. EventBus 系统（events.py）

### 3.1 系统概述

EventBus 提供发布/订阅模式的事件通信机制，支持异步事件处理和事件队列管理，实现游戏各模块间的松耦合通信。

### 3.2 核心组件

#### 枚举类型

**EventType（事件类型）**
```python
class EventType(Enum):
    COMBAT = "combat"           # 战斗事件
    INTERACTION = "interaction" # 交互事件
    ENVIRONMENT = "environment" # 环境事件
    QUEST = "quest"             # 任务事件
    SOCIAL = "social"           # 社交事件
    ECONOMY = "economy"         # 经济事件
    NPC_ACTION = "npc_action"   # NPC行动事件
    WORLD = "world"             # 世界事件
    SYSTEM = "system"           # 系统事件
    DANGER = "danger"           # 危险事件
```

#### 数据类

**GameEvent（游戏事件）**
```python
@dataclass
class GameEvent:
    event_type: EventType               # 事件类型
    source_id: str = ""                  # 事件源ID
    target_id: str = ""                  # 事件目标ID
    location_id: str = ""                 # 位置ID
    description: str = ""                # 事件描述
    data: dict[str, Any]                 # 事件附加数据
    turn: int = 0                        # 回合数
    timestamp: str                       # 时间戳（自动生成）
    id: str                              # 事件唯一ID（自动生成）
```

### 3.3 核心类

#### EventBus（事件总线）

**订阅机制：**
```python
# 订阅特定类型事件
def subscribe(self, event_type: EventType, handler: EventHandler)

# 订阅所有事件
def subscribe_all(self, handler: EventHandler)

# 取消订阅
def unsubscribe(self, event_type: EventType, handler: EventHandler)
```

**事件发布：**
```python
async def publish(self, event: GameEvent)
```
- 支持同步和异步处理器
- 按订阅顺序调用处理器
- 不阻塞发布者

**处理器类型：**
```python
EventHandler = Callable[[GameEvent], Coroutine[Any, Any, None] | None]
```
处理器可以是同步函数或异步协程。

#### EventQueue（事件队列）

FIFO 先进先出队列，用于存储待处理事件。

**主要方法：**
```python
def enqueue(self, event: GameEvent)     # 入队
def dequeue(self) -> GameEvent | None   # 出队
def peek(self) -> GameEvent | None      # 查看队首
def clear(self)                          # 清空队列
def get_history(self, limit: int = 20)  # 获取历史事件
```

**属性：**
- `is_empty`：队列是否为空
- `pending_count`：待处理事件数量

**历史记录：**
- 自动保存最近 100 个已处理事件
- 可通过 `get_history()` 查询历史

### 3.4 使用示例

```python
bus = EventBus()

# 订阅战斗事件
async def on_combat(event: GameEvent):
    print(f"Combat: {event.description}")

bus.subscribe(EventType.COMBAT, on_combat)

# 发布事件
event = GameEvent(
    event_type=EventType.COMBAT,
    source_id="player_1",
    target_id="goblin_5",
    description="Player attacks goblin",
    turn=10
)
await bus.publish(event)

# 使用队列
queue = EventQueue()
queue.enqueue(event)
pending = queue.dequeue()
```

---

## 4. RuleEngine 系统（rules.py）

### 4.1 系统概述

RuleEngine 是混合规则引擎，支持两种规则定义方式：
1. **声明式规则**：通过 YAML 文件定义，适合配置驱动
2. **注册式规则**：通过 Python 装饰器注册，适合复杂逻辑

### 4.2 核心组件

#### 数据类

**RuleCondition（规则条件）**
```python
@dataclass
class RuleCondition:
    attribute: str   # 属性路径，如 "source.health"、"target.state"
    operator: str    # 比较操作符
    value: Any       # 期望值
```

**支持的操作符：**
| 操作符 | 含义 | 示例 |
|--------|------|------|
| `eq` | 等于 | `source.level == 5` |
| `ne` | 不等于 | `target.alive != False` |
| `gt` | 大于 | `source.health > 10` |
| `lt` | 小于 | `target.distance < 5` |
| `gte` | 大于等于 | `source.mp >= 20` |
| `lte` | 小于等于 | `target.level <= 3` |
| `in` | 在列表中 | `target.type in ["goblin", "orc"]` |
| `not_in` | 不在列表中 | `source.status not_in ["poisoned"]` |
| `contains` | 包含 | `source.tags contains "fire"` |
| `has_property` | 具有属性 | `target has_property "wet"` |

**RuleEffect（规则效果）**
```python
@dataclass
class RuleEffect:
    action: str      # 动作类型
    target: str      # 目标路径
    value: Any       # 效果值
```

**支持的动作：**
- `set_state`：设置状态
- `emit_event`：发出事件
- `modify_attribute`：修改属性值
- `create_item`：创建物品
- `destroy_item`：销毁物品

**Rule（规则）**
```python
@dataclass
class Rule:
    name: str                        # 规则名称
    conditions: list[RuleCondition]  # 条件列表（AND关系）
    effects: list[RuleEffect]        # 效果列表
    probability: float = 1.0         # 触发概率（0.0-1.0）
    priority: int = 0                 # 优先级（高优先）
    max_chain_depth: int = 5         # 最大链式深度
    tags: list[str]                  # 标签
```

**RuleContext（规则上下文）**
```python
@dataclass
class RuleContext:
    source: dict[str, Any]   # 动作源
    target: dict[str, Any]   # 动作目标
    actor: dict[str, Any]    # 执行者
    world: dict[str, Any]    # 世界状态
    turn: int                # 当前回合
```

支持点号路径访问：`context.get_value("source.health")`

### 4.3 核心类

#### RuleEngine（规则引擎）

**初始化：**
```python
def __init__(self, event_bus: EventBus | None = None, max_chain_depth: int = 5)
```

**规则管理：**
```python
def add_rule(self, rule: Rule)           # 添加规则
def load_rules(self, path: str)          # 从YAML加载规则
```

**规则评估：**
```python
def evaluate(self, context: RuleContext) -> list[dict[str, Any]]
```
返回所有匹配规则产生的状态变更列表。

**执行流程：**
1. 按优先级排序规则
2. 逐一检查条件（AND 逻辑）
3. 通过概率检查
4. 应用效果并收集变更
5. 检查并执行 Python 处理器（如果存在）

### 4.4 YAML 规则格式

```yaml
- name: "fire_spreads_to_flammable"
  conditions:
    - attribute: "target.properties.flammable"
      operator: "eq"
      value: true
    - attribute: "source.state"
      operator: "eq"
      value: "on_fire"
  effects:
    - action: "set_state"
      target: "target"
      value: "on_fire"
  probability: 0.7
  priority: 10
  tags: ["fire", "environment"]

- name: "poison_damage"
  conditions:
    - attribute: "source.status"
      operator: "contains"
      value: "poisoned"
  effects:
    - action: "modify_attribute"
      target: "source.health"
      value: -5
  priority: 5
```

### 4.5 Python 注册规则

使用装饰器注册复杂规则处理器：

```python
from jag.core.rules import rule, RuleContext, RuleEffect

@rule("custom_combat_rule")
def handle_combat(context: RuleContext) -> list[RuleEffect]:
    """Python 实现的复杂规则"""
    if context.source.get("class") == "rogue":
        return [
            RuleEffect(
                action="modify_attribute",
                target="target.health",
                value=-context.actor.get("sneak_attack_damage", 0)
            )
        ]
    return []
```

**混合执行：**
当 YAML 规则名称与注册的 Python 规则匹配时：
1. 先执行 YAML 定义的 effects
2. 再执行 Python 处理器返回的额外 effects

### 4.6 使用示例

```python
# 创建规则引擎
bus = EventBus()
engine = RuleEngine(event_bus=bus)

# 方式1：加载YAML规则
engine.load_rules("data/rules/combat.yaml")

# 方式2：编程添加规则
engine.add_rule(Rule(
    name="heal_on_rest",
    conditions=[
        RuleCondition("source.action", "eq", "rest"),
        RuleCondition("source.in_combat", "eq", False),
    ],
    effects=[
        RuleEffect("modify_attribute", "source.health", 10)
    ],
    priority=5
))

# 评估规则
context = RuleContext(
    source={"id": "player_1", "action": "rest", "in_combat": False, "health": 50},
    turn=15
)
changes = engine.evaluate(context)
```

---

## 5. Items 系统（items.py）

### 5.1 系统概述

Items 系统实现了基于**属性（Affordance）**的物品系统。物品不是通过类型区分功能，而是通过其具有的属性来定义可能的交互方式。

### 5.2 核心组件

#### ItemProperties（物品属性）

定义物品的可供性属性：

```python
@dataclass
class ItemProperties:
    flammable: bool = False     # 可燃
    sharp: bool = False         # 锋利
    rope_like: bool = False     # 绳索状
    stick_like: bool = False    # 棍棒状
    liquid: bool = False        # 液体
    heavy: bool = False         # 沉重
    explosive: bool = False     # 易爆
    magical: bool = False       # 魔法
    edible: bool = False        # 可食用
    wearable: bool = False      # 可穿戴
    container: bool = False     # 容器
    light_source: bool = False # 光源
    toxic: bool = False         # 有毒
    conductive: bool = False    # 导电
```

支持序列化：
- `as_dict()`：转换为字典
- `from_dict(data)`：从字典创建

#### GameItem（游戏物品）

```python
@dataclass
class GameItem:
    id: str                         # 唯一标识
    name: str                       # 名称
    description: str = ""           # 描述
    item_type: str = "misc"         # 类型标签
    properties: ItemProperties      # 物品属性
    quantity: int = 1               # 数量
    value: int = 0                  # 价值
    weight: float = 0.0             # 重量
    tags: list[str]                 # 标签列表
    state: str = "normal"           # 状态（normal, broken, on_fire, wet等）
```

**方法：**
```python
def has_property(self, prop_name: str) -> bool
```
检查是否具有特定属性。

```python
def get_affordances(self) -> list[str]
```
根据属性返回可能的交互动作列表。

**属性到动作的映射：**
| 属性 | 可能的动作 |
|------|-----------|
| sharp | cut, stab, slice |
| stick_like | poke, reach, lever |
| rope_like | tie, climb, bind |
| flammable | burn, fuel |
| liquid | pour, splash, drink |
| heavy | smash, block, weigh_down |
| explosive | explode, throw |
| light_source | illuminate, signal |
| edible | eat, feed |
| container | store, fill, pour |

### 5.3 物品组合系统

#### CombinationResult（组合结果）

```python
@dataclass
class CombinationResult:
    success: bool                      # 是否成功
    result_item: GameItem | None       # 结果物品
    consumed_items: list[str]          # 消耗的物品ID
    description: str                   # 描述
```

#### ItemCombiner（物品组合器）

**加载组合规则：**
```python
def load_combinations(self, path: str)
```
从 YAML 文件加载组合规则。

**编程添加规则：**
```python
def add_combination(
    self,
    required_properties: list[str],  # 所需属性列表
    result: dict[str, Any],           # 结果物品定义
)
```

**尝试组合：**
```python
def try_combine(self, item_a: GameItem, item_b: GameItem) -> CombinationResult
```

**组合逻辑：**
1. 收集两个物品的所有属性
2. 检查是否满足任何组合规则的属性要求
3. 返回第一个匹配的组合结果

### 5.4 YAML 组合规则格式

```yaml
- required_properties: ["flammable", "sharp"]
  result:
    id: "fire_torch"
    name: "火把"
    description: "尖锐的可燃物制成的火把"
    item_type: "tool"
    properties:
      light_source: true
      flammable: true
      stick_like: true

- required_properties: ["container", "liquid"]
  result:
    id: "filled_container"
    name: "装满的容器"
    properties:
      container: true
      heavy: true
```

### 5.5 使用示例

```python
# 创建物品
sword = GameItem(
    id="iron_sword",
    name="铁剑",
    properties=ItemProperties(sharp=True, heavy=True)
)
sword.get_affordances()  # ['cut', 'stab', 'slice', 'smash', 'block', 'weigh_down']

# 物品组合
combiner = ItemCombiner()
combiner.load_combinations("data/combinations.yaml")

cloth = GameItem(id="cloth", properties=ItemProperties(flammable=True))
stick = GameItem(id="stick", properties=ItemProperties(stick_like=True))

result = combiner.try_combine(cloth, stick)
if result.success:
    print(f"Created: {result.result_item.name}")
    print(f"Consumed: {result.consumed_items}")
```

---

## 6. Perception 系统（perception.py）

### 6.1 系统概述

Perception 系统负责**环境感知过滤**，根据观察者的感知能力、环境条件等因素，决定实体对玩家可见的详细程度。

### 6.2 核心组件

#### PerceptionContext（感知上下文）

```python
@dataclass
class PerceptionContext:
    observer_id: str                     # 观察者ID
    observer_location_id: str            # 观察者位置ID
    light_level: int = 5                 # 光照等级（0-10）
    weather_modifier: float = 1.0        # 天气修正（0.0-1.0）
    observer_perception_skill: int = 10  # 观察者感知技能（基于WIS）
    stealth_values: dict[str, int]       # 实体隐匿值映射
```

**光照等级：**
- 0-2：黑暗（Dark）
- 3-4：昏暗（Dim）
- 5-7：正常（Normal）
- 8-10：明亮（Bright）

#### VisibleEntity（可见实体）

```python
@dataclass
class VisibleEntity:
    entity_id: str                  # 实体ID
    entity_type: str                # 实体类型（character, item, location_feature）
    name: str                       # 名称
    description: str = ""           # 描述
    distance: float = 0.0           # 距离
    detail_level: str = "full"      # 细节等级（full, partial, vague, hidden）
    is_notable: bool = False        # 是否显著
```

**细节等级：**
- `full`：完整细节（名称+描述）
- `partial`：部分细节（名称+简化描述）
- `vague`：模糊细节（仅名称）
- `hidden`：不可见

#### PerceptionResult（感知结果）

```python
@dataclass
class PerceptionResult:
    visible_entities: list[VisibleEntity]  # 可见实体列表
    visible_events: list[str]              # 可见事件列表
    ambient_description: str               # 环境描述
    hidden_count: int                      # 隐藏实体数量
```

### 6.3 核心类：PerceptionFilter

#### 可见性计算

**距离阈值（单位：位置单位）：**
```python
NEAR_DISTANCE = 1.0    # 近距
MEDIUM_DISTANCE = 3.0   # 中距
FAR_DISTANCE = 5.0     # 远距
```

**光照阈值：**
```python
DARK = 2    # 黑暗
DIM = 4     # 昏暗
NORMAL = 7  # 正常
BRIGHT = 9  # 明亮
```

#### calculate_visibility()

计算单个实体的可见性：

```python
def calculate_visibility(
    self,
    entity_id: str,
    entity_type: str,
    entity_name: str,
    entity_description: str,
    distance: float,
    entity_stealth: int,
    context: PerceptionContext,
) -> VisibleEntity | None
```

**计算逻辑：**

1. **基础感知分数** = `observer_perception_skill`

2. **光照修正：**
   - 黑暗（≤2）：-8
   - 昏暗（≤4）：-4
   - 明亮（≥9）：+2

3. **天气修正：**
   ```
   感知分数 = int(感知分数 × weather_modifier)
   ```

4. **距离修正：**
   - 近距（≤1.0）：+4
   - 中距（≤3.0）：+0
   - 远距（≤5.0）：-4
   - 超远距（>5.0）：-8

5. **隐匿对抗：**
   ```
   隐匿差值 = 感知分数 - 实体隐匿值
   ```
   - < -5：完全隐藏（返回 None）
   - -5 ~ 0：模糊（vague）
   - 0 ~ 5：部分（partial）
   - ≥ 5：完整（full）

6. **显著性判定：**
   完整细节且近距 = 显著实体

#### filter_entities()

批量过滤实体列表：

```python
def filter_entities(
    self,
    entities: list[dict[str, str | int | float]],
    context: PerceptionContext,
) -> PerceptionResult
```

返回过滤结果包含：
- 可见实体列表
- 环境描述（中文）
- 隐藏实体计数

**环境描述生成：**
```python
def _generate_ambient(self, context: PerceptionContext) -> str
```
根据光照和天气生成描述：
- 黑暗："几乎一片漆黑"
- 昏暗："光线昏暗"
- 明亮："光线充足"
- 恶劣天气："恶劣的天气影响了视线"

### 6.4 使用示例

```python
filter = PerceptionFilter()

# 设置观察上下文
context = PerceptionContext(
    observer_id="player_1",
    observer_location_id="room_5",
    light_level=6,
    weather_modifier=0.8,
    observer_perception_skill=14,
    stealth_values={"goblin_3": 12, "chest_hidden": 15}
)

# 待过滤的实体
entities = [
    {"id": "goblin_3", "type": "character", "name": "地精斥候",
     "description": "一个警惕的地精", "distance": 2.5, "stealth": 12},
    {"id": "chest_hidden", "type": "item", "name": "隐藏的宝箱",
     "description": "藏在阴影中", "distance": 8.0, "stealth": 15},
]

# 执行过滤
result = filter.filter_entities(entities, context)

for entity in result.visible_entities:
    print(f"{entity.name} ({entity.detail_level}): {entity.description}")
print(f"环境：{result.ambient_description}")
print(f"隐藏实体：{result.hidden_count}个")
```

---

## 7. 系统交互流程

### 7.1 典型使用场景

**战斗检定流程：**
```
1. Dice 系统 → 掷骰检定（优势/劣势、加值、DC）
2. RuleEngine → 评估战斗规则（伤害计算、暴击加成等）
3. EventBus → 发布战斗事件（COMBAT）
4. Perception → 决定战斗信息可见性
```

**物品交互流程：**
```
1. Items 系统 → 检查物品属性（get_affordances）
2. RuleEngine → 评估交互规则（如"可燃物遇火"）
3. EventBus → 发布环境事件（ENVIRONMENT）
4. Items 系统 → 更新物品状态（state = "on_fire"）
```

**环境感知流程：**
```
1. Perception 系统 → 计算可见性（光照、距离、隐匿）
2. EventBus → 订阅环境事件，更新感知上下文
3. RuleEngine → 根据环境条件应用感知规则
```

### 7.2 模块依赖关系

```
┌─────────────┐
│  EventBus   │ ← 异步事件通信
└──────┬──────┘
       │
       ├─────→ Dice（独立）
       │
       ├─────→ Items（独立）
       │
       ├─────→ Perception（独立）
       │
       └─────→ RuleEngine（依赖 EventBus）
```

---

## 8. 设计原则

### 8.1 单一职责

每个子系统专注单一职责：
- **Dice**：随机性与检定
- **Events**：事件通信
- **Rules**：规则评估
- **Items**：物品属性
- **Perception**：可见性过滤

### 8.2 可配置性

- Dice 系统：支持种子、自定义 DC
- Rules 系统：YAML 声明 + Python 注册
- Items 系统：YAML 组合规则
- Perception：参数化的距离、光照阈值

### 8.3 可测试性

所有核心类支持依赖注入和模拟：
- DiceRoller：可选种子保证可重复性
- RuleEngine：可选 EventBus 注入
- PerceptionFilter：纯函数计算，无副作用

### 8.4 扩展性

- 新事件类型：扩展 EventType 枚举
- 新规则操作符：扩展 `_check_condition()` 方法
- 新物品属性：扩展 ItemProperties 数据类
- 新感知因素：扩展 PerceptionContext 和计算逻辑

---

## 9. 性能考虑

### 9.1 事件系统

- EventQueue 限制历史记录为 100 条，避免内存泄漏
- EventBus 使用 defaultdict 优化处理器查找

### 9.2 规则引擎

- 规则按优先级排序，高优先级规则先执行
- 条件检查使用短路逻辑（all()）
- 概率检查在条件匹配后执行，避免不必要的计算

### 9.3 感知系统

- 批量过滤使用单次遍历
- 隐匿值使用字典存储，O(1) 查找
- 环境描述惰性生成

---

## 10. 最佳实践

### 10.1 Dice 系统

```python
# 推荐：使用语义化的检定方法
result = roller.roll_check(
    attribute_mod=strength_mod,
    proficiency_mod=proficiency,
    dc=15
)

# 避免：手动构造 Modifier 列表（除非需要复杂来源追踪）
```

### 10.2 EventBus

```python
# 推荐：异步处理器使用 async def
async def handle_combat(event: GameEvent):
    await some_async_operation()

# 同步处理器使用普通函数
def log_event(event: GameEvent):
    logger.info(event.description)
```

### 10.3 RuleEngine

```python
# 推荐：简单规则用 YAML，复杂逻辑用 Python
# YAML: fire_spreads.yaml
# Python: @rule("complex_combat_maneuver")

# 避免：在 Python 规则中进行 I/O 操作
```

### 10.4 Items

```python
# 推荐：使用属性查询而非类型判断
if item.has_property("sharp"):
    # 处理锋利物品

# 避免：依赖 item_type 字符串匹配
if item.item_type == "sword":  # 不推荐
```

### 10.5 Perception

```python
# 推荐：在渲染前批量过滤
result = filter.filter_entities(all_entities, context)
visible = result.visible_entities

# 避免：对每个实体单独调用 calculate_visibility
```

---

## 11. 未来扩展

### 11.1 计划中的功能

- **Dice**：骰子池系统、爆炸骰、重掷机制
- **Events**：事件优先级、事件过滤、事件重放
- **Rules**：规则热重载、规则调试器、性能分析
- **Items**：物品耐久度、物品附魔、物品品质
- **Perception**：听觉感知、嗅觉感知、感知技能树

### 11.2 扩展接口

所有系统设计考虑了扩展点：
- Dice：通过继承 DiceRoller 添加特殊骰子
- Events：通过继承 GameEvent 添加自定义事件
- Rules：通过 RuleEffect 支持新动作类型
- Items：ItemProperties 支持新属性
- Perception：PerceptionContext 支持新感知因素

---

## 12. 总结

`jag.core` 模块提供了游戏基础设施层的关键系统：

| 系统 | 核心价值 | 设计模式 |
|------|---------|---------|
| Dice | 随机性与公平性 | 策略模式（不同掷骰方式） |
| EventBus | 松耦合通信 | 发布/订阅模式 |
| RuleEngine | 灵活规则管理 | 混合模式（声明式+注册式） |
| Items | 物品交互可能性 | 属性驱动设计 |
| Perception | 信息过滤与沉浸感 | 过滤器模式 |

这些系统相互独立又可协同工作，为上层游戏逻辑提供了稳定、可测试、可扩展的基础设施。