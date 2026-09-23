from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response

from ..audit import MEDIA_UPLOAD, record
from ..deps import DbDep, get_episode, touch
from ..models import ContinuityReceipt, ENTITY_TYPES, Job, MEDIA_KINDS, MediaAsset, utcnow
from ..packzip import safe_filename, slugify
from ..rbac import PERM_IDENTITY, PERM_MEDIA, MediaOrIdentityUser, ReadUser, refuse_unless
from ..promptpreview import REF_ROLES
from ..schemas import MediaAssetOut, MediaRefRoleIn
from ..serializers import media_out
from ..store import get_store

router = APIRouter(tags=["media"])

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".txt", ".md", ".json"}
PREVIEW_SUFFIXES = IMAGE_SUFFIXES | {".json", ".mp4", ".webm", ".mov"}


@router.get("/api/episodes/{episode_id}/media", response_model=list[MediaAssetOut])
def list_media(episode_id: str, user: ReadUser, db: DbDep) -> list[MediaAssetOut]:
    episode = get_episode(db, episode_id, user)
    return [media_out(row) for row in episode.media]


@router.post(
    "/api/episodes/{episode_id}/media",
    response_model=MediaAssetOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_media(
    episode_id: str,
    user: MediaOrIdentityUser,
    db: DbDep,
    file: UploadFile = File(...),
    kind: str = Form("other"),
    entity_label: str = Form(""),
    entity_type: str = Form(""),
    notes: str = Form(""),
    ref_role: str = Form(""),
) -> MediaAssetOut:
    episode = get_episode(db, episode_id, user)
    if kind not in MEDIA_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="kind must be sheet, plate, costume, preview, or other.",
        )
    if kind in {"sheet", "plate", "costume"}:
        refuse_unless(user, PERM_IDENTITY, field="sheets/plates/costumes")
    else:
        refuse_unless(user, PERM_MEDIA, field="preview/other media")
    entity_kind = entity_type.strip()
    if kind == "costume" and not entity_kind:
        entity_kind = "costume"
    role = ref_role.strip()
    if role and role not in REF_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ref_role must be identity-lock, motion, environment, audio, or empty.",
        )
    if entity_kind and entity_kind not in ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="entity_type must be character, prop, scene, costume, or empty.",
        )
    original = file.filename or "upload.bin"
    suffix = Path(original).suffix.lower()
    allowed = PREVIEW_SUFFIXES if kind == "preview" else IMAGE_SUFFIXES
    if suffix and suffix not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Preview media may be json/txt receipts, images, or mp4/webm in the gitignored local store. "
                "Do not commit engine MP4s."
                if kind == "preview"
                else "Refusing this file type. Sheets/plates: png, jpg, webp, tiff. Notes: txt/md. Use kind=preview for hop-1 watch files."
            ),
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload.")
    if suffix in {".mp4", ".mov", ".webm"} and kind != "preview":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Engine MP4s belong on the hop-1 preview desk (kind=preview), not the sheet/plate library. They stay gitignored.",
        )
    asset = MediaAsset(
        episode_id=episode.id,
        kind=kind,
        original_name=original,
        stored_name="",
        content_type=file.content_type or "application/octet-stream",
        path="",
        entity_label=entity_label.strip(),
        entity_type=entity_kind,
        notes=notes.strip(),
        ref_role=role,
        created_by=user.name,
    )
    db.add(asset)
    db.flush()
    safe = slugify(Path(original).stem, "asset") + (suffix or "")
    stored = f"{asset.id}_{safe}"
    rel = Path(episode.id) / "assets" / stored
    get_store().put(str(rel), data)
    asset.stored_name = stored
    asset.path = str(rel)
    episode.updated_at = utcnow()
    touch(episode.project)
    record(
        db,
        actor=user.name,
        action=MEDIA_UPLOAD,
        project_id=episode.project_id,
        episode_id=episode.id,
        entity_type="media",
        entity_id=asset.id,
        detail={"kind": kind, "original_name": original},
    )
    db.commit()
    db.refresh(asset)
    return media_out(asset)


@router.patch("/api/episodes/{episode_id}/media/{asset_id}", response_model=MediaAssetOut)
def set_ref_role(
    episode_id: str,
    asset_id: str,
    body: MediaRefRoleIn,
    user: MediaOrIdentityUser,
    db: DbDep,
) -> MediaAssetOut:
    episode = get_episode(db, episode_id, user)
    asset = db.get(MediaAsset, asset_id)
    if asset is None or asset.episode_id != episode.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found.")
    role = body.ref_role.strip()
    if role and role not in REF_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ref_role must be identity-lock, motion, environment, audio, or empty.",
        )
    asset.ref_role = role
    episode.updated_at = utcnow()
    db.commit()
    db.refresh(asset)
    return media_out(asset)


@router.get("/api/media/{asset_id}")
def download_media(asset_id: str, user: ReadUser, db: DbDep):
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found.")
    get_episode(db, asset.episode_id, user)
    store = get_store()
    local = store.local_path(asset.path)
    if local is not None:
        if not local.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file missing from disk.")
        download_name = safe_filename(asset.original_name, "asset.bin")
        return FileResponse(local, media_type=asset.content_type, filename=download_name)
    data = store.get_bytes(asset.path)
    download_name = safe_filename(asset.original_name, "asset.bin")
    return Response(
        content=data,
        media_type=asset.content_type,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@router.delete("/api/media/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(asset_id: str, user: MediaOrIdentityUser, db: DbDep) -> None:
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found.")
    if asset.kind in {"sheet", "plate", "costume"}:
        refuse_unless(user, PERM_IDENTITY, field="sheets/plates/costumes")
    else:
        refuse_unless(user, PERM_MEDIA, field="preview/other media")
    get_episode(db, asset.episode_id, user)
    rel = asset.path
    episode = asset.episode
    for job in db.query(Job).filter(Job.media_id == asset.id).all():
        job.media_id = None
    for receipt in db.query(ContinuityReceipt).filter(ContinuityReceipt.media_id == asset.id).all():
        receipt.media_id = None
    db.delete(asset)
    episode.updated_at = utcnow()
    touch(episode.project)
    db.commit()
    get_store().delete(rel)
