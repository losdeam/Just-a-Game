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
