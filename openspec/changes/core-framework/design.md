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
│   ├── models.py             # 数据模型 (20 张表)
│   └── repository.py         # Repository 模式
└── demo/                     # Demo 世界
    ├── world_data.yaml       # 世界定义
    ├── npcs.yaml             # NPC 定义
    ├── items.yaml            # 物品定义
    ├── rules.yaml            # 规则定义
    └── factions.yaml         # 势力定义
```

## 3. 关键设计决策

### 3.1 LLM 抽象层

统一接口，支持多 Provider（OpenAI/Anthropic/本地模型），通过 litellm 统一调用。不同模块配置不同模型：高参与度（Story Director）用大模型，中参与度（NPC Agent）用小模型。

### 3.2 Tick 机制 — 事件驱动 + 回合制混合

玩家行动触发完整处理链：Action Planner → Rule Engine → Dice → World Update → NPC Tick → World Sim Tick → Quest Gen → Story Director → Memory Update → Persist → Narrative Output。

### 3.3 规则引擎 — 声明式 YAML 规则

条件-规则-效果模式。支持火焰传播、液体流动、爆炸连锁等涌现行为。

### 3.4 NPC Agent — Observe-Think-Plan-Act

每个 NPC 有 Goal/Desire/Fear/Memory/Relationship/Resources/Schedule。LLM 辅助决策，基于感知到的局部世界状态。

### 3.5 知识图谱 — NetworkX + 属性边

实体关系 CRUD、关系查询、事件推理（如：GoblinKing dies → John happy → Tavern celebration）。

### 3.6 数据持久化 — Repository Pattern

SQLite 默认，抽象层支持 PostgreSQL 切换。20 张表通过 Pydantic v2 模型定义。

### 3.7 世界配置 — YAML 驱动

所有世界数据（区域、NPC、物品、规则、势力）通过 YAML 文件定义，加载到数据库。

## 4. 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.13+ | 项目已指定 |
| CLI | click + rich | 丰富的终端交互 |
| LLM | litellm | 统一多 Provider 接口 |
| 异步 | asyncio | LLM 调用异步化 |
| 数据库 | SQLite + 抽象层 | 零配置，可扩展 |
| 知识图谱 | NetworkX | 轻量，Python 原生 |
| 配置 | PyYAML | 人类可读的世界定义 |
| 数据模型 | Pydantic v2 | 类型安全 + 序列化 |
| 测试 | pytest | 标准 Python 测试 |

## 5. 实现顺序

自底向上：Persistence → Core Systems → Knowledge & Memory → LLM Layer → World Simulation → Agent Layer → GameMaster → CLI → Demo World
