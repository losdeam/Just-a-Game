---
name: location-generation
description: 根据地形、魔法等级、氛围等词条生成地点，构建连通图并接入当前世界。复用 WorldBuilder 的预制地点池。当用户要求生成地点、新增区域地点、扩展世界地图时使用。
category: generation
---

# 地点生成 Skill

## 用途
根据地形/魔法/氛围等词条生成地点，构建连通图并接入当前世界状态。

## 何时使用
- 用户要求"生成地点""新增区域地点""扩展世界地图"
- 世界某区域需要补充地点
- 根据特定地形词条生成对应地点

## 调用方式

```python
result = await registry.execute(
    "location_generation",
    SkillContext(gm=gm, params={
        "terrain": ["forest", "mountains"],
        "magic": "medium",          # none/low/medium/high
        "region_id": "main_region",
        "atmosphere": ["mysterious"],
        "era": "medieval",
    }),
)
```

## 参数说明
| 参数 | 类型 | 说明 |
|------|------|------|
| `terrain` | list[str] | 地形词条（city/forest/mountains/swamp/desert/coast/underground/plains） |
| `magic` | str | 魔法等级（none/low/medium/high），决定附加魔法地点 |
| `region_id` | str | 归属区域 id，默认 `main_region` |
| `atmosphere` | list[str] | 氛围词条（影响光照/危险修正） |
| `era` | str | 时代（影响光照修正） |
| `danger_base` | int | 危险基础值（可选） |

## 输出结构
```
result.data = {
    "locations": [{"id","name","description","type","light","danger","connected"}],
    "count": int,
}
```

## 生成逻辑
- 每种地形提供 3 个预制地点（含 id/name/desc/type/light/danger）
- 魔法等级附加 0-2 个魔法地点
- 光照 = 基础 + 时代修正 + 氛围修正（钳制 1-10）
- 危险 = 基础 + danger_base + 氛围修正（钳制 0-10）
- 连通图：链式连接（每个地点连前一个）

## 底层实现
- 入口：`jag/skills/location_generation.py::LocationGenerationSkill`
- 数据池：`jag/world/world_builder.py::_TERRAIN_LOCS / _MAGIC_LOCS / _ATMO_MOD / _ERA_INFO`
- 注册：`gm.world.add_location`

## 相关文件
- [location_generation.py](file:///workspace/jag/skills/location_generation.py)
- [world_builder.py](file:///workspace/jag/world/world_builder.py)
- [world.py](file:///workspace/jag/world/world.py)
