---
name: director
description: 综合当前场景、人物、情况调度相关信息进行生成（故事节拍/剧情线/叙事）。支持两种模式：develop（根据世界状态生成故事发展）与 action（处理玩家动作走完整 tick 管道）。当用户要求推进剧情、生成故事发展、处理玩家动作、调度导演系统时使用。
category: orchestration
---

# 导演系统 Skill

## 用途
综合当前**场景、人物、情况**调度相关信息进行生成。封装 `StoryDirector` +
`GameMaster` 编排能力，是叙事生成的中央调度器。

## 何时使用
- 用户要求"推进剧情""生成故事发展""导演调度"
- 需要根据当前场景/人物/情况生成故事节拍或剧情线
- 需要处理一个玩家动作并得到沉浸式叙事 + 建议选项

## 调用方式

### 模式一：故事发展（develop）
根据当前世界状态生成故事节拍 / 剧情线：

```python
result = await registry.execute(
    "director",
    SkillContext(gm=gm, params={
        "mode": "develop",
        "situation": "玩家进入酒馆，气氛紧张",
        "events": [  # 可选：显式情况事件
            {"type": "social", "source_id": "npc_tavern_owner",
             "location_id": "tavern", "data": {...}},
        ],
    }),
)
```

### 模式二：玩家动作（action）
走完整 tick 管道（ActionPlan → Rules → Dice → World → NPC → Story → Narrative）：

```python
result = await registry.execute(
    "director",
    SkillContext(gm=gm, params={
        "mode": "action",
        "action": "向酒馆老板打听消息",
    }),
)
```

## 参数说明
| 参数 | 类型 | 说明 |
|------|------|------|
| `mode` | str | `develop`（故事发展）或 `action`（玩家动作），默认 `develop` |
| `action` | str | mode=action 时的玩家输入文本 |
| `situation` | str | 当前情况描述（develop 模式） |
| `events` | list[dict] | 显式情况事件列表（develop 模式，可选） |

## 输出结构
```
# develop
result.data = {"story_beats": [...], "active_threads": [...], "scene": {...}}
# action
result.data = {"narrative": str, "suggested_options": [...], "status": {...}}
```

## 底层实现
- 入口：`jag/skills/director.py::DirectorSkill`
- 故事导演：`jag/agents/story_director.py::StoryDirector.process`
- 动作编排：`jag/agents/game_master.py::GameMaster.process_action`
- tick 管道：`jag/world/tick.py::TickEngine`
- 上下文聚合：自动收集玩家所在地点、附近 NPC、时间季节

## 相关文件
- [director.py](file:///workspace/jag/skills/director.py)
- [story_director.py](file:///workspace/jag/agents/story_director.py)
- [tick.py](file:///workspace/jag/world/tick.py)
