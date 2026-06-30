# World API 文档

本文档描述了游戏世界状态管理的核心类和方法。

## WorldState 类

世界状态的主容器，管理游戏中的区域、地点、角色、物品和时间系统。

### 构造函数

```python
WorldState()
```

初始化一个空的世界状态实例。

### 主要方法

#### add_region()

添加一个区域到世界中。

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `region` | `WorldRegion` | 要添加的区域对象 |

**返回值：** `None`

---

#### add_location()

添加一个地点到世界中。如果地点关联了区域ID，会自动将该地点添加到对应区域的地点列表中。

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `location` | `WorldLocation` | 要添加的地点对象 |

**返回值：** `None`

---

#### add_character()

添加一个角色到世界中。如果角色数据中包含 `location_id`，会自动将角色添加到对应地点的实体列表中。

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `char_id` | `str` | 角色唯一标识符 |
| `data` | `dict[str, Any]` | 角色数据字典，可包含 `location_id` 等字段 |

**返回值：** `None`

---

#### snapshot()

获取世界状态的快照摘要。

**参数：** 无

**返回值：** `dict[str, Any]`

返回包含以下字段的字典：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `turn` | `int` | 当前回合数 |
| `time` | `str` | 当前时间字符串，格式为 "HH:00 (时段)" |
| `day` | `int` | 当前天数 |
| `season` | `str` | 当前季节 |
| `regions` | `int` | 区域总数 |
| `locations` | `int` | 地点总数 |
| `characters` | `int` | 角色总数 |

---

### 其他方法

#### add_item()

添加物品到世界中。

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `item_id` | `str` | 物品唯一标识符 |
| `data` | `dict[str, Any]` | 物品数据字典 |

---

#### move_character()

移动角色到新地点。

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `char_id` | `str` | 角色ID |
| `from_loc` | `str` | 原地点ID |
| `to_loc` | `str` | 目标地点ID |

---

#### get_location_entities()

获取指定地点的所有角色ID列表。

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `location_id` | `str` | 地点ID |

**返回值：** `list[str]` - 角色ID列表

---

#### get_location_items()

获取指定地点的所有物品ID列表。

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `location_id` | `str` | 地点ID |

**返回值：** `list[str]` - 物品ID列表

---

#### advance_time()

推进游戏时间。

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `turns` | `int` | 推进的回合数，默认为1 |

---

#### is_dangerous_location()

检查地点是否危险（危险等级 >= 5）。

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `location_id` | `str` | 地点ID |

**返回值：** `bool` - 是否危险

---

#### get_hostile_characters_at()

获取指定地点的敌对角色列表。

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `location_id` | `str` | 地点ID |
| `exclude_id` | `str \| None` | 要排除的角色ID，可选 |

**返回值：** `list[str]` - 敌对角色ID列表

---

#### generate_npc_at()

在指定地点生成NPC。

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `location_id` | `str` | 地点ID |
| `npc_type` | `str` | NPC类型，可选值：`guard`、`merchant`、`citizen`、`monster`，默认为 `guard` |

**返回值：** `dict[str, Any]` - 包含 `id` 和 `data` 字段的NPC信息

---

## 相关类

### WorldRegion

表示世界中的一个区域，包含多个地点。

**属性：**

| 属性名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | `str` | 必填 | 区域唯一标识符 |
| `name` | `str` | 必填 | 区域名称 |
| `description` | `str` | `""` | 区域描述 |
| `region_type` | `str` | `"settlement"` | 区域类型 |
| `danger_level` | `int` | `0` | 危险等级 |
| `locations` | `list[str]` | `[]` | 区域内地点ID列表 |

---

### WorldLocation

表示世界中的一个具体地点。

**属性：**

| 属性名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id` | `str` | 必填 | 地点唯一标识符 |
| `name` | `str` | 必填 | 地点名称 |
| `description` | `str` | `""` | 地点描述 |
| `region_id` | `str` | `""` | 所属区域ID |
| `location_type` | `str` | `"room"` | 地点类型（如 `room`、`outdoor` 等） |
| `light_level` | `int` | `5` | 光照等级（1-10） |
| `danger_level` | `int` | `0` | 危险等级 |
| `connected` | `list[str]` | `[]` | 相连地点ID列表 |
| `entities` | `list[str]` | `[]` | 该地点的角色ID列表 |
| `items` | `list[str]` | `[]` | 该地点的物品ID列表 |
| `tags` | `list[str]` | `[]` | 标签列表 |

---

### TimeState

游戏时间追踪系统。

**属性：**

| 属性名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `turn` | `int` | `0` | 当前回合数 |
| `hour` | `int` | `8` | 当前小时（0-23） |
| `day` | `int` | `1` | 当前天数 |
| `season` | `str` | `"spring"` | 当前季节 |

**常量：**

- `SEASON_NAMES`：季节中文名称映射
  ```python
  {"spring": "春季", "summer": "夏季", "autumn": "秋季", "winter": "冬季"}
  ```
- `TIME_NAMES`：时段中文名称映射
  ```python
  {"morning": "清晨", "afternoon": "午后", "evening": "傍晚", "night": "深夜"}
  ```

**方法：**

| 方法名 | 参数 | 返回值 | 说明 |
|--------|------|--------|------|
| `advance(turns)` | `turns: int = 1` | `None` | 推进时间N回合（1回合约1小时） |
| `time_of_day()` | 无 | `str` | 获取当前时段（morning/afternoon/evening/night） |
| `time_of_day_display()` | 无 | `str` | 获取时段中文名称 |
| `season_display()` | 无 | `str` | 获取季节中文名称 |
| `is_dark()` | 无 | `bool` | 判断当前是否为黑暗时段（<6时或>=20时） |

**时段判断规则：**

- `morning`（清晨）：6:00 - 11:59
- `afternoon`（午后）：12:00 - 17:59
- `evening`（傍晚）：18:00 - 21:59
- `night`（深夜）：22:00 - 5:59