---
change: core-framework
design-doc: docs/superpowers/specs/2026-06-18-core-framework-design.md
base-ref: 5e0ece4
---

# Implementation Plan: JAG Core Framework

## Overview

从零构建 JAG Agentic Open World RPG Framework v2.0，Python 3.13+ 项目。
按自底向上策略，分 8 个阶段、31 个任务逐步构建。

## Task 1.1: 项目结构搭建

**目标**：创建完整包结构和依赖配置

**文件变更**：
- `pyproject.toml` — 添加所有依赖
- `jag/__init__.py` — 包初始化
- `jag/core/__init__.py`
- `jag/agents/__init__.py`
- `jag/world/__init__.py`
- `jag/knowledge/__init__.py`
- `jag/persistence/__init__.py`
- `jag/demo/__init__.py`

**关键实现**：
```toml
# pyproject.toml dependencies
dependencies = [
    "litellm>=1.0",
    "instructor>=1.0",
    "sqlmodel>=0.0.22",
    "click>=8.0",
    "rich>=13.0",
    "pyyaml>=6.0",
    "networkx>=3.0",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]
```

**验证**：`python -c "import jag"` 成功

---

## Task 1.2: 全局配置系统

**目标**：统一的配置管理

**文件变更**：
- `jag/config.py` — 配置类

**关键实现**：
- `GameConfig` dataclass/Pydantic model
- LLM Provider 配置（provider, model, api_key, temperature）
- 数据库路径配置
- YAML 配置加载函数 `load_config(path: str) -> GameConfig`
- 模块级 LLM 配置映射

**验证**：能加载示例 YAML 配置

---

## Task 1.3: 数据模型定义

**目标**：20 张表的 SQLModel 模型

**文件变更**：
- `jag/persistence/models.py`

**关键实现**：
- Character, Item, Location, Region, Quest
- Faction, Relationship, NPCGoal, NPCSchedule, Event
- KnowledgeNode, KnowledgeEdge
- WorldEvent, StoryThread
- EconomyState, WeatherState
- MemoryShort, MemoryLong
- ActionLog, RuleTrigger

所有模型使用 SQLModel（Pydantic + SQLAlchemy），JSON 字段用于灵活属性。

**验证**：模型可实例化，字段类型正确

---

## Task 1.4: 数据库抽象层

**目标**：Repository Pattern 协议

**文件变更**：
- `jag/persistence/database.py` — Database 协议和连接管理
- `jag/persistence/repository.py` — Repository 协议定义

**关键实现**：
```python
class Repository(Protocol):
    async def save(self, entity: SQLModel) -> None: ...
    async def find(self, model: type[T], id: str) -> T | None: ...
    async def find_all(self, model: type[T], **filters) -> list[T]: ...
    async def delete(self, entity: SQLModel) -> None: ...
    async def query(self, model: type[T], conditions: dict) -> list[T]: ...
```

**验证**：协议定义可被类型检查器识别

---

## Task 1.5: SQLite 后端实现

**目标**：完整的 SQLite 持久化

**文件变更**：
- `jag/persistence/sqlite_backend.py`

**关键实现**：
- SQLiteRepository 实现 Repository 协议
- 使用 SQLModel 引擎自动建表
- CRUD 操作
- 查询过滤（基本操作符：eq, gt, lt, in_, like）
- 事务支持

**验证**：CRUD 测试通过

---

## Task 2.1: Dice System

**目标**：D20 判定系统

**文件变更**：
- `jag/core/dice.py`

**关键实现**：
- `DiceRoller` 类
- `roll(sides, count, advantage, modifiers)` 方法
- 修正类型枚举：ATTRIBUTE, PROFICIENCY, ITEM, STATUS
- 优势/劣势机制（roll 2d20, 取高/低）
- 判定结果：CRITICAL_SUCCESS, SUCCESS, FAILURE, CRITICAL_FAILURE

**验证**：单元测试覆盖所有修正类型和边界

---

## Task 2.2: 事件系统

**目标**：事件驱动架构基础

**文件变更**：
- `jag/core/events.py`

**关键实现**：
- `GameEvent` 基类（type, source, target, data, timestamp）
- `EventBus` — 事件发布/订阅
- `EventHandler` 注册机制
- `EventQueue` — 待处理事件队列
- 事件类型枚举：COMBAT, INTERACTION, ENVIRONMENT, QUEST, SOCIAL, ECONOMY

**验证**：发布/订阅测试、事件队列 FIFO 测试

---

## Task 2.3: 规则引擎

**目标**：混合规则系统（YAML + Python）

**文件变更**：
- `jag/core/rules.py`

**关键实现**：
- `Rule` 模型（name, conditions, effects, probability）
- `YAMLRulLoader` — 从 YAML 加载声明式规则
- `@rule` 装饰器 — 注册 Python 规则函数
- `RuleEngine` — 条件匹配、效果执行、连锁处理
- 连锁深度限制（max_chain_depth=5）
- `RuleContext` — 规则执行上下文（world, actor, target, item）

**验证**：YAML 规则加载测试、Python 规则注册测试、连锁测试

---

## Task 2.4: 物品系统

**目标**：物品属性 + Affordance + 组合

**文件变更**：
- `jag/core/items.py`

**关键实现**：
- `ItemProperties` — 属性标签（flammable, sharp, rope_like, stick_like, liquid 等）
- `Item` 模型 — 继承自持久化模型，增加属性标签
- `ItemCombiner` — 基于属性推导组合结果
- `ItemAffordance` — 推导物品可能的用途
- 预定义组合规则（YAML 可配）

**验证**：属性标签测试、组合推导测试

---

## Task 2.5: 感知系统

**目标**：玩家感知过滤

**文件变更**：
- `jag/core/perception.py`

**关键实现**：
- `PerceptionFilter` — 根据条件过滤世界状态
- 影响因素：光照等级、天气、距离、潜行值、感知技能
- `PerceptionResult` — 过滤后的可见实体和事件
- 可见性计算公式

**验证**：不同光照/距离下的感知过滤测试

---

## Task 3.1: 知识图谱

**目标**：实体关系图谱 + 推理

**文件变更**：
- `jag/knowledge/graph.py`

**关键实现**：
- `KnowledgeGraph` 类（基于 NetworkX DiGraph）
- CRUD：add_entity, add_relation, query, remove
- `infer(event)` — 基于事件推理关系变化
- 关系类型：OWNS, LIKES, HATES, ALLIED_WITH, ENEMY_OF, OWES, KNOWS
- 传递推理（A hates B, B allied C → A 可能对 C 不友好）
- 持久化：图数据序列化到 knowledge_nodes/knowledge_edges 表

**验证**：关系推理测试、持久化测试

---

## Task 3.2: 记忆系统

**目标**：短期 + 长期记忆

**文件变更**：
- `jag/knowledge/memory.py`

**关键实现**：
- `ShortTermMemory` — 滑动窗口（最近 N 事件），内存维护
- `LongTermMemory` — SQLite 持久化（声望、关系、历史事件摘要）
- `MemoryStore` — 统一管理短期和长期记忆
- `recall(context)` — 根据上下文检索相关记忆
- NPC 独立记忆实例

**验证**：窗口滑动测试、持久化存取测试

---

## Task 3.3: 记忆压缩

**目标**：LLM 驱动的记忆摘要

**文件变更**：
- `jag/knowledge/compression.py`

**关键实现**：
- `MemoryCompressor` — 调用 LLM 将短期记忆压缩为长期记忆
- 压缩触发条件：短期记忆超过阈值
- 压缩策略：100 事件 → 3 条长期记忆摘要
- 使用 LLM structured output 确保摘要格式

**验证**：Mock LLM 压缩测试

---

## Task 4.1: LLM Provider 协议

**目标**：统一的 LLM 调用接口

**文件变更**：
- `jag/agents/llm.py`

**关键实现**：
```python
class LLMProvider(Protocol):
    async def complete(self, prompt: str, system: str = "", **kwargs) -> str: ...
    async def structured(self, prompt: str, response_model: type[T], **kwargs) -> T: ...

class MockLLMProvider(LLMProvider):
    """测试用 Mock Provider"""
```

**验证**：Mock Provider 测试

---

## Task 4.2: OpenAI Provider

**目标**：基于 litellm 的 OpenAI 实现

**文件变更**：
- `jag/agents/llm.py`（追加）

**关键实现**：
- `LiteLLMProvider` — 基于 litellm 的通用 Provider
- 支持 OpenAI 模型（gpt-4, gpt-3.5-turbo 等）
- 错误重试（3 次）+ 超时处理
- Token 使用量追踪

**验证**：Mock 模式下 Provider 可正常调用

---

## Task 4.3: Anthropic Provider

**目标**：Anthropic 模型支持

**文件变更**：
- `jag/agents/llm.py`（追加）

**关键实现**：
- 通过 litellm 支持 Anthropic Claude 模型
- 与 OpenAI Provider 共享 LiteLLMProvider 实现（litellm 统一处理）

**验证**：Mock 模式下可切换 Provider

---

## Task 4.4: LLM 工厂

**目标**：按配置创建 Provider

**文件变更**：
- `jag/agents/llm.py`（追加）

**关键实现**：
```python
class LLMFactory:
    def __init__(self, config: LLMConfig): ...
    def create(self, module_name: str) -> LLMProvider: ...
    # 支持按模块名返回不同模型配置
    # e.g. "action_planner" → gpt-4, "npc_agent" → gpt-3.5
```

**验证**：工厂创建测试、模块映射测试

---

## Task 5.1: 世界状态管理

**目标**：世界核心状态容器

**文件变更**：
- `jag/world/world.py`

**关键实现**：
- `WorldState` — 世界状态主容器
- `Region` — 区域（包含多个 Location）
- `Location` — 地点（包含 entities, items）
- `TimeSystem` — 游戏时间（turn, hour, day, season）
- `world.advance_time(turns)` — 推进时间
- 实体管理（characters, items in location）

**验证**：世界状态创建、时间推进测试

---

## Task 5.2: NPC 模型

**目标**：NPC 数据结构

**文件变更**：
- `jag/world/npc.py`

**关键实现**：
- `NPC` 模型：
  - goal: str（长期目标）
  - desires: list[str]（短期欲望）
  - fears: list[str]（恐惧因素）
  - memory: MemoryStore（独立记忆）
  - relationships: dict[str, float]（关系值）
  - resources: dict[str, int]（物品/金钱）
  - schedule: list[ScheduleEntry]（日常作息）
  - current_action: str
  - location_id: str
- `NPCState` — NPC 运行时状态

**验证**：NPC 创建、属性访问测试

---

## Task 5.3: Tick 引擎

**目标**：回合处理链

**文件变更**：
- `jag/world/tick.py`

**关键实现**：
- `TickEngine` 类
- `async tick(player_action) -> TickResult`
- 处理链顺序：ActionPlanner → RuleEngine → Dice → WorldUpdate → NPCTick → WorldSim → Quest → Story → Memory → Knowledge → Persist → Narrative
- NPC 并发执行（asyncio.gather + Semaphore 限流）
- `TickResult` — 回合结果（叙事文本 + 世界状态快照）

**验证**：Mock 子系统的 Tick 完整流程测试

---

## Task 5.4: 势力模拟

**目标**：势力关系与冲突

**文件变更**：
- `jag/world/faction.py`

**关键实现**：
- `Faction` 模型（name, members, goals, resources）
- `FactionRelation` — 势力关系矩阵（hostile/neutral/friendly/allied）
- `FactionSimulator` — 每 tick 更新势力状态
- 声望系统：玩家行为影响势力关系
- 冲突检测：敌对势力可能触发事件

**验证**：势力关系变更测试、冲突检测测试

---

## Task 5.5: 经济模拟

**目标**：基础经济系统

**文件变更**：
- `jag/world/economy.py`

**关键实现**：
- `Commodity` — 商品（name, base_price, supply, demand）
- `Market` — 市场（location 级别，商品列表 + 价格）
- `EconomySimulator` — 每 tick 更新供需和价格
- 价格波动公式：price = base_price * (demand / supply) * random_factor
- 交易记录

**验证**：价格波动测试、交易记录测试

---

## Task 5.6: 天气模拟

**目标**：天气状态机

**文件变更**：
- `jag/world/weather.py`

**关键实现**：
- `WeatherState` — 当前天气（clear, cloudy, rain, storm, snow 等）
- `WeatherSimulator` — 状态机转换
- 季节影响（不同季节不同天气概率）
- 天气对游戏的影响标记（影响感知、旅行、战斗等）

**验证**：天气状态转换测试、季节影响测试

---

## Task 5.7: 任务生成器

**目标**：动态任务生成

**文件变更**：
- `jag/world/quest.py`

**关键实现**：
- `QuestTemplate` — 任务模板（type, conditions, rewards）
- `QuestGenerator` — 检查世界状态，匹配模板，生成任务
- 任务来源：NPC 需求、势力冲突、世界事件、玩家行为
- `Quest` 模型（title, description, objectives, status, rewards）
- 事件链触发（bandit_attack → trade_route_blocked → escort_quest）

**验证**：任务生成触发测试、任务状态变更测试

---

## Task 5.8: 事件调度器

**目标**：整合事件系统与世界模拟

**文件变更**：
- `jag/world/tick.py`（追加）或 `jag/core/events.py`（追加）

**关键实现**：
- `EventScheduler` — 管理定时事件和条件触发事件
- 时间触发：每到特定时间自动触发
- 条件触发：世界状态满足条件时触发
- 事件连锁：事件A完成后触发事件B
- 与世界 Tick 集成

**验证**：定时触发测试、条件触发测试、连锁测试

---

## Task 6.1: Action Planner

**目标**：自然语言→结构化 ActionPlan

**文件变更**：
- `jag/agents/action_planner.py`

**关键实现**：
- `ActionPlan` 模型（action, tool, target, intent, risk, estimated_effects）
- `ActionPlanner` — 调用 LLM structured output 解析玩家输入
- Prompt 模板：包含当前世界上下文（位置、可见实体、背包物品）
- 风险等级：LOW, MEDIUM, HIGH, EXTREME
- Fallback：LLM 失败时返回默认动作

**验证**：Mock LLM 解析测试、fallback 测试

---

## Task 6.2: NPC Agent

**目标**：NPC 自主行为

**文件变更**：
- `jag/agents/npc_agent.py`

**关键实现**：
- `NPCAgent` — Observe→Think→Plan→Act 循环
- `observe(world)` — 获取 NPC 局部感知
- `think(observations)` — 更新内部状态
- `plan(observations)` — LLM 辅助决策（可选，简单 NPC 用规则）
- `act(plan)` — 执行动作
- 与 TickEngine 集成

**验证**：NPC 自主行为测试、决策合理性测试

---

## Task 6.3: Story Director

**目标**：剧情节奏控制

**文件变更**：
- `jag/agents/story_director.py`

**关键实现**：
- `StoryDirector` — 分析游戏状态，决定是否需要注入剧情事件
- 节奏分析：连续 N 回合无事件 → 注入冲突
- 兴趣分析：基于玩家行为推断兴趣偏好
- 线索引导：将分散的事件串联为故事线
- `StoryThread` 模型管理

**验证**：节奏检测测试、事件注入测试

---

## Task 6.4: Narrative Generator

**目标**：世界状态→叙事文本

**文件变更**：
- `jag/agents/narrative.py`

**关键实现**：
- `NarrativeGenerator` — 调用 LLM 生成叙事
- 输入：TickResult（行动结果 + 世界变化 + NPC 行为）
- 输出：富有沉浸感的叙事文本
- 感知过滤：先通过 PerceptionFilter 再叙述
- 风格一致性：system prompt 控制叙事风格

**验证**：Mock LLM 叙事生成测试

---

## Task 7.1: GameMaster

**目标**：总调度器

**文件变更**：
- `jag/agents/game_master.py`

**关键实现**：
- `GameMaster` — 持有所有子系统引用
- `async process_action(player_input: str) -> str` — 完整回合处理
- `async advance_world(turns: int)` — 无玩家行动时推进世界
- 初始化所有子系统
- 游戏状态管理（save/load）

**验证**：完整回合处理集成测试（Mock 子系统）

---

## Task 7.2: CLI 界面

**目标**：命令行交互

**文件变更**：
- `jag/cli.py`

**关键实现**：
- click + rich 实现
- 命令：play（开始游戏）、status（查看状态）、inventory（背包）、help
- 主循环：读取输入 → GameMaster.process_action → 显示叙事
- Rich 美化输出（面板、表格、颜色）

**验证**：CLI 启动测试

---

## Task 7.3: 游戏启动流程

**目标**：端到端启动

**文件变更**：
- `jag/cli.py`（追加）
- `jag/__init__.py`（追加）

**关键实现**：
- 加载配置 → 初始化数据库 → 加载世界数据 → 创建 GameMaster → 进入主循环
- 首次启动：自动创建数据库 + 加载 demo 世界
- 继续游戏：从存档恢复

**验证**：完整启动流程测试

---

## Task 8.1: Demo 世界数据

**目标**：可玩的 demo 世界

**文件变更**：
- `jag/demo/world_data.yaml`
- `jag/demo/npcs.yaml`
- `jag/demo/items.yaml`
- `jag/demo/rules.yaml`
- `jag/demo/factions.yaml`

**关键实现**：
- 灰石村：酒馆、铁匠铺、广场、村口
- 暗影森林：小径、营地、遗迹入口
- 3-5 个 NPC：酒馆老板、铁匠、猎人、神秘旅人、盗贼
- 基础物品：油灯、剑、绳索、药水、食物
- 基础规则：火焰传播、战斗、交易
- 2 个势力：村民、森林盗贼团

**验证**：YAML 格式验证

---

## Task 8.2: 世界加载器

**目标**：YAML → 数据库

**文件变更**：
- `jag/demo/__init__.py`（追加 loader 逻辑）

**关键实现**：
- `WorldLoader` — 读取所有 YAML 文件
- 转换为 SQLModel 实例
- 通过 Repository 存入 SQLite
- 验证数据完整性

**验证**：加载测试、数据完整性测试

---

## Task 8.3: 集成测试

**目标**：完整游戏循环验证

**文件变更**：
- `tests/test_integration.py`

**关键实现**：
- 加载 demo 世界
- 使用 MockLLMProvider（返回预定义响应）
- 执行 20+ 回合游戏循环
- 验证：行动解析 → 判定 → 世界更新 → NPC 反应 → 叙事输出 → 持久化
- 验证：世界状态一致性、记忆系统工作、知识图谱更新

**验证**：集成测试全部通过

---

## Execution Order

```
Phase 1 (Tasks 1.1-1.5) → 基础设施
    ↓
Phase 2 (Tasks 2.1-2.5) → 核心系统
    ↓
Phase 3 (Tasks 3.1-3.3) → 知识记忆
    ↓
Phase 4 (Tasks 4.1-4.4) → LLM 层
    ↓
Phase 5 (Tasks 5.1-5.8) → 世界模拟
    ↓
Phase 6 (Tasks 6.1-6.4) → Agent 层
    ↓
Phase 7 (Tasks 7.1-7.3) → 总调度+CLI
    ↓
Phase 8 (Tasks 8.1-8.3) → Demo+集成
```

每个 Phase 完成后提交一次代码。
