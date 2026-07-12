from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class NoteCreate(BaseModel):
    title: str = ""
    original_note: str = Field(min_length=1)


class NoteUpdate(BaseModel):
    title: str = ""
    original_note: str = Field(min_length=1)


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    original_note: str
    elaborated_note: str | None
    tags: str | None
    enrichment_status: str
    last_enrichment_error: str | None
    created_at: datetime
    updated_at: datetime
    enriched_at: datetime | None


class SearchResult(BaseModel):
    query: str
    results: list[NoteRead]


class EnrichmentResponse(BaseModel):
    processed: int


class JournalEntryCreate(BaseModel):
    entry_date: date
    original_entry: str = Field(min_length=1)


class JournalEntryUpdate(BaseModel):
    original_entry: str = Field(min_length=1)


class JournalEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_date: date
    original_entry: str
    elaborated_entry: str | None
    enrichment_status: str
    last_enrichment_error: str | None
    created_at: datetime
    updated_at: datetime
    enriched_at: datetime | None


class JournalSearchResult(BaseModel):
    query: str
    page: int
    page_size: int
    total_results: int
    results: list[JournalEntryRead]
