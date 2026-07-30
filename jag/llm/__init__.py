"""LLM abstraction layer: provider protocol, implementations, and factory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers."""

    async def complete(self, prompt: str, system: str = "", **kwargs: Any) -> str: ...

    async def structured(
        self, prompt: str, response_model: type[T], system: str = "", **kwargs: Any
    ) -> T: ...


class LiteLLMProvider:
    """LLM provider using litellm for multi-provider support."""

    def __init__(
        self,
        model: str = "gpt-4",
        provider: str = "",
        api_key: str = "",
        api_base: str | None = None,
        disable_thinking: bool = False,
        **kwargs: Any,
    ) -> None:
        self.provider = provider
        self.api_key = api_key
        self.api_base = api_base
        self.disable_thinking = disable_thinking
        self._extra = kwargs
        self.model = f"{provider}/{model}" if provider and "/" not in model else model

    async def complete(self, prompt: str, system: str = "", **kwargs: Any) -> str:
        import litellm

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            **self._extra,
            **kwargs,
        }
        if self.api_key:
            params["api_key"] = self.api_key
        if self.api_base:
            params["api_base"] = self.api_base
        if self.disable_thinking:
            params.setdefault("extra_body", {})["thinking"] = {"type": "disabled"}

        response = await litellm.acompletion(**params)
        return response.choices[0].message.content or ""

    async def structured(
        self, prompt: str, response_model: type[T], system: str = "", **kwargs: Any
    ) -> T:
        import instructor
        import litellm

        client = instructor.from_litellm(litellm.acompletion)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "response_model": response_model,
            **self._extra,
            **kwargs,
        }
        if self.api_key:
            params["api_key"] = self.api_key
        if self.api_base:
            params["api_base"] = self.api_base
        if self.disable_thinking:
            params.setdefault("extra_body", {})["thinking"] = {"type": "disabled"}

        return await client.create(**params)


class MockLLMProvider:
    """Mock LLM provider for testing/offline use. Returns default model instances."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or [])
        self._call_count = 0
        self.calls: list[dict[str, Any]] = []

    async def complete(self, prompt: str, system: str = "", **kwargs: Any) -> str:
        self.calls.append({"prompt": prompt, "system": system, **kwargs})
        if self._responses:
            response = self._responses[min(self._call_count, len(self._responses) - 1)]
        else:
            response = "Mock response"
        self._call_count += 1
        return response

    async def structured(
        self, prompt: str, response_model: type[T], system: str = "", **kwargs: Any
    ) -> T:
        self.calls.append({"prompt": prompt, "system": system, "model": response_model, **kwargs})
        self._call_count += 1
        return response_model()


@dataclass
class LLMConfig:
    """Configuration for a single LLM instance (internal)."""

    provider: str = "litellm"  # internal: "litellm" or "mock"
    upstream_provider: str = ""  # upstream: "openai", "deepseek", etc.
    model: str = "gpt-4"
    api_key: str = ""
    api_base: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048
    disable_thinking: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class LLMFactory:
    """Factory for creating LLM providers based on config."""

    def __init__(
        self,
        default_config: LLMConfig | None = None,
        module_configs: dict[str, LLMConfig] | None = None,
    ) -> None:
        self._default = default_config or LLMConfig()
        self._modules = module_configs or {}
        self._cache: dict[str, LLMProvider] = {}

    def get(self, module_name: str = "default") -> LLMProvider:
        if module_name in self._cache:
            return self._cache[module_name]
        config = self._modules.get(module_name, self._default)
        provider = self._create_provider(config)
        self._cache[module_name] = provider
        return provider

    def clear_cache(self) -> None:
        self._cache.clear()

    def _create_provider(self, config: LLMConfig) -> LLMProvider:
        if config.provider == "mock":
            return MockLLMProvider()
        return LiteLLMProvider(
            model=config.model,
            provider=config.upstream_provider,
            api_key=config.api_key,
            api_base=config.api_base,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            disable_thinking=config.disable_thinking,
            **config.extra,
        )


def llm_config_from_pydantic(module_cfg) -> LLMConfig:
    """Bridge a config.LLMModuleConfig (pydantic) to the internal LLMConfig (dataclass).

    `module_cfg.provider == "mock"` stays mock; anything else is routed through litellm
    with the original provider preserved as `upstream_provider`.
    """
    if module_cfg.provider == "mock":
        return LLMConfig(provider="mock", model=module_cfg.model)
    return LLMConfig(
        provider="litellm",
        upstream_provider=module_cfg.provider,
        model=module_cfg.model,
        api_key=module_cfg.api_key,
        api_base=module_cfg.api_base,
        temperature=module_cfg.temperature,
        max_tokens=module_cfg.max_tokens,
        disable_thinking=module_cfg.disable_thinking,
    )


def build_factory(config) -> LLMFactory:
    """Build an LLMFactory from a GameConfig (pydantic)."""
    default = llm_config_from_pydantic(config.llm.default)
    modules = {name: llm_config_from_pydantic(cfg) for name, cfg in config.llm.modules.items()}
    return LLMFactory(default_config=default, module_configs=modules)
