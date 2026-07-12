from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from recall.core.db import Base
from recall.core.llm import HeuristicLLMClient
from recall.core.models import Tag
from recall.core.service import NoteService, build_note_service


def make_service(tmp_path: Path) -> NoteService:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return NoteService(session=session_factory(), llm_client=HeuristicLLMClient(), context_path=tmp_path / "context.md")


def test_create_and_search_notes(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.create_note("Remember the code for the garage door")
    service.create_note("Buy coffee beans on Thursday")
    results = service.search_notes("garage")
    assert len(results) == 1
    assert results[0].original_note == "Remember the code for the garage door"


def test_enrich_note_preserves_original_text(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    note = service.create_note("Pack sunscreen for the trip")
    enriched = service.enrich_note(note.id)
    assert enriched is not None
    assert enriched.original_note == "Pack sunscreen for the trip"
    assert enriched.elaborated_note is not None
    assert enriched.tags is not None


def test_update_resets_enrichment_state(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    note = service.create_note("Pick up dry cleaning")
    service.enrich_note(note.id)
    updated = service.update_note(note.id, "Pick up dry cleaning after work")
    assert updated is not None
    assert updated.elaborated_note is None
    assert updated.tags is None
    assert updated.enrichment_status == "pending"


def test_enrich_fills_title_when_empty(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    note = service.create_note("Submit travel reimbursement on Monday", title="")
    assert note.title is None

    enriched = service.enrich_note(note.id)
    assert enriched is not None
    assert enriched.title is not None
    assert enriched.title != ""


def test_search_notes_paginated_uses_page_size_ten(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    for idx in range(25):
        service.create_note(f"Project alpha task {idx}", title=f"Alpha {idx}")

    page_one, total = service.search_notes_paginated("alpha", page=1, page_size=10)
    page_three, _ = service.search_notes_paginated("alpha", page=3, page_size=10)

    assert total == 25
    assert len(page_one) == 10
    assert len(page_three) == 5


def test_record_enrichment_failure_resets_to_pending(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    note = service.create_note("Retry me")
    service.enrich_note(note.id)

    failed = service.record_enrichment_failure(note.id, "temporary network failure")
    assert failed is not None
    assert failed.enrichment_status == "pending"
    assert failed.elaborated_note is None
    assert failed.tags is None
    assert failed.enriched_at is None
    assert failed.last_enrichment_error is not None


def test_tag_management_and_context_file(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    tag = service.create_tag("Travel")
    assert tag is not None
    assert tag.name == "travel"
    assert tag.enabled is True

    toggled = service.toggle_tag(tag.id)
    assert toggled is not None
    assert toggled.enabled is False

    assert service.create_tag("Travel") == toggled

    service.save_context_text("Duckie is my dog.")
    assert service.get_context_text().strip() == "Duckie is my dog."


def test_enrich_note_uses_enabled_tags_and_context(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.create_tag("travel")
    service.create_tag("dog")
    service.toggle_tag(service.create_tag("dog").id)  # disable the first dog tag
    service.create_tag("pet")
    service.save_context_text("Duckie is my dog.")

    note = service.create_note("Take Duckie for a walk on the trip")
    enriched = service.enrich_note(note.id)

    assert enriched is not None
    assert enriched.tags is not None
    assert "travel" in enriched.tags or "pet" in enriched.tags or "dog" in enriched.tags
    assert "Duckie is my dog." in enriched.elaborated_note


def test_save_journal_entry_is_unique_per_day(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    entry_date = date(2026, 6, 20)

    first = service.save_journal_entry(entry_date, "First version")
    second = service.save_journal_entry(entry_date, "Second version")

    assert first.id == second.id
    assert second.original_entry == "Second version"
    assert service.get_journal_entry_by_date(entry_date) is not None


def test_journal_search_matches_elaborated_entry(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.save_context_text("Important context for elaboration")
    entry_date = date(2026, 6, 20)

    created = service.save_journal_entry(entry_date, "Remember this uncommon phrase")
    enriched = service.enrich_journal_entry(created.id)

    assert enriched is not None
    assert enriched.elaborated_entry is not None

    results, total = service.search_journal_entries_paginated("important context", page=1, page_size=10)
    assert total == 1
    assert len(results) == 1
    assert results[0].entry_date == entry_date


def test_journal_month_presence_map(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.save_journal_entry(date(2026, 6, 3), "Entry one")
    service.save_journal_entry(date(2026, 6, 18), "Entry two")

    month_map = service.get_journal_entries_for_month(2026, 6)
    assert date(2026, 6, 3) in month_map
    assert date(2026, 6, 18) in month_map
    assert date(2026, 6, 20) not in month_map


def test_journal_failure_resets_pending(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    entry = service.save_journal_entry(date(2026, 6, 20), "Entry pending")
    service.enrich_journal_entry(entry.id)

    failed = service.record_journal_enrichment_failure(entry.id, "temporary issue")
    assert failed is not None
    assert failed.enrichment_status == "pending"
    assert failed.elaborated_entry is None
    assert failed.enriched_at is None
    assert failed.last_enrichment_error == "temporary issue"


def test_save_journal_entry_rejects_blank_text(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    entry_date = date(2026, 6, 20)

    try:
        service.save_journal_entry(entry_date, "   ")
        assert False, "Expected ValueError for blank journal entry"
    except ValueError as exc:
        assert "required" in str(exc)
