"""Builder → studio pack zip staging. Not auto-generate."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from .models import Episode, PackHandoff, utcnow
from .packzip import PackZipError, extract_pack_json, safe_filename
from .store import get_store

HANDOFF_TTL = timedelta(hours=2)
HONESTY = (
    "Builder Open in Studio stages a pack zip. Pick a project/episode to import. "
    "Never auto-generate. Failure modes: studio down, auth refused, expired handoff."
)


def assert_episode_in_org(db: Session, episode_id: str | None, organization_id: str) -> None:
    """Refuse a handoff pinned to an episode outside the caller's org."""
    token = (episode_id or "").strip()
    if not token:
        return
    episode = db.get(Episode, token)
    project = episode.project if episode is not None else None
    if project is None or project.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Episode not found in this organization.",
        )


def create_handoff(
    db: Session,
    *,
    organization_id: str,
    user_name: str,
    filename: str,
    data: bytes,
    episode_id: str | None = None,
) -> PackHandoff:
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload.")
    assert_episode_in_org(db, episode_id, organization_id)
    try:
        extract_pack_json(data)
    except PackZipError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    now = utcnow()
    safe_name = safe_filename(filename or "", "pack.zip")
    if not safe_name.lower().endswith(".zip"):
        safe_name = f"{safe_name}.zip"
    row = PackHandoff(
        organization_id=organization_id,
        episode_id=(episode_id or "").strip() or None,
        filename=safe_name,
        zip_path="",
        created_by=user_name,
        created_at=now,
        expires_at=now + HANDOFF_TTL,
    )
    db.add(row)
    db.flush()
    rel = Path("handoffs") / organization_id / f"{row.id}.zip"
    get_store().put(str(rel), data)
    row.zip_path = str(rel)
    return row


def get_live_handoff(db: Session, handoff_id: str, organization_id: str) -> PackHandoff:
    row = db.get(PackHandoff, handoff_id)
    if not row or row.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handoff not found.")
    now = utcnow()
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=now.tzinfo)
    if expires < now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Handoff expired. Export the zip from the builder and Import pack zip by hand.",
        )
    if row.consumed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Handoff already imported. Export a new zip to hand off again.",
        )
    return row


def read_handoff_bytes(row: PackHandoff) -> bytes:
    try:
        return get_store().get_bytes(row.zip_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handoff zip is missing from the media store.",
        ) from exc


def consume_handoff(db: Session, row: PackHandoff) -> None:
    """Single-use consume. A second import loses the compare-and-set and rolls back."""
    now = utcnow()
    result = db.execute(
        update(PackHandoff)
        .where(
            PackHandoff.id == row.id,
            PackHandoff.organization_id == row.organization_id,
            PackHandoff.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    if result.rowcount != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Handoff already imported. Export a new zip to hand off again.",
        )
    row.consumed_at = now


def handoff_out(row: PackHandoff) -> dict[str, Any]:
    return {
        "id": row.id,
        "filename": row.filename,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "expires_at": row.expires_at,
        "consumed": row.consumed_at is not None,
        "episode_id": row.episode_id,
        "honesty": HONESTY,
        "auto_generate": False,
    }
