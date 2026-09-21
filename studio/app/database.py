from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
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


def ensure_schema(bind=None) -> None:
    """create_all plus additive columns for existing local SQLite files."""
    target = bind or engine
    Base.metadata.create_all(bind=target)
    try:
        inspector = inspect(target)
        tables = inspector.get_table_names()
    except Exception:
        return
    if "media_assets" not in tables:
        return
    cols = {column["name"] for column in inspector.get_columns("media_assets")}
    if "entity_type" not in cols:
        with target.begin() as conn:
            conn.execute(text("ALTER TABLE media_assets ADD COLUMN entity_type VARCHAR(32) DEFAULT ''"))


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
