from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from recall.core.config import settings


logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def _prepare_database_path(database_path: Path) -> Path:
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        fallback_path = Path.cwd() / database_path.name
        logger.warning("Unable to write to %s; falling back to %s", database_path.parent, fallback_path)
        fallback_path.parent.mkdir(parents=True, exist_ok=True)
        return fallback_path
    return database_path


def _build_engine(database_path: Path) -> Engine:
    resolved_path = _prepare_database_path(database_path)
    engine = create_engine(
        f"sqlite:///{resolved_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite_connection(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


engine = _build_engine(settings.database_path)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    from recall.core.models import JournalEntry, Note, Tag  # noqa: F401
    from recall.core.service import DEFAULT_TAG_NAMES

    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError as exc:
        if "unable to open database file" not in str(exc):
            raise
        logger.warning("Database path %s is not yet accessible; retrying after preparing the parent directory", settings.database_path)
        resolved_path = _prepare_database_path(settings.database_path)
        global engine
        engine = _build_engine(resolved_path)
        SessionLocal.configure(bind=engine)
        Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(notes)"))
        }
        if "title" not in columns:
            conn.execute(text("ALTER TABLE notes ADD COLUMN title VARCHAR(255)"))

    with SessionLocal() as session:
        if session.scalar(text("SELECT COUNT(*) FROM tags")) == 0:
            for tag_name in DEFAULT_TAG_NAMES:
                session.add(Tag(name=tag_name, enabled=True))
            session.commit()
