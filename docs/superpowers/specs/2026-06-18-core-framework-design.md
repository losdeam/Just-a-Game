---
comet_change: core-framework
role: technical-design
canonical_spec: openspec
---

# JAG Core Framework — Technical Design Doc

## 1. LLM 抽象层

### 方案：litellm + instructor 双层抽象

- **litellm**：统一 LLM 调用接口，支持 OpenAI / Anthropic / 本地模型（Ollama）等 100+ 模型
- **instructor**：结构化输出层，基于 JSON Schema 强制 LLM 返回结构化数据

```python
# llm.py 核心接口
class LLMProvider(Protocol):
    async def complete(self, prompt: str, system: str = "", **kwargs) -> str: ...
    async def structured(self, prompt: str, response_model: type[T], **kwargs) -> T: ...

class LiteLLMProvider(LLMProvider):
    """基于 litellm + instructor 的实现"""
    
class LLMFactory:
    """按模块配置创建不同 Provider"""
    # 高参与度模块（Action Planner, Story Director, Narrative）→ 大模型
    # 中参与度模块（NPC Agent, Quest Generator）→ 小模型
```

### 风险与对策

| 风险 | 对策 |
|------|------|
| LLM 超时/失败 | 重试 3 次 + fallback 到规则系统返回默认响应 |
| litellm 版本兼容 | 锁定版本，CI 测试 |
| 本地模型兼容 | Ollama 作为本地模型后端，litellm 原生支持 |
| 成本控制 | 按模块配模型等级，NPC 用小模型 |

## 2. 规则引擎 — 混合模式

### 方案：YAML 声明式 + Python 注册式

简单规则用 YAML 声明，复杂规则用 Python 函数注册：

```yaml
# rules.yaml — 声明式规则
- name: fire_spread
  conditions:
    - source.property: flammable
    - source.state: on_fire
    - target.property: flammable
    - target.state_not: on_fire
    - distance(source, target) <= 1
  effects:
    - set_state(target, on_fire)
    - emit_event(fire_spread, source, target)
  probability: 0.8
```

```python
# 注册式规则 — 用于复杂逻辑
@rule("chain_explosion")
async def chain_explosion(context: RuleContext) -> list[Effect]:
    """爆炸连锁：爆炸物引爆周围爆炸物"""
    ...
```

规则引擎执行流程：
1. 收集上下文（世界状态 + 角色状态 + 环境状态）
2. 匹配 YAML 规则（条件检查）
3. 匹配注册的 Python 规则
4. 执行效果（状态变更 + 事件创建）
5. 连锁处理（最大深度 5 层，防止爆炸循环）

## 3. 数据库 — SQLModel (Pydantic + SQLAlchemy)

```python
# models.py
class Character(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    location_id: str = Field(foreign_key="location.id")
    hp: int = 20
    max_hp: int = 20
    attributes: dict  # JSON 字段：STR, DEX, CON, INT, WIS, CHA
    status_effects: list[str] = Field(default_factory=list)
    ...
```

20 张表全部用 SQLModel 定义，自动建表，SQLite 默认。

### Repository Pattern

```python
class Repository(Protocol):
    async def save(self, entity: SQLModel) -> None: ...
    async def find(self, model: type[T], id: str) -> T | None: ...
    async def find_all(self, model: type[T], **filters) -> list[T]: ...
    async def delete(self, entity: SQLModel) -> None: ...
```

## 4. Tick 引擎 — async 顺序 + NPC 并发

```python
class TickEngine:
    async def tick(self, player_action: str) -> TickResult:
        # 1. Action Planner (LLM async)
        plan = await self.action_planner.parse(player_action)
        
        # 2. Rule Engine (sync)
        effects = self.rule_engine.evaluate(plan, self.world)
        
        # 3. Dice (sync)
        results = self.dice.resolve(plan, effects)
        
        # 4. World Update (sync + DB)
        self.world.apply_effects(effects, results)
        
        # 5. NPC Tick (LLM async, 并发)
        sem = asyncio.Semaphore(5)  # 限流
        npc_actions = await asyncio.gather(*[
            self.npc_agent.tick(npc, self.world, sem)
            for npc in self.world.active_npcs
        ])
        
        # 6. World Sim (sync)
        self.faction_sim.tick(self.world)
        self.economy_sim.tick(self.world)
        self.weather_sim.tick(self.world)
        
        # 7. Quest Generator (sync + 规则)
        new_quests = self.quest_gen.check(self.world)
        
        # 8. Story Director (LLM async)
        await self.story_director.evaluate(self.world)
        
        # 9. Memory Update (LLM async for compression)
        await self.memory.update(self.world)
        
        # 10. Knowledge Graph Update (sync)
        self.knowledge.update(effects, npc_actions)
        
        # 11. Persist (sync)
        await self.persistence.flush()
        
        # 12. Narrative (LLM async)
        narrative = await self.narrative.generate(
            self.world, plan, results, effects, npc_actions
        )
        
        return TickResult(narrative=narrative, world_state=self.world.snapshot())
```

## 5. 知识图谱 — NetworkX 属性图

```python
class KnowledgeGraph:
    def __init__(self):
        self.g = nx.DiGraph()
    
    def add_entity(self, entity_id: str, **attrs): ...
    def add_relation(self, src: str, tgt: str, rel_type: str, **attrs): ...
    def query(self, entity_id: str, rel_type: str | None = None) -> list[Relation]: ...
    def infer(self, event: GameEvent) -> list[Inference]:
        """基于事件推理关系变化"""
        # 例：GoblinKing dies → 所有 hates GoblinKing 的实体 +happy
        ...
```

推理触发时机：每次 tick 结束后，将本轮事件批量送入知识图谱推理。

## 6. 记忆系统

```
短期记忆（滑动窗口）          长期记忆（压缩存储）
═══════════════════         ═══════════════════
最近 20 事件                 玩家声望
当前会话上下文               势力关系
NPC 近期交互                 历史事件摘要

                    │
                    ▼ 定期压缩（LLM）
              100 事件 → 3 条长期记忆
```

- 短期记忆：内存中维护，每 tick 追加，超过窗口大小自动淘汰
- 长期记忆：SQLite 持久化，LLM 压缩摘要
- NPC 记忆：每个 NPC 独立的短期+长期记忆

## 7. 测试策略

| Phase | 测试类型 | 方法 |
|-------|---------|------|
| 1-2 | 单元测试 | Dice 概率分布统计测试、规则匹配测试、CRUD 测试 |
| 3 | 单元+集成 | 知识图谱推理测试、记忆存取测试 |
| 4 | 单元测试 | LLM Mock Provider、接口协议测试 |
| 5-6 | 集成测试 | NPC 行为测试、世界 Tick 完整性测试 |
| 7 | E2E 测试 | CLI 完整游戏循环 |
| 8 | 验收测试 | 20 回合完整体验 |

LLM 测试使用 MockLLMProvider，返回预定义响应，避免依赖真实 API。

## 8. 依赖清单

```
litellm          # LLM 统一调用
instructor       # 结构化 LLM 输出
sqlmodel         # ORM
click            # CLI
rich             # 终端 UI
pyyaml           # YAML 配置
networkx         # 知识图谱
pydantic>=2.0    # 数据模型
pytest           # 测试
pytest-asyncio   # 异步测试
```

## 9. 实现顺序

自底向上构建，每层可独立测试：

1. **Persistence** → models + repository + sqlite (Phase 1)
2. **Core Systems** → dice, events, rules, items, perception (Phase 2)
3. **Knowledge & Memory** → graph, memory, compression (Phase 3)
4. **LLM Layer** → provider, factory (Phase 4)
5. **World Simulation** → world, npc, tick, faction, economy, weather, quest (Phase 5)
6. **Agent Layer** → action_planner, npc_agent, story_director, narrative (Phase 6)
7. **GameMaster + CLI** → game_master, cli, startup (Phase 7)
8. **Demo World** → yaml data + loader + integration test (Phase 8)
