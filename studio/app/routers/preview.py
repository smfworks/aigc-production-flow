from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from ..deps import DbDep, get_episode, latest_revision, touch
from ..models import Shot, utcnow
from ..packzip import slugify
from ..preview import (
    apply_receipt,
    hop1_required_shots,
    mark_preview_watched,
    pack_of,
    parse_preview_bytes,
    receipt_blockers,
    receipt_complete,
    receipt_out,
    extend_ok,
)
from ..rbac import MutateUser, ReadUser
from ..store import get_store
from ..schemas import (
    ContinuityReceiptOut,
    PreviewDeskOut,
    PreviewDeskShot,
    PreviewWatchedSet,
    ReceiptSet,
)
from ..serializers import shot_out

router = APIRouter(tags=["preview"])

PREVIEW_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".txt",
    ".md",
    ".json",
    ".mp4",
    ".webm",
    ".mov",
}


def _get_shot(db, episode_id: str, shot_id: str) -> Shot:
    episode = get_episode(db, episode_id)
    shot = db.get(Shot, shot_id)
    if not shot or shot.episode_id != episode.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shot not found.")
    return shot


@router.get("/api/episodes/{episode_id}/preview-desk", response_model=PreviewDeskOut)
def get_preview_desk(episode_id: str, _user: ReadUser, db: DbDep) -> PreviewDeskOut:
    episode = get_episode(db, episode_id)
    pack = pack_of(episode)
    required = hop1_required_shots(episode, pack)
    required_ids = {row.id for row in required}
    shots = []
    blockers: list[dict[str, str]] = []
    complete_count = 0
    for shot in episode.shots:
        required_flag = shot.id in required_ids
        receipt = shot.receipt
        problems = receipt_blockers(receipt) if required_flag else []
        if required_flag and problems:
            blockers.append(
                {
                    "shot_id": shot.id,
                    "take": shot.take or "",
                    "reason": "; ".join(problems),
                }
            )
        if required_flag and not problems:
            complete_count += 1
        shots.append(
            PreviewDeskShot(
                shot=shot_out(shot),
                required=required_flag,
                complete=receipt_complete(receipt) if required_flag else True,
                extend_ok=extend_ok(receipt),
                blockers=problems,
            )
        )
    revision = latest_revision(episode)
    generate_ok_ready = bool(revision and revision.all_gates_green and not blockers)
    return PreviewDeskOut(
        episode_id=episode.id,
        required_count=len(required),
        complete_count=complete_count,
        generate_ok_ready=generate_ok_ready,
        blockers=blockers,
        shots=shots,
    )


@router.get(
    "/api/episodes/{episode_id}/shots/{shot_id}/receipt",
    response_model=ContinuityReceiptOut | None,
)
def get_receipt(episode_id: str, shot_id: str, _user: ReadUser, db: DbDep) -> ContinuityReceiptOut | None:
    shot = _get_shot(db, episode_id, shot_id)
    return receipt_out(shot.receipt)


@router.put(
    "/api/episodes/{episode_id}/shots/{shot_id}/receipt",
    response_model=ContinuityReceiptOut,
)
def set_receipt(
    episode_id: str, shot_id: str, body: ReceiptSet, user: MutateUser, db: DbDep
) -> ContinuityReceiptOut:
    shot = _get_shot(db, episode_id, shot_id)
    from ..notify import blocker_codes, notify_blockers_cleared

    before = blocker_codes(shot.episode)
    receipt = apply_receipt(
        db,
        shot,
        user_name=user.name,
        media_id=body.media_id,
        duration_s=body.duration_s,
        frames=body.frames,
        fps=body.fps,
        still_vs_lock=body.still_vs_lock,
        ng_reason=body.ng_reason,
        source=body.source,
        parse_media=body.parse_media,
        notes=body.notes,
        watched=body.watched,
    )
    shot.episode.updated_at = utcnow()
    touch(shot.episode.project)
    db.flush()
    notify_blockers_cleared(db, shot.episode, before, blocker_codes(shot.episode), actor=user.name)
    db.commit()
    db.refresh(receipt)
    return receipt_out(receipt)  # type: ignore[return-value]


@router.put(
    "/api/episodes/{episode_id}/shots/{shot_id}/preview-watched",
    response_model=ContinuityReceiptOut,
)
def set_preview_watched(
    episode_id: str, shot_id: str, body: PreviewWatchedSet, user: MutateUser, db: DbDep
) -> ContinuityReceiptOut:
    shot = _get_shot(db, episode_id, shot_id)
    if shot.receipt is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "receipt_incomplete",
                "message": "Attach hop-1 preview media and a continuity receipt before preview-watched.",
            },
        )
    from ..notify import blocker_codes, notify_blockers_cleared

    before = blocker_codes(shot.episode)
    receipt = mark_preview_watched(shot.receipt, user.name, body.watched)
    if body.note.strip():
        receipt.notes = (receipt.notes + "\n" + body.note.strip()).strip()
    shot.episode.updated_at = utcnow()
    touch(shot.episode.project)
    db.flush()
    notify_blockers_cleared(db, shot.episode, before, blocker_codes(shot.episode), actor=user.name)
    db.commit()
    db.refresh(receipt)
    return receipt_out(receipt)  # type: ignore[return-value]


@router.post(
    "/api/episodes/{episode_id}/shots/{shot_id}/preview",
    response_model=ContinuityReceiptOut,
    status_code=status.HTTP_201_CREATED,
)
async def attach_preview(
    episode_id: str,
    shot_id: str,
    user: MutateUser,
    db: DbDep,
    file: UploadFile | None = File(default=None),
    media_id: str = Form(""),
    duration_s: str = Form(""),
    frames: str = Form(""),
    fps: str = Form(""),
    still_vs_lock: str = Form(""),
    ng_reason: str = Form(""),
    notes: str = Form(""),
    watched: str = Form(""),
) -> ContinuityReceiptOut:
    from ..models import MediaAsset

    shot = _get_shot(db, episode_id, shot_id)
    episode = shot.episode
    attached_id = media_id.strip() or None
    parsed: dict = {}
    if file is not None:
        original = file.filename or "preview.bin"
        suffix = Path(original).suffix.lower()
        if suffix and suffix not in PREVIEW_SUFFIXES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Preview media: json/txt/md receipts, images, or mp4/webm (gitignored local store).",
            )
        data = await file.read()
        if not data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload.")
        parsed = parse_preview_bytes(data, suffix=suffix, content_type=file.content_type or "")
        asset = MediaAsset(
            episode_id=episode.id,
            kind="preview",
            original_name=original,
            stored_name="",
            content_type=file.content_type or "application/octet-stream",
            path="",
            entity_label=shot.take or "",
            notes=f"hop-1 preview for shot {shot.id}",
            created_by=user.name,
        )
        db.add(asset)
        db.flush()
        stored = f"{asset.id}_{slugify(Path(original).stem, 'preview')}{suffix}"
        rel = Path(episode.id) / "previews" / stored
        get_store().put(str(rel), data)
        asset.stored_name = stored
        asset.path = str(rel)
        attached_id = asset.id
    duration_value = _float(duration_s)
    frames_value = _int(frames)
    fps_value = _float(fps)
    source = None
    if duration_value is None and parsed.get("duration_s") is not None:
        duration_value = float(parsed["duration_s"])
        source = "parsed"
    if frames_value is None and parsed.get("frames") is not None:
        frames_value = int(parsed["frames"])
        source = source or "parsed"
    if fps_value is None and parsed.get("fps") is not None:
        fps_value = float(parsed["fps"])
    lock_note = still_vs_lock.strip() or str(parsed.get("still_vs_lock") or "")
    watched_flag = None
    if watched.strip().lower() in {"1", "true", "yes"}:
        watched_flag = True
    elif watched.strip().lower() in {"0", "false", "no"}:
        watched_flag = False
    receipt = apply_receipt(
        db,
        shot,
        user_name=user.name,
        media_id=attached_id,
        duration_s=duration_value,
        frames=frames_value,
        fps=fps_value,
        still_vs_lock=lock_note if lock_note else None,
        ng_reason=ng_reason,
        source=source or ("manual" if duration_s.strip() or frames.strip() else None),
        parse_media=not parsed,
        notes=notes,
        watched=watched_flag,
    )
    episode.updated_at = utcnow()
    touch(episode.project)
    db.commit()
    db.refresh(receipt)
    return receipt_out(receipt)  # type: ignore[return-value]


def _float(raw: str) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="duration_s / fps must be a number.") from exc


def _int(raw: str) -> int | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError as extra:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="frames must be an integer.") from extra
