from fastapi import APIRouter, HTTPException, status

from ..deps import DbDep, get_episode, touch
from ..identity import (
    approve_asset,
    get_identity_asset,
    identity_summary,
    link_plate,
)
from ..models import utcnow
from ..rbac import MediaUser, ReadUser
from ..schemas import IdentityApprove, IdentityLink, IdentityStoreOut, MediaAssetOut
from ..serializers import media_out

router = APIRouter(tags=["identity"])


@router.get("/api/episodes/{episode_id}/identity", response_model=IdentityStoreOut)
def get_identity(episode_id: str, user: ReadUser, db: DbDep) -> IdentityStoreOut:
    episode = get_episode(db, episode_id, user)
    return IdentityStoreOut.model_validate(identity_summary(episode))


@router.post(
    "/api/episodes/{episode_id}/identity/{asset_id}/approve",
    response_model=MediaAssetOut,
)
def approve_identity(
    episode_id: str,
    asset_id: str,
    user: MediaUser,
    db: DbDep,
    body: IdentityApprove | None = None,
) -> MediaAssetOut:
    episode = get_episode(db, episode_id, user)
    asset = get_identity_asset(db, episode, asset_id)
    approve_asset(
        db,
        episode,
        asset,
        user_name=user.name,
        note=(body.note if body else ""),
        lock_keywords=body.lock_keywords if body else None,
        entity_label=body.entity_label if body else None,
        entity_type=body.entity_type if body else None,
    )
    episode.updated_at = utcnow()
    touch(episode.project)
    db.commit()
    db.refresh(asset)
    return media_out(asset)


@router.post(
    "/api/episodes/{episode_id}/identity/{asset_id}/link",
    response_model=MediaAssetOut,
)
def link_identity_plate(
    episode_id: str,
    asset_id: str,
    user: MediaUser,
    db: DbDep,
    body: IdentityLink,
) -> MediaAssetOut:
    episode = get_episode(db, episode_id, user)
    asset = get_identity_asset(db, episode, asset_id)
    if asset.kind != "plate":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only plates link to a shot/window.",
        )
    link_plate(
        db,
        episode,
        asset,
        user_name=user.name,
        shot_id=body.shot_id,
        edit_row_id=body.edit_row_id,
        lock_keywords=body.lock_keywords,
        entity_label=body.entity_label,
        entity_type=body.entity_type,
    )
    episode.updated_at = utcnow()
    touch(episode.project)
    db.commit()
    db.refresh(asset)
    return media_out(asset)
