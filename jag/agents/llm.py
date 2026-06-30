"""LLM abstraction layer supporting multiple providers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers."""

    async def complete(self, prompt: str, system: str = "", **kwargs: Any) -> str:
        """Generate a text completion."""
        ...

    async def structured(
        self, prompt: str, response_model: type[T], system: str = "", **kwargs: Any
    ) -> T:
        """Generate a structured (JSON schema) completion."""
        ...


class LiteLLMProvider:
    """LLM provider using litellm for multi-provider support."""

    def __init__(self, model: str = "gpt-4", provider: str = "", api_key: str = "", api_base: str | None = None, disable_thinking: bool = False, **kwargs: Any) -> None:
        self.provider = provider
        self.api_key = api_key
        self.api_base = api_base
        self.disable_thinking = disable_thinking
        self._extra = kwargs
        self.model = f"{provider}/{model}" if provider and "/" not in model else model

    async def complete(self, prompt: str, system: str = "", **kwargs: Any) -> str:
        """Generate completion via litellm."""
        import litellm

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "timeout": 10,  # 10 second timeout to avoid blocking
            **self._extra,
            **kwargs,
        }
        if self.api_key:
            params["api_key"] = self.api_key
        if self.api_base:
            params["api_base"] = self.api_base
        if self.disable_thinking:
            params.setdefault("extra_body", {})["thinking"] = {"type": "disabled"}

        try:
            response = await litellm.acompletion(**params)
            return response.choices[0].message.content or ""
        except litellm.exceptions.Timeout:
            raise TimeoutError("LLM request timed out after 10 seconds") from None

    async def structured(
        self, prompt: str, response_model: type[T], system: str = "", **kwargs: Any
    ) -> T:
        """Generate structured output via instructor."""
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
            "timeout": 10,
            **self._extra,
            **kwargs,
        }
        if self.api_key:
            params["api_key"] = self.api_key
        if self.api_base:
            params["api_base"] = self.api_base
        if self.disable_thinking:
            params.setdefault("extra_body", {})["thinking"] = {"type": "disabled"}

        try:
            return await client.create(**params)
        except Exception as e:
            if "timeout" in str(e).lower():
                raise TimeoutError("LLM structured request timed out after 10 seconds") from None
            raise


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or [])
        self._call_count = 0
        self.calls: list[dict[str, Any]] = []

    async def complete(self, prompt: str, system: str = "", **kwargs: Any) -> str:
        self.calls.append({"prompt": prompt, "system": system, **kwargs})
        if self._responses:
            response = self._responses[min(self._call_count, len(self._responses) - 1)]
            self._call_count += 1
            return response
        self._call_count += 1
        return "Mock response"

    async def structured(
        self, prompt: str, response_model: type[T], system: str = "", **kwargs: Any
    ) -> T:
        self.calls.append({"prompt": prompt, "system": system, "model": response_model, **kwargs})
        self._call_count += 1
        # Return a default instance
        return response_model()


@dataclass
class LLMConfig:
    """Configuration for a single LLM instance."""

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

    def __init__(self, default_config: LLMConfig | None = None, module_configs: dict[str, LLMConfig] | None = None) -> None:
        self._default = default_config or LLMConfig()
        self._modules = module_configs or {}
        self._cache: dict[str, LLMProvider] = {}

    def get(self, module_name: str = "default") -> LLMProvider:
        """Get or create an LLM provider for a module."""
        if module_name in self._cache:
            return self._cache[module_name]

        config = self._modules.get(module_name, self._default)
        provider = self._create_provider(config)
        self._cache[module_name] = provider
        return provider

    def _create_provider(self, config: LLMConfig) -> LLMProvider:
        """Create a provider from config."""
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
