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
