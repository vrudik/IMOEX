from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from libs.domain.models import Base
from libs.utils.config import settings


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(settings.database_url, future=True)


def ensure_schema() -> None:
    Base.metadata.create_all(get_engine())


def get_session_factory() -> sessionmaker[Session]:
    engine = get_engine()
    # Best-effort local bootstrap for sqlite; for Postgres expect migrations.
    try:
        ensure_schema()
    except Exception:
        pass
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def database_available() -> bool:
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

