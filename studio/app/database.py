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


_ADDITIVE_COLUMNS = (
    ("media_assets", "entity_type", "VARCHAR(32) DEFAULT ''"),
    ("projects", "still_adapter", "VARCHAR(80) DEFAULT 'stub'"),
    ("projects", "clip_adapter", "VARCHAR(80) DEFAULT 'stub'"),
    ("projects", "budget_cap_units", "FLOAT"),
    ("projects", "budget_hard_stop", "BOOLEAN DEFAULT 0"),
    ("projects", "retention_days", "INTEGER"),
    ("jobs", "estimated_cost_units", "FLOAT DEFAULT 0"),
    ("jobs", "actual_cost_units", "FLOAT"),
    ("jobs", "cost_currency", "VARCHAR(32) DEFAULT 'credits'"),
    ("jobs", "cost_note", "TEXT DEFAULT ''"),
    ("comments", "shot_id", "VARCHAR(36)"),
    ("comments", "board_node_id", "VARCHAR(80) DEFAULT ''"),
    ("comments", "resolved", "BOOLEAN DEFAULT 0"),
    ("comments", "resolved_by", "VARCHAR(120) DEFAULT ''"),
    ("comments", "resolved_at", "DATETIME"),
    ("organizations", "is_default", "BOOLEAN DEFAULT 0"),
    ("audit_events", "organization_id", "VARCHAR(36)"),
    ("media_assets", "approval_status", "VARCHAR(20) DEFAULT 'draft'"),
    ("media_assets", "approved_by", "VARCHAR(120) DEFAULT ''"),
    ("media_assets", "approved_at", "DATETIME"),
    ("media_assets", "shot_id", "VARCHAR(36) DEFAULT ''"),
    ("media_assets", "edit_row_id", "VARCHAR(80) DEFAULT ''"),
    ("media_assets", "lock_keywords", "TEXT DEFAULT ''"),
    ("episodes", "season", "INTEGER DEFAULT 1"),
    ("episodes", "sequence_index", "INTEGER DEFAULT 1"),
    ("episodes", "log_line", "TEXT DEFAULT ''"),
    ("episodes", "map_notes", "TEXT DEFAULT ''"),
    ("episodes", "dialogue", "TEXT DEFAULT ''"),
)


def _add_column(target, table: str, name: str, ddl: str) -> None:
    inspector = inspect(target)
    tables = inspector.get_table_names()
    if table not in tables:
        return
    cols = {column["name"] for column in inspector.get_columns(table)}
    if name in cols:
        return
    with target.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def ensure_schema(bind=None) -> None:
    """create_all plus additive columns for existing local SQLite files."""
    target = bind or engine
    Base.metadata.create_all(bind=target)
    try:
        inspect(target).get_table_names()
    except Exception:
        return
    for table, name, ddl in _ADDITIVE_COLUMNS:
        try:
            _add_column(target, table, name, ddl)
        except Exception:
            continue


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
