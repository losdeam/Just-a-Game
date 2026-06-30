# GameMaster API 文档

GameMaster 是游戏的核心编排器，持有所有子系统引用并提供主游戏循环接口。

## 类概述

```python
class GameMaster:
    """Central game orchestrator.

    Holds references to all subsystems and provides the main game loop interface.
    """
```

GameMaster 是整个游戏系统的核心控制类，负责协调世界状态、事件处理、规则引擎、NPC 行为、叙事生成等所有子系统。

---

## 主要方法

### setup_world()

设置游戏世界，初始化区域、地点、NPC 和玩家。

#### 参数

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `regions` | `list[WorldRegion] \| None` | 否 | 世界区域列表 |
| `locations` | `list[WorldLocation] \| None` | 否 | 地点列表 |
| `npcs` | `list[NPC] \| None` | 否 | NPC 列表 |
| `player_data` | `dict[str, Any] \| None` | 否 | 玩家初始数据 |
| `lore` | `dict[str, Any] \| None` | 否 | 世界背景设定 |

#### 返回值

`None`

#### 详细说明

此方法执行以下操作：
- 将所有区域添加到世界状态，并为每个区域初始化天气系统
- 将所有地点添加到世界状态
- 将所有 NPC 添加到世界状态并注册到 tick 引擎
- 初始化玩家角色：
  - 如果提供了 `player_data`，则使用该数据创建玩家
  - 如果未提供，则创建默认玩家（放置在第一个地点）
  - 自动确保玩家拥有 `health` 和 `max_health` 字段（默认值为 100）
- 存储世界背景设定 (`lore`)

#### 示例

```python
from jag.world.world import WorldRegion, WorldLocation
from jag.world.npc import NPC

gm = GameMaster()

# 创建区域
regions = [
    WorldRegion(id="forest", name="迷雾森林", description="古老的森林"),
]

# 创建地点
locations = [
    WorldLocation(
        id="village",
        name="起始村庄",
        description="一个宁静的小村庄",
        region_id="forest",
        location_type="settlement",
    ),
]

# 创建 NPC
npcs = [
    NPC(
        id="elder",
        name="村长",
        location_id="village",
        personality="睿智、和蔼",
    ),
]

# 玩家数据
player_data = {
    "location_id": "village",
    "inventory": ["生锈的剑", "面包"],
    "name": "冒险者",
}

# 世界背景
lore = {
    "world_name": "艾尔德兰大陆",
    "background": "一个充满魔法与神秘的世界",
}

# 设置世界
gm.setup_world(
    regions=regions,
    locations=locations,
    npcs=npcs,
    player_data=player_data,
    lore=lore,
)
```

---

### process_action()

处理玩家行动并返回叙事文本和建议选项。

#### 参数

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `player_input` | `str` | 是 | 玩家输入的自然语言行动描述 |

#### 返回值

`tuple[str, list[dict[str, Any]]]`

- **第一个元素 (str)**: 叙事文本，描述行动结果
- **第二个元素 (list)**: 建议的下一步行动选项列表

#### 详细说明

此方法是玩家与游戏交互的核心入口：
1. 将玩家输入封装为行动对象
2. 通过 tick 引擎处理行动，触发规则引擎、NPC 响应、叙事生成等
3. 增加回合计数
4. 将行动记录到玩家记忆中
5. 获取建议的下一步行动选项

#### 示例

```python
# 同步调用示例（需要在异步环境中）
narrative, options = await gm.process_action("我走向村长并与他交谈")

print(f"叙事: {narrative}")
print(f"可选行动: {options}")

# 输出示例：
# 叙事: 你走向村长，他抬起头用慈祥的目光看着你...
# 可选行动: [
#     {"text": "询问村庄附近的危险", "type": "dialogue"},
#     {"text": "查看自己的装备", "type": "info"},
#     {"text": "离开村庄探索森林", "type": "movement"},
# ]
```

---

### advance_world()

在没有玩家行动的情况下推进世界时间。

#### 参数

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `turns` | `int` | 否 | 推进的回合数，默认为 1 |

#### 返回值

`tuple[list[str], list[dict[str, Any]]]`

- **第一个元素 (list[str])**: 叙事文本列表，每个推进回合可能产生一条叙事
- **第二个元素 (list)**: 建议的行动选项列表

#### 详细说明

此方法用于：
- 推进时间流逝（例如玩家休息、等待）
- 让 NPC 和世界事件继续发展
- 触发后台事件（天气变化、经济波动、势力活动等）

#### 示例

```python
# 推进世界 3 个回合（玩家休息）
narratives, options = await gm.advance_world(turns=3)

for i, narrative in enumerate(narratives, 1):
    print(f"回合 {i}: {narrative}")

# 输出示例：
# 回合 1: 太阳渐渐升起，村庄开始苏醒...
# 回合 2: 村民们开始忙碌起来，商贩们摆出了摊位...
# 回合 3: 正午时分，你感到精神焕发...
```

---

### save_game()

将当前游戏状态保存到 JSON 文件。

#### 参数

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `path` | `str` | 否 | 保存文件路径，默认为 `"savegame.json"` |

#### 返回值

`None`

#### 详细说明

保存的游戏状态包括：
- **world**: 世界快照（区域、地点等）
- **time**: 时间信息（回合、小时、天数、季节）
- **characters**: 所有角色的状态（位置、背包、名称等）
- **global_flags**: 全局标志
- **knowledge**: 知识图谱数据

如果父目录不存在，会自动创建。

#### 示例

```python
# 保存到默认路径
gm.save_game()

# 保存到指定路径
gm.save_game(path="saves/slot1.json")

# 保存到带时间戳的文件
import datetime
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
gm.save_game(path=f"saves/autosave_{timestamp}.json")
```

---

### load_game()

从 JSON 文件加载游戏状态。

#### 参数

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `path` | `str` | 否 | 存档文件路径，默认为 `"savegame.json"` |

#### 返回值

`bool`

- `True`: 加载成功
- `False`: 加载失败（文件不存在或解析错误）

#### 详细说明

加载操作会恢复：
- 时间状态（回合、小时、天数、季节）
- 全局标志
- 知识图谱

#### 示例

```python
# 从默认路径加载
if gm.load_game():
    print("游戏加载成功！")
    status = gm.get_status()
    print(f"当前位置: {status['location']}")
else:
    print("加载失败，存档文件不存在或已损坏")

# 从指定路径加载
if gm.load_game(path="saves/slot1.json"):
    print("存档 1 加载成功")
```

---

### get_status()

获取当前游戏状态信息。

#### 参数

无

#### 返回值

`dict[str, Any]`

返回包含以下字段的字典：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `turn` | `int` | 当前回合数 |
| `time` | `str` | 当前时间（格式："HH:00（时段）"） |
| `day` | `int` | 当前天数 |
| `season` | `str` | 当前季节 |
| `location` | `str` | 当前地点名称 |
| `location_description` | `str` | 当前地点描述 |
| `inventory` | `list[str]` | 玩家背包物品 |
| `health` | `int` | 当前生命值 |
| `max_health` | `int` | 最大生命值 |
| `equipment` | `list` | 装备列表 |
| `nearby_npcs` | `list[str]` | 附近的 NPC ID 列表 |
| `nearby_entities` | `list[str]` | 附近的实体 ID 列表 |
| `active_threads` | `int` | 活跃故事线数量 |
| `active_quests` | `int` | 活跃任务数量 |

#### 示例

```python
status = gm.get_status()

print(f"回合 {status['turn']} - {status['time']}")
print(f"第 {status['day']} 天，{status['season']}")
print(f"位置: {status['location']}")
print(f"描述: {status['location_description']}")
print(f"生命值: {status['health']}/{status['max_health']}")
print(f"背包: {', '.join(status['inventory']) or '空'}")
print(f"附近NPC: {', '.join(status['nearby_npcs']) or '无'}")
print(f"活跃任务: {status['active_quests']}")

# 输出示例：
# 回合 15 - 14:00（下午）
# 第 3 天，春季
# 位置: 起始村庄
# 描述: 一个宁静的小村庄，村民们过着平静的生活
# 生命值: 85/100
# 背包: 生锈的剑, 面包, 治疗药水
# 附近NPC: elder, merchant, guard
# 活跃任务: 2
```

---

### generate_opening()

生成沉浸式的游戏开场白。

#### 参数

无

#### 返回值

`str`

返回一段描述玩家初次来到这个世界时的所见所感。

#### 详细说明

此方法会：
1. 获取玩家当前位置信息
2. 如果有可用的叙事生成器（Narrator）和 LLM，则使用 AI 生成沉浸式开场白
3. 如果 LLM 不可用或生成失败，则返回基于模板的默认开场白

开场白内容包括：
- 当前地点的环境氛围
- 感官细节
- 对前方冒险的暗示

#### 示例

```python
# 生成开场白
opening = await gm.generate_opening()
print(opening)

# 输出示例：
# 你睁开双眼，发现自己身处起始村庄。阳光透过树叶的缝隙洒落，
# 空气中弥漫着泥土和青草的芬芳。远处传来村民们的谈笑声，
# 你的背包里有一把生锈的剑和一些面包。
# 一场伟大的冒险正等待着你……
```

---

## 完整使用流程示例

以下是一个完整的游戏流程示例：

```python
import asyncio
from jag.agents.game_master import GameMaster
from jag.world.world import WorldRegion, WorldLocation
from jag.world.npc import NPC
from jag.config import GameConfig

async def main():
    # 1. 创建 GameMaster 实例
    config = GameConfig()
    gm = GameMaster(config)

    # 2. 定义世界内容
    regions = [
        WorldRegion(
            id="starter_region",
            name="起源之地",
            description="新手玩家的起始区域"
        ),
    ]

    locations = [
        WorldLocation(
            id="village",
            name="晨曦村",
            description="一个位于森林边缘的小村庄",
            region_id="starter_region",
            location_type="settlement",
        ),
        WorldLocation(
            id="forest_entrance",
            name="森林入口",
            description="通往迷雾森林的小径",
            region_id="starter_region",
            location_type="outdoor",
        ),
    ]

    npcs = [
        NPC(
            id="village_elder",
            name="村长艾德蒙",
            location_id="village",
            personality="睿智、友善、乐于助人",
        ),
        NPC(
            id="merchant",
            name="商人玛拉",
            location_id="village",
            personality="精明、健谈",
        ),
    ]

    player_data = {
        "location_id": "village",
        "inventory": ["旧地图", "水壶"],
        "name": "旅行者",
    }

    lore = {
        "world_name": "艾尔德兰大陆",
        "current_era": "第三纪元",
        "background": "一个充满魔法与传说的世界",
    }

    # 3. 初始化游戏世界
    gm.setup_world(
        regions=regions,
        locations=locations,
        npcs=npcs,
        player_data=player_data,
        lore=lore,
    )

    # 4. 生成并显示开场白
    opening = await gm.generate_opening()
    print("=" * 50)
    print(opening)
    print("=" * 50)

    # 5. 显示初始状态
    status = gm.get_status()
    print(f"\n【状态】回合 {status['turn']} | {status['time']} | 第{status['day']}天")
    print(f"【位置】{status['location']}")
    print(f"【背包】{', '.join(status['inventory'])}")

    # 6. 游戏主循环
    while True:
        # 获取建议选项
        options = await gm.get_suggested_options()

        print("\n【可选行动】")
        for i, opt in enumerate(options[:5], 1):
            print(f"  {i}. {opt.get('text', str(opt))}")

        # 获取玩家输入
        player_input = input("\n你的行动: ").strip()

        if player_input.lower() in ["退出", "quit", "exit"]:
            break

        if player_input.lower() == "保存":
            gm.save_game("saves/manual_save.json")
            print("游戏已保存！")
            continue

        if player_input.lower() == "状态":
            status = gm.get_status()
            print(f"\n【状态】回合 {status['turn']}")
            print(f"  时间: {status['time']}")
            print(f"  位置: {status['location']}")
            print(f"  生命: {status['health']}/{status['max_health']}")
            print(f"  背包: {', '.join(status['inventory']) or '空'}")
            continue

        # 处理玩家行动
        narrative, new_options = await gm.process_action(player_input)
        print(f"\n{narrative}")

        # 每隔几回合自动保存
        if gm.get_status()['turn'] % 5 == 0:
            gm.save_game("saves/autosave.json")

    # 7. 结束游戏前保存
    gm.save_game("saves/exit_save.json")
    print("\n感谢游玩！游戏进度已保存。")

# 运行游戏
if __name__ == "__main__":
    asyncio.run(main())
```

---

## 其他实用方法

### get_suggested_options()

获取玩家当前可执行的建议行动。

```python
options = await gm.get_suggested_options()
# 返回: [{"text": "与村长交谈", "type": "dialogue"}, ...]
```

### clear_world()

清除所有世界状态，用于重新构建游戏世界。

```python
gm.clear_world()
# 清空: 世界状态、背景设定、回合计数、NPC、知识图谱、任务、事件总线、规则引擎
```

---

## 注意事项

1. **异步方法**: `process_action()`、`advance_world()`、`generate_opening()` 和 `get_suggested_options()` 都是异步方法，需要在异步环境中调用。

2. **LLM 依赖**: 叙事生成和建议选项功能依赖 LLM，需要正确配置 LLM 提供者。

3. **存档兼容性**: 游戏存档格式可能会随版本更新而变化，建议在版本升级时检查存档格式。

4. **线程安全**: GameMaster 不是线程安全的，不要在多线程环境中共享同一个实例。

5. **资源清理**: 在长时间运行的程序中，考虑定期调用 `clear_world()` 释放资源。