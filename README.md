# JAG — Agentic Open World RPG Framework

JAG 是一个基于 LLM 驱动的开放世界 RPG 框架。NPC 拥有独立的记忆、性格和目标，世界会自主演化——天气变化、经济波动、派系斗争、任务生成——即使玩家不操作，世界也在运转。

## 架构

```
jag/
  core/         核心系统：骰子、事件总线、规则引擎、物品系统、感知过滤
  world/        世界模拟：世界状态、NPC、Tick 引擎、经济、派系、天气、任务
  agents/       LLM 代理层：LLM 抽象、GameMaster、行动规划、NPC 决策、故事导演、叙事生成
  knowledge/    知识图谱 (NetworkX) + 双存储记忆系统
  persistence/  持久化层：SQLModel 模型、Repository 模式、SQLite 后端
  web/          FastAPI + WebSocket 调试界面
  demo/         示例世界数据 (YAML)
```

### 分层说明

| 层 | 职责 |
|---|---|
| **core/** | 基础机制：D20 骰子判定、EventBus 发布/订阅、声明式+Python 混合规则引擎、基于属性的物品系统、环境感知过滤 |
| **world/** | 世界模拟器：TimeState 时间系统、NPC 属性/状态/日程、12 步 Tick 流水线、供需经济、派系关系矩阵、马尔可夫链天气、模板化任务生成 |
| **agents/** | LLM 驱动层：`GameMaster` 作为门面协调所有子系统，`ActionPlanner` 将自然语言转为结构化行动，`NPCAgent` 执行观察→思考→规划→行动循环，`StoryDirector` 控制叙事节奏，`NarrativeGenerator` 生成沉浸式描述文本 |
| **knowledge/** | 记忆与知识：`ShortTermMemory` 滑动窗口 + `LongTermMemory` 持久化关键词召回，`KnowledgeGraph` 基于 NetworkX 的实体关系图与推理 |
| **persistence/** | 数据持久化：20 个 SQLModel 表，Repository 协议抽象，支持 SQLite 和内存数据库 |
| **web/** | FastAPI 调试服务器，提供 REST API 和 WebSocket 实时游戏交互 |

### Tick 流水线

每 tick 按序执行 12 步：

1. **ActionPlan** — 将玩家输入解析为结构化行动
2. **Rules** — 规则引擎评估行动条件与效果
3. **Dice** — D20 检定（含优势/劣势、属性加值）
4. **WorldUpdate** — 更新世界状态
5. **NPCTick** — 所有 NPC 并发决策（Semaphore 限流）
6. **WorldSim** — 天气/经济/派系模拟
7. **QuestGen** — 检查并触发新任务
8. **Story** — 故事导演调控节奏
9. **Memory** — 记忆维护与压缩
10. **Knowledge** — 知识图谱推理
11. **Persist** — 数据持久化
12. **Narrative** — 生成最终叙事文本

### 设计模式

- **Facade**: `GameMaster` 统一对外接口
- **Pub/Sub**: `EventBus` 解耦子系统
- **Protocol**: `LLMProvider`、`Repository` 等接口协议
- **Factory**: `LLMFactory` 按模块创建 LLM 实例
- **Repository**: 数据访问抽象层
- **Pipeline**: Tick 引擎的 12 步流水线

## 快速开始

### 安装

```bash
# 克隆项目后
uv sync                    # 安装依赖
uv sync --group dev        # 含开发依赖
```

### 配置

复制环境变量模板并编辑：

```bash
cp .env.example .env
```

关键配置项：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `LLM_PROVIDER` | LLM 提供商 | openai |
| `LLM_MODEL` | 模型名称 | gpt-4o-mini |
| `LLM_API_KEY` | API 密钥 | — |
| `DB_BACKEND` | 数据库后端 | sqlite |
| `DB_PATH` | 数据库路径 | jag.db |
| `NPC_CONCURRENCY` | NPC 并发数 | 5 |
| `WEB_HOST` | Web 服务监听地址 | 127.0.0.1 |
| `WEB_PORT` | Web 服务端口 | 8000 |

### 启动

```bash
# 交互式 CLI 游戏
uv run jag play

# Web 调试界面
uv run jag web

# 查看版本
uv run jag version
```

或直接通过 Python 模块运行：

```bash
uv run python -m jag.cli play
```

## 技术栈

| 依赖 | 用途 |
|---|---|
| litellm | 统一 LLM API（支持 100+ 提供商） |
| instructor | 结构化 LLM 输出 |
| sqlmodel | ORM（Pydantic + SQLAlchemy） |
| click | CLI 框架 |
| rich | 终端 UI |
| networkx | 知识图谱 |
| fastapi + uvicorn | Web 调试服务器 |
| pydantic | 数据验证 |

Python >= 3.13。
