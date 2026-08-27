"""Session đồng bộ cho Celery worker.

App HTTP dùng async (asyncpg); Celery task chạy đồng bộ nên dùng engine sync (psycopg)
thay vì nhét event loop vào worker.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

sync_engine = create_engine(_settings.sync_database_url, pool_pre_ping=True, future=True)
SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False, class_=Session)


@contextmanager
def sync_session() -> Iterator[Session]:
    session = SyncSessionLocal()
    try:
        yield session
    finally:
        session.close()
