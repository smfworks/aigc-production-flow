from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response

from ..audit import MEDIA_UPLOAD, record
from ..deps import DbDep, get_episode, touch
from ..models import ContinuityReceipt, ENTITY_TYPES, Job, MEDIA_KINDS, MediaAsset, utcnow
from ..packzip import slugify
from ..rbac import MediaUser, ReadUser
from ..schemas import MediaAssetOut
from ..store import get_store

router = APIRouter(tags=["media"])

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".txt", ".md"}
PREVIEW_SUFFIXES = IMAGE_SUFFIXES | {".json", ".mp4", ".webm", ".mov"}


@router.get("/api/episodes/{episode_id}/media", response_model=list[MediaAssetOut])
def list_media(episode_id: str, _user: ReadUser, db: DbDep) -> list[MediaAssetOut]:
    episode = get_episode(db, episode_id)
    return [MediaAssetOut.model_validate(row) for row in episode.media]


@router.post(
    "/api/episodes/{episode_id}/media",
    response_model=MediaAssetOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_media(
    episode_id: str,
    user: MediaUser,
    db: DbDep,
    file: UploadFile = File(...),
    kind: str = Form("other"),
    entity_label: str = Form(""),
    entity_type: str = Form(""),
    notes: str = Form(""),
) -> MediaAssetOut:
    episode = get_episode(db, episode_id)
    if kind not in MEDIA_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="kind must be sheet, plate, costume, preview, or other.",
        )
    entity_kind = entity_type.strip()
    if kind == "costume" and not entity_kind:
        entity_kind = "costume"
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
    return MediaAssetOut.model_validate(asset)


@router.get("/api/media/{asset_id}")
def download_media(asset_id: str, _user: ReadUser, db: DbDep):
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found.")
    store = get_store()
    local = store.local_path(asset.path)
    if local is not None:
        if not local.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file missing from disk.")
        return FileResponse(local, media_type=asset.content_type, filename=asset.original_name)
    data = store.get_bytes(asset.path)
    return Response(
        content=data,
        media_type=asset.content_type,
        headers={"Content-Disposition": f'attachment; filename="{asset.original_name}"'},
    )


@router.delete("/api/media/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(asset_id: str, _user: MediaUser, db: DbDep) -> None:
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found.")
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
