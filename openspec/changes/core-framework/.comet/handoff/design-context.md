# Comet Design Handoff

- Change: core-framework
- Phase: design
- Mode: compact
- Context hash: ff423785b2956cf1bcaf614a871966a22fe9f27f0730d31a598c0f869aff37b7

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/core-framework/proposal.md

- Source: openspec/changes/core-framework/proposal.md
- Lines: 1-79
- SHA256: a2ff19828589087fd813439491f08502d7129a328b6265895d86442a7241a83a

```md
# Proposal: JAG Core Framework

## 问题背景

当前 JAG 项目只有一个空的 Python 项目骨架。目标是构建一个完整的 Agent 驱动开放世界 RPG 框架（v2.0），支持：

- 玩家自然语言自由行动输入
- 世界持续自主运转（即使玩家不行动，世界仍在演化）
- NPC 拥有自主目标、记忆与计划
- 任务由世界状态动态生成（非预设脚本）
- 事件产生涌现式结果（火焰传播、经济波动、势力冲突）
- 支持长期战役（记忆系统 + 知识图谱）

## 目标

构建一个**通用的 Agent RPG 引擎框架**，提供所有核心抽象和系统实现，附带一个简单 demo 世界用于验证框架功能。

框架使用者（开发者）可以通过 YAML/JSON/Python 配置来定义自己的世界、NPC、规则和故事。

## 范围

### 包含（In Scope）

**架构层次（7层）**：

1. **Presentation Layer** — CLI 入口（首版），预留 Web/API 扩展接口
2. **GameMaster Agent Orchestrator** — 总调度 Agent，管理回合流、协调所有子系统
3. **Action Planner** — 自然语言行为解释器，LLM 驱动，将玩家输入解析为结构化 ActionPlan
4. **Core Systems**：
   - Dice System（D20 判定 + 修正系统）
   - Rule Engine（条件-规则-效果 驱动的世界互动）
   - Perception System（玩家感知过滤，不等于真实世界状态）
   - Item Affordance System（物品属性 + 自由组合）
   - Story Director（LLM 驱动的剧情节奏控制）
5. **World Simulation**：
   - NPC Agent System（Observe→Think→Plan→Act 循环）
   - Quest Generator（世界状态驱动的任务生成）
   - Faction Simulation（势力关系与冲突）
   - Economy Simulation（市场供需与波动）
   - Weather Simulation（天气系统）
   - Event Scheduler（事件调度与连锁）
6. **Knowledge & Memory Layer**：
   - Knowledge Graph（NetworkX 实现，实体关系推理）
   - Memory Store（短期记忆 + 长期记忆）
   - Memory Compression（记忆摘要压缩）
7. **Persistence Layer** — SQLite 优先，通过抽象层支持 PostgreSQL 切换

**数据库表（20张）**：
characters, items, locations, regions, quests, factions, relationships, npc_goals, npc_schedules, events, knowledge_nodes, knowledge_edges, world_events, story_threads, economy_state, weather_state, memory_short, memory_long, action_logs, rule_triggers

**LLM 集成**：
- 支持多 Provider（OpenAI / Anthropic / 本地模型）
- 不同模块可配置不同模型（NPC 用小模型，Story Director 用大模型）
- 统一的 LLM 抽象层

**Demo 世界**：
- 一个简单村庄 + 周边区域
- 3-5 个有独立目标的 NPC
- 基础物品和规则集
- 可验证核心循环：行动→判定→世界更新→NPC反应→叙事输出

### 不包含（Out of Scope）

- Web UI / Discord / API 网关集成（仅预留接口）
- 多人游戏 / 并发玩家
- 图形渲染 / 前端界面
- 具体完整的游戏世界内容（仅提供 demo）
- 性能优化和压测
- 国际化

## 成功标准

1. 玩家可以通过 CLI 输入自然语言行动，获得有意义的游戏响应
2. NPC 能够自主决策和行动（即使玩家不互动，NPC 也有自己的活动）
3. 世界 Tick 能够推进时间、触发事件、更新状态
4. 规则引擎能处理物品互动（如：油灯+木门=着火）
5. 知识图谱能追踪实体关系并支持推理
6. 记忆系统能维持跨回合的上下文连贯性
7. Demo 世界能运行至少 20 个回合的完整游戏体验
```

## openspec/changes/core-framework/design.md

- Source: openspec/changes/core-framework/design.md
- Lines: 1-137
- SHA256: 8f477c6c9cc5382d9fcd43495be5897097461134b543363fbe0376fb0a9c0364

[TRUNCATED]

```md
# Design: JAG Core Framework — 高层架构决策

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                  Presentation Layer                          │
│                  CLI (首版) / Web / API (预留)                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  GameMaster Agent                            │
│              (总调度 + 回合管理 + 系统协调)                    │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Action       │  │ Narrative    │  │ Story            │  │
│  │ Planner      │  │ Generator    │  │ Director         │  │
│  │ (NLU→Plan)   │  │ (状态→叙述)   │  │ (节奏→事件)       │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    Core Systems                              │
│  ┌──────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ Dice │ │ Rule     │ │Perception│ │ Item Affordance  │  │
│  │      │ │ Engine   │ │ System   │ │ System           │  │
│  └──────┘ └──────────┘ └──────────┘ └──────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                  World Simulation                            │
│  ┌──────┐ ┌───────┐ ┌────────┐ ┌───────┐ ┌──────┐ ┌───┐ │
│  │ NPC  │ │ Quest │ │Faction │ │Economy│ │Weather│ │Evt│ │
│  │Agent │ │ Gen   │ │ Sim    │ │ Sim   │ │ Sim  │ │Sch│ │
│  └──────┘ └───────┘ └────────┘ └───────┘ └──────┘ └───┘ │
├─────────────────────────────────────────────────────────────┤
│              Knowledge & Memory Layer                        │
│  ┌──────────────────┐  ┌──────────────────────────────┐    │
│  │ Knowledge Graph  │  │ Memory Store (Short + Long)  │    │
│  │ (NetworkX)       │  │ + Compression                │    │
│  └──────────────────┘  └──────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│                  Persistence Layer                           │
│          SQLite (默认) / PostgreSQL (可选)                    │
│          Repository Pattern + Abstract Backend               │
└─────────────────────────────────────────────────────────────┘
```

## 2. 项目结构

```
jag/
├── __init__.py
├── cli.py                    # CLI 入口 (click/rich)
├── config.py                 # 全局配置
├── core/                     # 核心系统
│   ├── dice.py               # D20 判定系统
│   ├── rules.py              # 规则引擎
│   ├── perception.py         # 感知系统
│   ├── items.py              # 物品 + Affordance
│   └── events.py             # 事件系统
├── agents/                   # Agent 系统
│   ├── llm.py                # LLM 抽象层 (多 Provider)
│   ├── game_master.py        # GameMaster 调度器
│   ├── action_planner.py     # 行为解释器
│   ├── npc_agent.py          # NPC Agent
│   ├── story_director.py     # 剧情导演
│   └── narrative.py          # 叙事生成器
├── world/                    # 世界模拟
│   ├── world.py              # 世界状态管理
│   ├── tick.py               # Tick 引擎
│   ├── npc.py                # NPC 模型 + 行为
│   ├── quest.py              # 任务生成器
│   ├── faction.py            # 势力模拟
│   ├── economy.py            # 经济模拟
│   └── weather.py            # 天气模拟
├── knowledge/                # 知识与记忆
│   ├── graph.py              # 知识图谱 (NetworkX)
│   ├── memory.py             # 记忆系统
│   └── compression.py        # 记忆压缩
├── persistence/              # 持久化
│   ├── database.py           # 数据库抽象层
│   ├── sqlite_backend.py     # SQLite 实现
```

Full source: openspec/changes/core-framework/design.md

## openspec/changes/core-framework/tasks.md

- Source: openspec/changes/core-framework/tasks.md
- Lines: 1-60
- SHA256: 6e0b256da26cdef7c4763c47848a214fcd913f33b8dd8c35eaacae815fc11731

```md
# Tasks: JAG Core Framework

## Phase 1: 基础设施与持久化层

- [ ] 1.1 项目结构搭建 — 创建完整的包结构（jag/core, jag/agents, jag/world, jag/knowledge, jag/persistence, jag/demo）、pyproject.toml 依赖配置
- [ ] 1.2 全局配置系统 — config.py，支持 YAML 配置加载、LLM Provider 配置、数据库路径配置
- [ ] 1.3 数据模型定义 — models.py，20 张表的 Pydantic v2 模型
- [ ] 1.4 数据库抽象层 — database.py + repository.py，Repository Pattern 协议定义
- [ ] 1.5 SQLite 后端实现 — sqlite_backend.py，建表、CRUD、查询过滤

## Phase 2: 核心系统

- [ ] 2.1 Dice System — dice.py，D20 掷骰、优势/劣势、各类修正
- [ ] 2.2 事件系统 — events.py，事件定义、事件队列、事件处理器、事件分发
- [ ] 2.3 规则引擎 — rules.py，YAML 规则加载、条件匹配、效果执行、连锁处理
- [ ] 2.4 物品系统 — items.py，物品属性模型、Affordance 标签、物品组合
- [ ] 2.5 感知系统 — perception.py，基于光照/天气/距离/潜行/技能的感知过滤

## Phase 3: 知识与记忆层

- [ ] 3.1 知识图谱 — graph.py，NetworkX 实现，实体/关系 CRUD、推理
- [ ] 3.2 记忆系统 — memory.py，短期记忆 + 长期记忆
- [ ] 3.3 记忆压缩 — compression.py，LLM 驱动的记忆摘要压缩

## Phase 4: LLM 抽象层

- [ ] 4.1 LLM Provider 协议 — llm.py，Protocol + complete() + structured() 接口
- [ ] 4.2 OpenAI Provider — 基于 litellm 的 OpenAI 实现
- [ ] 4.3 Anthropic Provider — 基于 litellm 的 Anthropic 实现
- [ ] 4.4 LLM 工厂 — LLMFactory，按配置创建 Provider，支持按模块配不同模型

## Phase 5: 世界模拟

- [ ] 5.1 世界状态管理 — world.py，WorldState、区域/地点/实体管理、时间系统
- [ ] 5.2 NPC 模型 — npc.py，Goal/Desire/Fear/Memory/Relationship/Resources/Schedule
- [ ] 5.3 Tick 引擎 — tick.py，回合处理链编排
- [ ] 5.4 势力模拟 — faction.py，势力关系矩阵、声望、冲突检测
- [ ] 5.5 经济模拟 — economy.py，商品供需、价格波动、交易
- [ ] 5.6 天气模拟 — weather.py，天气状态机、季节影响
- [ ] 5.7 任务生成器 — quest.py，基于世界状态的动态任务生成
- [ ] 5.8 事件调度器 — 整合事件系统与世界模拟

## Phase 6: Agent 层

- [ ] 6.1 Action Planner — action_planner.py，LLM 驱动自然语言解析→结构化 ActionPlan
- [ ] 6.2 NPC Agent — npc_agent.py，Observe→Think→Plan→Act 循环
- [ ] 6.3 Story Director — story_director.py，节奏控制、冲突制造、线索引导
- [ ] 6.4 Narrative Generator — narrative.py，世界状态→叙事文本

## Phase 7: GameMaster 与 CLI

- [ ] 7.1 GameMaster — game_master.py，总调度器、回合管理、子系统协调
- [ ] 7.2 CLI 界面 — cli.py，click + rich 命令行交互
- [ ] 7.3 游戏启动流程 — 初始化世界、加载配置、进入主循环

## Phase 8: Demo 世界与集成

- [ ] 8.1 Demo 世界数据 — world_data/npcs/items/rules/factions YAML
- [ ] 8.2 世界加载器 — YAML→数据库
- [ ] 8.3 集成测试 — 完整游戏循环（至少 20 回合）
```

