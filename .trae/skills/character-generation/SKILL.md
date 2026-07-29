---
name: character-generation
description: 生成人物（NPC），支持指定角色/性格/地点，可批量生成并建立关系网络。基于纯代码随机生成器（比 LLM 快约 1000 倍）。当用户要求生成 NPC、创建人物、批量生成角色时使用。
category: generation
---

# 人物生成 Skill

## 用途
生成人物（NPC），支持指定角色/性格/地点，可批量生成并自动建立关系网络。
生成后自动注册到当前世界的指定地点与 tick 引擎。

## 何时使用
- 用户要求"生成 NPC""创建人物""批量生成角色"
- 世界某地点需要新增 NPC
- 需要生成带属性/日程/关系/性格的完整 NPC

## 调用方式

```python
result = await registry.execute(
    "character_generation",
    SkillContext(gm=gm, params={
        "count": 3,
        "genre": "fantasy",            # 跟随世界观则省略，自动取 gm.world_lore["genre"]
        "location_ids": ["tavern", "hub"],
        "role_ids": ["merchant", "guard"],  # 可选，限定角色类型
        "seed": 42,                     # 可选，确定性生成
    }),
)
```

## 参数说明
| 参数 | 类型 | 说明 |
|------|------|------|
| `count` | int | 生成数量，默认 1 |
| `genre` | str | 类型（fantasy/sci-fi/western/...），默认跟随当前世界观 |
| `location_ids` | list[str] | 分配地点 id 列表 |
| `role_ids` | list[str] | 限定角色类型（可选） |
| `seed` | int | 随机种子（可选，用于确定性生成） |

## 输出结构
```
result.data = {
    "npcs": [{"id","name","description","role","age","traits","goal",
              "personality","location_id","attributes","resources"}],
    "count": int,
    "relationships": [{"from","to","value"}],  # 自动生成的关系网络
}
```

## 生成内容
每个 NPC 包含：身份、性格（2-4 个 trait）、目标、6 维属性（STR/DEX/CON/INT/WIS/CHA，
含 trait 修正与年龄修正）、日程（白天工作/夜间休息）、资源、描述。

## 底层实现
- 入口：`jag/skills/character_generation.py::CharacterGenerationSkill`
- 核心：`jag/world/dynamic_npc_generator.py::DynamicNPCGenerator.generate_batch`
- 数据池：`TRAIT_POOL`（20 trait）/ `ROLE_POOL`（7 genre × 6-10 role）/ `NAME_POOLS` / `RELATIONSHIP_TYPES`（9 种）
- 注册：`gm.world.add_character` + `gm.tick_engine.register_npc`

## 相关文件
- [character_generation.py](file:///workspace/jag/skills/character_generation.py)
- [dynamic_npc_generator.py](file:///workspace/jag/world/dynamic_npc_generator.py)
- [npc.py](file:///workspace/jag/world/npc.py)
