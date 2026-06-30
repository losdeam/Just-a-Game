# 规则扩展指南

本文档介绍如何通过 YAML 声明式规则和 Python 注册规则来扩展游戏规则系统。

## 1. 添加 YAML 规则

### 规则 YAML 格式

YAML 规则文件是一个包含多个规则对象的列表。每个规则对象包含以下字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | string | 是 | - | 规则名称，唯一标识符 |
| `conditions` | list | 否 | `[]` | 触发条件列表 |
| `effects` | list | 否 | `[]` | 触发后执行的效果列表 |
| `probability` | float | 否 | `1.0` | 触发概率（0.0 ~ 1.0） |
| `priority` | int | 否 | `0` | 执行优先级，数值越大越先执行 |
| `tags` | list[str] | 否 | `[]` | 规则标签，用于分类 |

### 条件操作符

每个条件对象包含三个字段：

| 字段 | 说明 |
|------|------|
| `attribute` | 上下文属性路径，使用点号分隔（如 `source.type`、`target.state`） |
| `operator` | 比较操作符 |
| `value` | 期望值 |

支持的操作符：

| 操作符 | 说明 | 示例 |
|--------|------|------|
| `eq` | 等于 | `source.type == "fire"` |
| `ne` | 不等于 | `source.state != "dead"` |
| `gt` | 大于 | `source.energy > 0.3` |
| `lt` | 小于 | `target.health < 10` |
| `gte` | 大于等于 | `source.level >= 5` |
| `lte` | 小于等于 | `target.distance <= 3` |
| `in` | 在列表中 | `source.type in ["fire", "ice"]` |
| `not_in` | 不在列表中 | `target.state not in ["immune", "shielded"]` |
| `contains` | 包含（用于列表或字符串） | `source.tags contains "elite"` |
| `has_property` | 检查属性是否为真 | `target.properties.flammable == true` |

### 效果类型

每个效果对象包含三个字段：

| 字段 | 说明 |
|------|------|
| `action` | 效果动作类型 |
| `target` | 目标属性路径 |
| `value` | 效果值 |

支持的效果动作：

| 动作 | 说明 | target | value |
|------|------|--------|-------|
| `set_state` | 设置目标状态 | 属性路径（如 `target.on_fire`） | 新状态值 |
| `emit_event` | 发送事件 | 事件名称 | 事件数据 |
| `modify_attribute` | 修改属性值 | 属性路径 | 增量值（正/负） |
| `create_item` | 创建物品 | 目标位置 | 物品数据 |
| `destroy_item` | 销毁物品 | 物品标识 | - |

### 示例 YAML 规则

```yaml
# 火焰蔓延规则
- name: 火焰蔓延
  conditions:
    - attribute: source.type
      operator: eq
      value: fire
    - attribute: target.properties.flammable
      operator: has_property
      value: true
  effects:
    - action: set_state
      target: target.on_fire
      value: true
    - action: emit_event
      target: fire_spread
      value: true
  probability: 0.7
  priority: 10
  tags: [fire, environment]

# 黑暗惩罚规则
- name: 黑暗惩罚
  conditions:
    - attribute: world.time_of_day
      operator: eq
      value: night
    - attribute: source.has_light
      operator: eq
      value: false
  effects:
    - action: modify_attribute
      target: source.perception
      value: -3
  probability: 1.0
  priority: 5
  tags: [perception, environment]

# NPC 恐惧反应规则
- name: NPC恐惧反应
  conditions:
    - attribute: source.mood
      operator: eq
      value: fearful
    - attribute: source.energy
      operator: gt
      value: 0.3
  effects:
    - action: emit_event
      target: npc_flee
      value: true
  probability: 0.6
  priority: 8
  tags: [npc, behavior]

# 战斗高地优势规则
- name: 战斗高地优势
  conditions:
    - attribute: source.position
      operator: eq
      value: elevated
  effects:
    - action: modify_attribute
      target: source.attack_bonus
      value: 2
  probability: 1.0
  priority: 3
  tags: [combat]
```

---

## 2. 注册 Python 规则

对于更复杂的规则逻辑，可以使用 Python 代码注册自定义规则处理器。

### 使用 @rule 装饰器

```python
from jag.core.rules import rule, RuleContext, RuleEffect

@rule("custom_rule_name")
def my_rule_handler(context: RuleContext) -> list[RuleEffect]:
    """
    自定义规则处理器。

    Args:
        context: 规则上下文，包含 source、target、actor、world 等信息

    Returns:
        效果列表，当 YAML 规则匹配时会自动执行这些效果
    """
    effects = []

    # 访问上下文数据
    source_type = context.source.get("type")
    target_health = context.target.get("health", 0)
    current_turn = context.turn

    # 自定义逻辑判断
    if source_type == "poison" and target_health > 0:
        effects.append(
            RuleEffect(
                action="modify_attribute",
                target="target.health",
                value=-5
            )
        )

    return effects
```

### RuleContext 参数说明

`RuleContext` 是传递给规则处理器的上下文对象，包含以下属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `source` | `dict[str, Any]` | 规则触发源对象数据 |
| `target` | `dict[str, Any]` | 规则目标对象数据 |
| `actor` | `dict[str, Any]` | 执行动作的实体数据 |
| `world` | `dict[str, Any]` | 世界状态数据 |
| `turn` | `int` | 当前回合数 |

#### 获取嵌套属性值

使用 `get_value(path)` 方法获取嵌套属性：

```python
# 获取 source 对象的 type 属性
source_type = context.get_value("source.type")

# 获取 target 对象的 properties.flammable 属性
flammable = context.get_value("target.properties.flammable")

# 获取 world.time_of_day 属性
time_of_day = context.get_value("world.time_of_day")
```

### 返回 list[RuleEffect]

Python 规则处理器必须返回 `list[RuleEffect]`。`RuleEffect` 的结构如下：

```python
@dataclass
class RuleEffect:
    action: str      # 效果动作类型
    target: str      # 目标属性路径
    value: Any       # 效果值
```

### 示例 Python 规则

```python
from jag.core.rules import rule, RuleContext, RuleEffect

# 毒素扩散规则
@rule("poison_spread")
def poison_spread_rule(context: RuleContext) -> list[RuleEffect]:
    """处理毒素在相邻实体间扩散的逻辑。"""
    effects = []

    source = context.source
    target = context.target

    # 检查源是否携带毒素
    if not source.get("has_poison", False):
        return effects

    # 检查目标是否有毒素抗性
    if target.get("poison_immune", False):
        return effects

    # 计算毒素强度衰减
    distance = target.get("distance_from_source", 1)
    poison_strength = source.get("poison_level", 1) / distance

    if poison_strength > 0.1:
        effects.extend([
            RuleEffect(
                action="set_state",
                target="target.poisoned",
                value=True
            ),
            RuleEffect(
                action="modify_attribute",
                target="target.poison_level",
                value=poison_strength
            ),
        ])

    return effects


# 装备耐久度检查规则
@rule("equipment_durability_check")
def equipment_durability_rule(context: RuleContext) -> list[RuleEffect]:
    """检查装备耐久度，损坏时触发事件。"""
    effects = []

    equipment = context.source.get("equipment", {})

    for slot, item in equipment.items():
        durability = item.get("durability", 100)
        max_durability = item.get("max_durability", 100)

        if durability <= 0:
            effects.append(
                RuleEffect(
                    action="emit_event",
                    target="equipment_broken",
                    value={"slot": slot, "item_id": item.get("id")}
                )
            )
        elif durability < max_durability * 0.2:
            effects.append(
                RuleEffect(
                    action="emit_event",
                    target="equipment_damaged",
                    value={"slot": slot, "item_id": item.get("id")}
                )
            )

    return effects
```

---

## 3. 规则引擎执行流程

规则引擎 `RuleEngine` 负责协调规则的评估和执行。执行流程如下：

```
┌─────────────────────────────────────────────────────────────┐
│                     1. 收集上下文                            │
│  构建 RuleContext 对象，包含 source、target、actor、world、turn │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     2. 匹配 YAML 规则                        │
│  按优先级（priority）排序，逐条检查 conditions 是否全部满足      │
│  - 获取 attribute 路径对应的实际值                              │
│  - 使用 operator 比较 actual 与 expected                      │
│  - 所有条件必须同时满足（AND 逻辑）                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    3. 概率检查                                │
│  若规则 probability < 1.0，进行随机数检查                       │
│  random() > probability → 跳过该规则                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    4. 执行效果                                │
│  遍历 effects 列表，执行每个效果动作：                          │
│  - set_state: 设置目标属性值                                   │
│  - emit_event: 发送游戏事件                                    │
│  - modify_attribute: 修改属性值（增量）                         │
│  - create_item / destroy_item: 创建/销毁物品                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  5. 调用 Python 规则处理器                     │
│  检查是否存在同名 Python 规则（通过 @rule 装饰器注册）            │
│  若存在，调用处理器获取额外效果并执行                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    6. 连锁处理                                │
│  若效果触发了新事件，可能触发新的规则评估                         │
│  最大连锁深度默认为 5 层，防止无限递归                           │
└─────────────────────────────────────────────────────────────┘
```

### 执行流程详解

#### 3.1 收集上下文

```python
context = RuleContext(
    source={"id": "fire_001", "type": "fire"},
    target={"id": "tree_001", "properties": {"flammable": True}},
    actor={"id": "player_001"},
    world={"time_of_day": "day"},
    turn=42
)
```

#### 3.2 匹配 YAML 规则

规则引擎按 `priority` 降序排列规则。对每个规则：

1. 遍历所有 `conditions`
2. 对每个条件调用 `_check_condition()`
3. 使用 `context.get_value(attribute)` 获取实际值
4. 应用对应的 `operator` 进行比较

#### 3.3 执行效果

效果执行后返回状态变更字典，格式如下：

```python
{
    "target.on_fire": True,
    "_emit_event": GameEvent(...),
    "_rule": "火焰蔓延"
}
```

#### 3.4 连锁处理

规则引擎初始化时设置最大连锁深度：

```python
engine = RuleEngine(event_bus=event_bus, max_chain_depth=5)
```

当效果触发事件时，事件可能触发新的规则评估。连锁深度限制确保不会无限循环。

### 使用示例

```python
from jag.core.rules import RuleEngine, RuleContext

# 创建规则引擎
engine = RuleEngine(event_bus=event_bus)

# 加载 YAML 规则
engine.load_rules("path/to/rules.yaml")

# 评估规则
context = RuleContext(
    source={"type": "fire"},
    target={"properties": {"flammable": True}},
    world={"time_of_day": "night"}
)

changes = engine.evaluate(context)

# 处理变更
for change in changes:
    rule_name = change.get("_rule")
    print(f"规则 '{rule_name}' 触发，变更: {change}")
```

---

## 参考资源

- 规则引擎实现：`jag/core/rules.py`
- 示例规则文件：`jag/demo/rules.yaml`
- 事件系统：`jag/core/events.py`