from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from ..config import get_settings
from ..deps import DbDep, UserDep, get_episode, touch
from ..models import ENTITY_TYPES, MEDIA_KINDS, MediaAsset, utcnow
from ..packzip import slugify, write_bytes
from ..schemas import MediaAssetOut

router = APIRouter(tags=["media"])

ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".txt", ".md"}


@router.get("/api/episodes/{episode_id}/media", response_model=list[MediaAssetOut])
def list_media(episode_id: str, _user: UserDep, db: DbDep) -> list[MediaAssetOut]:
    episode = get_episode(db, episode_id)
    return [MediaAssetOut.model_validate(row) for row in episode.media]


@router.post(
    "/api/episodes/{episode_id}/media",
    response_model=MediaAssetOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_media(
    episode_id: str,
    user: UserDep,
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
            detail="kind must be sheet, plate, costume, or other.",
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
    if suffix and suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refusing this file type. Sheets/plates: png, jpg, webp, tiff. Notes: txt/md. No MP4s.",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload.")
    if suffix in {".mp4", ".mov"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Do not store engine MP4s in this public flow.",
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
    settings = get_settings()
    write_bytes(settings.media_path / rel, data)
    asset.stored_name = stored
    asset.path = str(rel)
    episode.updated_at = utcnow()
    touch(episode.project)
    db.commit()
    db.refresh(asset)
    return MediaAssetOut.model_validate(asset)


@router.get("/api/media/{asset_id}")
def download_media(asset_id: str, _user: UserDep, db: DbDep) -> FileResponse:
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found.")
    path = get_settings().media_path / asset.path
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file missing from disk.")
    return FileResponse(path, media_type=asset.content_type, filename=asset.original_name)


@router.delete("/api/media/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(asset_id: str, _user: UserDep, db: DbDep) -> None:
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found.")
    path = get_settings().media_path / asset.path
    episode = asset.episode
    db.delete(asset)
    episode.updated_at = utcnow()
    touch(episode.project)
    db.commit()
    if path.is_file():
        path.unlink()
