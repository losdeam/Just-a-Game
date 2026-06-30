# 测试指南

本文档介绍 Just-a-Game (JAG) 项目的测试方法、策略和工具使用。

## 1. 测试运行方法

### pytest 命令

项目使用 pytest 作为测试框架。运行测试的基本命令：

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_integration.py

# 运行特定测试类
pytest tests/test_integration.py::TestGameLoop

# 运行特定测试方法
pytest tests/test_integration.py::TestGameLoop::test_basic_action

# 显示详细输出
pytest -v

# 显示测试函数名称和结果
pytest -v --tb=short

# 运行并打印 print 输出
pytest -s
```

### 测试文件位置

所有测试文件位于 `tests/` 目录下：

```
tests/
├── __init__.py
└── test_integration.py
```

### pytest.ini_options 配置

项目在 `pyproject.toml` 中配置了 pytest 选项：

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

配置说明：
- `asyncio_mode = "auto"`: 自动检测异步测试函数，无需手动标记 `@pytest.mark.asyncio`
- `testpaths = ["tests"]`: 指定测试文件搜索路径

## 2. 测试策略说明

### 2.1 单元测试

单元测试专注于测试单个组件的功能正确性。

#### Dice 概率分布统计测试

骰子系统是游戏的核心随机性来源，需要进行统计测试：

```python
from jag.core.dice import DiceRoller, RollResult

def test_dice_distribution():
    """测试骰子概率分布符合统计预期"""
    roller = DiceRoller(seed=42)  # 固定种子确保可重复

    # 统计测试：大量样本
    results = []
    for _ in range(1000):
        result = roller.roll(sides=20, dc=10)
        results.append(result.result)

    # 验证成功率大致符合预期（约 55% 成功，考虑自然 1/20）
    success_rate = sum(1 for r in results if r.is_success) / len(results)
    assert 0.50 < success_rate < 0.60

def test_critical_rolls():
    """测试暴击和暴击失败"""
    roller = DiceRoller(seed=42)

    # 测试多个骰子确保覆盖各种情况
    critical_successes = 0
    critical_failures = 0

    for _ in range(1000):
        result = roller.roll(sides=20)
        if result.result == RollResult.CRITICAL_SUCCESS:
            critical_successes += 1
        elif result.result == RollResult.CRITICAL_FAILURE:
            critical_failures += 1

    # 自然 20 和自然 1 各约 5% 概率
    assert 0.03 < critical_successes / 1000 < 0.07
    assert 0.03 < critical_failures / 1000 < 0.07

def test_advantage_disadvantage():
    """测试优势和劣势机制"""
    roller = DiceRoller(seed=42)

    # 优势应该提高平均值
    normal_rolls = [roller.roll(sides=20).base_roll for _ in range(100)]
    advantage_rolls = [roller.roll(sides=20, advantage=True).base_roll for _ in range(100)]
    disadvantage_rolls = [roller.roll(sides=20, disadvantage=True).base_roll for _ in range(100)]

    avg_normal = sum(normal_rolls) / len(normal_rolls)
    avg_advantage = sum(advantage_rolls) / len(advantage_rolls)
    avg_disadvantage = sum(disadvantage_rolls) / len(disadvantage_rolls)

    assert avg_advantage > avg_normal
    assert avg_disadvantage < avg_normal
```

#### 规则匹配测试

规则引擎需要测试条件匹配和效果应用：

```python
from jag.core.rules import RuleEngine, Rule, RuleCondition, RuleEffect, RuleContext

def test_rule_condition_matching():
    """测试规则条件匹配"""
    engine = RuleEngine()

    rule = Rule(
        name="health_check",
        conditions=[
            RuleCondition(attribute="actor.health", operator="lt", value=50)
        ],
        effects=[
            RuleEffect(action="set_state", target="actor.status", value="wounded")
        ]
    )

    engine.add_rule(rule)

    # 测试条件匹配
    context = RuleContext(actor={"health": 30, "status": "normal"})
    changes = engine.evaluate(context)

    assert len(changes) > 0
    assert any("wounded" in str(c) for c in changes)

def test_rule_priority():
    """测试规则优先级"""
    engine = RuleEngine()

    # 高优先级规则
    high_priority_rule = Rule(
        name="high_priority",
        priority=10,
        conditions=[],
        effects=[RuleEffect(action="set_state", target="actor.modifier", value=10)]
    )

    # 低优先级规则
    low_priority_rule = Rule(
        name="low_priority",
        priority=1,
        conditions=[],
        effects=[RuleEffect(action="set_state", target="actor.modifier", value=5)]
    )

    engine.add_rule(low_priority_rule)
    engine.add_rule(high_priority_rule)

    # 规则应该按优先级排序
    assert engine._rules[0].name == "high_priority"
    assert engine._rules[1].name == "low_priority"
```

#### CRUD 测试

持久化层的增删改查测试：

```python
from jag.persistence.database import Database
from jag.persistence.models import Character, Item

def test_character_crud():
    """测试角色 CRUD 操作"""
    db = Database(":memory:")

    # Create
    character = Character(
        id="test_hero",
        name="Test Hero",
        type="player",
        location_id="tavern"
    )
    db.save_character(character)

    # Read
    loaded = db.get_character("test_hero")
    assert loaded is not None
    assert loaded.name == "Test Hero"

    # Update
    character.name = "Updated Hero"
    db.save_character(character)
    updated = db.get_character("test_hero")
    assert updated.name == "Updated Hero"

    # Delete
    db.delete_character("test_hero")
    deleted = db.get_character("test_hero")
    assert deleted is None
```

### 2.2 集成测试

集成测试验证多个组件协同工作的正确性。

#### 知识图谱推理测试

```python
from jag.knowledge.graph import KnowledgeGraph

def test_knowledge_graph_inference():
    """测试知识图谱推理能力"""
    graph = KnowledgeGraph()

    # 添加知识节点
    graph.add_fact("hero", "location", "tavern")
    graph.add_fact("tavern", "contains", "innkeeper")
    graph.add_fact("innkeeper", "sells", "ale")

    # 测试推理查询
    nearby_entities = graph.query_path("hero", max_depth=2)
    assert "innkeeper" in nearby_entities

    # 测试关系查询
    relations = graph.get_relations("innkeeper")
    assert any(r.target == "ale" for r in relations)
```

#### 记忆存取测试

```python
from jag.knowledge.memory import MemorySystem

def test_memory_storage_and_retrieval():
    """测试记忆系统存储和检索"""
    memory = MemorySystem()

    # 存储记忆
    memory.add_memory(
        "hero",
        "Met the innkeeper at the tavern",
        importance=0.7,
        turn=1
    )

    # 检索相关记忆
    relevant = memory.get_relevant_memories("hero", "innkeeper", limit=5)
    assert len(relevant) > 0
    assert "innkeeper" in relevant[0].content

    # 测试记忆衰减
    memory.add_memory("hero", "Old memory", importance=0.5, turn=1)
    memory.add_memory("hero", "Recent memory", importance=0.5, turn=10)

    # 最近记忆应优先
    memories = memory.get_memories("hero", limit=10)
    recent_index = next(i for i, m in enumerate(memories) if "Recent" in m.content)
    old_index = next(i for i, m in enumerate(memories) if "Old" in m.content)
    assert recent_index < old_index
```

#### NPC 行为测试

```python
from jag.world.npc import NPC
from jag.agents.npc_agent import NPCAgent

async def test_npc_behavior():
    """测试 NPC 行为决策"""
    npc = NPC(
        id="merchant",
        name="Merchant",
        location_id="market",
        personality="friendly"
    )

    agent = NPCAgent(npc=npc, llm_provider=mock_provider)

    # 测试日常行为
    action = await agent.decide_action(context={"time": "morning"})
    assert action is not None

    # 测试对玩家反应
    reaction = await agent.react_to_player(
        player_action="greet",
        context={"player_reputation": "friendly"}
    )
    assert reaction is not None
```

#### 世界 Tick 完整性测试

```python
from jag.world.tick import TickEngine
from jag.world.world import World

async def test_world_tick_integrity():
    """测试世界时间推进的完整性"""
    world = World()
    tick_engine = TickEngine(world)

    # 初始化世界状态
    initial_turn = world.time.turn

    # 执行多次 tick
    for _ in range(10):
        await tick_engine.tick()

    # 验证时间正确推进
    assert world.time.turn == initial_turn + 10

    # 验证所有 NPC 都被执行
    for npc_id, npc in world.npcs.items():
        assert npc.last_active_turn == world.time.turn

    # 验证经济系统更新
    assert world.economy.last_update_turn == world.time.turn
```

### 2.3 E2E 测试

端到端测试验证完整的游戏循环。

#### CLI 完整游戏循环

```python
from click.testing import CliRunner
from jag.cli import main

def test_cli_game_loop():
    """测试 CLI 完整游戏循环"""
    runner = CliRunner()

    # 启动新游戏
    result = runner.invoke(main, ['new', '--name', 'TestHero'])
    assert result.exit_code == 0
    assert "Welcome" in result.output or "Game started" in result.output

    # 执行一系列动作
    actions = [
        'action "look around"',
        'action "go to tavern"',
        'action "talk to innkeeper"',
        'status',
    ]

    for action in actions:
        result = runner.invoke(main, action.split())
        assert result.exit_code == 0

    # 保存游戏
    result = runner.invoke(main, ['save', 'test_save.json'])
    assert result.exit_code == 0

    # 加载游戏
    result = runner.invoke(main, ['load', 'test_save.json'])
    assert result.exit_code == 0
```

### 2.4 验收测试

验收测试验证完整的游戏体验。

#### 20 回合完整体验

项目中已实现 20 回合集成测试，位于 `tests/test_integration.py`：

```python
@pytest.mark.asyncio
async def test_20_turn_integration(self, game_master: GameMaster):
    """Integration test: run 20+ turns and verify consistency."""
    actions = [
        "explore the village square",
        "talk to the villagers",
        "go to the tavern",
        "order a drink",
        "listen to stories",
        "go to the blacksmith",
        "examine the weapons",
        "go to the market",
        "buy some supplies",
        "head to the village gate",
        "look into the forest",
        "venture into the forest",
        "search for tracks",
        "find the hidden camp",
        "investigate the camp",
        "head to the ruins",
        "examine the ancient runes",
        "return to the forest path",
        "go back to the village",
        "rest at the tavern",
    ]

    errors = []
    for i, action in enumerate(actions):
        try:
            result = await game_master.process_action(action)
            assert isinstance(result, str), f"Turn {i+1}: narrative is not a string"
        except Exception as e:
            errors.append(f"Turn {i+1} ({action}): {e}")

    assert not errors, f"Errors during integration: {errors}"

    status = game_master.get_status()
    assert status["turn"] >= 20, f"Expected 20+ turns, got {status['turn']}"

    # Verify world state consistency
    assert len(game_master.world.characters) > 0
    assert len(game_master.world.locations) >= 6
    assert game_master.world.time.turn >= 20
```

验收测试验证：
- 20+ 回合无异常执行
- 每回合返回有效的叙事文本
- 世界状态一致性（角色、地点、时间）
- 玩家位置和历史正确记录

## 3. MockLLMProvider 使用说明

`MockLLMProvider` 是用于测试的模拟 LLM 提供者，无需真实 API 调用即可测试 LLM 集成逻辑。

### 3.1 基本使用

```python
from jag.agents.llm import MockLLMProvider

# 创建 Mock 提供者
mock_provider = MockLLMProvider()

# 使用 mock 提供者进行测试
async def test_with_mock():
    response = await mock_provider.complete("What is the weather?")
    assert response == "Mock response"  # 默认响应
```

### 3.2 设置预设响应

可以通过构造函数传入预设响应列表：

```python
from jag.agents.llm import MockLLMProvider

# 设置预设响应
mock_provider = MockLLMProvider(responses=[
    "The weather is sunny today.",
    "I recommend visiting the tavern.",
    "The innkeeper greets you warmly."
])

# 按顺序返回预设响应
async def test_sequential_responses():
    response1 = await mock_provider.complete("Ask about weather")
    assert response1 == "The weather is sunny today."

    response2 = await mock_provider.complete("Ask for recommendations")
    assert response2 == "I recommend visiting the tavern."

    response3 = await mock_provider.complete("Enter tavern")
    assert response3 == "The innkeeper greets you warmly."
```

### 3.3 验证调用记录

`MockLLMProvider` 自动记录所有调用，可用于验证 LLM 交互：

```python
from jag.agents.llm import MockLLMProvider

async def test_call_verification():
    mock_provider = MockLLMProvider(responses=["Test response"])

    # 执行调用
    await mock_provider.complete(
        prompt="What should I do?",
        system="You are a helpful game master."
    )

    # 验证调用记录
    assert len(mock_provider.calls) == 1
    assert mock_provider.calls[0]["prompt"] == "What should I do?"
    assert mock_provider.calls[0]["system"] == "You are a helpful game master."

    # 验证调用计数
    assert mock_provider._call_count == 1
```

### 3.4 在测试中使用

结合 pytest fixture 使用：

```python
import pytest
from jag.agents.llm import MockLLMProvider
from jag.agents.game_master import GameMaster

@pytest.fixture
def mock_llm():
    """创建预配置的 Mock LLM 提供者"""
    return MockLLMProvider(responses=[
        "You see a bustling marketplace.",
        "The merchant offers you a deal.",
        "Your quest begins now."
    ])

@pytest.fixture
def game_master_with_mock(mock_llm):
    """创建使用 Mock LLM 的 GameMaster"""
    # 配置 GameMaster 使用 mock LLM
    config = GameConfig(llm=LLMConfig(provider="mock"))
    gm = GameMaster(config=config)
    gm._llm = mock_llm
    return gm

async def test_game_with_mock_llm(game_master_with_mock, mock_llm):
    """测试游戏逻辑并验证 LLM 调用"""
    result = await game_master_with_mock.process_action("look around")

    # 验证响应
    assert result == "You see a bustling marketplace."

    # 验证 LLM 被正确调用
    assert len(mock_llm.calls) >= 1
    assert "look" in mock_llm.calls[0]["prompt"].lower()
```

### 3.5 结构化输出测试

测试结构化输出功能：

```python
from pydantic import BaseModel
from jag.agents.llm import MockLLMProvider

class CharacterInfo(BaseModel):
    name: str
    level: int
    health: int

async def test_structured_output():
    mock_provider = MockLLMProvider()

    # 调用 structured 方法
    result = await mock_provider.structured(
        prompt="Generate character info",
        response_model=CharacterInfo,
        system="You are a character generator."
    )

    # 返回默认实例（所有字段为默认值）
    assert isinstance(result, CharacterInfo)
    # 注意：MockLLMProvider 返回的是默认实例，字段值为 None 或默认值
    # 实际测试中可能需要自定义 Mock 行为
```

### 3.6 高级用法：自定义 Mock 行为

如果需要更复杂的 Mock 行为，可以继承 `MockLLMProvider`：

```python
from jag.agents.llm import MockLLMProvider
from typing import Any

class AdvancedMockLLMProvider(MockLLMProvider):
    """支持响应映射的高级 Mock 提供者"""

    def __init__(self):
        super().__init__()
        self._response_map = {
            "weather": "It's a sunny day.",
            "tavern": "The tavern is crowded.",
            "combat": "You engage in battle!"
        }

    async def complete(self, prompt: str, system: str = "", **kwargs: Any) -> str:
        # 记录调用
        self.calls.append({"prompt": prompt, "system": system, **kwargs})
        self._call_count += 1

        # 根据提示词关键词返回不同响应
        for keyword, response in self._response_map.items():
            if keyword in prompt.lower():
                return response

        return "Default mock response"
```

## 4. 测试最佳实践

### 4.1 异步测试

项目使用 `pytest-asyncio`，异步测试无需额外标记：

```python
# pytest.ini_options 中配置了 asyncio_mode = "auto"
# 因此无需 @pytest.mark.asyncio 装饰器

async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

### 4.2 测试隔离

每个测试应该独立运行，不依赖其他测试的状态：

```python
@pytest.fixture
def fresh_game_master():
    """每次测试都创建新的 GameMaster 实例"""
    config = GameConfig(
        world_name="Test World",
        llm=LLMConfig(default=LLMModuleConfig(provider="mock", model="mock"))
    )
    return GameMaster(config=config)
```

### 4.3 临时文件

使用 pytest 的 `tmp_path` fixture 处理临时文件：

```python
async def test_save_load(game_master: GameMaster, tmp_path):
    """测试保存和加载游戏"""
    save_path = str(tmp_path / "test_save.json")

    # 执行一些操作
    await game_master.process_action("look around")

    # 保存
    game_master.save_game(save_path)

    # 加载
    success = game_master.load_game(save_path)
    assert success
```

### 4.4 测试命名约定

- 测试文件：`test_*.py` 或 `*_test.py`
- 测试类：`Test*`（驼峰命名）
- 测试函数：`test_*`（蛇形命名）
- 描述性测试名：`test_user_can_save_game` 而非 `test_save`

## 5. 持续集成

项目使用以下测试命令进行 CI：

```bash
# 安装依赖
uv sync --extra dev

# 运行所有测试
pytest

# 运行测试并生成覆盖率报告
pytest --cov=jag --cov-report=html

# 运行特定类型的测试
pytest -k "integration"  # 运行集成测试
pytest -k "not slow"     # 跳过慢速测试
```

## 6. 参考资料

- [pytest 官方文档](https://docs.pytest.org/)
- [pytest-asyncio 文档](https://pytest-asyncio.readthedocs.io/)
- 项目配置文件：`pyproject.toml`
- 测试文件：`tests/test_integration.py`
- LLM 提供者实现：`jag/agents/llm.py`