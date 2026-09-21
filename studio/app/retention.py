"""Expire stub job outputs / temp media. Pack revisions are kept by default."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .models import ContinuityReceipt, Episode, Job, MediaAsset, PackRevision, Project, utcnow

KEEP_NOTE = "Pack revisions are not deleted by default."


def effective_days(project: Project | None, settings: Settings | None = None) -> int:
    cfg = settings or get_settings()
    if project is not None and project.retention_days is not None:
        return max(0, int(project.retention_days))
    return max(0, int(cfg.retention_days or 0))


def is_ephemeral(asset: MediaAsset) -> bool:
    path = (asset.path or "").replace("\\", "/")
    notes = asset.notes or ""
    if "/jobs/" in f"/{path}":
        return True
    if notes.startswith("adapter=") or " job=" in notes:
        return True
    if asset.kind == "preview" and "stub" in notes.lower():
        return True
    return False


def cutoff_for(days: int, now: datetime | None = None) -> datetime | None:
    if days <= 0:
        return None
    stamp = now or utcnow()
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp - timedelta(days=days)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def candidates(
    db: Session,
    *,
    project_id: str | None = None,
    episode_id: str | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    query = db.query(MediaAsset)
    project: Project | None = None
    if episode_id:
        query = query.filter(MediaAsset.episode_id == episode_id)
        episode = db.get(Episode, episode_id)
        project = episode.project if episode else None
    elif project_id:
        query = query.join(Episode, MediaAsset.episode_id == Episode.id).filter(
            Episode.project_id == project_id
        )
        project = db.get(Project, project_id)
    days = effective_days(project, cfg)
    limit = cutoff_for(days, now)
    rows: list[dict[str, Any]] = []
    kept_revisions = 0
    if project_id:
        kept_revisions = (
            db.query(PackRevision)
            .join(Episode, PackRevision.episode_id == Episode.id)
            .filter(Episode.project_id == project_id)
            .count()
        )
    elif episode_id:
        kept_revisions = db.query(PackRevision).filter(PackRevision.episode_id == episode_id).count()
    else:
        kept_revisions = db.query(PackRevision).count()

    if limit is None:
        return {
            "retention_days": days,
            "enabled": False,
            "cutoff": None,
            "keep_pack_revisions": True,
            "keep_note": KEEP_NOTE,
            "candidates": [],
            "revision_count_kept": kept_revisions,
        }

    for asset in query.all():
        if not is_ephemeral(asset):
            continue
        created = _aware(asset.created_at)
        if created is None or created > limit:
            continue
        episode = asset.episode
        rows.append(
            {
                "id": asset.id,
                "episode_id": asset.episode_id,
                "project_id": episode.project_id if episode else None,
                "kind": asset.kind,
                "original_name": asset.original_name,
                "path": asset.path,
                "created_at": asset.created_at,
                "notes": asset.notes or "",
            }
        )
    return {
        "retention_days": days,
        "enabled": True,
        "cutoff": limit,
        "keep_pack_revisions": True,
        "keep_note": KEEP_NOTE,
        "candidates": rows,
        "revision_count_kept": kept_revisions,
    }


def apply(
    db: Session,
    *,
    project_id: str | None = None,
    episode_id: str | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    preview = candidates(
        db,
        project_id=project_id,
        episode_id=episode_id,
        settings=settings,
        now=now,
    )
    deleted: list[str] = []
    media_root = (settings or get_settings()).media_path
    for row in preview["candidates"]:
        asset = db.get(MediaAsset, row["id"])
        if not asset:
            continue
        path = media_root / asset.path
        for job in db.query(Job).filter(Job.media_id == asset.id).all():
            job.media_id = None
        for receipt in db.query(ContinuityReceipt).filter(ContinuityReceipt.media_id == asset.id).all():
            receipt.media_id = None
        db.delete(asset)
        deleted.append(asset.id)
        if path.is_file():
            path.unlink()
    db.commit()
    preview["deleted_ids"] = deleted
    preview["deleted_count"] = len(deleted)
    preview["applied"] = True
    return preview
