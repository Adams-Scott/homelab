from __future__ import annotations

import calendar
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from recall.core.config import settings
from recall.core.db import get_session, init_db
from recall.core.llm import build_llm_client
from recall.core.service import NoteService, build_note_service
from recall.core.worker_status import load_worker_status


app = FastAPI(title=f"{settings.app_name} Web")
base_path = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(base_path / "templates"))
app.mount("/static", StaticFiles(directory=str(base_path / "static")), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def get_note_service(session: Session = Depends(get_session)) -> NoteService:
    return build_note_service(session, build_llm_client(settings.llm_provider))


def _resolve_month(year: int | None, month: int | None) -> tuple[int, int]:
    today = date.today()
    resolved_year = year or today.year
    resolved_month = month or today.month
    if resolved_month < 1:
        resolved_month = 1
    if resolved_month > 12:
        resolved_month = 12
    return resolved_year, resolved_month


def _adjacent_month(year: int, month: int, delta: int) -> tuple[int, int]:
    new_month = month + delta
    new_year = year
    if new_month < 1:
        new_month = 12
        new_year -= 1
    elif new_month > 12:
        new_month = 1
        new_year += 1
    return new_year, new_month


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        context={
            "request": request,
            "app_name": settings.app_name,
        },
    )


@app.get("/search", response_class=HTMLResponse)
def search_page(request: Request, q: str = "", page: int = 1, service: NoteService = Depends(get_note_service)):
    current_page = max(page, 1)
    page_size = 10
    has_searched = True
    notes, total_results = service.search_notes_paginated(q, page=current_page, page_size=page_size)
    total_pages = (total_results + page_size - 1) // page_size if total_results else 0
    return templates.TemplateResponse(
        request,
        "search.html",
        context={
            "request": request,
            "app_name": settings.app_name,
            "notes": notes,
            "query": q,
            "has_searched": has_searched,
            "page": current_page,
            "page_size": page_size,
            "total_results": total_results,
            "total_pages": total_pages,
        },
    )


@app.get("/journal", response_class=HTMLResponse)
def journal_page(
    request: Request,
    year: int | None = None,
    month: int | None = None,
    service: NoteService = Depends(get_note_service),
):
    resolved_year, resolved_month = _resolve_month(year, month)

    cal = calendar.Calendar(firstweekday=6)
    weeks = cal.monthdatescalendar(resolved_year, resolved_month)
    start_date = weeks[0][0]
    end_date = weeks[-1][-1]
    entry_map = service.get_journal_entries_between(start_date, end_date)

    cells = []
    today = date.today()
    for week in weeks:
        for day in week:
            entry = entry_map.get(day)
            cells.append(
                {
                    "date": day,
                    "is_current_month": day.month == resolved_month,
                    "is_today": day == today,
                    "has_entry": entry is not None,
                    "entry_status": entry.enrichment_status if entry is not None else "",
                }
            )

    prev_year, prev_month = _adjacent_month(resolved_year, resolved_month, -1)
    next_year, next_month = _adjacent_month(resolved_year, resolved_month, 1)

    return templates.TemplateResponse(
        request,
        "journal.html",
        context={
            "request": request,
            "app_name": settings.app_name,
            "month_label": date(resolved_year, resolved_month, 1).strftime("%B %Y"),
            "year": resolved_year,
            "month": resolved_month,
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
            "today": today,
            "today_url": f"/journal/date/{today.isoformat()}",
            "calendar_cells": cells,
        },
    )


@app.get("/journal/search", response_class=HTMLResponse)
def journal_search_page(
    request: Request,
    q: str = "",
    page: int = 1,
    service: NoteService = Depends(get_note_service),
):
    current_page = max(page, 1)
    page_size = 10
    has_searched = True
    search_results, total_results = service.search_journal_entries_paginated(q, page=current_page, page_size=page_size)
    total_pages = (total_results + page_size - 1) // page_size if total_results else 0
    return templates.TemplateResponse(
        request,
        "journal_search.html",
        context={
            "request": request,
            "app_name": settings.app_name,
            "query": q,
            "has_searched": has_searched,
            "search_results": search_results,
            "page": current_page,
            "page_size": page_size,
            "total_results": total_results,
            "total_pages": total_pages,
        },
    )


@app.get("/journal/date/{entry_date}", response_class=HTMLResponse)
def journal_date_page(request: Request, entry_date: date, service: NoteService = Depends(get_note_service)):
    entry = service.get_journal_entry_by_date(entry_date)
    return templates.TemplateResponse(
        request,
        "journal_entry.html",
        context={
            "request": request,
            "app_name": settings.app_name,
            "entry_date": entry_date,
            "entry": entry,
            "month": entry_date.month,
            "year": entry_date.year,
        },
    )


@app.post("/journal/date/{entry_date}")
def save_journal_date_entry(
    entry_date: date,
    original_entry: str = Form(...),
    service: NoteService = Depends(get_note_service),
):
    try:
        service.save_journal_entry(entry_date, original_entry)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/journal/date/{entry_date.isoformat()}", status_code=303)


@app.get("/worker-health", response_class=HTMLResponse)
def worker_health(request: Request, service: NoteService = Depends(get_note_service)):
    worker_status = load_worker_status()
    status_counts = service.get_status_counts()
    return templates.TemplateResponse(
        request,
        "worker_health.html",
        context={
            "request": request,
            "app_name": settings.app_name,
            "status_counts": status_counts,
            "last_check_in": worker_status.last_check_in,
            "last_processed": worker_status.last_processed,
        },
    )


@app.post("/notes")
def create_note(
    original_note: str = Form(...),
    title: str = Form(default=""),
    service: NoteService = Depends(get_note_service),
):
    note = service.create_note(original_note, title=title)
    return RedirectResponse(url=f"/notes/{note.id}", status_code=303)


@app.get("/notes/{note_id}", response_class=HTMLResponse)
def note_detail(request: Request, note_id: int, service: NoteService = Depends(get_note_service)):
    note = service.get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return templates.TemplateResponse(
        request,
        "detail.html",
        context={
            "request": request,
            "app_name": settings.app_name,
            "note": note,
        },
    )


@app.get("/notes/{note_id}/edit", response_class=HTMLResponse)
def edit_note(request: Request, note_id: int, service: NoteService = Depends(get_note_service)):
    note = service.get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return templates.TemplateResponse(
        request,
        "edit.html",
        context={
            "request": request,
            "app_name": settings.app_name,
            "note": note,
        },
    )


@app.post("/notes/{note_id}/edit")
def save_note(
    note_id: int,
    original_note: str = Form(...),
    title: str = Form(default=""),
    service: NoteService = Depends(get_note_service),
):
    if service.update_note(note_id, original_note, title=title) is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return RedirectResponse(url=f"/notes/{note_id}", status_code=303)


@app.post("/notes/{note_id}/delete")
def delete_note(note_id: int, service: NoteService = Depends(get_note_service)):
    if not service.delete_note(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return RedirectResponse(url="/", status_code=303)


@app.get("/tags", response_class=HTMLResponse)
def tags_page(request: Request, service: NoteService = Depends(get_note_service)):
    return templates.TemplateResponse(
        request,
        "tags.html",
        context={
            "request": request,
            "app_name": settings.app_name,
            "tags": service.list_tags(),
        },
    )


@app.post("/tags")
def create_tag(name: str = Form(...), service: NoteService = Depends(get_note_service)):
    created = service.create_tag(name)
    if created is None:
        raise HTTPException(status_code=400, detail="Tag name is required")
    return RedirectResponse(url="/tags", status_code=303)


@app.post("/tags/{tag_id}/toggle")
def toggle_tag(tag_id: int, service: NoteService = Depends(get_note_service)):
    if service.toggle_tag(tag_id) is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return RedirectResponse(url="/tags", status_code=303)


@app.post("/tags/{tag_id}/delete")
def delete_tag(tag_id: int, service: NoteService = Depends(get_note_service)):
    if not service.delete_tag(tag_id):
        raise HTTPException(status_code=404, detail="Tag not found")
    return RedirectResponse(url="/tags", status_code=303)


@app.get("/context", response_class=HTMLResponse)
def context_page(request: Request, service: NoteService = Depends(get_note_service)):
    context_path = service.context_path
    return templates.TemplateResponse(
        request,
        "context.html",
        context={
            "request": request,
            "app_name": settings.app_name,
            "context_text": service.get_context_text(),
            "context_path": context_path,
        },
    )


@app.post("/context")
def save_context(context_text: str = Form(default=""), service: NoteService = Depends(get_note_service)):
    service.save_context_text(context_text)
    return RedirectResponse(url="/context", status_code=303)
