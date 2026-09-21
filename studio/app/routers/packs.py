from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from ..audit import PACK_EXPORT, PACK_IMPORT, record
from ..deps import DbDep, get_episode, latest_revision, touch
from ..gates import gate_snapshot
from ..models import PackRevision, utcnow
from ..packzip import PackZipError, extract_pack_json, slugify
from ..rbac import PackUser, ReadUser
from ..schemas import GateSnapshotOut, PackRevisionOut, PackRevisionSummary
from ..shots import sync_shots_from_pack
from ..store import get_store

router = APIRouter(tags=["packs"])


def _revision_out(revision: PackRevision) -> PackRevisionOut:
    return PackRevisionOut(
        id=revision.id,
        episode_id=revision.episode_id,
        filename=revision.filename,
        all_gates_green=revision.all_gates_green,
        created_by=revision.created_by,
        created_at=revision.created_at,
        pack=revision.pack_json,
        gate_snapshot=GateSnapshotOut.model_validate(revision.gate_snapshot),
    )


@router.get("/api/episodes/{episode_id}/revisions", response_model=list[PackRevisionSummary])
def list_revisions(episode_id: str, user: ReadUser, db: DbDep) -> list[PackRevisionSummary]:
    episode = get_episode(db, episode_id, user)
    return [PackRevisionSummary.model_validate(row) for row in episode.revisions]


@router.get("/api/episodes/{episode_id}/revisions/{revision_id}", response_model=PackRevisionOut)
def get_revision(
    episode_id: str, revision_id: str, user: ReadUser, db: DbDep
) -> PackRevisionOut:
    episode = get_episode(db, episode_id, user)
    revision = db.get(PackRevision, revision_id)
    if not revision or revision.episode_id != episode.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found.")
    return _revision_out(revision)


@router.get("/api/episodes/{episode_id}/gates", response_model=GateSnapshotOut)
def get_gates(episode_id: str, user: ReadUser, db: DbDep) -> GateSnapshotOut:
    episode = get_episode(db, episode_id, user)
    revision = latest_revision(episode)
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pack revision yet. Import a pack zip first.",
        )
    return GateSnapshotOut.model_validate(revision.gate_snapshot)


@router.post(
    "/api/episodes/{episode_id}/pack",
    response_model=PackRevisionOut,
    status_code=status.HTTP_201_CREATED,
)
async def import_pack(
    episode_id: str,
    user: PackUser,
    db: DbDep,
    file: UploadFile = File(..., description="Pack zip exported from the builder (must include pack.json)."),
) -> PackRevisionOut:
    episode = get_episode(db, episode_id, user)
    from ..notify import blocker_codes

    before = blocker_codes(episode)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload.")
    try:
        pack = extract_pack_json(data)
    except PackZipError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    snapshot = gate_snapshot(pack)
    revision = PackRevision(
        episode_id=episode.id,
        filename=file.filename or f"pack-{slugify(str(pack.get('title') or episode.title))}.zip",
        pack_json=pack,
        gate_snapshot=snapshot,
        all_gates_green=bool(snapshot["all_green"]),
        zip_path="",
        created_by=user.name,
    )
    db.add(revision)
    db.flush()
    rel = Path(episode.id) / "revisions" / f"{revision.id}.zip"
    get_store().put(str(rel), data)
    revision.zip_path = str(rel)
    sync_shots_from_pack(db, episode, revision)
    episode.updated_at = utcnow()
    touch(episode.project)
    record(
        db,
        actor=user.name,
        action=PACK_IMPORT,
        project_id=episode.project_id,
        episode_id=episode.id,
        entity_type="pack",
        entity_id=revision.id,
        detail={
            "filename": revision.filename,
            "all_gates_green": revision.all_gates_green,
        },
    )
    db.flush()
    from ..notify import blocker_codes, notify_blockers_cleared

    notify_blockers_cleared(db, episode, before, blocker_codes(episode), actor=user.name)
    db.commit()
    db.refresh(revision)
    return _revision_out(revision)


@router.get("/api/episodes/{episode_id}/pack")
def export_pack(episode_id: str, user: ReadUser, db: DbDep):
    episode = get_episode(db, episode_id, user)
    revision = latest_revision(episode)
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pack revision yet. Import a pack zip first.",
        )
    store = get_store()
    local = store.local_path(revision.zip_path)
    record(
        db,
        actor=user.name,
        action=PACK_EXPORT,
        project_id=episode.project_id,
        episode_id=episode.id,
        entity_type="pack",
        entity_id=revision.id,
        detail={"filename": revision.filename},
    )
    db.commit()
    if local is not None:
        if not local.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stored pack zip is missing from the media store.",
            )
        return FileResponse(
            local,
            media_type="application/zip",
            filename=revision.filename,
        )
    data = store.get_bytes(revision.zip_path)
    from fastapi.responses import Response

    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{revision.filename}"'},
    )
