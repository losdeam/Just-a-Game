# Tick 引擎流程文档

本文档详细描述了 Just-a-Game 游戏的核心 Tick 引擎处理流程。

## 概述

Tick 引擎是游戏的核心调度器，负责处理每个游戏回合（Tick）的所有逻辑。每个 Tick 按顺序执行 14 个步骤，将玩家输入转化为最终叙事文本。

```
DangerCheck → DynamicNPC → ActionPlan → Rules → Dice → WorldUpdate → NPCTick → WorldSim → QuestGen → Story → Memory → Knowledge → Persist → Narrative
```

---

## 完整流程详解

### 步骤 1: DangerCheck（危险检查）

检查玩家是否处于危险中或正在进入危险区域。这是一个纯代码步骤，不涉及 LLM。

**输入：**
- `player_action`: 玩家行动字典（可选）
- `WorldState`: 当前世界状态

**处理逻辑：**
1. 如果玩家正在移动，检查目标位置的危险等级
2. 如果目标位置 `danger_level >= 7`，进行 D20 检定决定是否遭遇危险
3. 检查当前位置是否有敌对角色
4. 如果遭遇危险，发布 `DANGER` 类型事件

**输出：**
- `danger_encountered`: 是否遭遇危险
- `GameEvent`: 危险事件（如果有）

**示例：**
```python
# 玩家移动到危险等级 8 的洞穴
# 检定 DC = 8 + 8 - 5 = 11
# 如果检定失败，触发危险遭遇
```

---

### 步骤 2: DynamicNPC（动态 NPC 生成）

根据位置类型和标签动态生成 NPC。纯代码步骤。

**输入：**
- `player_action`: 玩家行动字典
- `WorldState`: 当前世界状态

**处理逻辑：**
1. 获取玩家当前位置
2. 根据位置类型决定生成概率：
   - 酒馆/市场/商店：70% 生成商人
   - 城门/塔楼/堡垒：80% 生成守卫
   - 森林/洞穴/遗迹：40% + danger_level 生成怪物
3. 检查位置标签（如 `tavern`）进行额外生成
4. 如果位置实体数 < 10 且满足生成条件，创建 NPC

**输出：**
- `NPC`: 新创建的 NPC 对象
- `npc_actions`: 生成行动记录

---

### 步骤 3: ActionPlan（行动规划）

解析玩家输入并规划行动。可选使用 LLM 进行语义解析。

**输入：**
- `action_text`: 玩家输入的自然语言文本
- `player_id`: 玩家 ID
- `WorldState`: 当前世界状态

**处理逻辑：**
1. 如果配置了 `ActionPlanner`，调用其 `plan()` 方法
2. 将自然语言解析为结构化行动：
   - `type`: 行动类型（move/attack/interact/take/drop 等）
   - `target`: 目标实体/位置 ID
   - `params`: 行动参数
   - `dc`: 难度等级
   - `attribute`: 相关属性
   - `risk`: 风险评估
3. 如果解析失败，使用原始输入作为回退

**输出：**
```python
{
    "type": "move",
    "target": "tavern_entrance",
    "params": {},
    "text": "走向酒馆",
    "dc": 10,
    "attribute": "dexterity",
    "risk": "low"
}
```

---

### 步骤 4: Rules（规则评估）

评估游戏规则，检查行动条件和效果。纯代码步骤。

**输入：**
- `action`: 结构化的玩家行动
- `actor`: 行动者数据
- `world`: 世界状态快照
- `turn`: 当前回合数

**处理逻辑：**
1. 创建 `RuleContext` 上下文
2. 调用 `RuleEngine.evaluate()` 评估规则
3. 收集规则变更和事件
4. 发布规则触发的事件

**输出：**
- `rule_changes`: 规则变更列表
- `GameEvent[]`: 触发的事件列表

---

### 步骤 5: Dice（骰子检定）

使用 D20 系统解决行动结果。纯代码步骤。

**输入：**
- `action`: 包含检定参数的行动字典
  - `dc`: 难度等级
  - `attribute_mod`: 属性加值
  - `proficiency_mod`: 熟练加值
  - `advantage`: 是否有优势
  - `disadvantage`: 是否有劣势

**处理逻辑：**
1. 仅对 `attack`、`check`、`skill` 类型行动进行检定
2. 调用 `DiceRoller.roll_check()` 执行 D20 检定
3. 处理优势/劣势（掷两次取优/劣）
4. 计算最终结果

**检定结果类型：**
- `critical_success`: 大成功（自然 20）
- `success`: 成功（总数 >= DC）
- `failure`: 失败（总数 < DC）
- `critical_failure`: 大失败（自然 1）

**输出：**
- `DiceResult`: 包含以下字段
  - `base_roll`: 基础骰值
  - `total`: 最终总数
  - `result`: 结果类型
  - `is_success`: 是否成功

**示例：**
```
玩家攻击，DC=15，敏捷加值+3，熟练加值+2
掷骰: 14 + 3 + 2 = 19 >= 15 → 成功
```

---

### 步骤 6: WorldUpdate（世界更新）

应用行动效果到世界状态。纯代码步骤。

**输入：**
- `action`: 已解析的行动
- `WorldState`: 当前世界状态

**处理的行动类型：**

| 行动类型 | 处理逻辑 |
|---------|---------|
| `move` | 更新角色位置，从当前位置移除，添加到目标位置 |
| `take` | 从位置移除物品，添加到角色背包 |
| `drop` | 从角色背包移除物品，添加到当前位置 |

**输出：**
- `WorldState`: 更新后的世界状态
- `GameEvent[]`: 移动/互动事件

---

### 步骤 7: NPCTick（NPC 处理）

并发处理所有注册 NPC 的决策和行动。支持 Semaphore 限流。

**输入：**
- `NPC[]`: 所有注册的 NPC 列表
- `WorldState`: 当前世界状态
- `npc_concurrency`: 最大并发数（默认 5）

**并发处理说明：**

```python
# 使用 asyncio.Semaphore 限制并发
self._semaphore = asyncio.Semaphore(npc_concurrency)

# 并发执行所有 NPC 处理
tasks = [self._process_single_npc(npc_id, npc, result) for npc_id, npc in self._npcs.items()]
await asyncio.gather(*tasks, return_exceptions=True)
```

**单个 NPC 处理流程：**
1. 构建观察数据：
   - 当前位置信息
   - 附近角色和物品
   - 时间和日程安排
2. 获取 NPC 决策：
   - 如果配置了 `NPCAgent`，调用 LLM 决策
   - 否则使用默认行为（跟随日程或空闲）
3. 应用 NPC 行动（如移动）
4. 更新 NPC 状态（能量衰减、饥饿增加）
5. 记录非空闲行动到记忆

**输出：**
- `npc_actions`: NPC 行动列表
- `GameEvent[]`: NPC 行动事件

---

### 步骤 8: WorldSim（世界模拟）

运行天气、经济、派系模拟。纯代码步骤。

**输入：**
- `WorldState`: 当前世界状态
- `season`: 当前季节

**模拟器类型：**

| 模拟器 | 功能 | 输出事件类型 |
|-------|------|-------------|
| `WeatherSimulator` | 天气变化模拟 | `weather_change` |
| `EconomySimulator` | 经济价格波动 | `price_shift` |
| `FactionSimulator` | 派系关系演变 | `faction_tension` |

**输出：**
- `sim_events`: 模拟事件列表
- 转换为 `GameEvent[]` 并添加到 `world_events`

---

### 步骤 9: QuestGen（任务生成）

基于事件检查并触发新任务。纯代码步骤。

**输入：**
- `WorldState`: 当前世界状态
- `sim_events`: 模拟事件列表

**处理逻辑：**
1. 调用 `QuestGenerator.check()` 检查触发条件
2. 根据事件和世界状态生成新任务
3. 发布任务事件

**输出：**
- `Quest[]`: 新生成的任务列表
- `GameEvent[]`: 任务通知事件

---

### 步骤 10: Story（故事处理）

处理故事弧线和发展。可选 LLM 步骤。

**输入：**
- `world_events`: 本回合的所有事件
- `WorldState`: 当前世界状态

**处理逻辑：**
1. 如果配置了 `StoryDirector`，调用其 `process()` 方法
2. 分析事件并生成故事发展
3. 调整节奏和张力

**输出：**
- `story_beats`: 故事节拍列表

---

### 步骤 11: Memory（记忆维护）

维护和压缩 NPC 记忆。纯代码步骤。

**输入：**
- `MemoryStore[]`: 所有 NPC 的记忆存储

**处理逻辑：**
1. 遍历所有 NPC 的记忆存储
2. 短期记忆使用滑动窗口自动管理容量
3. 长期记忆压缩由外部 `MemoryCompressor` 处理

**输出：**
- 更新后的记忆存储（隐式）

---

### 步骤 12: Knowledge（知识图谱）

从事件更新知识图谱。纯代码步骤。

**输入：**
- `world_events`: 本回合的所有事件

**处理逻辑：**
1. 将 `GameEvent` 转换为字典格式
2. 调用 `KnowledgeGraph.infer()` 进行推理
3. 更新实体关系和属性

**输出：**
- 更新后的知识图谱（隐式）

---

### 步骤 13: Persist（持久化）

保存游戏状态。纯代码步骤。

**输入：**
- `WorldState`: 当前世界状态
- `TickResult`: 本回合结果

**处理逻辑：**
1. 如果设置了持久化回调，调用 `persist_callback`
2. 保存世界状态、角色数据、任务进度等

**输出：**
- 持久化确认（隐式）

---

### 步骤 14: Narrative（叙事生成）

生成最终叙事文本。支持 LLM 或代码回退。

**输入：**
- `TickResult`: 本回合完整结果
- `WorldState`: 当前世界状态

**处理逻辑：**
1. 如果配置了 `Narrator`，调用 LLM 生成叙事
2. 否则使用代码回退生成：
   - 玩家行动描述
   - 骰子结果反馈
   - 危险事件描述
   - NPC 行动总结
   - 其他重要事件

**代码回退叙事示例：**
```python
# 大成功
"你完美地完成了！这真是一次出色的表现！"

# 成功
"你成功了！事情进展得很顺利。"

# 失败
"你失败了……事情没有按计划进行。"

# 大失败
"糟糕！这是一次灾难性的失败！"
```

**输出：**
- `narrative`: 叙事文本字符串

---

## 并发处理说明

### NPC 并发机制

NPC 处理是 Tick 流程中唯一的并发步骤，设计如下：

```python
class TickEngine:
    def __init__(self, ..., npc_concurrency: int = 5):
        # Semaphore 限制最大并发数
        self._semaphore = asyncio.Semaphore(npc_concurrency)

    async def _step_npc_tick(self, result: TickResult, trace: TickTrace | None = None):
        # 创建所有 NPC 处理任务
        tasks = [
            self._process_single_npc(npc_id, npc, result)
            for npc_id, npc in self._npcs.items()
        ]
        # 并发执行，允许异常独立处理
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_single_npc(self, npc_id: str, npc: NPC, result: TickResult):
        # 获取信号量许可
        async with self._semaphore:
            # 处理单个 NPC
            ...
```

**设计要点：**

1. **信号量限流**：默认最大 5 个 NPC 同时处理，防止资源耗尽
2. **异常隔离**：单个 NPC 处理失败不影响其他 NPC
3. **异步 I/O**：支持 NPC 决策调用外部 LLM API
4. **可配置并发数**：通过构造函数参数调整

---

## TickResult 数据结构

每个 Tick 的结果汇总在 `TickResult` 中：

```python
@dataclass
class TickResult:
    turn: int = 0                          # 回合数
    success: bool = True                   # 是否成功
    player_action: dict[str, Any]          # 玩家行动
    dice_result: DiceResult | None          # 骰子结果
    rule_changes: list[dict[str, Any]]      # 规则变更
    npc_actions: list[dict[str, Any]]       # NPC 行动
    world_events: list[GameEvent]           # 世界事件
    new_quests: list[Quest]                  # 新任务
    story_beats: list[dict[str, Any]]       # 故事节拍
    narrative: str                           # 叙事文本
    errors: list[str]                       # 错误列表
```

---

## 示例流程

### 场景：玩家攻击哥布林

**输入：**
```python
player_action = {
    "text": "用剑攻击哥布林",
    "type": "attack",
    "target": "goblin_01",
    "dc": 12,
    "attribute_mod": 3,  # 力量加值
    "proficiency_mod": 2,  # 武器熟练
}
```

**流程执行：**

| 步骤 | 输入 | 处理 | 输出 |
|-----|------|------|------|
| DangerCheck | 玩家在森林 | 检查敌对角色 | 哥布林存在，触发危险事件 |
| DynamicNPC | 森林位置 | 生成概率检查 | 无新 NPC |
| ActionPlan | 攻击哥布林 | 解析行动 | 结构化行动字典 |
| Rules | 攻击规则 | 检查武器、距离 | 规则通过 |
| Dice | DC=12, +5 加值 | D20 检定 | 掷出 14，总数 19，成功 |
| WorldUpdate | 攻击成功 | 应用伤害 | 哥布林 HP 减少 |
| NPCTick | 哥布林 NPC | 决策反击 | 哥布林攻击玩家 |
| WorldSim | 森林环境 | 天气变化 | 开始下雨 |
| QuestGen | 哥布林受伤 | 检查触发 | 无新任务 |
| Story | 战斗事件 | 故事节奏 | 增加紧张感 |
| Memory | 战斗记忆 | 记录 | 双方记忆更新 |
| Knowledge | 哥布林关系 | 推理 | 玩家-哥布林敌对 |
| Persist | 完整状态 | 保存 | 写入数据库 |
| Narrative | 所有结果 | 生成文本 | "你挥剑斩向哥布林..." |

**输出：**
```python
TickResult(
    turn=42,
    success=True,
    player_action={"type": "attack", "target": "goblin_01", ...},
    dice_result=DiceResult(base_roll=14, total=19, result="success"),
    npc_actions=[{"npc_id": "goblin_01", "action": "attack", ...}],
    world_events=[GameEvent(type="combat", ...), GameEvent(type="environment", ...)],
    narrative="你挥剑斩向哥布林，剑刃划出一道弧光。这一击命中了！哥布林愤怒地咆哮，举起木棒向你反击..."
)
```

---

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        Tick Engine                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │ Danger   │───▶│ Dynamic  │───▶│ Action   │                  │
│  │ Check    │    │ NPC Gen  │    │ Plan     │                  │
│  └──────────┘    └──────────┘    └──────────┘                  │
│        │                                              │          │
│        ▼                                              ▼          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│  │ Persist  │◀───│Narrative │◀───│ Knowledge│◀───│  Rules   │   │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘   │
│        │                               │              │          │
│        │         ┌──────────┐          │              ▼          │
│        │         │  Memory  │◀─────────┘       ┌──────────┐      │
│        │         └──────────┘                   │   Dice   │      │
│        │               │                        └──────────┘      │
│        │               │                              │          │
│        │               ▼                              ▼          │
│        │         ┌──────────┐                  ┌──────────┐      │
│        │         │  Story   │                  │  World   │      │
│        │         └──────────┘                  │  Update  │      │
│        │               │                        └──────────┘      │
│        │               ▼                              │          │
│        │         ┌──────────┐                         │          │
│        │         │ QuestGen │◀────────┐               │          │
│        │         └──────────┘         │               │          │
│        │               │               │               │          │
│        │               ▼               ▼               ▼          │
│        │         ┌─────────────────────────────────────────┐     │
│        │         │              WorldSim                    │     │
│        │         │  ┌─────────┐ ┌─────────┐ ┌─────────┐    │     │
│        │         │  │ Weather │ │ Economy │ │ Faction │    │     │
│        │         │  └─────────┘ └─────────┘ └─────────┘    │     │
│        │         └─────────────────────────────────────────┘     │
│        │                              ▲                           │
│        │                              │                           │
│        │         ┌──────────┐         │                           │
│        └────────▶│ NPCTick  │─────────┘                           │
│                  │(并发)    │                                     │
│                  └──────────┘                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 扩展点

Tick 引擎通过 Protocol 接口支持以下扩展：

| 接口 | 用途 | 实现阶段 |
|-----|------|---------|
| `ActionPlanner` | 解析玩家自然语言输入 | Phase 6 (LLM Agent) |
| `StoryDirector` | 故事节奏控制 | Phase 6 (LLM Agent) |
| `Narrator` | 叙事文本生成 | Phase 6 (LLM Agent) |
| `NPCAgent` | NPC 智能决策 | Phase 6 (LLM Agent) |

---

## 相关文件

- 核心实现: `jag/world/tick.py`
- 骰子系统: `jag/core/dice.py`
- 规则引擎: `jag/core/rules.py`
- 世界状态: `jag/world/world.py`
- NPC 系统: `jag/world/npc.py`
- 任务系统: `jag/world/quest.py`
- 记忆系统: `jag/knowledge/memory.py`
- 知识图谱: `jag/knowledge/graph.py`