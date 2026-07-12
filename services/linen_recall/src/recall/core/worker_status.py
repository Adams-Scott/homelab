from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import os

import yaml


@dataclass(frozen=True)
class WorkerStatus:
    last_check_in: str | None
    last_processed: int | None


def get_worker_status_path() -> Path:
    return Path(os.getenv("RECALL_WORKER_STATUS_PATH", "/data/worker_status.yaml"))


def record_worker_check_in(processed: int) -> None:
    path = get_worker_status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_check_in": datetime.now(UTC).isoformat(),
        "last_processed": processed,
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def load_worker_status() -> WorkerStatus:
    path = get_worker_status_path()
    if not path.exists():
        return WorkerStatus(last_check_in=None, last_processed=None)

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return WorkerStatus(last_check_in=None, last_processed=None)

    last_check_in = raw.get("last_check_in")
    last_processed = raw.get("last_processed")
    parsed_last_check_in = str(last_check_in) if isinstance(last_check_in, str) and last_check_in.strip() else None
    parsed_last_processed = int(last_processed) if isinstance(last_processed, int) else None
    return WorkerStatus(last_check_in=parsed_last_check_in, last_processed=parsed_last_processed)