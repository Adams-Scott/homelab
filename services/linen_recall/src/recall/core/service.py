from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from recall.core.context_store import load_context_text, save_context_text
from recall.core.config import settings
from recall.core.llm import BaseLLMClient
from recall.core.models import JournalEntry, Note, Tag


DEFAULT_TAG_NAMES = ["personal", "home", "work", "family", "health", "travel", "idea", "todo"]


class NoteService:
    def __init__(self, session: Session, llm_client: BaseLLMClient, context_path: Path | None = None):
        self.session = session
        self.llm_client = llm_client
        self.context_path = context_path or settings.context_path

    def refresh_runtime_inputs(self) -> tuple[str, list[str]]:
        return self.get_context_text(), self.get_enabled_tag_names()

    def create_note(self, original_note: str, title: str = "") -> Note:
        normalized_title = title.strip() or None
        note = Note(title=normalized_title, original_note=original_note.strip(), enrichment_status="pending")
        self.session.add(note)
        self.session.commit()
        self.session.refresh(note)
        return note

    def list_notes(self) -> list[Note]:
        statement = select(Note).order_by(Note.updated_at.desc(), Note.id.desc())
        return list(self.session.scalars(statement).all())

    def get_status_counts(self) -> dict[str, int]:
        pending = self.session.scalar(select(func.count()).where(Note.enrichment_status == "pending")) or 0
        in_progress = self.session.scalar(select(func.count()).where(Note.enrichment_status == "in_progress")) or 0
        done = self.session.scalar(select(func.count()).where(Note.enrichment_status == "done")) or 0
        return {
            "pending": int(pending),
            "in_progress": int(in_progress),
            "done": int(done),
        }

    def get_note(self, note_id: int) -> Note | None:
        return self.session.get(Note, note_id)

    def list_tags(self) -> list[Tag]:
        statement = select(Tag).order_by(Tag.enabled.desc(), Tag.name.asc())
        return list(self.session.scalars(statement).all())

    def create_tag(self, name: str, enabled: bool = True) -> Tag | None:
        normalized = name.strip().lower()
        if not normalized:
            return None
        existing = self.session.scalar(select(Tag).where(Tag.name == normalized))
        if existing is not None:
            return existing
        tag = Tag(name=normalized, enabled=enabled)
        self.session.add(tag)
        self.session.commit()
        self.session.refresh(tag)
        return tag

    def toggle_tag(self, tag_id: int) -> Tag | None:
        tag = self.session.get(Tag, tag_id)
        if tag is None:
            return None
        tag.enabled = not tag.enabled
        tag.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(tag)
        return tag

    def delete_tag(self, tag_id: int) -> bool:
        tag = self.session.get(Tag, tag_id)
        if tag is None:
            return False
        self.session.delete(tag)
        self.session.commit()
        return True

    def get_enabled_tag_names(self) -> list[str]:
        statement = select(Tag.name).where(Tag.enabled.is_(True)).order_by(Tag.name.asc())
        return list(self.session.scalars(statement).all())

    def get_context_text(self) -> str:
        return load_context_text(self.context_path)

    def save_context_text(self, text: str) -> Path:
        return save_context_text(self.context_path, text)

    def update_note(self, note_id: int, original_note: str, title: str = "") -> Note | None:
        note = self.get_note(note_id)
        if note is None:
            return None

        note.title = title.strip() or None
        note.original_note = original_note.strip()
        note.elaborated_note = None
        note.tags = None
        note.enrichment_status = "pending"
        note.last_enrichment_error = None
        note.enriched_at = None
        note.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(note)
        return note

    def delete_note(self, note_id: int) -> bool:
        note = self.get_note(note_id)
        if note is None:
            return False

        self.session.delete(note)
        self.session.commit()
        return True

    def search_notes(self, query: str) -> list[Note]:
        normalized = query.strip().lower()
        if not normalized:
            return self.list_notes()

        terms = [term for term in normalized.split() if term]
        statement = select(Note)
        for term in terms:
            pattern = f"%{term}%"
            statement = statement.where(
                or_(
                    Note.title.ilike(pattern),
                    Note.original_note.ilike(pattern),
                    Note.elaborated_note.ilike(pattern),
                    Note.tags.ilike(pattern),
                )
            )
        statement = statement.order_by(Note.updated_at.desc(), Note.id.desc())
        return list(self.session.scalars(statement).all())

    def search_notes_paginated(self, query: str, page: int = 1, page_size: int = 10) -> tuple[list[Note], int]:
        normalized = query.strip().lower()
        statement = select(Note)
        terms = [term for term in normalized.split() if term]
        for term in terms:
            pattern = f"%{term}%"
            statement = statement.where(
                or_(
                    Note.title.ilike(pattern),
                    Note.original_note.ilike(pattern),
                    Note.elaborated_note.ilike(pattern),
                    Note.tags.ilike(pattern),
                )
            )

        count_statement = select(func.count()).select_from(statement.subquery())
        total = self.session.scalar(count_statement) or 0

        paged_statement = (
            statement.order_by(Note.updated_at.desc(), Note.id.desc())
            .offset((max(page, 1) - 1) * page_size)
            .limit(page_size)
        )
        return list(self.session.scalars(paged_statement).all()), total

    def claim_pending_notes(self, limit: int) -> list[Note]:
        statement = (
            select(Note)
            .where(Note.enrichment_status == "pending")
            .order_by(Note.updated_at.asc(), Note.id.asc())
            .limit(limit)
        )
        notes = list(self.session.scalars(statement).all())
        for note in notes:
            note.enrichment_status = "in_progress"
            note.last_enrichment_error = None
        self.session.commit()
        return notes

    def enrich_note(self, note_id: int) -> Note | None:
        note = self.get_note(note_id)
        if note is None:
            return None

        context_text, enabled_tags = self.refresh_runtime_inputs()
        result = self.llm_client.enrich(note.original_note, context_text=context_text, allowed_tags=enabled_tags)
        if not note.title:
            note.title = result.title
        note.elaborated_note = result.elaborated_note
        note.tags = ", ".join(result.tags)
        note.enrichment_status = "done"
        note.last_enrichment_error = None
        note.enriched_at = datetime.now(UTC)
        note.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(note)
        return note

    def record_enrichment_failure(self, note_id: int, error_message: str) -> Note | None:
        note = self.get_note(note_id)
        if note is None:
            return None

        note.elaborated_note = None
        note.tags = None
        note.enriched_at = None
        note.enrichment_status = "pending"
        note.last_enrichment_error = error_message
        note.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(note)
        return note

    def get_journal_entry_by_date(self, entry_date: date) -> JournalEntry | None:
        statement = select(JournalEntry).where(JournalEntry.entry_date == entry_date)
        return self.session.scalar(statement)

    def save_journal_entry(self, entry_date: date, original_entry: str) -> JournalEntry:
        normalized_entry = original_entry.strip()
        if not normalized_entry:
            raise ValueError("Journal entry text is required")
        existing = self.get_journal_entry_by_date(entry_date)
        now = datetime.now(UTC)

        if existing is None:
            entry = JournalEntry(
                entry_date=entry_date,
                original_entry=normalized_entry,
                enrichment_status="pending",
                updated_at=now,
            )
            self.session.add(entry)
            self.session.commit()
            self.session.refresh(entry)
            return entry

        existing.original_entry = normalized_entry
        existing.elaborated_entry = None
        existing.enrichment_status = "pending"
        existing.last_enrichment_error = None
        existing.enriched_at = None
        existing.updated_at = now
        self.session.commit()
        self.session.refresh(existing)
        return existing

    def search_journal_entries_paginated(
        self,
        query: str,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[JournalEntry], int]:
        normalized = query.strip().lower()
        statement = select(JournalEntry)
        terms = [term for term in normalized.split() if term]
        for term in terms:
            pattern = f"%{term}%"
            statement = statement.where(
                or_(
                    JournalEntry.original_entry.ilike(pattern),
                    JournalEntry.elaborated_entry.ilike(pattern),
                )
            )

        count_statement = select(func.count()).select_from(statement.subquery())
        total = self.session.scalar(count_statement) or 0

        paged_statement = (
            statement.order_by(JournalEntry.entry_date.desc())
            .offset((max(page, 1) - 1) * page_size)
            .limit(page_size)
        )
        return list(self.session.scalars(paged_statement).all()), total

    def get_journal_entries_between(self, start_date: date, end_date: date) -> dict[date, JournalEntry]:
        statement = (
            select(JournalEntry)
            .where(JournalEntry.entry_date >= start_date, JournalEntry.entry_date <= end_date)
            .order_by(JournalEntry.entry_date.asc())
        )
        entries = list(self.session.scalars(statement).all())
        return {entry.entry_date: entry for entry in entries}

    def get_journal_entries_for_month(self, year: int, month: int) -> dict[date, JournalEntry]:
        start = date(year, month, 1)
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        end = next_month - timedelta(days=1)
        return self.get_journal_entries_between(start, end)

    def claim_pending_journal_entries(self, limit: int) -> list[JournalEntry]:
        statement = (
            select(JournalEntry)
            .where(JournalEntry.enrichment_status == "pending")
            .order_by(JournalEntry.updated_at.asc(), JournalEntry.id.asc())
            .limit(limit)
        )
        entries = list(self.session.scalars(statement).all())
        for entry in entries:
            entry.enrichment_status = "in_progress"
            entry.last_enrichment_error = None
        self.session.commit()
        return entries

    def enrich_journal_entry(self, entry_id: int) -> JournalEntry | None:
        entry = self.session.get(JournalEntry, entry_id)
        if entry is None:
            return None

        context_text, enabled_tags = self.refresh_runtime_inputs()
        result = self.llm_client.enrich(entry.original_entry, context_text=context_text, allowed_tags=enabled_tags)
        entry.elaborated_entry = result.elaborated_note
        entry.enrichment_status = "done"
        entry.last_enrichment_error = None
        entry.enriched_at = datetime.now(UTC)
        entry.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def record_journal_enrichment_failure(self, entry_id: int, error_message: str) -> JournalEntry | None:
        entry = self.session.get(JournalEntry, entry_id)
        if entry is None:
            return None

        entry.elaborated_entry = None
        entry.enriched_at = None
        entry.enrichment_status = "pending"
        entry.last_enrichment_error = error_message
        entry.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(entry)
        return entry


def build_note_service(session: Session, llm_client: BaseLLMClient, context_path: Path | None = None) -> NoteService:
    return NoteService(session=session, llm_client=llm_client, context_path=context_path)
