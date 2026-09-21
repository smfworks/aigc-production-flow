"""Org/project episode metadata backup + restore.

Export is a zip of JSON metadata and a media manifest (paths/hashes). Restore
dry-run reports what would be created. Apply never deletes existing pack
revisions — it adds missing projects/episodes/revisions/media metadata.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .models import (
    Episode,
    MediaAsset,
    Organization,
    PackRevision,
    Project,
    utcnow,
)
from .packzip import slugify
from .shots import sync_shots_from_pack
from .store import get_store

BACKUP_VERSION = 1
KEEP_REVISIONS_NOTE = (
    "Pack revisions are preserved. Restore apply never deletes an existing "
    "PackRevision row. Missing revisions are added. Media files are restored "
    "from the zip when present. A manifest path is not rebound — that would "
    "point at another org's store object. Ids that already belong to another "
    "org are refused."
)
HONESTY = (
    "Metadata + media manifest backup. Not a CapCut project, not an NLE, not a "
    "full disk image. Likeness stills and engine MP4s should not live in git."
)


def _iso(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_json(raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Backup zip is not valid JSON: {exc}",
        ) from exc
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backup manifest must be a JSON object.",
        )
    return data


def export_org_backup(db: Session, org: Organization) -> bytes:
    store = get_store()
    projects = (
        db.query(Project)
        .filter(Project.organization_id == org.id)
        .order_by(Project.created_at.asc())
        .all()
    )
    project_rows: list[dict[str, Any]] = []
    episode_rows: list[dict[str, Any]] = []
    revision_rows: list[dict[str, Any]] = []
    media_rows: list[dict[str, Any]] = []
    files: list[tuple[str, bytes]] = []

    for project in projects:
        project_rows.append(
            {
                "id": project.id,
                "name": project.name,
                "slug": project.slug,
                "description": project.description,
                "still_adapter": project.still_adapter,
                "clip_adapter": project.clip_adapter,
                "budget_cap_units": project.budget_cap_units,
                "budget_hard_stop": project.budget_hard_stop,
                "retention_days": project.retention_days,
                "created_at": _iso(project.created_at),
            }
        )
        for episode in project.episodes:
            episode_rows.append(
                {
                    "id": episode.id,
                    "project_id": project.id,
                    "title": episode.title,
                    "chapter": episode.chapter,
                    "synopsis": episode.synopsis,
                    "review_state": episode.review_state,
                    "created_at": _iso(episode.created_at),
                }
            )
            for revision in episode.revisions:
                zip_bytes = b""
                zip_hash = ""
                if revision.zip_path:
                    try:
                        zip_bytes = store.get_bytes(revision.zip_path)
                        zip_hash = _sha256(zip_bytes)
                    except Exception:
                        zip_bytes = b""
                revision_rows.append(
                    {
                        "id": revision.id,
                        "episode_id": episode.id,
                        "filename": revision.filename,
                        "pack_json": revision.pack_json,
                        "gate_snapshot": revision.gate_snapshot,
                        "all_gates_green": revision.all_gates_green,
                        "zip_path": revision.zip_path,
                        "zip_sha256": zip_hash,
                        "created_by": revision.created_by,
                        "created_at": _iso(revision.created_at),
                    }
                )
                if zip_bytes:
                    files.append((f"revisions/{revision.id}.zip", zip_bytes))
            for asset in episode.media:
                blob = b""
                digest = ""
                missing = False
                if asset.path:
                    try:
                        blob = store.get_bytes(asset.path)
                        digest = _sha256(blob)
                    except Exception:
                        missing = True
                media_rows.append(
                    {
                        "id": asset.id,
                        "episode_id": episode.id,
                        "kind": asset.kind,
                        "original_name": asset.original_name,
                        "stored_name": asset.stored_name,
                        "content_type": asset.content_type,
                        "path": asset.path,
                        "entity_label": asset.entity_label,
                        "entity_type": asset.entity_type,
                        "notes": asset.notes,
                        "created_by": asset.created_by,
                        "approval_status": asset.approval_status or "draft",
                        "approved_by": asset.approved_by or "",
                        "approved_at": _iso(asset.approved_at),
                        "shot_id": asset.shot_id or "",
                        "edit_row_id": asset.edit_row_id or "",
                        "lock_keywords": asset.lock_keywords or "",
                        "sha256": digest,
                        "missing": missing or not bool(blob),
                    }
                )
                if blob:
                    files.append((f"media/{asset.id}/{asset.original_name or asset.stored_name}", blob))

    manifest = {
        "v": BACKUP_VERSION,
        "honesty": HONESTY,
        "keep_pack_revisions": True,
        "keep_note": KEEP_REVISIONS_NOTE,
        "exported_at": utcnow().isoformat(),
        "organization": {"id": org.id, "name": org.name, "is_default": bool(org.is_default)},
        "projects": project_rows,
        "episodes": episode_rows,
        "pack_revisions": revision_rows,
        "media_manifest": media_rows,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        for name, data in files:
            archive.writestr(name, data)
    return buf.getvalue()


def parse_backup(data: bytes) -> dict[str, Any]:
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty backup zip.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if "manifest.json" not in archive.namelist():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Backup zip needs manifest.json.",
                )
            manifest = _safe_json(archive.read("manifest.json"))
            files = {name: archive.read(name) for name in archive.namelist() if name != "manifest.json"}
    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not a zip backup.",
        ) from exc
    manifest["_files"] = files
    return manifest


def _row_id(row: Any) -> str:
    if not isinstance(row, dict):
        return ""
    return str(row.get("id") or "")


def cross_org_conflicts(db: Session, org: Organization, manifest: dict[str, Any]) -> list[str]:
    """Ids that already belong to a different organization. Restore must not write them."""
    conflicts: list[str] = []
    for row in manifest.get("projects") or []:
        existing = db.get(Project, _row_id(row))
        if existing is not None and existing.organization_id != org.id:
            conflicts.append(f"project {existing.id}")
    for row in manifest.get("episodes") or []:
        existing = db.get(Episode, _row_id(row))
        project = existing.project if existing is not None else None
        if existing is not None and (project is None or project.organization_id != org.id):
            conflicts.append(f"episode {existing.id}")
    for row in manifest.get("pack_revisions") or []:
        existing = db.get(PackRevision, _row_id(row))
        episode = existing.episode if existing is not None else None
        project = episode.project if episode is not None else None
        if existing is not None and (project is None or project.organization_id != org.id):
            conflicts.append(f"pack revision {existing.id}")
    for row in manifest.get("media_manifest") or []:
        existing = db.get(MediaAsset, _row_id(row))
        episode = existing.episode if existing is not None else None
        project = episode.project if episode is not None else None
        if existing is not None and (project is None or project.organization_id != org.id):
            conflicts.append(f"media {existing.id}")
    return conflicts


def _plan(db: Session, org: Organization, manifest: dict[str, Any]) -> dict[str, Any]:
    projects = manifest.get("projects") if isinstance(manifest.get("projects"), list) else []
    episodes = manifest.get("episodes") if isinstance(manifest.get("episodes"), list) else []
    revisions = manifest.get("pack_revisions") if isinstance(manifest.get("pack_revisions"), list) else []
    media = manifest.get("media_manifest") if isinstance(manifest.get("media_manifest"), list) else []
    would_create_projects: list[str] = []
    would_skip_projects: list[str] = []
    would_create_episodes: list[str] = []
    would_skip_episodes: list[str] = []
    would_add_revisions: list[str] = []
    would_keep_revisions: list[str] = []
    would_create_media: list[str] = []
    would_skip_media: list[str] = []
    for row in projects:
        if not isinstance(row, dict):
            continue
        existing = db.get(Project, str(row.get("id") or ""))
        slug = str(row.get("slug") or "")
        clash = (
            db.query(Project)
            .filter(Project.organization_id == org.id, Project.slug == slug)
            .first()
            if slug
            else None
        )
        if existing or clash:
            would_skip_projects.append(str(row.get("name") or row.get("id")))
        else:
            would_create_projects.append(str(row.get("name") or row.get("id")))
    for row in episodes:
        if not isinstance(row, dict):
            continue
        existing = db.get(Episode, str(row.get("id") or ""))
        if existing:
            would_skip_episodes.append(str(row.get("title") or row.get("id")))
        else:
            would_create_episodes.append(str(row.get("title") or row.get("id")))
    for row in revisions:
        if not isinstance(row, dict):
            continue
        existing = db.get(PackRevision, str(row.get("id") or ""))
        if existing:
            would_keep_revisions.append(str(row.get("id")))
        else:
            would_add_revisions.append(str(row.get("filename") or row.get("id")))
    for row in media:
        if not isinstance(row, dict):
            continue
        existing = db.get(MediaAsset, str(row.get("id") or ""))
        label = str(row.get("original_name") or row.get("id"))
        if existing:
            would_skip_media.append(label)
        else:
            would_create_media.append(label)
    return {
        "honesty": HONESTY,
        "keep_pack_revisions": True,
        "keep_note": KEEP_REVISIONS_NOTE,
        "organization": {"id": org.id, "name": org.name},
        "source_organization": manifest.get("organization") or {},
        "would_create_projects": would_create_projects,
        "would_skip_projects": would_skip_projects,
        "would_create_episodes": would_create_episodes,
        "would_skip_episodes": would_skip_episodes,
        "would_add_revisions": would_add_revisions,
        "would_keep_revisions": would_keep_revisions,
        "would_create_media": would_create_media,
        "would_skip_media": would_skip_media,
        "cross_org_conflicts": cross_org_conflicts(db, org, manifest),
        "dry_run": True,
        "applied": False,
    }


def restore_backup(
    db: Session,
    org: Organization,
    data: bytes,
    *,
    dry_run: bool,
    user_name: str,
) -> dict[str, Any]:
    manifest = parse_backup(data)
    plan = _plan(db, org, manifest)
    conflicts = list(plan.get("cross_org_conflicts") or [])
    if conflicts and not dry_run:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Backup ids belong to another organization. Cross-org restore is refused. "
                + "; ".join(conflicts[:8])
            ),
        )
    if dry_run:
        return plan
    files: dict[str, bytes] = manifest.get("_files") if isinstance(manifest.get("_files"), dict) else {}
    store = get_store()
    id_map_projects: dict[str, str] = {}
    created_projects = 0
    created_episodes = 0
    added_revisions = 0
    created_media = 0

    for row in manifest.get("projects") or []:
        if not isinstance(row, dict):
            continue
        old_id = str(row.get("id") or "")
        existing = db.get(Project, old_id) if old_id else None
        if existing:
            if existing.organization_id != org.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Backup project id belongs to another org. Cross-org restore is refused.",
                )
            id_map_projects[old_id] = existing.id
            continue
        slug = str(row.get("slug") or slugify(str(row.get("name") or "restored"), "restored"))
        clash = (
            db.query(Project)
            .filter(Project.organization_id == org.id, Project.slug == slug)
            .first()
        )
        if clash:
            id_map_projects[old_id] = clash.id
            continue
        project = Project(
            organization_id=org.id,
            name=str(row.get("name") or "Restored project"),
            slug=slug,
            description=str(row.get("description") or ""),
            still_adapter=str(row.get("still_adapter") or "stub"),
            clip_adapter=str(row.get("clip_adapter") or "stub"),
            budget_cap_units=row.get("budget_cap_units"),
            budget_hard_stop=bool(row.get("budget_hard_stop")),
            retention_days=row.get("retention_days"),
        )
        if old_id:
            project.id = old_id
        db.add(project)
        db.flush()
        id_map_projects[old_id] = project.id
        created_projects += 1

    id_map_episodes: dict[str, str] = {}
    for row in manifest.get("episodes") or []:
        if not isinstance(row, dict):
            continue
        old_id = str(row.get("id") or "")
        existing = db.get(Episode, old_id) if old_id else None
        if existing:
            project = existing.project
            if project is None or project.organization_id != org.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Backup episode id belongs to another org. Cross-org restore is refused.",
                )
            id_map_episodes[old_id] = existing.id
            continue
        project_id = id_map_projects.get(str(row.get("project_id") or ""))
        if not project_id:
            continue
        episode = Episode(
            project_id=project_id,
            title=str(row.get("title") or "Restored episode"),
            chapter=int(row.get("chapter") or 1),
            synopsis=str(row.get("synopsis") or ""),
            review_state=str(row.get("review_state") or "draft"),
        )
        if old_id:
            episode.id = old_id
        db.add(episode)
        db.flush()
        id_map_episodes[old_id] = episode.id
        created_episodes += 1

    for row in manifest.get("pack_revisions") or []:
        if not isinstance(row, dict):
            continue
        old_id = str(row.get("id") or "")
        if old_id and db.get(PackRevision, old_id):
            continue
        episode_id = id_map_episodes.get(str(row.get("episode_id") or ""))
        if not episode_id:
            continue
        episode = db.get(Episode, episode_id)
        if episode is None:
            continue
        zip_name = f"revisions/{old_id}.zip"
        zip_bytes = files.get(zip_name, b"")
        revision = PackRevision(
            episode_id=episode.id,
            filename=str(row.get("filename") or "restored.zip"),
            pack_json=row.get("pack_json") if isinstance(row.get("pack_json"), dict) else {},
            gate_snapshot=row.get("gate_snapshot") if isinstance(row.get("gate_snapshot"), dict) else {},
            all_gates_green=bool(row.get("all_gates_green")),
            zip_path="",
            created_by=str(row.get("created_by") or user_name),
        )
        if old_id:
            revision.id = old_id
        db.add(revision)
        db.flush()
        rel = Path(episode.id) / "revisions" / f"{revision.id}.zip"
        if zip_bytes:
            store.put(str(rel), zip_bytes)
            revision.zip_path = str(rel)
        sync_shots_from_pack(db, episode, revision)
        added_revisions += 1

    for row in manifest.get("media_manifest") or []:
        if not isinstance(row, dict):
            continue
        old_id = str(row.get("id") or "")
        if old_id and db.get(MediaAsset, old_id):
            continue
        episode_id = id_map_episodes.get(str(row.get("episode_id") or ""))
        if not episode_id:
            continue
        original = str(row.get("original_name") or row.get("stored_name") or "asset.bin")
        blob = b""
        prefix = f"media/{old_id}/"
        for name, data in files.items():
            if name.startswith(prefix):
                blob = data
                break
        asset = MediaAsset(
            episode_id=episode_id,
            kind=str(row.get("kind") or "other"),
            original_name=original,
            stored_name=str(row.get("stored_name") or original),
            content_type=str(row.get("content_type") or "application/octet-stream"),
            path="",
            entity_label=str(row.get("entity_label") or ""),
            entity_type=str(row.get("entity_type") or ""),
            notes=str(row.get("notes") or ""),
            created_by=str(row.get("created_by") or user_name),
            approval_status=str(row.get("approval_status") or "draft"),
            approved_by=str(row.get("approved_by") or ""),
            shot_id=str(row.get("shot_id") or ""),
            edit_row_id=str(row.get("edit_row_id") or ""),
            lock_keywords=str(row.get("lock_keywords") or ""),
        )
        if old_id:
            asset.id = old_id
        db.add(asset)
        db.flush()
        rel = Path(episode_id) / "restored" / f"{asset.id}_{slugify(Path(original).stem, 'asset')}{Path(original).suffix}"
        if blob:
            store.put(str(rel), blob)
            asset.path = str(rel)
        created_media += 1

    db.flush()
    plan.update(
        {
            "dry_run": False,
            "applied": True,
            "created_projects": created_projects,
            "created_episodes": created_episodes,
            "added_revisions": added_revisions,
            "created_media": created_media,
            "keep_pack_revisions": True,
        }
    )
    return plan
