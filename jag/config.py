"""Global configuration system for JAG."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class LLMModuleConfig(BaseModel):
    """LLM configuration for a specific module."""

    provider: str = "openai"
    model: str = "gpt-4"
    api_key: str = ""
    api_base: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048


class LLMConfig(BaseModel):
    """LLM configuration with per-module overrides."""

    default: LLMModuleConfig = Field(default_factory=LLMModuleConfig)
    modules: dict[str, LLMModuleConfig] = Field(default_factory=dict)

    def get_module_config(self, module_name: str) -> LLMModuleConfig:
        """Get config for a specific module, falling back to default."""
        return self.modules.get(module_name, self.default)


class DatabaseConfig(BaseModel):
    """Database configuration."""

    backend: str = "sqlite"
    path: str = "jag_world.db"
    url: str | None = None  # For PostgreSQL


class GameConfig(BaseModel):
    """Main game configuration."""

    world_name: str = "Default World"
    world_data_dir: str = "jag/demo"
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    max_chain_depth: int = 5
    npc_concurrency: int = 5
    short_term_memory_size: int = 20
    memory_compression_threshold: int = 100

    @classmethod
    def from_yaml(cls, path: str | Path) -> GameConfig:
        """Load configuration from a YAML file."""
        path = Path(path)
        if not path.exists():
            return cls()
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)

    def to_yaml(self, path: str | Path) -> None:
        """Save configuration to a YAML file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False, allow_unicode=True)


def load_config(path: str | Path | None = None) -> GameConfig:
    """Load game configuration, with optional path."""
    if path is None:
        # Try default locations
        for candidate in ["jag_config.yaml", "config.yaml"]:
            if Path(candidate).exists():
                return GameConfig.from_yaml(candidate)
        return GameConfig()
    return GameConfig.from_yaml(path)
