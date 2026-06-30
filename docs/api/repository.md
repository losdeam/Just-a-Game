# Repository API 文档

Repository 模式是一种数据访问抽象，提供了统一的数据操作接口。本文档介绍了 Repository 协议及其 SQLite 实现。

## Repository 协议

`Repository` 是一个协议（Protocol），定义了基本的数据访问操作接口。

### 协议定义

```python
from typing import Any, Protocol, TypeVar
from sqlmodel import SQLModel

T = TypeVar("T", bound=SQLModel)

class Repository(Protocol):
    """Repository protocol for data access."""

    def save(self, entity: SQLModel) -> None: ...
    def find(self, model: type[T], entity_id: str) -> T | None: ...
    def find_all(self, model: type[T], **filters: Any) -> list[T]: ...
    def delete(self, entity: SQLModel) -> None: ...
    def update(self, entity: SQLModel) -> None: ...
```

### 方法说明

#### save()

保存实体到数据存储中。

**参数：**
- `entity: SQLModel` - 要保存的实体对象

**返回值：**
- `None`

**说明：**
- 如果实体已存在（根据主键判断），则更新；否则插入新记录

---

#### find()

根据 ID 查找单个实体。

**参数：**
- `model: type[T]` - 实体类型
- `entity_id: str` - 实体 ID

**返回值：**
- `T | None` - 找到的实体对象，如果不存在则返回 `None`

---

#### find_all()

查找所有符合条件的实体。

**参数：**
- `model: type[T]` - 实体类型
- `**filters: Any` - 过滤条件（可选）

**返回值：**
- `list[T]` - 符合条件的实体列表

**说明：**
- 不提供过滤条件时返回所有实体
- 支持按字段名和值进行过滤

---

#### delete()

从数据存储中删除实体。

**参数：**
- `entity: SQLModel` - 要删除的实体对象

**返回值：**
- `None`

---

#### update()

更新已存在的实体。

**参数：**
- `entity: SQLModel` - 要更新的实体对象

**返回值：**
- `None`

---

## SQLiteRepository 实现

`SQLiteRepository` 是基于 SQLite 数据库的 Repository 实现，使用 SQLModel 和 SQLAlchemy 进行数据操作。

### 类定义

```python
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, select

class SQLiteRepository:
    """SQLite-backed repository implementing the Repository protocol."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
```

### 初始化

创建 `SQLiteRepository` 实例时需要传入 SQLAlchemy 的 `Engine` 对象。

```python
from sqlalchemy import create_engine

engine = create_engine("sqlite:///database.db")
repository = SQLiteRepository(engine)
```

### 扩展方法

除了实现 Repository 协议的基本方法外，`SQLiteRepository` 还提供了以下扩展方法：

#### save_batch()

批量保存多个实体，在单个事务中完成。

**参数：**
- `entities: list[SQLModel]` - 要保存的实体列表

**返回值：**
- `None`

---

#### query()

根据条件查询实体，是 `find_all()` 的别名。

**参数：**
- `model: type[T]` - 实体类型
- `conditions: dict[str, Any]` - 查询条件

**返回值：**
- `list[T]` - 符合条件的实体列表

---

#### count()

统计符合条件的实体数量。

**参数：**
- `model: type[T]` - 实体类型
- `**filters: Any` - 过滤条件（可选）

**返回值：**
- `int` - 实体数量

---

## 使用示例

### 定义实体模型

首先定义一个继承自 `SQLModel` 的实体类：

```python
from sqlmodel import Field, SQLModel
from typing import Optional

class Player(SQLModel, table=True):
    """玩家实体。"""
    id: str = Field(primary_key=True)
    name: str
    level: int = 1
    health: int = 100
```

### 初始化 Repository

```python
from sqlalchemy import create_engine
from jag.persistence.sqlite_backend import SQLiteRepository

# 创建数据库引擎
engine = create_engine("sqlite:///game.db")

# 创建 Repository 实例
repo = SQLiteRepository(engine)

# 创建数据表
from sqlmodel import SQLModel
SQLModel.metadata.create_all(engine)
```

### 创建（Create）

```python
# 创建新玩家
player = Player(
    id="player_001",
    name="Alice",
    level=1,
    health=100
)
repo.save(player)
print(f"玩家 {player.name} 已创建")
```

### 读取（Read）

```python
# 根据ID查找单个玩家
player = repo.find(Player, "player_001")
if player:
    print(f"找到玩家: {player.name}, 等级: {player.level}")
else:
    print("玩家不存在")

# 查找所有玩家
all_players = repo.find_all(Player)
print(f"共有 {len(all_players)} 名玩家")

# 按条件查找玩家
high_level_players = repo.find_all(Player, level=10)
print(f"10级玩家有 {len(high_level_players)} 名")

# 多条件查找
players = repo.find_all(Player, level=5, health=80)
```

### 更新（Update）

```python
# 获取玩家并更新
player = repo.find(Player, "player_001")
if player:
    player.level = 5
    player.health = 150
    repo.update(player)
    print(f"玩家已更新: {player.name}, 新等级: {player.level}")
```

### 删除（Delete）

```python
# 删除玩家
player = repo.find(Player, "player_001")
if player:
    repo.delete(player)
    print("玩家已删除")
```

### 批量操作

```python
# 批量创建玩家
players = [
    Player(id="player_002", name="Bob", level=1),
    Player(id="player_003", name="Charlie", level=2),
    Player(id="player_004", name="Diana", level=3),
]
repo.save_batch(players)
print(f"批量创建了 {len(players)} 名玩家")

# 统计玩家数量
total_count = repo.count(Player)
print(f"总玩家数: {total_count}")

# 统计特定等级玩家数量
level_1_count = repo.count(Player, level=1)
print(f"1级玩家数: {level_1_count}")
```

### 完整示例

```python
from sqlalchemy import create_engine
from sqlmodel import Field, SQLModel
from jag.persistence.sqlite_backend import SQLiteRepository

# 定义实体
class Player(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    level: int = 1
    health: int = 100

# 初始化
engine = create_engine("sqlite:///game.db")
SQLModel.metadata.create_all(engine)
repo = SQLiteRepository(engine)

# CRUD 操作演示
# Create
new_player = Player(id="p001", name="Alice", level=1)
repo.save(new_player)

# Read
found = repo.find(Player, "p001")
print(f"找到: {found.name if found else 'None'}")

# Update
if found:
    found.level = 10
    repo.update(found)

# Delete
# repo.delete(found)  # 取消注释以删除
```

## 设计说明

### 为什么使用 Repository 模式？

1. **抽象数据访问**：将数据访问逻辑与业务逻辑分离
2. **易于测试**：可以轻松替换为内存实现进行单元测试
3. **灵活性**：可以切换不同的数据库实现而不影响业务代码
4. **一致性**：提供统一的 CRUD 操作接口

### 实现细节

- **SQLiteRepository** 使用 SQLModel 的 `Session` 进行数据库操作
- `save()` 方法使用 `session.merge()` 实现插入或更新
- `find_all()` 支持动态过滤条件，支持单值和列表值（使用 `IN` 查询）
- 所有操作都在独立的 Session 中执行，确保事务隔离

## 参见

- [Persistence 架构文档](../architecture/persistence.md)
- [SQLModel 官方文档](https://sqlmodel.tiangolo.com/)