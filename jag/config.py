"""Global configuration system for JAG."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class LLMModuleConfig(BaseModel):
    """LLM configuration for a specific module."""

    provider: str = "openai"
    model: str = "gpt-4"
    api_key: str = ""
    api_base: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048
    disable_thinking: bool = False


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
    web_host: str = "127.0.0.1"
    web_port: int = 8000

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
    # Load .env file
    load_dotenv()

    if path is None:
        # Try default locations
        for candidate in ["jag_config.yaml", "config.yaml"]:
            if Path(candidate).exists():
                cfg = GameConfig.from_yaml(candidate)
                _apply_env_overrides(cfg)
                return cfg
        cfg = GameConfig()
        _apply_env_overrides(cfg)
        return cfg
    cfg = GameConfig.from_yaml(path)
    _apply_env_overrides(cfg)
    return cfg


def _apply_env_overrides(cfg: GameConfig) -> None:
    """Override config fields from .env variables."""
    # LLM default config
    if provider := os.getenv("LLM_PROVIDER"):
        cfg.llm.default.provider = provider
    if model := os.getenv("LLM_MODEL"):
        cfg.llm.default.model = model
    if api_key := os.getenv("LLM_API_KEY"):
        cfg.llm.default.api_key = api_key
    if api_base := os.getenv("LLM_API_BASE"):
        cfg.llm.default.api_base = api_base
    if temp := os.getenv("LLM_TEMPERATURE"):
        try:
            cfg.llm.default.temperature = float(temp)
        except ValueError:
            pass
    if max_tokens := os.getenv("LLM_MAX_TOKENS"):
        try:
            cfg.llm.default.max_tokens = int(max_tokens)
        except ValueError:
            pass
    if disable_thinking := os.getenv("LLM_DISABLE_THINKING"):
        cfg.llm.default.disable_thinking = disable_thinking.lower() in ("true", "1", "yes")

    # Per-module LLM overrides
    for key, value in os.environ.items():
        if key.startswith("LLM_MODULE_"):
            parts = key.split("_", 3)
            if len(parts) >= 4:
                module_name = parts[2].lower()
                field_name = parts[3].lower()
                if module_name not in cfg.llm.modules:
                    cfg.llm.modules[module_name] = LLMModuleConfig()
                module_cfg = cfg.llm.modules[module_name]
                if field_name == "provider":
                    module_cfg.provider = value
                elif field_name == "model":
                    module_cfg.model = value
                elif field_name == "api_key":
                    module_cfg.api_key = value
                elif field_name == "api_base":
                    module_cfg.api_base = value
                elif field_name == "temperature":
                    try:
                        module_cfg.temperature = float(value)
                    except ValueError:
                        pass
                elif field_name == "max_tokens":
                    try:
                        module_cfg.max_tokens = int(value)
                    except ValueError:
                        pass
                elif field_name == "disable_thinking":
                    module_cfg.disable_thinking = value.lower() in ("true", "1", "yes")

    # Database overrides
    if db_backend := os.getenv("DB_BACKEND"):
        cfg.database.backend = db_backend
    if db_path := os.getenv("DB_PATH"):
        cfg.database.path = db_path
    if db_url := os.getenv("DB_URL"):
        cfg.database.url = db_url

    # Game config overrides
    if world_name := os.getenv("WORLD_NAME"):
        cfg.world_name = world_name
    if max_depth := os.getenv("MAX_CHAIN_DEPTH"):
        try:
            cfg.max_chain_depth = int(max_depth)
        except ValueError:
            pass
    if npc_conc := os.getenv("NPC_CONCURRENCY"):
        try:
            cfg.npc_concurrency = int(npc_conc)
        except ValueError:
            pass
    if web_host := os.getenv("WEB_HOST"):
        cfg.web_host = web_host
    if web_port := os.getenv("WEB_PORT"):
        try:
            cfg.web_port = int(web_port)
        except ValueError:
            pass
