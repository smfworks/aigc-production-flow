"""Builder → studio pack zip staging. Not auto-generate."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .models import PackHandoff, utcnow
from .packzip import PackZipError, extract_pack_json, slugify
from .store import get_store

HANDOFF_TTL = timedelta(hours=2)
HONESTY = (
    "Builder Open in Studio stages a pack zip. Pick a project/episode to import. "
    "Never auto-generate. Failure modes: studio down, auth refused, expired handoff."
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
    try:
        extract_pack_json(data)
    except PackZipError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    now = utcnow()
    row = PackHandoff(
        organization_id=organization_id,
        episode_id=episode_id,
        filename=filename or f"pack-{slugify('handoff')}.zip",
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


def mark_consumed(row: PackHandoff) -> None:
    row.consumed_at = utcnow()


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
