---
name: world-generation
description: 根据用户选择的词条（类型/时代/氛围/地形/魔法/危险）生成完整世界观，并将世界观设定持久化保存至当前剧本（存档 JSON）作为后续导演/叙事/NPC 生成的提示词。当用户要求生成世界、创建剧本、设置世界设定、按词条生成世界观时使用。
category: generation
---

# 世界观生成 Skill

## 用途
根据用户选择的词条（tags）组合生成完整世界观（区域 + 地点 + NPC + 主线设定），
并将世界观设定**持久化保存至当前剧本**（`savegame.json`），作为后续导演、叙事、
NPC 生成的**提示词**。

## 何时使用
- 用户要求"生成世界""创建剧本""设置世界设定"
- 用户给出词条（奇幻/中世纪/阴暗/森林/高魔法/危险）要求据此生成世界
- 需要把世界设定固化到存档以便后续读取

## 调用方式

通过 Python Skill 注册表动态调度：

```python
from jag.skills import SkillRegistry, SkillContext

registry = SkillRegistry.instance()
registry.register_defaults()

result = await registry.execute(
    "world_generation",
    SkillContext(gm=gm, params={
        "world_name": "艾尔多兰",
        "tags": {
            "genre": ["fantasy"],
            "era": ["medieval"],
            "atmosphere": ["mysterious"],
            "terrain": ["forest", "mountains"],
            "magic": ["medium"],
            "danger": ["moderate"],
        },
        "description": "一个被遗忘魔法笼罩的古老王国",
        "use_llm": False,        # True 则调用 LLM 生成更丰富的世界
        "save_path": "savegame.json",
    }),
)
```

## 参数说明
| 参数 | 类型 | 说明 |
|------|------|------|
| `world_name` | str | 世界名称 |
| `tags` | dict[str, list[str]] | 词条，键为 `genre/era/atmosphere/terrain/magic/danger` |
| `description` | str | 世界描述（可选） |
| `use_llm` | bool | 是否用 LLM 生成（默认 False，纯代码组合更快） |
| `save_path` | str | 存档路径，默认 `savegame.json` |

## 输出结构
```
result.data = {
    "world": {...},          # WorldBuilder 产物
    "world_lore": {...},     # 世界设定（已写入 gm.world_lore）
    "prompts": {...},        # 结构化剧本提示词（世界名/描述/词条/区域/地点）
    "regions": int, "locations": int, "npcs": int,
}
```

## 持久化行为
执行成功后自动调用 `gm.save_game(save_path)`，存档中包含：
`world_lore`（剧本提示词）、`regions`、`locations`、`npcs`、`quests`、`story_threads`、
`characters`、`knowledge`、`time`、`global_flags`。

## 底层实现
- 入口：`jag/skills/world_generation.py::WorldGenerationSkill`
- 核心：`jag/world/world_builder.py::WorldBuilder.build_from_tags` / `build_with_llm`
- 词条池常量：`TAG_CATEGORIES / _GENRE / _TERRAIN_LOCS / _MAGIC_LOCS`
- 持久化：`jag/agents/game_master.py::GameMaster.save_game`

## 相关文件
- [world_generation.py](file:///workspace/jag/skills/world_generation.py)
- [world_builder.py](file:///workspace/jag/world/world_builder.py)
- [game_master.py](file:///workspace/jag/agents/game_master.py)
