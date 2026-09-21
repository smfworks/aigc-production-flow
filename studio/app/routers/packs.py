import json
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from ..audit import PACK_DIFF, PACK_EXPORT, PACK_IMPORT, PACK_SAVE, record
from ..blankpack import pack_zip_bytes
from ..createflow import seed_blank_pack
from ..deps import DbDep, get_episode, latest_revision, touch
from ..gates import gate_snapshot
from ..handoff import consume_handoff, get_live_handoff, read_handoff_bytes
from ..models import PackRevision, utcnow
from ..packdiff import diff_packs, pack_payload, revision_ref
from ..packzip import MAX_PACK_JSON_BYTES, PackZipError, extract_pack_json, safe_filename, slugify
from ..rbac import CraftUser, PackUser, ReadUser
from ..schemas import (
    GateSnapshotOut,
    PackDiffOut,
    PackDiffRef,
    PackJsonIn,
    PackResetIn,
    PackRevisionOut,
    PackRevisionSummary,
    PackSaveOut,
)
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


def _get_revision(db, episode, revision_id: str) -> PackRevision:
    revision = db.get(PackRevision, revision_id)
    if not revision or revision.episode_id != episode.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found.")
    return revision


def _apply_zip(
    db,
    episode,
    user,
    *,
    data: bytes,
    filename: str,
    handoff_id: str = "",
    from_handoff: bool = False,
) -> PackRevision:
    from ..notify import blocker_codes, notify_blockers_cleared

    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload.")
    try:
        pack = extract_pack_json(data)
    except PackZipError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    before = blocker_codes(episode)
    snapshot = gate_snapshot(pack)
    revision = PackRevision(
        episode_id=episode.id,
        filename=filename or f"pack-{slugify(str(pack.get('title') or episode.title))}.zip",
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
    if from_handoff and handoff_id and user.org_id:
        row = get_live_handoff(db, handoff_id, user.org_id)
        consume_handoff(db, row)
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
            "handoff_id": handoff_id or None,
        },
    )
    db.flush()
    notify_blockers_cleared(db, episode, before, blocker_codes(episode), actor=user.name)
    return revision


def _diff_out(
    *,
    left: PackRevision | None,
    right: PackRevision | None,
    right_pack: dict | None = None,
    right_filename: str = "",
    candidate: bool = False,
) -> PackDiffOut:
    left_pack = pack_payload(left)
    if right is not None:
        right_body = pack_payload(right)
        right_snap = right.gate_snapshot if isinstance(right.gate_snapshot, dict) else None
    else:
        right_body = right_pack or {}
        right_snap = None
    left_snap = left.gate_snapshot if left and isinstance(left.gate_snapshot, dict) else None
    payload = diff_packs(left_pack, right_body, left_snapshot=left_snap, right_snapshot=right_snap)
    right_ref: PackDiffRef | None
    if right is not None:
        right_ref = PackDiffRef.model_validate({**revision_ref(right), "candidate": False})
    else:
        snap = gate_snapshot(right_body) if right_body else {}
        right_ref = PackDiffRef(
            filename=right_filename or "candidate.zip",
            label=right_filename or "candidate import",
            candidate=True,
            all_gates_green=bool(snap.get("all_green")),
        )
    return PackDiffOut(
        honesty=payload["honesty"],
        left=PackDiffRef.model_validate(revision_ref(left)) if left else None,
        right=right_ref,
        gates=payload["gates"],
        entity_schedule=payload["entity_schedule"],
        edit_list=payload["edit_list"],
        identity_keywords=payload["identity_keywords"],
        summary=payload["summary"],
        auto_generate=False,
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
    return _revision_out(_get_revision(db, episode, revision_id))


@router.get(
    "/api/episodes/{episode_id}/revisions/{left_id}/diff/{right_id}",
    response_model=PackDiffOut,
)
def diff_revisions(
    episode_id: str, left_id: str, right_id: str, user: ReadUser, db: DbDep
) -> PackDiffOut:
    episode = get_episode(db, episode_id, user)
    left = _get_revision(db, episode, left_id)
    right = _get_revision(db, episode, right_id)
    result = _diff_out(left=left, right=right)
    record(
        db,
        actor=user.name,
        action=PACK_DIFF,
        project_id=episode.project_id,
        episode_id=episode.id,
        entity_type="pack",
        entity_id=right.id,
        detail={"left_id": left.id, "right_id": right.id, "candidate": False},
    )
    db.commit()
    return result


@router.get("/api/episodes/{episode_id}/gates", response_model=GateSnapshotOut)
def get_gates(episode_id: str, user: ReadUser, db: DbDep) -> GateSnapshotOut:
    episode = get_episode(db, episode_id, user)
    revision = latest_revision(episode)
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pack revision yet. Start a blank pack, template, or brain dump in Studio. Zip import is optional.",
        )
    return GateSnapshotOut.model_validate(revision.gate_snapshot)


@router.post("/api/episodes/{episode_id}/pack/diff", response_model=PackDiffOut)
async def preview_import_diff(
    episode_id: str,
    user: PackUser,
    db: DbDep,
    file: UploadFile | None = File(None),
    handoff_id: str = Form(""),
) -> PackDiffOut:
    episode = get_episode(db, episode_id, user)
    data, filename, _source = await _load_zip(db, user, file=file, handoff_id=handoff_id)
    try:
        pack = extract_pack_json(data)
    except PackZipError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    latest = latest_revision(episode)
    result = _diff_out(
        left=latest,
        right=None,
        right_pack=pack,
        right_filename=filename,
        candidate=True,
    )
    record(
        db,
        actor=user.name,
        action=PACK_DIFF,
        project_id=episode.project_id,
        episode_id=episode.id,
        entity_type="pack",
        entity_id=latest.id if latest else "",
        detail={"candidate": True, "filename": filename, "handoff_id": handoff_id or None},
    )
    db.commit()
    return result


@router.post(
    "/api/episodes/{episode_id}/pack",
    response_model=PackRevisionOut,
    status_code=status.HTTP_201_CREATED,
)
async def import_pack(
    episode_id: str,
    user: PackUser,
    db: DbDep,
    file: UploadFile | None = File(
        None, description="Pack zip exported from the builder (must include pack.json)."
    ),
    handoff_id: str = Form(""),
) -> PackRevisionOut:
    episode = get_episode(db, episode_id, user)
    data, filename, source = await _load_zip(db, user, file=file, handoff_id=handoff_id)
    revision = _apply_zip(
        db,
        episode,
        user,
        data=data,
        filename=filename,
        handoff_id=handoff_id.strip(),
        from_handoff=source == "handoff",
    )
    db.commit()
    db.refresh(revision)
    return _revision_out(revision)


async def _load_zip(db, user, *, file: UploadFile | None, handoff_id: str) -> tuple[bytes, str, str]:
    """Return (bytes, filename, source). A live handoff_id wins over a simultaneous file part."""
    token = (handoff_id or "").strip()
    if token:
        if not user.org_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handoff not found.")
        row = get_live_handoff(db, token, user.org_id)
        return read_handoff_bytes(row), row.filename, "handoff"
    if file is not None:
        data = await file.read()
        if data:
            return data, safe_filename(file.filename or "pack.zip", "pack.zip"), "upload"
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Provide a pack zip file or a handoff_id from Open in Studio.",
    )


@router.get("/api/episodes/{episode_id}/pack")
def export_pack(episode_id: str, user: ReadUser, db: DbDep):
    episode = get_episode(db, episode_id, user)
    revision = latest_revision(episode)
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pack revision yet. Start a blank pack, template, or brain dump in Studio. Zip import is optional.",
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
            filename=safe_filename(revision.filename, "pack.zip"),
        )
    data = store.get_bytes(revision.zip_path)
    from fastapi.responses import Response

    download_name = safe_filename(revision.filename, "pack.zip")
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


def _prepare_editor_pack(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pack must be a JSON object.")
    encoded = json.dumps(raw).encode("utf-8")
    if len(encoded) > MAX_PACK_JSON_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="pack.json is too large.")
    pack = dict(raw)
    if not isinstance(pack.get("look"), dict):
        pack["look"] = {
            "styleLine": "",
            "paletteGrade": "",
            "era": "",
            "lensGrain": "",
            "extrasForbidden": "",
        }
    if not isinstance(pack.get("title"), str):
        pack["title"] = str(pack.get("title") or "")
    meta = pack.get("studioMeta") if isinstance(pack.get("studioMeta"), dict) else {}
    meta = dict(meta)
    meta.setdefault("source", "studio-editor")
    meta.setdefault("status", "draft")
    meta["generate_ready"] = False
    meta["model_ran"] = bool(meta.get("model_ran"))
    meta["note"] = str(meta.get("note") or "Saved from the in-studio pack editor. Not a generate.")
    pack["studioMeta"] = meta
    return pack


def _save_pack_dict(db, episode, user, pack: dict) -> PackRevision:
    snapshot = gate_snapshot(pack)
    filename = f"studio-{slugify(str(pack.get('title') or episode.title))}.zip"
    data = pack_zip_bytes(pack)
    revision = PackRevision(
        episode_id=episode.id,
        filename=filename,
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
        action=PACK_SAVE,
        project_id=episode.project_id,
        episode_id=episode.id,
        entity_type="pack",
        entity_id=revision.id,
        detail={
            "filename": revision.filename,
            "all_gates_green": revision.all_gates_green,
            "generate_ready": False,
            "source": "studio-editor",
        },
    )
    return revision


@router.post("/api/episodes/{episode_id}/pack/json", response_model=PackSaveOut)
def save_pack_json(
    episode_id: str, body: PackJsonIn, user: CraftUser, db: DbDep
) -> PackSaveOut:
    """Autosave from the in-studio stages. A new revision. Does not generate."""
    episode = get_episode(db, episode_id, user)
    pack = _prepare_editor_pack(body.pack)
    revision = _save_pack_dict(db, episode, user, pack)
    db.commit()
    return PackSaveOut(
        project_id=episode.project_id,
        episode_id=episode.id,
        revision_id=revision.id,
        filename=revision.filename,
        gates_green=bool(revision.all_gates_green),
        generate_ready=False,
    )


@router.post("/api/episodes/{episode_id}/pack/blank", response_model=PackSaveOut)
def reset_blank_pack(
    episode_id: str, body: PackResetIn, user: CraftUser, db: DbDep
) -> PackSaveOut:
    """Replace the working pack with a blank revision. Earlier revisions stay."""
    episode = get_episode(db, episode_id, user)
    if episode.revisions and (body.confirm or "").strip() != "reset":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "confirm_reset",
                "message": (
                    "Resetting replaces the working pack with a blank one. "
                    "Look stays blank and gates stay red. Earlier revisions are kept. "
                    "Send confirm=reset after an in-app confirm."
                ),
            },
        )
    revision = seed_blank_pack(db, episode, user.name)
    record(
        db,
        actor=user.name,
        action=PACK_SAVE,
        project_id=episode.project_id,
        episode_id=episode.id,
        entity_type="pack",
        entity_id=revision.id,
        detail={"source": "blank-reset", "gates_green": False, "generate_ready": False},
    )
    touch(episode.project)
    db.commit()
    return PackSaveOut(
        project_id=episode.project_id,
        episode_id=episode.id,
        revision_id=revision.id,
        filename=revision.filename,
        gates_green=False,
        generate_ready=False,
    )
