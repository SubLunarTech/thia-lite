from __future__ import annotations

"""
Thia-Lite Configuration Management
====================================
Handles all user-facing config in ~/.thia-lite/config.toml
with sensible defaults and environment variable overrides.
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────────

APP_NAME = "thia-lite"
CONFIG_DIR = Path(os.getenv("THIA_LITE_CONFIG_DIR", Path.home() / f".{APP_NAME}"))
DATA_DIR = CONFIG_DIR / "data"
DB_PATH = CONFIG_DIR / "thia.db"
EPHE_DIR = CONFIG_DIR / "data" / "ephe"
LOG_DIR = CONFIG_DIR / "logs"


class OllamaSettings(BaseSettings):
    """Ollama LLM backend configuration."""
    host: str = Field(default="http://localhost:11434", description="Ollama server URL")
    model: str = Field(default="qwen3.5:9b", description="Default model for chat/tool calling")
    fallback_model: str = Field(default="qwen3.5:4b", description="Fallback if primary too large")
    timeout: int = Field(default=120, description="Request timeout in seconds")
    context_length: int = Field(default=32768, description="Max context window tokens")
    temperature: float = Field(default=0.3, description="Sampling temperature for tool calling")

    model_config = {"env_prefix": "THIA_OLLAMA_"}


class MCPSettings(BaseSettings):
    """MCP server/client configuration."""
    server_port: int = Field(default=8443, description="MCP server HTTP port")
    server_mode: str = Field(default="stdio", description="MCP server mode: stdio, http, ws")
    external_servers: Dict[str, str] = Field(
        default_factory=dict,
        description="External MCP servers to connect to {name: url}"
    )

    model_config = {"env_prefix": "THIA_MCP_"}


class AppSettings(BaseSettings):
    """Top-level application configuration."""
    # General
    debug: bool = Field(default=False, description="Enable debug logging")
    interface: str = Field(default="cli", description="Default UI: cli, tui, desktop")

    # Sub-configs
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)

    # Paths
    config_dir: Path = Field(default=CONFIG_DIR)
    db_path: Path = Field(default=DB_PATH)
    ephe_dir: Path = Field(default=EPHE_DIR)

    # Rules
    rule_sources: List[str] = Field(
        default=["lilly", "ptolemy"],
        description="Active astrology rule sources for RAG"
    )

    model_config = {"env_prefix": "THIA_"}


# ─── Singleton ────────────────────────────────────────────────────────────────

_settings: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = AppSettings()
        _ensure_dirs()
    return _settings


def _ensure_dirs():
    """Create required directories."""
    s = get_settings()
    for d in [s.config_dir, s.config_dir / "data" / "ephe", s.config_dir / "logs"]:
        d.mkdir(parents=True, exist_ok=True)


def save_config(overrides: Dict[str, Any]) -> None:
    """Save config overrides to config.toml."""
    config_file = CONFIG_DIR / "config.toml"
    existing = {}

    if config_file.exists():
        try:
            import tomllib
            with open(config_file, "rb") as f:
                existing = tomllib.load(f)
        except Exception:
            pass

    # Deep merge
    for key, value in overrides.items():
        parts = key.split(".")
        target = existing
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value

    # Write as TOML (simple serialization)
    lines = []
    _toml_serialize(existing, lines, "")
    config_file.write_text("\n".join(lines) + "\n")
    logger.info(f"Config saved to {config_file}")


def _toml_serialize(data: dict, lines: list, prefix: str):
    """Simple TOML serializer for flat config."""
    for key, value in data.items():
        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            lines.append(f"\n[{full_key}]")
            _toml_serialize(value, lines, full_key)
        elif isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        elif isinstance(value, bool):
            lines.append(f'{key} = {"true" if value else "false"}')
        elif isinstance(value, (int, float)):
            lines.append(f'{key} = {value}')
        elif isinstance(value, list):
            items = ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in value)
            lines.append(f'{key} = [{items}]')
