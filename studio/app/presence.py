"""Lightweight episode presence. Heartbeat + TTL. Not a realtime NLE cursor."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .config import get_settings
from .models import PresenceHeartbeat, utcnow

DEFAULT_TTL_SECONDS = 60


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def ttl_seconds(settings=None) -> int:
    cfg = settings or get_settings()
    try:
        value = int(cfg.presence_ttl_seconds)
    except (TypeError, ValueError):
        value = DEFAULT_TTL_SECONDS
    return max(5, min(value, 600))


def cutoff(now: datetime | None = None, settings=None) -> datetime:
    stamp = _aware(now) or utcnow()
    return stamp - timedelta(seconds=ttl_seconds(settings))


def heartbeat(
    db: Session,
    *,
    episode_id: str,
    user_name: str,
    role: str | None,
    shot_id: str | None = None,
    now: datetime | None = None,
) -> PresenceHeartbeat:
    name = (user_name or "").strip() or "local-dev"
    row = (
        db.query(PresenceHeartbeat)
        .filter(PresenceHeartbeat.episode_id == episode_id, PresenceHeartbeat.user_name == name)
        .first()
    )
    stamp = _aware(now) or utcnow()
    if row is None:
        row = PresenceHeartbeat(
            episode_id=episode_id,
            user_name=name,
            role=role or "",
            shot_id=shot_id or "",
            last_seen=stamp,
        )
        db.add(row)
    else:
        row.role = role or row.role or ""
        row.shot_id = shot_id or ""
        row.last_seen = stamp
    db.commit()
    db.refresh(row)
    return row


def list_active(
    db: Session,
    episode_id: str,
    *,
    now: datetime | None = None,
    settings=None,
) -> list[PresenceHeartbeat]:
    limit = cutoff(now, settings)
    rows = (
        db.query(PresenceHeartbeat)
        .filter(
            PresenceHeartbeat.episode_id == episode_id,
            PresenceHeartbeat.last_seen >= limit,
        )
        .order_by(PresenceHeartbeat.last_seen.desc())
        .all()
    )
    return rows


def prune(db: Session, *, now: datetime | None = None, settings=None) -> int:
    limit = cutoff(now, settings)
    stale = db.query(PresenceHeartbeat).filter(PresenceHeartbeat.last_seen < limit).all()
    count = len(stale)
    for row in stale:
        db.delete(row)
    if count:
        db.commit()
    return count
