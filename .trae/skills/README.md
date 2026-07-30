# JAG 生成 Skill 集

5 个生成模块，封装为统一 Skill 接口，支持动态调度。

## Skill 列表

| Skill | 名称 | 用途 |
|-------|------|------|
| `world_generation` | 世界观生成 | 根据词条生成世界观，持久化到剧本作为提示词 |
| `director` | 导演系统 | 综合场景/人物/情况调度生成（故事节拍 / 玩家动作） |
| `character_generation` | 人物生成 | 生成 NPC，支持批量与关系网络 |
| `location_generation` | 地点生成 | 根据地形/魔法/氛围生成地点 |
| `quest_generation` | 任务生成 | 根据事件或参数生成任务 |

## 快速开始

```python
from jag.skills import SkillRegistry, SkillContext

registry = SkillRegistry.instance()
registry.register_defaults()

# 查看可用 skill
print(registry.list_skills())

# 1. 生成世界观（持久化到剧本）
await registry.execute("world_generation", SkillContext(
    gm=gm, params={"world_name": "艾尔多兰", "tags": {"genre": ["fantasy"]}}))

# 2. 动态调度导演
await registry.execute("director", SkillContext(
    gm=gm, params={"mode": "action", "action": "查看周围"}))

# 3. 生成 NPC
await registry.execute("character_generation", SkillContext(
    gm=gm, params={"count": 3, "location_ids": ["tavern"]}))

# 4. 生成地点
await registry.execute("location_generation", SkillContext(
    gm=gm, params={"terrain": ["forest"], "magic": "medium"}))

# 5. 生成任务
await registry.execute("quest_generation", SkillContext(
    gm=gm, params={"custom_quest": {"title": "寻找圣剑", "objectives": ["前往古墓"]}}))
```

## 架构

```
jag/skills/
├── __init__.py              # 公开接口
├── base.py                  # Skill / SkillContext / SkillResult 基类
├── registry.py              # SkillRegistry 动态调度注册表
├── world_generation.py      # 世界观生成 + 剧本提示词持久化
├── director.py              # 导演系统（develop / action 双模式）
├── character_generation.py  # 人物生成（批量 + 关系网络）
├── location_generation.py   # 地点生成（连通图）
└── quest_generation.py      # 任务生成（事件触发 / 自定义）
```

## 持久化

`world_generation` 执行后自动调用 `gm.save_game()`，存档 `savegame.json` 包含：
`world_lore`（剧本提示词）、`regions`、`locations`、`npcs`（含属性/日程/关系/记忆）、
`quests`、`story_threads`、`characters`、`knowledge`、`time`、`global_flags`。
