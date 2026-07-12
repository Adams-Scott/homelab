from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


def _default_db_path() -> Path:
    raw_path = os.getenv("RECALL_DB_PATH", "/data/recall.db")
    return Path(raw_path)


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("RECALL_APP_NAME", "Recall")
    database_path: Path = _default_db_path()
    context_path: Path = Path(os.getenv("RECALL_CONTEXT_PATH", "/data/context.md"))
    llm_provider: str = os.getenv("RECALL_LLM_PROVIDER", "heuristic")
    enrich_batch_size: int = int(os.getenv("RECALL_ENRICH_BATCH_SIZE", "10"))
    enrich_interval_seconds: int = int(os.getenv("RECALL_ENRICH_INTERVAL_SECONDS", "60"))


settings = Settings()
