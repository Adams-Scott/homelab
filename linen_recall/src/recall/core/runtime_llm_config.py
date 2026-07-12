from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

import yaml


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str
    model: str
    timeout_seconds: int


@dataclass(frozen=True)
class RuntimeLLMConfig:
    provider: str
    ollama: OllamaConfig


def _default_config_data() -> dict[str, object]:
    return {
        "provider": "ollama",
        "ollama": {
            "base_url": os.getenv("RECALL_OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
            "model": os.getenv("RECALL_OLLAMA_MODEL", "llama3.1:8b"),
            "timeout_seconds": int(os.getenv("RECALL_OLLAMA_TIMEOUT_SECONDS", "30")),
        },
    }


def get_runtime_llm_config_path() -> Path:
    return Path(os.getenv("RECALL_LLM_CONFIG_PATH", "/data/llm_config.yaml"))


def load_or_create_runtime_llm_config(path: Path | None = None) -> tuple[RuntimeLLMConfig, Path]:
    config_path = path or get_runtime_llm_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if not config_path.exists():
        config_path.write_text(yaml.safe_dump(_default_config_data(), sort_keys=False), encoding="utf-8")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    provider = str(raw.get("provider", "heuristic")).strip().lower() or "heuristic"

    ollama_raw = raw.get("ollama") if isinstance(raw, dict) else None
    if not isinstance(ollama_raw, dict):
        ollama_raw = {}

    defaults = _default_config_data()["ollama"]
    assert isinstance(defaults, dict)
    ollama = OllamaConfig(
        base_url=str(ollama_raw.get("base_url", defaults["base_url"])).strip(),
        model=str(ollama_raw.get("model", defaults["model"])).strip(),
        timeout_seconds=int(ollama_raw.get("timeout_seconds", defaults["timeout_seconds"])),
    )

    return RuntimeLLMConfig(provider=provider, ollama=ollama), config_path