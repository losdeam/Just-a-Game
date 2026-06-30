# 文档系统构建 Spec

## Why

项目代码结构日趋复杂，目前仅有基础 README 和技术设计文档。为了支持长期开发和团队协作，需要建立一套完整的文档系统，包括架构文档、API 文档、开发指南等，以便新开发者快速上手，现有开发者理解各模块职责。

## What Changes

- 为每个核心模块创建独立的架构文档（agents, core, world, knowledge, persistence）
- 创建 API 文档（主要类、函数、协议的说明）
- 创建开发指南（配置、测试、扩展）
- 整理现有 docs 目录结构，使其与代码模块对应

## Impact

- Affected specs: 文档系统
- Affected code: 无代码变更，仅文档生成
- Affected directories: `docs/`, `.trae/specs/`

## ADDED Requirements

### Requirement: 架构文档

系统 SHALL 为每个主要代码模块提供详细的架构文档，包括模块职责、关键类、依赖关系、设计模式。

#### Scenario: 开发者查看 agents 模块架构
- **WHEN** 开发者打开 `docs/architecture/agents.md`
- **THEN** 文档包含 agents 模块的职责说明、主要类（GameMaster、ActionPlanner、NPCAgent、StoryDirector、NarrativeGenerator）的详细介绍、与其他模块的依赖关系、使用的设计模式

#### Scenario: 开发者查看 world 模块架构
- **WHEN** 开发者打开 `docs/architecture/world.md`
- **THEN** 文档包含 world 模块的职责说明、Tick 引擎的 12 步流程、NPC 系统、经济/派系/天气模拟器的说明

#### Scenario: 开发者查看 core 模块架构
- **WHEN** 开发者打开 `docs/architecture/core.md`
- **THEN** 文档包含 core 模块的职责说明、Dice 系统、EventBus、RuleEngine、Items 系统、Perception 系统的说明

#### Scenario: 开发者查看 knowledge 模块架构
- **WHEN** 开发者打开 `docs/architecture/knowledge.md`
- **THEN** 文档包含 knowledge 模块的职责说明、知识图谱结构、记忆系统（短期/长期）、压缩机制的说明

#### Scenario: 开发者查看 persistence 模块架构
- **WHEN** 开发者打开 `docs/architecture/persistence.md`
- **THEN** 文档包含 persistence 模块的职责说明、20 张表的说明、Repository 模式、数据库配置的说明

### Requirement: API 文档

系统 SHALL 为主要的类、函数、协议提供 API 文档，包括参数说明、返回值说明、使用示例。

#### Scenario: 开发者查看 DiceRoller API
- **WHEN** 开发者打开 `docs/api/dice.md`
- **THEN** 文档包含 DiceRoller 类的方法说明（roll、roll_check、roll_damage）、参数说明、返回值说明、使用示例

#### Scenario: 开发者查看 LLMProvider API
- **WHEN** 开发者打开 `docs/api/llm.md`
- **THEN** 文档包含 LLMProvider 协议的方法说明（complete、structured）、LLMFactory 的使用说明、配置示例

#### Scenario: 开发者查看 GameMaster API
- **WHEN** 开发者打开 `docs/api/game_master.md`
- **THEN** 文档包含 GameMaster 类的主要方法说明（setup_world、process_action、advance_world、save_game、load_game）、参数说明、返回值说明、使用示例

#### Scenario: 开发者查看 WorldState API
- **WHEN** 开发者打开 `docs/api/world.md`
- **THEN** 文档包含 WorldState 类的主要方法说明（add_region、add_location、add_character、snapshot）、参数说明、返回值说明

#### Scenario: 开发者查看 Repository API
- **WHEN** 开发者打开 `docs/api/repository.md`
- **THEN** 文档包含 Repository 协议的方法说明（save、find、find_all、delete）、使用示例

### Requirement: 开发指南

系统 SHALL 提供开发指南，包括配置说明、测试指南、扩展指南。

#### Scenario: 开发者配置环境
- **WHEN** 开发者打开 `docs/guides/configuration.md`
- **THEN** 文档包含环境变量说明、配置文件说明、LLM 配置说明、数据库配置说明、Web 服务器配置说明

#### Scenario: 开发者运行测试
- **WHEN** 开发者打开 `docs/guides/testing.md`
- **THEN** 文档包含测试运行方法、测试策略说明、MockLLMProvider 使用说明

#### Scenario: 开发者扩展规则系统
- **WHEN** 开发者打开 `docs/guides/extending-rules.md`
- **THEN** 文档包含如何添加 YAML 规则、如何注册 Python 规则、规则引擎执行流程说明

#### Scenario: 开发者扩展 NPC 系统
- **WHEN** 开发者打开 `docs/guides/extending-npcs.md`
- **THEN** 文档包含如何创建新 NPC、如何配置 NPC 行为、如何配置 NPC 日程的说明

#### Scenario: 开发者扩展世界数据
- **WHEN** 开发者打开 `docs/guides/extending-world.md`
- **THEN** 文档包含如何创建新世界数据 YAML、世界数据格式说明、如何加载世界数据的说明

### Requirement: 文档目录结构

系统 SHALL 建立清晰的文档目录结构，使文档与代码模块对应。

#### Scenario: 开发者浏览文档目录
- **WHEN** 开发者查看 `docs/` 目录
- **THEN** 目录结构包含：
  - `architecture/` - 各模块架构文档
  - `api/` - API 文档
  - `guides/` - 开发指南
  - `superpowers/` - 现有的设计和规划文档（保留）

### Requirement: Tick 引擎流程文档

系统 SHALL 提供 Tick 引擎的详细流程文档，包括每个步骤的说明、输入输出、示例。

#### Scenario: 开发者查看 Tick 引擎流程
- **WHEN** 开发者打开 `docs/architecture/tick-engine.md`
- **THEN** 文档包含 12 步 Tick 流程的详细说明、每个步骤的输入输出、并发处理说明、示例流程

### Requirement: 数据模型文档

系统 SHALL 提供数据模型的文档，包括 20 张表的说明、字段说明、关系说明。

#### Scenario: 开发者查看数据模型
- **WHEN** 开发者打开 `docs/api/models.md`
- **THEN** 文档包含所有 20 张 SQLModel 表的说明、字段说明、表之间的关系说明、使用示例

## MODIFIED Requirements

无修改的需求。

## REMOVED Requirements

无删除的需求。