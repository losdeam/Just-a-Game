# Tasks

## 阶段 1: 目录结构准备

- [x] Task 1: 创建文档目录结构
  - [x] SubTask 1.1: 创建 `docs/architecture/` 目录
  - [x] SubTask 1.2: 创建 `docs/api/` 目录
  - [x] SubTask 1.3: 创建 `docs/guides/` 目录

## 阶段 2: 架构文档编写

- [x] Task 2: 编写 agents 模块架构文档 (`docs/architecture/agents.md`)
  - [x] SubTask 2.1: 说明模块职责（LLM 驱动层）
  - [x] SubTask 2.2: 详细介绍 GameMaster、ActionPlanner、NPCAgent、StoryDirector、NarrativeGenerator
  - [x] SubTask 2.3: 说明与 world、knowledge、persistence 的依赖关系
  - [x] SubTask 2.4: 说明使用的设计模式（Facade、Factory）

- [x] Task 3: 编写 world 模块架构文档 (`docs/architecture/world.md`)
  - [x] SubTask 3.1: 说明模块职责（世界模拟）
  - [x] SubTask 3.2: 详细介绍 WorldState、NPC 系统
  - [x] SubTask 3.3: 说明经济、派系、天气模拟器
  - [x] SubTask 3.4: 说明任务生成系统

- [x] Task 4: 编写 core 模块架构文档 (`docs/architecture/core.md`)
  - [x] SubTask 4.1: 说明模块职责（基础机制）
  - [x] SubTask 4.2: 详细介绍 Dice 系统（D20 检定）
  - [x] SubTask 4.3: 详细介绍 EventBus（Pub/Sub）
  - [x] SubTask 4.4: 详细介绍 RuleEngine（混合规则引擎）
  - [x] SubTask 4.5: 详细介绍 Items 系统（基于属性）
  - [x] SubTask 4.6: 详细介绍 Perception 系统（环境感知过滤）

- [x] Task 5: 编写 knowledge 模块架构文档 (`docs/architecture/knowledge.md`)
  - [x] SubTask 5.1: 说明模块职责（记忆与知识）
  - [x] SubTask 5.2: 详细介绍知识图谱（NetworkX）
  - [x] SubTask 5.3: 详细介绍记忆系统（短期/长期）
  - [x] SubTask 5.4: 说明记忆压缩机制

- [x] Task 6: 编写 persistence 模块架构文档 (`docs/architecture/persistence.md`)
  - [x] SubTask 6.1: 说明模块职责（数据持久化）
  - [x] SubTask 6.2: 说明 Repository 模式
  - [x] SubTask 6.3: 说明数据库配置（SQLite/内存）

- [x] Task 7: 编写 Tick 引擎流程文档 (`docs/architecture/tick-engine.md`)
  - [x] SubTask 7.1: 详细说明 12 步 Tick 流程
  - [x] SubTask 7.2: 说明每个步骤的输入输出
  - [x] SubTask 7.3: 说明并发处理（NPC 并发）
  - [x] SubTask 7.4: 提供示例流程

## 阶段 3: API 文档编写

- [x] Task 8: 编写 Dice API 文档 (`docs/api/dice.md`)
  - [x] SubTask 8.1: DiceRoller 类方法说明
  - [x] SubTask 8.2: 参数说明（sides、advantage、disadvantage、modifiers、dc）
  - [x] SubTask 8.3: 返回值说明（DiceResult）
  - [x] SubTask 8.4: 使用示例

- [x] Task 9: 编写 LLM API 文档 (`docs/api/llm.md`)
  - [x] SubTask 9.1: LLMProvider 协议说明
  - [x] SubTask 9.2: LLMFactory 使用说明
  - [x] SubTask 9.3: 配置示例

- [x] Task 10: 编写 GameMaster API 文档 (`docs/api/game_master.md`)
  - [x] SubTask 10.1: setup_world 方法说明
  - [x] SubTask 10.2: process_action 方法说明
  - [x] SubTask 10.3: advance_world 方法说明
  - [x] SubTask 10.4: save_game/load_game 方法说明
  - [x] SubTask 10.5: 使用示例

- [x] Task 11: 编写 World API 文档 (`docs/api/world.md`)
  - [x] SubTask 11.1: WorldState 方法说明
  - [x] SubTask 11.2: 参数说明
  - [x] SubTask 11.3: 返回值说明

- [x] Task 12: 编写 Repository API 文档 (`docs/api/repository.md`)
  - [x] SubTask 12.1: Repository 协议说明
  - [x] SubTask 12.2: 使用示例

- [x] Task 13: 编写数据模型文档 (`docs/api/models.md`)
  - [x] SubTask 13.1: 所有 20 张表的说明
  - [x] SubTask 13.2: 字段说明
  - [x] SubTask 13.3: 表之间的关系
  - [x] SubTask 13.4: 使用示例

## 阶段 4: 开发指南编写

- [x] Task 14: 编写配置指南 (`docs/guides/configuration.md`)
  - [x] SubTask 14.1: 环境变量说明
  - [x] SubTask 14.2: YAML 配置说明
  - [x] SubTask 14.3: LLM 配置说明（按模块配置）
  - [x] SubTask 14.4: 数据库配置说明

- [x] Task 15: 编写测试指南 (`docs/guides/testing.md`)
  - [x] SubTask 15.1: 测试运行方法
  - [x] SubTask 15.2: 测试策略说明
  - [x] SubTask 15.3: MockLLMProvider 使用说明

- [x] Task 16: 编写规则扩展指南 (`docs/guides/extending-rules.md`)
  - [x] SubTask 16.1: 如何添加 YAML 规则
  - [x] SubTask 16.2: 如何注册 Python 规则
  - [x] SubTask 16.3: 规则引擎执行流程

- [x] Task 17: 编写 NPC 扩展指南 (`docs/guides/extending-npcs.md`)
  - [x] SubTask 17.1: 如何创建新 NPC
  - [x] SubTask 17.2: 如何配置 NPC 行为
  - [x] SubTask 17.3: 如何配置 NPC 日程

- [x] Task 18: 编写世界数据扩展指南 (`docs/guides/extending-world.md`)
  - [x] SubTask 18.1: 如何创建新世界数据 YAML
  - [x] SubTask 18.2: 世界数据格式说明
  - [x] SubTask 18.3: 如何加载世界数据

## 阶段 5: 文档整理与验证

- [x] Task 19: 整理现有文档目录
  - [x] SubTask 19.1: 检查 docs/superpowers 目录是否保留现有文档
  - [x] SubTask 19.2: 确保文档结构与代码模块对应

- [x] Task 20: 验证文档完整性
  - [x] SubTask 20.1: 检查所有架构文档是否包含必要信息
  - [x] SubTask 20.2: 检查所有 API 文档是否包含必要信息
  - [x] SubTask 20.3: 检查所有开发指南是否包含必要信息

# Task Dependencies

- Task 2-7 依赖 Task 1（需要目录结构）
- Task 8-13 依赖 Task 1（需要目录结构）
- Task 14-18 依赖 Task 1（需要目录结构）
- Task 19 可以与 Task 2-18 并行执行
- Task 20 依赖 Task 2-18（需要所有文档完成）