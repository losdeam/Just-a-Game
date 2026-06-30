# JAG 配置指南

本指南详细介绍 JAG（Just a Game）的配置系统，包括环境变量配置和 YAML 配置文件。

## 目录

- [环境变量配置](#环境变量配置)
  - [LLM 配置](#llm-配置)
  - [数据库配置](#数据库配置)
  - [游戏配置](#游戏配置)
  - [按模块 LLM 配置](#按模块-llm-配置)
- [YAML 配置文件](#yaml-配置文件)
  - [GameConfig 结构](#gameconfig-结构)
  - [LLMConfig 和 LLMModuleConfig](#llmconfig-和-llmmoduleconfig)
  - [DatabaseConfig](#databaseconfig)
- [LLM 按模块配置说明](#llm-按模块配置说明)
- [数据库配置说明](#数据库配置说明)
- [Web 服务器配置说明](#web-服务器配置说明)

---

## 环境变量配置

环境变量通过 `.env` 文件或系统环境变量设置，会覆盖 YAML 配置文件中的默认值。

### LLM 配置

以下环境变量用于配置默认的 LLM 设置：

| 环境变量 | 说明 | 默认值 | 示例 |
|---------|------|--------|------|
| `LLM_PROVIDER` | LLM 提供商 | `openai` | `openai`, `anthropic`, `groq`, `deepseek`, `azure`, `ollama` |
| `LLM_MODEL` | 使用的模型名称 | `gpt-4` | `gpt-4`, `gpt-3.5-turbo`, `claude-3-opus` |
| `LLM_API_KEY` | API 密钥 | 空 | `sk-xxxx...` |
| `LLM_API_BASE` | API 基础 URL（可选） | `None` | `https://api.example.com/v1` |
| `LLM_TEMPERATURE` | 生成温度（0.0-2.0） | `0.7` | `0.7` |
| `LLM_MAX_TOKENS` | 最大生成令牌数 | `2048` | `4096` |
| `LLM_DISABLE_THINKING` | 禁用思考模式 | `false` | `true`, `1`, `yes` |

**示例 `.env` 文件：**

```bash
# LLM 配置
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
LLM_API_KEY=your-api-key-here
LLM_API_BASE=
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048
LLM_DISABLE_THINKING=true
```

### 数据库配置

| 环境变量 | 说明 | 默认值 | 示例 |
|---------|------|--------|------|
| `DB_BACKEND` | 数据库后端类型 | `sqlite` | `sqlite`, `memory`, `postgresql` |
| `DB_PATH` | 数据库文件路径（SQLite） | `jag_world.db` | `data/game.db` |
| `DB_URL` | 数据库连接 URL（PostgreSQL） | `None` | `postgresql://user:pass@localhost/jag` |

**示例：**

```bash
# SQLite 配置
DB_BACKEND=sqlite
DB_PATH=jag_world.db

# 或 PostgreSQL 配置
DB_BACKEND=postgresql
DB_URL=postgresql://user:password@localhost:5432/jag_world
```

### 游戏配置

| 环境变量 | 说明 | 默认值 | 示例 |
|---------|------|--------|------|
| `WORLD_NAME` | 世界名称 | `Default World` | `艾泽拉斯` |
| `MAX_CHAIN_DEPTH` | 行动链最大深度 | `5` | `10` |
| `NPC_CONCURRENCY` | NPC 并发处理数 | `5` | `10` |
| `WEB_HOST` | Web 服务器主机 | `127.0.0.1` | `0.0.0.0` |
| `WEB_PORT` | Web 服务器端口 | `8000` | `3000` |

**示例：**

```bash
# 游戏配置
WORLD_NAME=默认世界
MAX_CHAIN_DEPTH=5
NPC_CONCURRENCY=5

# Web 服务配置
WEB_HOST=127.0.0.1
WEB_PORT=8000
```

### 按模块 LLM 配置

可以为特定模块覆盖默认的 LLM 配置。格式为：

```
LLM_MODULE_<模块名>_<字段>
```

支持的模块名（不区分大小写）：
- `action_planner` - 行动规划器
- `story_director` - 故事导演
- `narrator` / `narrative` - 叙事生成器
- `npc_agent` - NPC 代理
- `quest_generator` - 任务生成器

**示例：**

```bash
# 为叙事模块使用更大的模型
LLM_MODULE_NARRATOR_MODEL=gpt-4
LLM_MODULE_NARRATOR_TEMPERATURE=0.9

# 为 NPC 代理使用更快的模型
LLM_MODULE_NPC_AGENT_MODEL=gpt-3.5-turbo
LLM_MODULE_NPC_AGENT_TEMPERATURE=0.5
```

---

## YAML 配置文件

JAG 支持 YAML 格式的配置文件，默认查找 `jag_config.yaml` 或 `config.yaml`。

### GameConfig 结构

`GameConfig` 是主配置类，包含以下字段：

| 字段 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `world_name` | str | `Default World` | 世界名称 |
| `world_data_dir` | str | `jag/demo` | 世界数据目录 |
| `database` | DatabaseConfig | - | 数据库配置 |
| `llm` | LLMConfig | - | LLM 配置 |
| `max_chain_depth` | int | `5` | 行动链最大深度 |
| `npc_concurrency` | int | `5` | NPC 并发处理数 |
| `short_term_memory_size` | int | `20` | 短期记忆大小 |
| `memory_compression_threshold` | int | `100` | 记忆压缩阈值 |
| `web_host` | str | `127.0.0.1` | Web 服务器主机 |
| `web_port` | int | `8000` | Web 服务器端口 |

**完整 YAML 配置示例：**

```yaml
world_name: 艾泽拉斯
world_data_dir: jag/demo
max_chain_depth: 5
npc_concurrency: 5
short_term_memory_size: 20
memory_compression_threshold: 100
web_host: 127.0.0.1
web_port: 8000

database:
  backend: sqlite
  path: jag_world.db

llm:
  default:
    provider: openai
    model: gpt-4
    api_key: ""
    api_base: null
    temperature: 0.7
    max_tokens: 2048
    disable_thinking: false
  modules:
    narrator:
      model: gpt-4
      temperature: 0.9
    npc_agent:
      model: gpt-3.5-turbo
      temperature: 0.5
```

### LLMConfig 和 LLMModuleConfig

**LLMModuleConfig** 字段：

| 字段 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `provider` | str | `openai` | LLM 提供商 |
| `model` | str | `gpt-4` | 模型名称 |
| `api_key` | str | `""` | API 密钥 |
| `api_base` | str \| None | `None` | API 基础 URL |
| `temperature` | float | `0.7` | 生成温度 |
| `max_tokens` | int | `2048` | 最大令牌数 |
| `disable_thinking` | bool | `False` | 禁用思考模式 |

**LLMConfig** 结构：

```python
class LLMConfig:
    default: LLMModuleConfig      # 默认配置
    modules: dict[str, LLMModuleConfig]  # 按模块覆盖配置

    def get_module_config(self, module_name: str) -> LLMModuleConfig:
        """获取特定模块的配置，如果不存在则返回默认配置"""
```

### DatabaseConfig

| 字段 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `backend` | str | `sqlite` | 数据库后端 (`sqlite`, `memory`, `postgresql`) |
| `path` | str | `jag_world.db` | SQLite 数据库文件路径 |
| `url` | str \| None | `None` | PostgreSQL 连接 URL |

**配置示例：**

```yaml
# SQLite
database:
  backend: sqlite
  path: data/game.db

# 内存数据库（用于测试）
database:
  backend: memory

# PostgreSQL
database:
  backend: postgresql
  url: postgresql://user:pass@localhost:5432/jag_world
```

---

## LLM 按模块配置说明

不同模块对 LLM 的需求不同，可以根据模块特点配置不同的模型：

### 高参与度模块（推荐使用大模型）

这些模块负责核心叙事和决策，影响游戏体验的关键部分：

| 模块名 | 说明 | 推荐配置 |
|-------|------|---------|
| `action_planner` | 行动规划器 - 解析玩家意图并规划行动 | 大模型（如 GPT-4） |
| `story_director` | 故事导演 - 控制故事走向和剧情发展 | 大模型（如 GPT-4） |
| `narrative` / `narrator` | 叙事生成器 - 生成游戏描述和文本 | 大模型（如 GPT-4） |

**配置示例：**

```bash
# 高参与度模块使用 GPT-4
LLM_MODULE_ACTION_PLANNER_MODEL=gpt-4
LLM_MODULE_ACTION_PLANNER_TEMPERATURE=0.8

LLM_MODULE_STORY_DIRECTOR_MODEL=gpt-4
LLM_MODULE_STORY_DIRECTOR_TEMPERATURE=0.7

LLM_MODULE_NARRATIVE_MODEL=gpt-4
LLM_MODULE_NARRATIVE_TEMPERATURE=0.9
```

### 中参与度模块（可使用小模型）

这些模块处理相对简单的任务，可以使用更快的模型：

| 模块名 | 说明 | 推荐配置 |
|-------|------|---------|
| `npc_agent` | NPC 代理 - 控制 NPC 行为和对话 | 小模型（如 GPT-3.5-turbo） |
| `quest_generator` | 任务生成器 - 生成任务内容 | 小模型（如 GPT-3.5-turbo） |

**配置示例：**

```bash
# 中参与度模块使用 GPT-3.5-turbo
LLM_MODULE_NPC_AGENT_MODEL=gpt-3.5-turbo
LLM_MODULE_NPC_AGENT_TEMPERATURE=0.6
LLM_MODULE_NPC_AGENT_MAX_TOKENS=1024

LLM_MODULE_QUEST_GENERATOR_MODEL=gpt-3.5-turbo
LLM_MODULE_QUEST_GENERATOR_TEMPERATURE=0.7
```

---

## 数据库配置说明

### SQLite（推荐用于开发和测试）

SQLite 是默认的数据库后端，无需额外配置，适合单机使用。

**特点：**
- 零配置，开箱即用
- 数据存储在本地文件中
- 适合开发和测试环境
- 不适合高并发场景

**配置：**

```bash
# 环境变量
DB_BACKEND=sqlite
DB_PATH=jag_world.db
```

```yaml
# YAML 配置
database:
  backend: sqlite
  path: jag_world.db
```

### 内存数据库（用于测试）

数据存储在内存中，程序退出后数据丢失，适合自动化测试。

**配置：**

```bash
DB_BACKEND=memory
```

```yaml
database:
  backend: memory
```

### PostgreSQL（推荐用于生产环境）

适合生产环境，支持高并发访问。

**配置：**

```bash
DB_BACKEND=postgresql
DB_URL=postgresql://username:password@hostname:5432/database_name
```

```yaml
database:
  backend: postgresql
  url: postgresql://username:password@hostname:5432/database_name
```

---

## Web 服务器配置说明

JAG 提供 Web 界面和 API 服务，通过以下配置控制：

| 环境变量 | 说明 | 默认值 | 使用场景 |
|---------|------|--------|---------|
| `WEB_HOST` | 监听的主机地址 | `127.0.0.1` | 仅本地访问 |
| | | `0.0.0.0` | 允许外部访问 |
| `WEB_PORT` | 监听的端口号 | `8000` | 避免端口冲突时可修改 |

**本地开发配置：**

```bash
WEB_HOST=127.0.0.1
WEB_PORT=8000
```

**局域网访问配置：**

```bash
WEB_HOST=0.0.0.0
WEB_PORT=8000
```

**YAML 配置：**

```yaml
web_host: 127.0.0.1
web_port: 8000
```

---

## 配置优先级

配置加载顺序如下（后者覆盖前者）：

1. **代码默认值** - `config.py` 中定义的默认值
2. **YAML 配置文件** - `jag_config.yaml` 或 `config.yaml`
3. **环境变量** - `.env` 文件或系统环境变量

这意味着环境变量具有最高优先级，可以用于在不修改配置文件的情况下覆盖特定设置。

---

## 快速开始配置示例

### 开发环境配置

创建 `.env` 文件：

```bash
# LLM 配置
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
LLM_API_KEY=your-api-key-here
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048

# 数据库配置
DB_BACKEND=sqlite
DB_PATH=dev_world.db

# 游戏配置
WORLD_NAME=开发测试世界
MAX_CHAIN_DEPTH=5
NPC_CONCURRENCY=3
WEB_HOST=127.0.0.1
WEB_PORT=8000
```

### 生产环境配置

创建 `.env` 文件：

```bash
# LLM 配置 - 默认使用快速模型
LLM_PROVIDER=openai
LLM_MODEL=gpt-3.5-turbo
LLM_API_KEY=your-api-key-here

# 关键模块使用大模型
LLM_MODULE_NARRATIVE_MODEL=gpt-4
LLM_MODULE_STORY_DIRECTOR_MODEL=gpt-4
LLM_MODULE_ACTION_PLANNER_MODEL=gpt-4

# 数据库配置
DB_BACKEND=postgresql
DB_URL=postgresql://jag:password@localhost:5432/jag_world

# 游戏配置
WORLD_NAME=艾泽拉斯
MAX_CHAIN_DEPTH=10
NPC_CONCURRENCY=10
WEB_HOST=0.0.0.0
WEB_PORT=8000
```