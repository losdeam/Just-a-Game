# Knowledge 模块架构文档

## 1. 模块职责

`jag.knowledge` 模块负责游戏世界中的**记忆与知识管理**，提供以下核心能力：

- **知识图谱**：构建和维护实体间的复杂关系网络，支持推理和查询
- **记忆系统**：模拟角色的短期和长期记忆机制，实现记忆的存储、检索和上下文构建
- **记忆压缩**：将大量短期记忆压缩为少量高价值的长期记忆，优化存储和检索效率

---

## 2. 知识图谱（KnowledgeGraph）

### 2.1 概述

`KnowledgeGraph` 是基于 NetworkX 的有向图结构，用于表示游戏世界中实体之间的关系网络。

**文件位置**: `jag/knowledge/graph.py`

### 2.2 核心数据结构

```python
class KnowledgeGraph:
    def __init__(self) -> None:
        self.g = nx.DiGraph()  # NetworkX 有向图
```

**节点**：代表游戏实体（角色、物品、地点等）
**边**：代表实体间的有向关系（如 `hates`、`allied_with`、`hostile` 等）

### 2.3 主要功能

#### CRUD 操作

| 方法 | 功能 |
|------|------|
| `add_entity(entity_id, **attrs)` | 添加或更新实体节点 |
| `remove_entity(entity_id)` | 删除实体及其所有关系 |
| `add_relation(source, target, relation_type, **attrs)` | 添加有向关系 |
| `remove_relation(source, target, relation_type)` | 删除指定关系 |
| `get_entity(entity_id)` | 获取实体属性 |

#### 查询功能

| 方法 | 功能 |
|------|------|
| `query(entity_id, relation_type)` | 查询从实体出发的关系 |
| `query_reverse(entity_id, relation_type)` | 查询指向实体的关系 |
| `get_all_entities()` | 获取所有实体 ID |
| `get_all_relations()` | 获取所有关系元组 |

#### 推理机制

`infer(event)` 方法根据游戏事件推断关系变化：

**支持的事件类型**：

| 事件类型 | 推理逻辑 |
|----------|----------|
| `death` | 仇恨者 → 庆祝；盟友/喜欢者 → 哀悼 |
| `combat` | 防守方盟友 → 对攻击者产生敌意 |

**推理结果**：返回 `Inference` 对象列表，包含：
- `source_id`: 推断来源实体
- `target_id`: 推断目标实体
- `relation_type`: 推断的关系类型
- `confidence`: 置信度（0.6-0.8）
- `reasoning`: 推理理由

```python
@dataclass
class Inference:
    source_id: str
    target_id: str
    relation_type: str
    confidence: float = 1.0
    reasoning: str = ""
```

#### 序列化

| 方法 | 功能 |
|------|------|
| `to_dict()` | 序列化为字典（用于持久化） |
| `from_dict(data)` | 从字典反序列化 |

---

## 3. 记忆系统

### 3.1 概述

记忆系统模拟角色的记忆机制，分为短期记忆和长期记忆两个层级。

**文件位置**: `jag/knowledge/memory.py`

### 3.2 核心数据结构

#### MemoryEntry

单条记忆条目：

```python
@dataclass
class MemoryEntry:
    id: str                      # 记忆 ID
    owner_id: str                # 所属角色 ID
    content: str                 # 记忆内容
    importance: int = 5          # 重要性（1-10）
    memory_type: str = "general" # 类型：general, reputation, relationship, historical
    turn: int = 0                # 游戏回合
    source_event_ids: list[str]  # 来源事件 ID
    timestamp: str                # 创建时间
    last_accessed: str            # 最后访问时间
```

### 3.3 短期记忆（ShortTermMemory）

#### 特性

- **滑动窗口机制**：保持最近 N 条事件（默认 20 条）
- **先进先出**：容量满时自动移除最旧记录

#### 核心方法

| 方法 | 功能 |
|------|------|
| `add(entry)` | 添加记忆，超出容量时移除最旧记录 |
| `get_all()` | 获取所有短期记忆 |
| `get_recent(n=5)` | 获取最近 N 条记忆 |
| `get_by_importance(min_importance=7)` | 获取重要性高于阈值的记忆 |
| `clear()` | 清空并返回所有条目（用于压缩） |
| `is_full` | 判断是否已满 |
| `count` | 当前条目数量 |

#### 初始化参数

```python
ShortTermMemory(owner_id: str, max_size: int = 20)
```

### 3.4 长期记忆（LongTermMemory）

#### 特性

- **持久化存储**：无容量限制
- **关键词召回**：基于上下文关键词匹配检索相关记忆
- **重要性加权**：检索时结合关键词匹配度和重要性评分

#### 核心方法

| 方法 | 功能 |
|------|------|
| `add(entry)` | 添加长期记忆 |
| `recall(context, limit=10)` | 基于上下文召回相关记忆 |
| `get_all()` | 获取所有长期记忆 |
| `get_by_type(memory_type)` | 按类型筛选记忆 |
| `count` | 当前条目数量 |

#### 召回算法

```python
def recall(self, context: str = "", limit: int = 10) -> list[MemoryEntry]:
    # 评分公式：score = 关键词重叠数 + (importance / 10.0)
    # 按分数降序返回前 limit 条
```

### 3.5 统一记忆存储（MemoryStore）

`MemoryStore` 整合短期和长期记忆，提供统一的记忆管理接口。

#### 初始化参数

```python
MemoryStore(
    owner_id: str,
    short_term_size: int = 20,        # 短期记忆容量
    compression_threshold: int = 100,  # 压缩阈值
)
```

#### 核心方法

| 方法 | 功能 |
|------|------|
| `record(content, importance, turn, event_id)` | 记录新记忆到短期记忆 |
| `needs_compression()` | 判断是否需要压缩 |
| `get_context(limit=10)` | 获取记忆上下文（用于 LLM 提示词） |

#### 上下文构建示例

```
Long-term memories:
  - 与精灵建立了友好关系
  - 击败了地精王
Recent events:
  - 发现了隐藏的宝箱
  - 与商人进行了交易
```

---

## 4. 记忆压缩机制

### 4.1 概述

记忆压缩将大量短期记忆压缩为少量长期记忆摘要，减少存储压力并提高检索效率。

**文件位置**: `jag/knowledge/compression.py`

### 4.2 设计理念

**压缩比例**：约 100 条短期记忆 → 3 条长期记忆摘要

### 4.3 核心组件

#### LLMCompressor 协议

定义 LLM 压缩器的接口规范：

```python
class LLMCompressor(Protocol):
    async def compress(self, entries_text: str, max_summaries: int = 3) -> list[str]: ...
```

#### RuleBasedCompressor（规则压缩器）

基于规则的备用压缩器，无需 LLM：

**压缩策略**：
1. 将记忆条目分组
2. 每组生成简要描述
3. 返回指定数量的摘要

```python
# 示例输出
["Multiple events: 事件1; 事件2...", "Multiple events: 事件3; 事件4...", "事件N"]
```

#### MemoryCompressor

主压缩器，协调短期记忆到长期记忆的转换。

**核心方法**：

```python
async def compress(self, store: MemoryStore, max_summaries: int = 3) -> list[MemoryEntry]:
    # 1. 清空短期记忆
    # 2. 构建文本输入
    # 3. 调用压缩器生成摘要
    # 4. 创建长期记忆条目
    # 5. 保留高重要性短期记忆（importance >= 8）
```

### 4.4 压缩流程

```
┌─────────────────────┐
│   短期记忆已满       │
│  (>= threshold)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   清空短期记忆       │
│   获取所有条目       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   构建文本输入       │
│ [Turn N] 内容       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   压缩器生成摘要     │
│   (LLM 或规则)      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   创建长期记忆       │
│   importance: 7     │
│   type: historical  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   保留高重要性记忆   │
│  (importance >= 8)  │
└─────────────────────┘
```

### 4.5 压缩结果属性

生成的长期记忆条目具有以下特性：

| 属性 | 值 |
|------|-----|
| `importance` | 7（较高重要性） |
| `memory_type` | `"historical"`（历史类型） |
| `source_event_ids` | 原始短期记忆 ID 列表 |

---

## 5. 模块交互

### 5.1 典型使用流程

```python
# 1. 创建记忆存储
store = MemoryStore(owner_id="hero", short_term_size=20, compression_threshold=100)

# 2. 记录游戏事件
store.record("发现了神秘的古代遗迹", importance=7, turn=15, event_id="event_001")

# 3. 检查是否需要压缩
if store.needs_compression():
    compressor = MemoryCompressor()
    await compressor.compress(store, max_summaries=3)

# 4. 获取上下文用于决策
context = store.get_context(limit=10)
```

### 5.2 与知识图谱的协同

```python
# 推断关系变化并记录到记忆
kg = KnowledgeGraph()
inferences = kg.infer({"type": "death", "entity_id": "goblin_king"})

for inf in inferences:
    store.record(
        content=inf.reasoning,
        importance=6,
        memory_type="relationship"
    )
    kg.apply_inference(inf)
```

---

## 6. 设计特点

### 6.1 可扩展性

- **LLMCompressor 协议**：支持自定义 LLM 压缩器实现
- **RuleBasedCompressor**：提供无依赖的备用方案

### 6.2 灵活配置

- 短期记忆容量可调（默认 20）
- 压缩阈值可调（默认 100）
- 压缩摘要数量可调（默认 3）

### 6.3 数据持久化

- `KnowledgeGraph.to_dict()` / `from_dict()`：图谱序列化
- `MemoryEntry` 使用标准 Python 类型，易于 JSON 序列化

---

## 7. 文件结构

```
jag/knowledge/
├── __init__.py       # 模块导出
├── graph.py          # 知识图谱实现
├── memory.py         # 记忆系统实现
└── compression.py    # 记忆压缩实现
```