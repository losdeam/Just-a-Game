# LLM API 文档

本文档描述了 Just-a-Game 的 LLM 抽象层，提供统一的接口支持多种 LLM 提供商。

## 概述

LLM 抽象层位于 `jag/agents/llm.py`，提供以下核心组件：

- **LLMProvider**: 协议定义，规范 LLM 提供商的行为
- **LiteLLMProvider**: 基于 litellm 的多提供商实现
- **MockLLMProvider**: 用于测试的模拟实现
- **LLMFactory**: 工厂类，根据配置创建 LLM 实例

---

## LLMProvider 协议

`LLMProvider` 是一个 Protocol 类，定义了所有 LLM 提供商必须实现的接口。

### 方法定义

#### `complete()` - 通用文本补全

```python
async def complete(self, prompt: str, system: str = "", **kwargs: Any) -> str:
    """Generate a text completion."""
```

**参数：**
- `prompt` (str): 用户输入的提示文本
- `system` (str, 可选): 系统提示，用于设定 AI 的角色和行为
- `**kwargs`: 额外的提供商特定参数

**返回：**
- `str`: 生成的文本补全结果

**用途：**
用于常规的文本生成、对话补全等场景。

---

#### `structured()` - 结构化输出

```python
async def structured(
    self,
    prompt: str,
    response_model: type[T],
    system: str = "",
    **kwargs: Any
) -> T:
    """Generate a structured (JSON schema) completion."""
```

**参数：**
- `prompt` (str): 用户输入的提示文本
- `response_model` (type[T]): Pydantic 模型类型，定义响应结构
- `system` (str, 可选): 系统提示
- `**kwargs`: 额外的提供商特定参数

**返回：**
- `T`: 指定的 Pydantic 模型实例

**用途：**
用于需要结构化输出的场景，如解析数据、生成特定格式的响应等。基于 `instructor` 库实现。

---

## LiteLLMProvider 实现

`LiteLLMProvider` 是基于 [litellm](https://github.com/BerriAI/litellm) 的实现，支持 OpenAI、DeepSeek、Claude 等多种 LLM 提供商。

### 构造函数

```python
def __init__(
    self,
    model: str = "gpt-4",
    provider: str = "",
    api_key: str = "",
    api_base: str | None = None,
    disable_thinking: bool = False,
    **kwargs: Any
) -> None:
```

**参数：**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model` | str | "gpt-4" | 模型名称 |
| `provider` | str | "" | 上游提供商名称（如 "openai", "deepseek"） |
| `api_key` | str | "" | API 密钥 |
| `api_base` | str \| None | None | 自定义 API 端点 |
| `disable_thinking` | bool | False | 是否禁用模型的 thinking 模式（部分模型支持） |
| `**kwargs` | Any | - | 额外的 litellm 参数 |

**说明：**
- 如果指定了 `provider` 且 `model` 不包含 `/`，则自动拼接为 `{provider}/{model}` 格式
- 支持透传任何 litellm 支持的参数

### 使用示例

```python
from jag.agents.llm import LiteLLMProvider

# 创建 OpenAI 提供商
provider = LiteLLMProvider(
    model="gpt-4-turbo",
    provider="openai",
    api_key="sk-xxx"
)

# 创建 DeepSeek 提供商
provider = LiteLLMProvider(
    model="deepseek-chat",
    provider="deepseek",
    api_key="sk-xxx",
    api_base="https://api.deepseek.com/v1"
)

# 文本补全
response = await provider.complete(
    prompt="你好，请介绍一下自己",
    system="你是一个友好的助手"
)

# 结构化输出
from pydantic import BaseModel

class UserInfo(BaseModel):
    name: str
    age: int
    hobby: list[str]

user = await provider.structured(
    prompt="生成一个用户信息",
    response_model=UserInfo
)
print(user.name, user.age, user.hobby)
```

### 特性说明

1. **自动消息构建**：自动将 `system` 和 `prompt` 组装为消息列表
2. **thinking 模式控制**：部分模型（如 DeepSeek）支持 thinking 模式，可通过 `disable_thinking=True` 禁用
3. **结构化输出**：通过 `instructor` 库实现强类型的结构化输出

---

## MockLLMProvider 实现

`MockLLMProvider` 是一个模拟实现，主要用于测试场景。

### 构造函数

```python
def __init__(self, responses: list[str] | None = None) -> None:
```

**参数：**
- `responses` (list[str] \| None): 预设的响应列表，按调用顺序返回

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `calls` | list[dict[str, Any]] | 记录所有调用的参数列表 |
| `_call_count` | int | 调用计数器 |

### 使用示例

```python
from jag.agents.llm import MockLLMProvider

# 创建带预设响应的 Mock
mock = MockLLMProvider(responses=["响应1", "响应2"])

# 调用 complete
result = await mock.complete("测试问题")
print(result)  # "响应1"

# 调用 structured
from pydantic import BaseModel

class Answer(BaseModel):
    text: str

answer = await mock.structured("测试", response_model=Answer)
print(answer)  # Answer()

# 查看调用记录
print(mock.calls)  # [{'prompt': '测试问题', 'system': ''}, {'prompt': '测试', 'system': '', 'model': Answer}]
```

### 行为说明

1. **complete()**:
   - 如果设置了 `responses`，按顺序返回预设响应
   - 当调用次数超过响应列表长度时，返回最后一个响应
   - 如果未设置 `responses`，返回 `"Mock response"`

2. **structured()**:
   - 返回指定模型的默认实例（调用无参构造函数）
   - 记录调用参数到 `calls` 列表

3. **调用跟踪**:
   - 所有调用都会记录到 `calls` 列表
   - 便于测试验证调用参数是否正确

---

## LLMFactory 使用说明

`LLMFactory` 是一个工厂类，根据配置创建和管理 LLM Provider 实例，支持按模块配置不同的 LLM 实例。

### LLMConfig 配置类

```python
@dataclass
class LLMConfig:
    provider: str = "litellm"        # 内部提供商: "litellm" 或 "mock"
    upstream_provider: str = ""       # 上游提供商: "openai", "deepseek" 等
    model: str = "gpt-4"              # 模型名称
    api_key: str = ""                 # API 密钥
    api_base: str | None = None       # 自定义 API 端点
    temperature: float = 0.7          # 温度参数
    max_tokens: int = 2048            # 最大 token 数
    disable_thinking: bool = False    # 禁用 thinking 模式
    extra: dict[str, Any] = field(default_factory=dict)  # 额外参数
```

### 工厂方法

```python
def __init__(
    self,
    default_config: LLMConfig | None = None,
    module_configs: dict[str, LLMConfig] | None = None
) -> None:
```

**参数：**
- `default_config`: 默认配置
- `module_configs`: 按模块名称映射的配置字典

```python
def get(self, module_name: str = "default") -> LLMProvider:
    """Get or create an LLM provider for a module."""
```

**参数：**
- `module_name` (str): 模块名称，默认为 "default"

**返回：**
- `LLMProvider`: 对应的 LLM 实例（带缓存）

### 使用示例

```python
from jag.agents.llm import LLMFactory, LLMConfig

# 创建工厂
factory = LLMFactory(
    default_config=LLMConfig(
        model="gpt-4",
        api_key="sk-xxx"
    ),
    module_configs={
        "planner": LLMConfig(
            upstream_provider="deepseek",
            model="deepseek-reasoner",
            api_key="sk-yyy",
            disable_thinking=False
        ),
        "executor": LLMConfig(
            upstream_provider="openai",
            model="gpt-4-turbo",
            api_key="sk-xxx",
            temperature=0.3
        ),
        "test": LLMConfig(
            provider="mock",
            responses=["测试响应"]
        )
    }
)

# 获取默认 Provider
default_llm = factory.get()

# 获取特定模块的 Provider
planner_llm = factory.get("planner")
executor_llm = factory.get("executor")
test_llm = factory.get("test")

# 相同模块名称返回同一实例（缓存）
assert factory.get("planner") is planner_llm
```

### 设计说明

1. **缓存机制**：相同模块名称返回同一实例，避免重复创建
2. **配置继承**：未配置的模块使用 `default_config`
3. **提供商选择**：
   - `provider == "mock"` → 创建 `MockLLMProvider`
   - 否则 → 创建 `LiteLLMProvider`

---

## 配置示例

### 环境变量配置

推荐使用环境变量管理敏感信息：

```bash
# .env 文件

# OpenAI 配置
OPENAI_API_KEY=sk-xxx
OPENAI_API_BASE=https://api.openai.com/v1

# DeepSeek 配置
DEEPSEEK_API_KEY=sk-yyy
DEEPSEEK_API_BASE=https://api.deepseek.com/v1

# 默认 LLM 配置
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4
```

### YAML 配置文件

创建 `config/llm.yaml`：

```yaml
# 默认 LLM 配置
default:
  provider: litellm
  upstream_provider: openai
  model: gpt-4-turbo
  temperature: 0.7
  max_tokens: 4096

# 模块特定配置
modules:
  # 规划器使用 DeepSeek Reasoner
  planner:
    upstream_provider: deepseek
    model: deepseek-reasoner
    disable_thinking: false

  # 执行器使用 GPT-4 Turbo（低温度）
  executor:
    upstream_provider: openai
    model: gpt-4-turbo
    temperature: 0.3
    max_tokens: 2048

  # 分析器使用 Claude
  analyzer:
    upstream_provider: anthropic
    model: claude-3-5-sonnet-20241022

  # 测试环境使用 Mock
  test:
    provider: mock
    responses:
      - "模拟响应1"
      - "模拟响应2"
```

### 加载配置

```python
import os
import yaml
from jag.agents.llm import LLMFactory, LLMConfig

def load_llm_factory(config_path: str = "config/llm.yaml") -> LLMFactory:
    """从 YAML 配置文件加载 LLMFactory"""
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 加载环境变量中的 API Key
    openai_key = os.getenv("OPENAI_API_KEY", "")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")

    # 解析默认配置
    default_dict = config.get("default", {})
    default_config = LLMConfig(
        provider=default_dict.get("provider", "litellm"),
        upstream_provider=default_dict.get("upstream_provider", ""),
        model=default_dict.get("model", "gpt-4"),
        api_key=openai_key,
        api_base=default_dict.get("api_base"),
        temperature=default_dict.get("temperature", 0.7),
        max_tokens=default_dict.get("max_tokens", 2048),
        disable_thinking=default_dict.get("disable_thinking", False),
        extra=default_dict.get("extra", {})
    )

    # 解析模块配置
    module_configs = {}
    for name, cfg in config.get("modules", {}).items():
        # 根据 upstream_provider 选择 API Key
        api_key = openai_key
        if cfg.get("upstream_provider") == "deepseek":
            api_key = deepseek_key

        module_configs[name] = LLMConfig(
            provider=cfg.get("provider", "litellm"),
            upstream_provider=cfg.get("upstream_provider", ""),
            model=cfg.get("model", "gpt-4"),
            api_key=api_key,
            api_base=cfg.get("api_base"),
            temperature=cfg.get("temperature", 0.7),
            max_tokens=cfg.get("max_tokens", 2048),
            disable_thinking=cfg.get("disable_thinking", False),
            extra=cfg.get("extra", {})
        )

    return LLMFactory(default_config, module_configs)

# 使用
factory = load_llm_factory()
llm = factory.get("planner")
```

---

## 最佳实践

### 1. 使用工厂模式

推荐通过 `LLMFactory` 统一管理 LLM 实例，而不是直接创建 `LiteLLMProvider`。

```python
# 推荐
factory = LLMFactory(default_config=config)
llm = factory.get("module_name")

# 不推荐
llm = LiteLLMProvider(model="gpt-4", api_key="xxx")
```

### 2. 环境隔离

为不同环境提供不同配置：

```python
import os

env = os.getenv("ENV", "development")

if env == "test":
    # 测试环境使用 Mock
    factory = LLMFactory(
        default_config=LLMConfig(provider="mock")
    )
else:
    # 生产环境使用真实 LLM
    factory = load_llm_factory()
```

### 3. 结构化输出优先

需要解析 LLM 输出时，优先使用 `structured()` 方法：

```python
from pydantic import BaseModel, Field

class ActionPlan(BaseModel):
    action: str = Field(description="要执行的动作")
    target: str = Field(description="目标对象")
    priority: int = Field(description="优先级 1-10")

plan = await llm.structured(
    prompt="为玩家制定一个行动计划",
    response_model=ActionPlan,
    system="你是一个游戏 AI 规划器"
)
```

### 4. 模块化配置

为不同功能的模块配置独立的 LLM：

- **规划器**：使用推理能力强的模型（如 DeepSeek Reasoner）
- **执行器**：使用速度快的模型（如 GPT-4 Turbo）
- **对话**：使用成本低的模型（如 GPT-3.5）

---

## 相关依赖

- **litellm**: 多提供商 LLM 统一接口
- **instructor**: 结构化输出支持
- **pydantic**: 数据验证和模型定义

安装依赖：

```bash
pip install litellm instructor pydantic
```