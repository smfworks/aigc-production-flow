"""Visual identity store: approved sheets + per-window plates.

Not embeddings. Synonym lock-diff rules stay in consistency.py.
Public trees use fixture/placeholder metadata — no likeness stills.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .audit import IDENTITY_APPROVE, IDENTITY_LINK, record
from .consistency import lock_diff_problems
from .models import (
    APPROVAL_APPROVED,
    APPROVAL_DRAFT,
    APPROVAL_STATUSES,
    ENTITY_TYPES,
    IDENTITY_KINDS,
    Episode,
    MediaAsset,
    Shot,
    utcnow,
)

HONESTY = (
    "Visual identity store: approved sheets and per-window plates linked to "
    "characters/props/scenes (and to shots/windows). Not embeddings. "
    "Synonym lock-diff groups are unchanged. Draft sheets/plates do not count "
    "for lock-diff or generate readiness. Fixture metadata only in public trees "
    "— no likeness stills."
)


def is_identity_kind(kind: str) -> bool:
    return kind in IDENTITY_KINDS


def is_approved(asset: MediaAsset) -> bool:
    return (asset.approval_status or APPROVAL_DRAFT) == APPROVAL_APPROVED


def identity_assets(episode: Episode) -> list[MediaAsset]:
    return [asset for asset in episode.media if is_identity_kind(asset.kind)]


def approved_identity(media: list[MediaAsset], *, kind: str | None = None) -> list[MediaAsset]:
    rows = [asset for asset in media if is_identity_kind(asset.kind) and is_approved(asset)]
    if kind:
        rows = [asset for asset in rows if asset.kind == kind]
    return rows


def identity_href(episode: Episode, asset_id: str) -> str:
    return f"#/projects/{episode.project_id}/episodes/{episode.id}/identity/{asset_id}"


def identity_lock_texts(episode: Episode) -> list[dict[str, str]]:
    """Approved identity keywords only. Same tokenizer as pack lock-diff."""
    rows: list[dict[str, str]] = []
    for asset in identity_assets(episode):
        if not is_approved(asset):
            continue
        text = (asset.lock_keywords or "").strip()
        if not text:
            continue
        kind = (asset.entity_type or "").strip() or "character"
        if kind not in {"character", "prop", "scene"}:
            kind = "character"
        name = (asset.entity_label or "").strip() or asset.original_name
        rows.append(
            {
                "entityName": name,
                "entityKind": kind,
                "source": f"identity {asset.kind} · {name}",
                "text": text,
            }
        )
    return rows


def identity_lock_diff_problems(episode: Episode, pack: dict[str, Any] | None = None) -> list[str]:
    extra = identity_lock_texts(episode)
    if not extra:
        return []
    return lock_diff_problems(pack or {}, extra_texts=extra)


def get_identity_asset(db: Session, episode: Episode, asset_id: str) -> MediaAsset:
    asset = db.get(MediaAsset, asset_id)
    if not asset or asset.episode_id != episode.id or not is_identity_kind(asset.kind):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Identity sheet/plate not found on this episode.",
        )
    return asset


def approve_asset(
    db: Session,
    episode: Episode,
    asset: MediaAsset,
    *,
    user_name: str,
    note: str = "",
    lock_keywords: str | None = None,
    entity_label: str | None = None,
    entity_type: str | None = None,
) -> MediaAsset:
    if not is_identity_kind(asset.kind):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only sheets and plates enter the identity store.",
        )
    if entity_type is not None:
        kind = entity_type.strip()
        if kind and kind not in ENTITY_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="entity_type must be character, prop, scene, costume, or empty.",
            )
        asset.entity_type = kind
    if entity_label is not None:
        asset.entity_label = entity_label.strip()
    keywords_changed = False
    if lock_keywords is not None:
        next_keywords = lock_keywords.strip()
        keywords_changed = next_keywords != (asset.lock_keywords or "")
        asset.lock_keywords = next_keywords
    status_value = (asset.approval_status or APPROVAL_DRAFT).strip().lower()
    if status_value not in APPROVAL_STATUSES:
        status_value = APPROVAL_DRAFT
    newly_approved = status_value != APPROVAL_APPROVED
    if newly_approved:
        asset.approval_status = APPROVAL_APPROVED
        asset.approved_by = user_name
        asset.approved_at = utcnow()
        if note.strip():
            extra = f"approved: {note.strip()}"
            asset.notes = f"{asset.notes}\n{extra}".strip() if asset.notes else extra
    if newly_approved or keywords_changed:
        record(
            db,
            actor=user_name,
            action=IDENTITY_APPROVE,
            project_id=episode.project_id,
            episode_id=episode.id,
            entity_type="media",
            entity_id=asset.id,
            detail={
                "kind": asset.kind,
                "entity_label": asset.entity_label,
                "entity_type": asset.entity_type,
                "approved_by": user_name,
            },
        )
    return asset


def link_plate(
    db: Session,
    episode: Episode,
    asset: MediaAsset,
    *,
    user_name: str,
    shot_id: str | None = None,
    edit_row_id: str | None = None,
    lock_keywords: str | None = None,
    entity_label: str | None = None,
    entity_type: str | None = None,
) -> MediaAsset:
    if asset.kind != "plate":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only plates link to a shot/window. Sheets stay on the entity.",
        )
    next_shot = (shot_id or "").strip()
    if next_shot:
        shot = db.get(Shot, next_shot)
        if not shot or shot.episode_id != episode.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shot not found.")
        asset.shot_id = shot.id
        if not (edit_row_id or "").strip():
            asset.edit_row_id = shot.edit_row_id or ""
    elif shot_id is not None:
        asset.shot_id = ""
    if edit_row_id is not None:
        asset.edit_row_id = edit_row_id.strip()
    if lock_keywords is not None:
        asset.lock_keywords = lock_keywords.strip()
    if entity_label is not None:
        asset.entity_label = entity_label.strip()
    if entity_type is not None:
        asset.entity_type = entity_type.strip()
    record(
        db,
        actor=user_name,
        action=IDENTITY_LINK,
        project_id=episode.project_id,
        episode_id=episode.id,
        entity_type="media",
        entity_id=asset.id,
        detail={
            "kind": asset.kind,
            "shot_id": asset.shot_id or "",
            "edit_row_id": asset.edit_row_id or "",
            "entity_label": asset.entity_label,
            "entity_type": asset.entity_type,
        },
    )
    return asset


def asset_out_fields(asset: MediaAsset) -> dict[str, Any]:
    return {
        "approval_status": asset.approval_status or APPROVAL_DRAFT,
        "approved_by": asset.approved_by or "",
        "approved_at": asset.approved_at,
        "shot_id": asset.shot_id or None,
        "edit_row_id": asset.edit_row_id or "",
        "lock_keywords": asset.lock_keywords or "",
        "approved": is_approved(asset),
    }


def identity_summary(episode: Episode) -> dict[str, Any]:
    sheets: list[dict[str, Any]] = []
    plates: list[dict[str, Any]] = []
    for asset in identity_assets(episode):
        row = {
            "id": asset.id,
            "kind": asset.kind,
            "original_name": asset.original_name,
            "entity_label": asset.entity_label or "",
            "entity_type": asset.entity_type or "",
            "notes": asset.notes or "",
            "href": identity_href(episode, asset.id),
            **asset_out_fields(asset),
            "created_by": asset.created_by,
            "created_at": asset.created_at,
        }
        if asset.kind == "sheet":
            sheets.append(row)
        else:
            plates.append(row)
    return {
        "episode_id": episode.id,
        "project_id": episode.project_id,
        "honesty": HONESTY,
        "embeddings": False,
        "likeness": False,
        "sheets": sheets,
        "plates": plates,
        "approved_sheet_count": sum(1 for row in sheets if row["approved"]),
        "approved_plate_count": sum(1 for row in plates if row["approved"]),
    }
