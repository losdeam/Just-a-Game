# Dice API 文档

本文档描述了 Just-a-Game 的 D20 骰子系统，提供完整的检定、优势/劣势、加值和暴击判定功能。

## 概述

骰子系统位于 `jag/core/dice.py`，提供以下核心组件：

- **DiceRoller**: D20 骰子掷骰器，支持优势/劣势、加值、暴击判定
- **DiceResult**: 掷骰结果数据类
- **Modifier**: 加值数据类
- **ModifierType**: 加值类型枚举
- **RollResult**: 检定结果枚举

---

## DiceRoller 类

`DiceRoller` 是骰子系统的核心类，实现了完整的 D20 骰子检定机制。

### 构造函数

```python
def __init__(self, seed: int | None = None) -> None:
    """Initialize the dice roller."""
```

**参数：**
- `seed` (int | None): 随机种子，用于生成可重复的随机序列。默认为 `None`，表示使用系统随机种子。

**说明：**
- 内部使用独立的 `random.Random` 实例，不共享全局状态
- 设置种子后可以复现相同的掷骰序列，便于测试

---

### roll() - 通用掷骰方法

执行骰子检定，支持任意面数、优势/劣势和加值。

```python
def roll(
    self,
    sides: int = 20,
    count: int = 1,
    advantage: bool = False,
    disadvantage: bool = False,
    modifiers: list[Modifier] | None = None,
    dc: int = 10,
) -> DiceResult:
    """Roll dice with optional advantage/disadvantage and modifiers."""
```

#### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sides` | int | 20 | 骰子面数（如 20 表示 D20，6 表示 D6） |
| `count` | int | 1 | 掷骰次数，多次掷骰结果会求和 |
| `advantage` | bool | False | 是否有优势（掷两骰取高值） |
| `disadvantage` | bool | False | 是否有劣势（掷两骰取低值） |
| `modifiers` | list[Modifier] \| None | None | 加值列表 |
| `dc` | int | 10 | 难度等级（Difficulty Class） |

#### 优势/劣势机制

- **优势（advantage=True）**: 掷两个骰子，取较高值作为基础掷骰值
- **劣势（disadvantage=True）**: 掷两个骰子，取较低值作为基础掷骰值
- **同时存在**: 优势与劣势相互抵消，视为普通掷骰

#### 暴击判定规则

| 条件 | 结果 |
|------|------|
| 基础掷骰值 = 骰子最大值（如 D20 的 20） | `CRITICAL_SUCCESS`（大成功） |
| 基础掷骰值 = 1 | `CRITICAL_FAILURE`（大失败） |
| 总值 ≥ DC | `SUCCESS`（成功） |
| 总值 < DC | `FAILURE`（失败） |

**注意**：暴击判定基于**基础掷骰值**（不含加值），而非总值。

#### 返回值

返回 `DiceResult` 对象，包含以下字段：

```python
@dataclass
class DiceResult:
    base_roll: int                  # 基础掷骰值（不含加值）
    modifiers: list[Modifier]       # 应用的加值列表
    total: int                      # 最终总值（基础值 + 加值）
    result: RollResult              # 检定结果
    advantage: bool                 # 是否有优势
    disadvantage: bool              # 是否有劣势
    sides: int                      # 骰子面数
```

`DiceResult` 提供的属性方法：

```python
@property
def is_success(self) -> bool:
    """判断是否成功（包括大成功）"""
    return self.result in (RollResult.SUCCESS, RollResult.CRITICAL_SUCCESS)

@property
def is_critical(self) -> bool:
    """判断是否暴击（大成功或大失败）"""
    return self.result in (RollResult.CRITICAL_SUCCESS, RollResult.CRITICAL_FAILURE)

def summary(self) -> str:
    """生成人类可读的结果描述"""
    # 示例输出: "d20: 18 (+3 +2) = 23 [success]"
```

#### 使用示例

```python
from jag.core.dice import DiceRoller, Modifier, ModifierType

roller = DiceRoller(seed=42)  # 固定种子用于测试

# 基础 D20 检定
result = roller.roll()
print(f"基础掷骰: {result.base_roll}, 总值: {result.total}, 结果: {result.result.value}")

# 带加值的检定
result = roller.roll(
    modifiers=[
        Modifier(ModifierType.ATTRIBUTE, 3, "力量"),
        Modifier(ModifierType.PROFICIENCY, 2, "熟练")
    ],
    dc=15
)
print(result.summary())  # "d20: 14 (+3 +2) = 19 [success]"

# 优势检定
result = roller.roll(advantage=True, dc=12)
print(f"优势检定: {result.summary()}")

# 劣势检定
result = roller.roll(disadvantage=True, dc=10)
print(f"劣势检定: {result.summary()}")

# 多骰掷骰（如 2D6）
result = roller.roll(sides=6, count=2)
print(f"2D6: {result.base_roll}")

# 检查结果
if result.is_success:
    print("检定成功!")
if result.is_critical:
    print("暴击!")
```

---

### roll_check() - 能力检定便捷方法

为常见的能力检定提供便捷接口，自动构造加值列表。

```python
def roll_check(
    self,
    attribute_mod: int = 0,
    proficiency_mod: int = 0,
    item_mod: int = 0,
    status_mod: int = 0,
    dc: int = 10,
    advantage: bool = False,
    disadvantage: bool = False,
) -> DiceResult:
    """Convenience method for ability checks."""
```

#### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `attribute_mod` | int | 0 | 属性加值（如力量、敏捷、智力等） |
| `proficiency_mod` | int | 0 | 熟练加值 |
| `item_mod` | int | 0 | 物品加值 |
| `status_mod` | int | 0 | 状态加值（如祝福、诅咒等） |
| `dc` | int | 10 | 难度等级 |
| `advantage` | bool | False | 是否有优势 |
| `disadvantage` | bool | False | 是否有劣势 |

#### 返回值

返回 `DiceResult` 对象，加值列表会自动填充对应的加值类型和来源描述。

#### 使用示例

```python
from jag.core.dice import DiceRoller

roller = DiceRoller()

# 力量检定（力量+3，熟练+2）
result = roller.roll_check(
    attribute_mod=3,
    proficiency_mod=2,
    dc=15
)

# 敏捷检定带优势
result = roller.roll_check(
    attribute_mod=4,      # 敏捷+4
    proficiency_mod=2,    # 熟练加值
    advantage=True,
    dc=12
)

# 带物品和状态加值的检定
result = roller.roll_check(
    attribute_mod=3,
    item_mod=1,          # 魔法武器+1
    status_mod=2,        # 祝福+2
    dc=18
)
print(result.summary())  # "d20: 16 (+3 +1 +2) = 22 [success]"

# 豁免检定（劣势）
result = roller.roll_check(
    attribute_mod=2,
    disadvantage=True,
    dc=10
)
```

#### 等效实现

`roll_check()` 方法内部会自动创建 `Modifier` 对象并调用 `roll()`：

```python
# roll_check 内部实现
def roll_check(self, attribute_mod=0, proficiency_mod=0, item_mod=0, status_mod=0, ...):
    modifiers = []
    if attribute_mod:
        modifiers.append(Modifier(ModifierType.ATTRIBUTE, attribute_mod, "attribute"))
    if proficiency_mod:
        modifiers.append(Modifier(ModifierType.PROFICIENCY, proficiency_mod, "proficiency"))
    if item_mod:
        modifiers.append(Modifier(ModifierType.ITEM, item_mod, "item"))
    if status_mod:
        modifiers.append(Modifier(ModifierType.STATUS, status_mod, "status"))

    return self.roll(modifiers=modifiers, dc=dc, advantage=advantage, disadvantage=disadvantage)
```

---

### roll_damage() - 伤害掷骰

解析骰子表达式并计算伤害值，支持标准 D&D 骰子表示法。

```python
def roll_damage(self, dice_str: str) -> int:
    """Roll damage dice like '2d6+3'."""
```

#### 参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| `dice_str` | str | 骰子表达式字符串，格式为 `"XdY+Z"` 或 `"XdY-Z"` |

#### 支持的格式

| 格式 | 说明 | 示例 |
|------|------|------|
| `dY` | 掷一个 Y 面骰子 | `"d6"` → 1-6 |
| `XdY` | 掷 X 个 Y 面骰子，求和 | `"2d6"` → 2-12 |
| `XdY+Z` | 掷骰结果加 Z | `"2d6+3"` → 5-15 |
| `XdY-Z` | 掷骰结果减 Z | `"1d8-1"` → 0-7 |

#### 返回值

- 返回 `int`：计算后的伤害总值
- 最小值为 0，不会返回负数

#### 使用示例

```python
from jag.core.dice import DiceRoller

roller = DiceRoller()

# 单骰
damage = roller.roll_damage("d6")
print(f"D6 伤害: {damage}")  # 1-6

# 多骰求和
damage = roller.roll_damage("2d6")
print(f"2D6 伤害: {damage}")  # 2-12

# 带固定加值
damage = roller.roll_damage("2d6+4")
print(f"2D6+4 伤害: {damage}")  # 6-16

# 带固定减值
damage = roller.roll_damage("1d8-2")
print(f"1D8-2 伤害: {damage}")  # 0-6（最小为0）

# 大量骰子
damage = roller.roll_damage("8d6")  # 火球术
print(f"8D6 伤害: {damage}")  # 8-48

# 默认格式（省略数量时为1）
damage = roller.roll_damage("d20")
print(f"D20: {damage}")  # 1-20
```

#### 注意事项

1. **不支持优势/劣势**：伤害骰通常不使用优势/劣势机制
2. **最小值为 0**：即使减值导致结果为负，也返回 0
3. **格式限制**：只支持单一骰子表达式，不支持混合骰子（如 `"1d6+1d8"`）
4. **无效格式**：如果格式无法解析，返回 0

---

## 数据类型

### Modifier - 加值

```python
@dataclass
class Modifier:
    mod_type: ModifierType  # 加值类型
    value: int              # 加值数值（可为负数）
    source: str = ""        # 加值来源描述
```

#### 属性说明

| 属性 | 类型 | 说明 |
|------|------|------|
| `mod_type` | ModifierType | 加值类型枚举 |
| `value` | int | 加值数值，可为正数或负数 |
| `source` | str | 加值来源描述，用于日志和显示 |

---

### ModifierType - 加值类型枚举

```python
class ModifierType(Enum):
    ATTRIBUTE = auto()      # 属性加值（力量、敏捷、智力等）
    PROFICIENCY = auto()    # 熟练加值
    ITEM = auto()           # 物品加值（魔法武器、装备等）
    STATUS = auto()         # 状态加值（祝福、诅咒、环境等）
```

#### 使用示例

```python
from jag.core.dice import Modifier, ModifierType

# 创建不同类型的加值
attribute_mod = Modifier(ModifierType.ATTRIBUTE, 3, "力量")
proficiency_mod = Modifier(ModifierType.PROFICIENCY, 2, "熟练")
item_mod = Modifier(ModifierType.ITEM, 1, "魔法武器")
status_mod = Modifier(ModifierType.STATUS, -2, "中毒")

# 使用加值列表
modifiers = [attribute_mod, proficiency_mod, item_mod, status_mod]
result = roller.roll(modifiers=modifiers, dc=15)
```

---

### RollResult - 检定结果枚举

```python
class RollResult(Enum):
    CRITICAL_SUCCESS = "critical_success"   # 大成功（自然掷出最大值）
    SUCCESS = "success"                     # 成功（总值 ≥ DC）
    FAILURE = "failure"                     # 失败（总值 < DC）
    CRITICAL_FAILURE = "critical_failure"   # 大失败（自然掷出 1）
```

#### 结果判断逻辑

```
基础掷骰值 = 骰子最大值 (如 D20 的 20)
    ↓ 是
CRITICAL_SUCCESS

基础掷骰值 = 1
    ↓ 是
CRITICAL_FAILURE

总值 ≥ DC
    ↓ 是
SUCCESS

总值 < DC
    ↓ 是
FAILURE
```

---

## 完整使用示例

### 基础检定

```python
from jag.core.dice import DiceRoller

roller = DiceRoller()

# 简单检定
result = roller.roll()
if result.is_success:
    print("成功!")
print(result.summary())
```

### 战斗场景

```python
from jag.core.dice import DiceRoller, Modifier, ModifierType

roller = DiceRoller()

# 攻击检定
attack_result = roller.roll_check(
    attribute_mod=4,      # 敏捷+4
    proficiency_mod=3,    # 熟练加值+3
    advantage=True,       # 有优势（目标被压制）
    dc=15                 # 目标 AC
)

if attack_result.is_success:
    # 命中！掷伤害
    if attack_result.is_critical:
        # 暴击！伤害骰翻倍
        damage = roller.roll_damage("2d8+4") + roller.roll_damage("2d8+4")
        print(f"暴击！造成 {damage} 点伤害！")
    else:
        damage = roller.roll_damage("1d8+4")
        print(f"命中！造成 {damage} 点伤害。")
else:
    print("未命中。")
```

### 技能检定

```python
from jag.core.dice import DiceRoller, Modifier, ModifierType

roller = DiceRoller()

# 潜行检定
stealth_result = roller.roll_check(
    attribute_mod=3,      # 敏捷+3
    proficiency_mod=2,    # 熟练加值
    dc=12                 # 被动察觉 DC
)

# 知识检定带物品加值
arcana_result = roller.roll(
    modifiers=[
        Modifier(ModifierType.ATTRIBUTE, 2, "智力"),
        Modifier(ModifierType.PROFICIENCY, 2, "熟练"),
        Modifier(ModifierType.ITEM, 2, "魔法典籍")
    ],
    dc=18
)

# 豁免检定带劣势
save_result = roller.roll_check(
    attribute_mod=1,       # 体质+1
    disadvantage=True,     # 中毒状态
    dc=13
)
print(f"豁免检定: {save_result.summary()}")
```

### 可重复测试

```python
from jag.core.dice import DiceRoller

# 使用固定种子进行测试
roller = DiceRoller(seed=42)

# 结果可重复
result1 = roller.roll()
result2 = roller.roll()

# 重置随机状态
roller2 = DiceRoller(seed=42)
result3 = roller2.roll()
assert result1.base_roll == result3.base_roll  # 相同的种子产生相同的结果
```

### 结果处理

```python
from jag.core.dice import DiceRoller, RollResult

roller = DiceRoller()
result = roller.roll_check(attribute_mod=3, proficiency_mod=2, dc=15)

# 方式1：检查布尔属性
if result.is_success:
    print("检定成功")

if result.is_critical:
    print("暴击!")

# 方式2：匹配结果枚举
match result.result:
    case RollResult.CRITICAL_SUCCESS:
        print("大成功！完美执行!")
    case RollResult.SUCCESS:
        print("成功!")
    case RollResult.FAILURE:
        print("失败...")
    case RollResult.CRITICAL_FAILURE:
        print("大失败！发生灾难性的错误!")

# 方式3：获取摘要字符串
print(result.summary())  # "d20: 18 (+3 +2) = 23 [success]"
```

---

## 最佳实践

### 1. 使用语义化的方法

```python
# 推荐：使用 roll_check 进行能力检定
result = roller.roll_check(
    attribute_mod=3,
    proficiency_mod=2,
    dc=15
)

# 仅在需要特殊加值来源追踪时手动构造 Modifier
result = roller.roll(
    modifiers=[
        Modifier(ModifierType.ATTRIBUTE, 3, "力量"),
        Modifier(ModifierType.ITEM, 1, "祝福武器"),
        Modifier(ModifierType.STATUS, 2, "英雄气概"),
    ],
    dc=15
)
```

### 2. 伤害骰使用 roll_damage

```python
# 推荐：使用 roll_damage 处理伤害骰
damage = roller.roll_damage("2d6+4")

# 不推荐：使用 roll 方法处理伤害（不支持骰子表达式）
# damage = roller.roll(sides=6, count=2, dc=0)  # 需要手动处理加值
```

### 3. 测试时使用种子

```python
# 推荐：测试时使用固定种子
roller = DiceRoller(seed=42)
result = roller.roll_check(attribute_mod=3, dc=10)
# 结果可预测，便于断言

# 不推荐：生产环境使用固定种子
# roller = DiceRoller(seed=42)  # 会导致所有玩家获得相同的掷骰结果
```

### 4. 检查结果属性而非值

```python
# 推荐：使用语义化属性
if result.is_success:
    handle_success()
if result.is_critical:
    handle_critical()

# 不推荐：直接比较枚举值
if result.result == RollResult.SUCCESS or result.result == RollResult.CRITICAL_SUCCESS:
    handle_success()
```

---

## 错误处理

骰子系统的设计目标是健壮和容错：

1. **无效骰子表达式**：`roll_damage()` 如果无法解析格式，返回 0
2. **空加值列表**：`modifiers=None` 被视为无加值
3. **优势劣势同时存在**：自动相互抵消，视为普通掷骰

```python
# 安全使用示例
roller = DiceRoller()

# 无效骰子表达式
damage = roller.roll_damage("invalid")  # 返回 0
damage = roller.roll_damage("abc")      # 返回 0

# 空加值列表
result = roller.roll(modifiers=None)    # 等同于 modifiers=[]

# 优势劣势抵消
result = roller.roll(advantage=True, disadvantage=True)  # 普通掷骰
```

---

## 性能考虑

1. **独立随机实例**：每个 `DiceRoller` 使用独立的 `random.Random` 实例，避免全局状态竞争
2. **无缓存**：每次调用都产生新的随机结果，无内部缓存
3. **轻量级**：`DiceResult` 和 `Modifier` 都是轻量数据类，创建开销极小

---

## 相关文档

- [Core 模块架构文档](../architecture/core.md) - Dice 系统在整体架构中的位置
- [战斗规则示例](../superpowers/specs/2026-06-18-core-framework-design.md) - Dice 系统在战斗中的应用