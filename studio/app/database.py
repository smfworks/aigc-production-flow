from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


def make_engine(url: str | None = None):
    settings = get_settings()
    database_url = url or settings.database_url
    return create_engine(database_url, **_engine_kwargs(database_url))


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_engine(url: str) -> None:
    """Test helper: rebind the global session maker to a fresh database."""
    global engine, SessionLocal
    engine.dispose()
    engine = make_engine(url)
    SessionLocal.configure(bind=engine)
