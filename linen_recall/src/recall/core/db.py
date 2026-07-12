from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from recall.core.config import settings


class Base(DeclarativeBase):
    pass


def _build_engine(database_path: Path) -> Engine:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{database_path}",
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
