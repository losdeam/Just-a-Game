# Agents 模块架构文档

## 1. 模块职责

`agents` 模块是 Just-a-Game 项目的 **LLM 驱动层**，负责将大语言模型（LLM）能力集成到游戏系统中。该模块提供了智能化的游戏体验，包括：

- **自然语言理解**：解析玩家的自然语言输入，转化为结构化的游戏行动
- **NPC 自主行为**：让 NPC 具备观察、思考、规划和行动的智能行为循环
- **叙事生成**：生成沉浸式的游戏叙事文本
- **故事导演**：控制叙事节奏、管理故事线程、注入游戏事件
- **LLM 抽象**：提供统一的 LLM 接口，支持多种模型提供商

## 2. 主要类详细介绍

### 2.1 GameMaster（中央协调器）

**文件**：`jag/agents/game_master.py`

`GameMaster` 是整个游戏系统的中央协调器，采用 **Facade 模式** 设计，持有所有子系统的引用并提供主要的游戏循环接口。

#### 核心职责

1. **系统初始化与协调**
   - 初始化核心系统（WorldState、EventBus、RuleEngine、KnowledgeGraph）
   - 初始化模拟器（WeatherSimulator、EconomySimulator、FactionSimulator、QuestGenerator）
   - 初始化所有 Agent 组件（ActionPlanner、NPCAgent、StoryDirector、NarrativeGenerator）

2. **游戏循环管理**
   - `process_action()`: 处理玩家行动，驱动一个完整的游戏回合
   - `advance_world()`: 在无玩家行动时推进世界时间
   - `get_suggested_options()`: 为玩家生成行动建议

3. **世界设置**
   - `setup_world()`: 配置游戏世界的区域、地点、NPC 和玩家
   - `clear_world()`: 清空世界状态以重建游戏

4. **存档管理**
   - `save_game()`: 将游戏状态保存为 JSON 文件
   - `load_game()`: 从 JSON 文件加载游戏状态

#### LLM 配置

`GameMaster` 通过 `LLMFactory` 为不同模块提供独立的 LLM 实例：

```python
# 各模块可配置独立的 LLM
self.action_planner = ActionPlanner(llm=self._get_llm("action_planner"))
self.npc_agent = NPCAgent(llm=self._get_llm("npc_agent"))
self.story_director = StoryDirector(llm=self._get_llm("story_director"))
self.narrator = NarrativeGenerator(llm=self._get_llm("narrator"))
```

#### 核心属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `world` | WorldState | 游戏世界状态 |
| `event_bus` | EventBus | 事件总线 |
| `rule_engine` | RuleEngine | 规则引擎 |
| `knowledge` | KnowledgeGraph | 知识图谱 |
| `tick_engine` | TickEngine | 游戏回合引擎 |
| `action_planner` | ActionPlanner | 行动规划器 |
| `npc_agent` | NPCAgent | NPC 代理 |
| `story_director` | StoryDirector | 故事导演 |
| `narrator` | NarrativeGenerator | 叙事生成器 |

---

### 2.2 ActionPlanner（行动规划器）

**文件**：`jag/agents/action_planner.py`

`ActionPlanner` 负责将玩家的自然语言输入解析为结构化的游戏行动。

#### 核心职责

1. **行动解析**：通过 LLM 将自然语言转化为 `ActionPlanModel`
   - 解析行动类型（move、attack、interact、use、take、drop、examine、rest、craft、speak）
   - 识别行动目标
   - 评估风险等级（LOW、MEDIUM、HIGH、EXTREME）
   - 计算难度等级（DC）
   - 确定使用的属性（STR、DEX、CON、INT、WIS、CHA）

2. **行动建议生成**：为玩家生成 3 个可选行动建议
   - 提供不同类型的选择（探索、社交、互动）
   - 包含不同风险级别的选项
   - 简短且符合 RPG 游戏风格

#### 数据模型

**ActionPlanModel**（结构化行动计划）：
```python
class ActionPlanModel(BaseModel):
    action_type: str          # 行动类型
    target: str               # 目标实体或地点 ID
    intent: str               # 玩家意图的自然语言描述
    risk: RiskLevel           # 风险等级
    estimated_effects: list   # 预期效果列表
    attribute: str            # 主要属性
    dc: int                   # 难度等级
    params: dict              # 额外参数
```

**SuggestedOption**（行动建议）：
```python
class SuggestedOption(BaseModel):
    text: str                 # 行动的自然语言文本
    description: str          # 行动描述
    risk: RiskLevel           # 风险等级
```

#### 回退机制

当 LLM 调用失败时，使用基于关键词的规则匹配作为回退：

```python
keywords = {
    "move": ["go", "walk", "travel", "run", "head", "move"],
    "attack": ["attack", "fight", "hit", "strike", "kill", "slash"],
    "take": ["take", "grab", "pick", "loot", "steal"],
    ...
}
```

---

### 2.3 NPCAgent（NPC 代理）

**文件**：`jag/agents/npc_agent.py`

`NPCAgent` 实现了 NPC 的自主行为循环：**观察 → 思考 → 规划 → 行动**。

#### 核心职责

1. **观察（Observe）**：收集 NPC 当前状态和环境信息
   - 位置信息（地点名称、类型）
   - 时间信息（时间、时段）
   - 附近角色和物品
   - 自身状态（精力、饥饿、心情）
   - 日程安排

2. **思考（Think）**：根据观察更新 NPC 内部状态
   - 根据精力/饥饿调整心情
   - 检测威胁（关系为负的角色）
   - 状态机驱动的情绪变化

3. **规划与行动（Plan & Act）**：
   - **LLM 模式**：使用 LLM 根据性格、目标、欲望、恐惧决定行动
   - **规则模式**（回退）：基于优先级规则决策

#### 行动类型

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

#### 规则决策优先级

1. **自我保护**：精力低于 15% → 休息；饥饿高于 85% → 寻找食物
2. **恐惧响应**：心情为恐惧 → 逃离
3. **日程遵循**：按日程移动或工作
4. **社交行为**：友好性格且附近有角色 → 社交
5. **默认行为**：闲置

#### 核心方法

```python
async def decide(
    self, npc: NPC, world: WorldState, observation: dict[str, Any]
) -> dict[str, Any]:
    """决定 NPC 本回合的行动，返回行动字典"""
```

---

### 2.4 StoryDirector（故事导演）

**文件**：`jag/agents/story_director.py`

`StoryDirector` 控制叙事节奏、管理故事线程，并在适当时机注入故事事件。

#### 核心职责

1. **节奏控制**：当游戏过于平静时注入事件
   - 跟踪无事件的回合数（`_turns_without_event`）
   - 超过阈值（默认 5 回合）时触发节奏注入

2. **故事线程管理**：
   - `create_thread()`: 创建新的故事线程
   - `get_active_threads()`: 获取活跃线程
   - 跟踪线程状态（active、climax、resolved、dormant）

3. **玩家兴趣分析**：追踪玩家行为模式
   - 按事件类型统计玩家参与度
   - 用于指导故事生成

4. **故事发展生成**：
   - **LLM 模式**：根据事件和线程生成有意义的故事发展
   - **规则模式**：从模板池中选择环境/社交/世界事件

#### 故事发展类型

| 类型 | 说明 |
|------|------|
| 升级 | 现有局势恶化 |
| 揭示 | 发现新信息 |
| 机遇 | 出现新的可能性 |
| 后果 | 过去的行为产生反作用 |
| 邂逅 | 意外的会面或发现 |

#### 数据模型

**StoryThread**（故事线程）：
```python
@dataclass
class StoryThread:
    id: str                           # 线程 ID
    title: str                        # 标题
    description: str                  # 描述
    status: str                       # 状态
    events: list[str]                 # 关联事件 ID
    involved_entities: list[str]      # 涉及的实体
    turns_active: int                 # 活跃回合数
    turns_since_event: int            # 距上次事件的回合数
```

**StoryBeatModel**（故事节拍）：
```python
class StoryBeatModel(BaseModel):
    event_type: str          # 类型：world、social、quest、environment
    description: str         # 描述
    source_id: str           # 来源实体
    location_id: str         # 发生地点
    importance: int          # 重要度 1-10
    data: dict               # 额外数据
```

---

### 2.5 NarrativeGenerator（叙事生成器）

**文件**：`jag/agents/narrative.py`

`NarrativeGenerator` 负责将游戏回合结果转化为沉浸式的叙事文本。

#### 核心职责

1. **叙事生成**：根据回合结果生成第二人称叙述
   - 时间和地点描述
   - 玩家行动及其结果
   - 骰子检定结果叙述
   - NPC 行动描述
   - 世界事件和任务更新

2. **感知过滤**：只叙述玩家可感知的内容
   - 仅包含玩家所在地点的事件
   - 仅描述同地点的 NPC 行动

3. **风格一致性**：通过系统提示保持叙事风格
   - 使用简体中文
   - 第二人称视角
   - 2-4 句简洁段落
   - 感官细节描写
   - 展现而非叙述

#### 叙事风格指南

系统提示定义了叙事风格：

```
风格指南：
- 用第二人称（"你"）描述玩家行动
- 描述性但简洁（每段叙事2-4句）
- 包含感官细节（视觉、声音、气味）
- 保持一致的奇幻风格语调
- 不要打破第四面墙
- 展现而非叙述：描述结果而非陈述机制
```

#### 骰子结果叙述

| 结果 | 叙述风格 |
|------|----------|
| 大成功 | 精湛的、令人印象深刻的行动 |
| 成功 | 熟练的、有效的行动 |
| 失败 | 出了什么问题，但保持趣味性 |
| 大失败 | 戏剧性的、令人难忘的失误 |

#### 回退机制

当 LLM 调用失败时，使用模板化叙述：

```python
# 玩家行动模板
if action_type == "move":
    parts.append(f"你前往{target}。")
elif action_type == "attack":
    parts.append(f"你攻击了{target}。")
...

# 骰子结果模板
if dice_result == "critical_success":
    parts.append("一次不可思议的大成功！")
elif dice_result == "success":
    parts.append("你的尝试成功了。")
...
```

---

### 2.6 LLM 抽象层

**文件**：`jag/agents/llm.py`

#### LLMProvider（协议）

`LLMProvider` 定义了 LLM 提供者的协议接口：

```python
class LLMProvider(Protocol):
    async def complete(self, prompt: str, system: str = "", **kwargs) -> str:
        """生成文本补全"""
        
    async def structured(
        self, prompt: str, response_model: type[T], system: str = "", **kwargs
    ) -> T:
        """生成结构化（JSON Schema）输出"""
```

#### LiteLLMProvider

使用 **litellm** 库实现多提供商支持：

- 支持 OpenAI、DeepSeek、Anthropic 等多种提供商
- 通过 `instructor` 库实现结构化输出
- 支持自定义 API 端点

#### MockLLMProvider

用于测试的模拟提供者：

- 可预设响应列表
- 记录所有调用历史
- 返回默认实例用于结构化输出

#### LLMFactory（工厂模式）

`LLMFactory` 采用 **Factory 模式**，根据配置创建 LLM 提供者：

```python
class LLMFactory:
    def __init__(
        self, 
        default_config: LLMConfig | None = None, 
        module_configs: dict[str, LLMConfig] | None = None
    ):
        self._default = default_config or LLMConfig()
        self._modules = module_configs or {}
        self._cache: dict[str, LLMProvider] = {}

    def get(self, module_name: str = "default") -> LLMProvider:
        """获取或创建模块的 LLM 提供者（带缓存）"""
```

支持特性：
- **默认配置**：未指定的模块使用默认配置
- **模块配置**：每个模块可独立配置
- **实例缓存**：同一模块复用同一实例

## 3. 依赖关系

### 3.1 模块依赖图

```
┌─────────────────────────────────────────────────────────────────┐
│                         agents 模块                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────┐                                                 │
│  │ GameMaster │ ──────────────────────────────────────┐        │
│  └─────┬──────┘                                       │        │
│        │                                              │        │
│        ├──────────────────────────┐                   │        │
│        │                          │                   │        │
│        ▼                          ▼                   ▼        │
│  ┌──────────────┐         ┌──────────────┐    ┌────────────┐  │
│  │ActionPlanner │         │  NPCAgent    │    │NarrativeGen│  │
│  └──────┬───────┘         └──────┬───────┘    └─────┬──────┘  │
│         │                        │                   │         │
│         │                        ▼                   │         │
│         │                 ┌──────────────┐          │         │
│         │                 │StoryDirector│          │         │
│         │                 └──────┬───────┘          │         │
│         │                        │                   │         │
│         └────────────────────────┼──────────────────┘         │
│                                  │                            │
│                                  ▼                            │
│                          ┌──────────────┐                     │
│                          │LLMProvider   │                     │
│                          │(LiteLLM/Mock)│                     │
│                          └──────────────┘                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   world 模块    │ │  knowledge 模块 │ │ persistence 模块│
├─────────────────┤ ├─────────────────┤ ├─────────────────┤
│ - WorldState    │ │ - KnowledgeGraph│ │ - Database      │
│ - WorldLocation │ │ - MemoryStore   │ │ - Repository    │
│ - NPC           │ │ - Compression   │ │ - Models        │
│ - TickEngine    │ └─────────────────┘ └─────────────────┘
│ - Weather       │
│ - Economy       │
│ - Faction       │
│ - Quest         │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│   core 模块     │
├─────────────────┤
│ - EventBus      │
│ - RuleEngine    │
│ - DiceRoller    │
│ - Events        │
└─────────────────┘
```

### 3.2 与 world 模块的关系

| agents 组件 | world 依赖 | 用途 |
|-------------|------------|------|
| GameMaster | WorldState、TickEngine、NPC、WorldLocation、WorldRegion | 世界状态管理、回合驱动、NPC 注册 |
| ActionPlanner | WorldState | 构建世界上下文用于行动规划 |
| NPCAgent | NPC、WorldState | NPC 状态更新、世界观察 |
| StoryDirector | WorldState | 基于世界状态生成故事事件 |
| NarrativeGenerator | WorldState、TickResult | 基于世界状态生成叙事 |

### 3.3 与 knowledge 模块的关系

| agents 组件 | knowledge 依赖 | 用途 |
|-------------|----------------|------|
| GameMaster | KnowledgeGraph、MemoryStore | 知识图谱管理、玩家记忆存储 |
| - | MemoryCompressor | 由 GameMaster 导入，用于记忆压缩 |

### 3.4 与 persistence 模块的关系

| agents 组件 | persistence 依赖 | 用途 |
|-------------|-----------------|------|
| GameMaster | 无直接依赖 | 通过 JSON 文件实现简单的 save/load |
| - | - | 注：GameMaster 的 save_game/load_game 是独立实现，未使用 persistence 模块 |

### 3.5 与 core 模块的关系

| agents 组件 | core 依赖 | 用途 |
|-------------|----------|------|
| GameMaster | EventBus、EventType、GameEvent、RuleEngine、DiceRoller | 事件系统、规则引擎、骰子检定 |
| StoryDirector | EventBus、EventType、GameEvent | 发布故事事件 |
| NarrativeGenerator | PerceptionFilter | 过滤玩家可感知的事件 |

## 4. 设计模式

### 4.1 Facade 模式（GameMaster）

`GameMaster` 是 **Facade 模式** 的典型应用：

```
┌──────────────────────────────────────────────────────────────┐
│                        Client Code                           │
│                    (CLI / Web Server)                        │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                       GameMaster                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 简化接口:                                                │ │
│  │ - process_action(player_input)                         │ │
│  │ - advance_world(turns)                                  │ │
│  │ - get_status()                                          │ │
│  │ - save_game(path)                                       │ │
│  │ - load_game(path)                                       │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐    │
│  │WorldState│ │EventBus  │ │RuleEngine│ │KnowledgeGraph│    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐    │
│  │TickEngine│ │ActionPlan│ │NPCAgent  │ │StoryDirector │    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                    │
│  │Narrator  │ │WeatherSim│ │EconomySim│                    │
│  └──────────┘ └──────────┘ └──────────┘                    │
└──────────────────────────────────────────────────────────────┘
```

**优势**：
- 为客户端提供简单、统一的接口
- 隐藏子系统复杂性
- 降低客户端与子系统之间的耦合
- 便于子系统的独立演进

### 4.2 Factory 模式（LLMFactory）

`LLMFactory` 是 **Factory 模式** 的应用：

```
┌──────────────────────────────────────────────────────────────┐
│                      LLMFactory                              │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 配置管理:                                               │ │
│  │ - default_config: LLMConfig                           │ │
│  │ - module_configs: dict[str, LLMConfig]                │ │
│  │ - _cache: dict[str, LLMProvider]                      │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 工厂方法:                                               │ │
│  │ - get(module_name) -> LLMProvider                     │ │
│  │ - _create_provider(config) -> LLMProvider            │ │
│  └────────────────────────────────────────────────────────┘ │
│                         │                                    │
│         ┌───────────────┼───────────────┐                   │
│         ▼               ▼               ▼                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │LiteLLMProvider│ │LiteLLMProvider│ │MockLLMProvider│      │
│  │(openai)      │ │(deepseek)    │ │(testing)     │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
│         ▲               ▲               ▲                   │
│         │               │               │                   │
│    action_planner   npc_agent      test_module             │
└──────────────────────────────────────────────────────────────┘
```

**优势**：
- 集中管理 LLM 实例创建
- 支持多模块独立配置
- 实例缓存避免重复创建
- 便于切换和测试不同的 LLM 提供者

### 4.3 Protocol 模式（LLMProvider）

`LLMProvider` 使用 Python 的 `Protocol` 定义接口，这是一种 **结构化子类型（Structural Subtyping）**：

```python
@runtime_checkable
class LLMProvider(Protocol):
    async def complete(self, prompt: str, system: str = "", **kwargs) -> str: ...
    async def structured(self, prompt: str, response_model: type[T], system: str = "", **kwargs) -> T: ...
```

**优势**：
- 无需显式继承，任何实现这些方法的类都是 `LLMProvider`
- 支持运行时类型检查（`@runtime_checkable`）
- 便于添加新的 LLM 提供者实现

### 4.4 Strategy 模式（NPC 决策）

`NPCAgent` 的决策方法隐式使用了 **Strategy 模式**：

```python
async def decide(self, npc: NPC, world: WorldState, observation: dict) -> dict:
    if self.use_llm:
        try:
            return await self._llm_decide(npc, obs)  # LLM 策略
        except Exception:
            pass
    return self._rule_decide(npc, obs)  # 规则策略
```

**优势**：
- 运行时可在 LLM 和规则之间切换
- LLM 失败时优雅降级
- 便于测试和调试

## 5. 数据流

### 5.1 玩家行动处理流程

```
玩家输入 (自然语言)
        │
        ▼
┌───────────────────┐
│   GameMaster      │
│ process_action()  │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  ActionPlanner    │
│   plan()          │
│                   │
│ 自然语言 → 结构化 │
│ ActionPlanModel   │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│   TickEngine      │
│   tick()          │
│                   │
│ 1. 规则处理       │
│ 2. 骰子检定       │
│ 3. 世界事件       │
│ 4. NPC 行动       │
│ 5. 故事导演       │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ NarrativeGenerator│
│   narrate()       │
│                   │
│ TickResult → 叙事 │
└────────┬──────────┘
         │
         ▼
   叙事文本 + 建议选项
```

### 5.2 NPC 行动循环

```
┌────────────────────┐
│     NPCAgent       │
│    decide()        │
└─────────┬──────────┘
          │
          ▼
    ┌─────────────┐
    │  Observe    │◄─── 世界状态、NPC 状态、日程
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │   Think     │◄─── 更新心情、检测威胁
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │    Plan     │◄─── LLM 或 规则决策
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │    Act      │────► 行动字典
    └─────────────┘
```

## 6. 配置说明

### 6.1 LLM 配置

```python
# config.py 中的配置结构
class LLMModuleConfig:
    provider: str        # "openai", "deepseek", "mock" 等
    model: str           # "gpt-4", "deepseek-chat" 等
    api_key: str         # API 密钥
    api_base: str        # 自定义 API 端点
    temperature: float   # 生成温度 (0.0-1.0)
    max_tokens: int      # 最大生成令牌数
    disable_thinking: bool  # 禁用思考模式

class GameConfig:
    llm: LLMConfig       # 默认配置
    modules: dict[str, LLMModuleConfig]  # 模块配置
```

### 6.2 模块特定配置

每个 Agent 模块可以独立配置 LLM：

| 模块 | 用途 | 建议配置 |
|------|------|----------|
| `action_planner` | 行动解析 | 较低温度（0.3-0.5），确保一致性 |
| `npc_agent` | NPC 决策 | 中等温度（0.5-0.7），增加多样性 |
| `story_director` | 故事生成 | 较高温度（0.7-0.9），增加创意 |
| `narrator` | 叙事生成 | 中高温度（0.6-0.8），平衡流畅与创意 |

## 7. 扩展指南

### 7.1 添加新的行动类型

1. 在 `ActionPlanner` 的系统提示中添加新类型
2. 在 `_fallback_plan()` 方法中添加关键词映射
3. 在 `TickEngine` 中实现行动处理逻辑

### 7.2 添加新的 NPC 行为

1. 在 `NPCAgent` 的系统提示中添加新行动类型
2. 在 `_rule_decide()` 方法中添加决策规则

### 7.3 添加新的故事事件类型

1. 在 `StoryDirector` 的系统提示中添加新类型
2. 在 `_pacing_injection()` 方法中添加模板

### 7.4 添加新的 LLM 提供者

1. 实现 `LLMProvider` 协议的两个方法
2. 在 `LLMFactory._create_provider()` 中添加分支
3. 更新配置支持

## 8. 注意事项

### 8.1 异步设计

所有 LLM 调用都是异步的，必须使用 `await`：

```python
# 正确
result = await self.llm.complete(prompt, system=system)

# 错误
result = self.llm.complete(prompt, system=system)  # 返回协程对象
```

### 8.2 错误处理

所有 Agent 组件都有回退机制，确保 LLM 失败时系统仍能运行：

```python
try:
    return await self._llm_decide(npc, obs)
except Exception as e:
    logger.warning("LLM failed: %s, using fallback", e)
    return self._rule_decide(npc, obs)
```

### 8.3 系统提示设计

所有系统提示都使用简体中文，并遵循以下原则：

- 明确角色定位和职责
- 列出可用选项和限制
- 提供输出格式要求
- 包含风格指南

### 8.4 结构化输出

使用 Pydantic 模型和 `instructor` 库确保 LLM 输出的结构化：

```python
class ActionPlanModel(BaseModel):
    action_type: str = Field(description="Action type...")
    target: str = Field(description="Target entity...")
    ...

result = await self.llm.structured(
    prompt=prompt,
    response_model=ActionPlanModel,
    system=PLANNER_SYSTEM_PROMPT,
)
```