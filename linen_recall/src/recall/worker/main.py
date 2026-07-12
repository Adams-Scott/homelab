from __future__ import annotations

import time

from apscheduler.schedulers.background import BackgroundScheduler

from recall.core.config import settings
from recall.core.db import SessionLocal, init_db
from recall.core.llm import build_llm_client
from recall.core.runtime_llm_config import load_or_create_runtime_llm_config
from recall.core.service import build_note_service
from recall.core.worker_status import record_worker_check_in


def process_pending_notes() -> int:
    session = SessionLocal()
    try:
        runtime_config, _config_path = load_or_create_runtime_llm_config()
        service = build_note_service(
            session,
            build_llm_client(
                runtime_config.provider,
                ollama_base_url=runtime_config.ollama.base_url,
                ollama_model=runtime_config.ollama.model,
                ollama_timeout_seconds=runtime_config.ollama.timeout_seconds,
            ),
        )
        processed = 0
        for note in service.claim_pending_notes(limit=settings.enrich_batch_size):
            try:
                if service.enrich_note(note.id) is not None:
                    processed += 1
            except Exception as exc:  # pragma: no cover - worker should keep going if one note fails
                service.record_enrichment_failure(note.id, str(exc))

        for entry in service.claim_pending_journal_entries(limit=settings.enrich_batch_size):
            try:
                if service.enrich_journal_entry(entry.id) is not None:
                    processed += 1
            except Exception as exc:  # pragma: no cover - worker should keep going if one note fails
                service.record_journal_enrichment_failure(entry.id, str(exc))
        record_worker_check_in(processed)
        return processed
    finally:
        session.close()


def main() -> None:
    runtime_config, config_path = load_or_create_runtime_llm_config()
    print(f"[worker] Using LLM provider '{runtime_config.provider}' from {config_path}")

    init_db()
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(process_pending_notes, "interval", seconds=settings.enrich_interval_seconds, id="recall-enrichment")
    scheduler.start()
    process_pending_notes()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
