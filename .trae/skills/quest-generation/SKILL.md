---
name: quest-generation
description: 根据世界事件触发任务模板生成任务，或根据标题/目标/奖励参数生成自定义任务。当用户要求生成任务、创建主线/支线、根据事件派发任务时使用。
category: generation
---

# 任务生成 Skill

## 用途
根据世界事件触发任务模板生成任务，或根据显式参数生成自定义任务。
生成后自动加入当前活跃任务列表。

## 何时使用
- 用户要求"生成任务""创建主线/支线"
- 需要根据世界事件派发任务
- 需要创建自定义任务（指定标题/目标/奖励）

## 调用方式

### 模式一：事件触发（默认）
根据世界事件匹配任务模板：

```python
result = await registry.execute(
    "quest_generation",
    SkillContext(gm=gm, params={
        "events": [
            {"type": "threat_nearby", "threat": "哥布林", "location": "森林边缘"},
            {"type": "npc_need", "need": "safety", "npc_name": "商人老陈",
             "location": "集市", "giver_name": "商人老陈"},
        ],
    }),
)
```

### 模式二：自定义任务
显式指定任务内容：

```python
result = await registry.execute(
    "quest_generation",
    SkillContext(gm=gm, params={
        "custom_quest": {
            "title": "寻找失落之剑",
            "description": "传说中沉睡于古墓的圣剑",
            "quest_type": "main",
            "giver_id": "npc_elder",
            "objectives": ["前往古墓", "击败守墓者", "取得圣剑"],
            "rewards": {"xp": 200, "gold": 100, "item": "圣剑"},
        },
    }),
)
```

## 参数说明
| 参数 | 类型 | 说明 |
|------|------|------|
| `events` | list[dict] | 世界事件列表（事件触发模式） |
| `custom_quest` | dict | 自定义任务规格（自定义模式） |

## 内置任务模板
- **escort**（护送）：`npc_need/safety` 触发，奖励 xp+gold
- **eliminate**（清剿）：`threat_nearby` 触发
- **delivery**（送货）：`npc_need/item` 触发
- **investigate**（调查）：`world_event` 触发

## 输出结构
```
result.data = {
    "new_quests": [{"id","title","description","quest_type","status",
                    "giver_id","objectives":[{"description","completed"}],"rewards","source"}],
    "active_quests": [...],   # 当前所有活跃任务
    "count": int,
}
```

## 底层实现
- 入口：`jag/skills/quest_generation.py::QuestGenerationSkill`
- 核心：`jag/world/quest.py::QuestGenerator.check`
- 模板：`_default_templates`（4 个内置）/ `add_template`（可扩展）
- 集成：tick 管道 `_step_quest_gen` 自动调用

## 相关文件
- [quest_generation.py](file:///workspace/jag/skills/quest_generation.py)
- [quest.py](file:///workspace/jag/world/quest.py)
