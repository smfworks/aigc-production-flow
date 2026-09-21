"""Vertical pack templates. Structured empty packs — gates stay red, no fake generate."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from .config import get_settings
from .gates import gate_snapshot
from .models import Episode, PackRevision, Project
from .packzip import PackZipError, extract_pack_json, slugify, write_bytes
from .shots import sync_shots_from_pack

STAGES = ["script", "assets", "storyboard", "preview"]


def templates_root() -> Path:
    settings = get_settings()
    if (settings.templates_root or "").strip():
        return Path(settings.templates_root).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "templates" / "verticals"


def _read_meta(folder: Path) -> dict[str, Any] | None:
    meta_path = folder / "vertical.json"
    if not meta_path.is_file():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not data.get("id"):
        return None
    return {
        "id": str(data.get("id")),
        "name": str(data.get("name") or folder.name),
        "blurb": str(data.get("blurb") or ""),
        "still_adapter": str(data.get("still_adapter") or "stub"),
        "clip_adapter": str(data.get("clip_adapter") or "stub"),
        "stages": list(data.get("stages") or STAGES),
        "gates_green": False,
        "fake_generate": False,
        "folder": str(folder),
    }


def list_templates() -> list[dict[str, Any]]:
    root = templates_root()
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        meta = _read_meta(child)
        if meta:
            rows.append(meta)
    return rows


def get_template(template_id: str) -> dict[str, Any]:
    wanted = (template_id or "").strip()
    for row in list_templates():
        if row["id"] == wanted:
            return row
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Unknown vertical template: {template_id}",
    )


def template_zip_bytes(template_id: str) -> bytes:
    meta = get_template(template_id)
    folder = Path(meta["folder"])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            if path.name == "vertical.json":
                continue
            rel = path.relative_to(folder).as_posix()
            archive.write(path, f"{folder.name}/{rel}")
    data = buf.getvalue()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Vertical template is empty.",
        )
    try:
        extract_pack_json(data)
    except PackZipError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vertical template pack.json is invalid: {exc}",
        ) from exc
    return data


def seed_pack_revision(db, episode: Episode, user_name: str, data: bytes, filename: str) -> PackRevision:
    pack = extract_pack_json(data)
    snapshot = gate_snapshot(pack)
    settings = get_settings()
    revision = PackRevision(
        episode_id=episode.id,
        filename=filename,
        pack_json=pack,
        gate_snapshot=snapshot,
        all_gates_green=bool(snapshot["all_green"]),
        zip_path="",
        created_by=user_name,
    )
    db.add(revision)
    db.flush()
    rel = Path(episode.id) / "revisions" / f"{revision.id}.zip"
    write_bytes(settings.media_path / rel, data)
    revision.zip_path = str(rel)
    sync_shots_from_pack(db, episode, revision)
    return revision


def create_project_from_template(
    db,
    *,
    org_id: str,
    template_id: str,
    user_name: str,
    name: str | None = None,
    description: str | None = None,
    still_adapter: str | None = None,
    clip_adapter: str | None = None,
    unique_slug,
) -> tuple[Project, Episode, PackRevision]:
    meta = get_template(template_id)
    title = (name or meta["name"]).strip() or meta["name"]
    slug = unique_slug(db, org_id, title)
    project = Project(
        organization_id=org_id,
        name=title,
        slug=slug,
        description=(description if description is not None else meta["blurb"]).strip(),
        still_adapter=(still_adapter or meta["still_adapter"] or "stub").strip() or "stub",
        clip_adapter=(clip_adapter or meta["clip_adapter"] or "stub").strip() or "stub",
    )
    db.add(project)
    db.flush()
    episode = Episode(
        project_id=project.id,
        title="Ep 1",
        chapter=1,
        synopsis=meta["blurb"],
        review_state="draft",
    )
    db.add(episode)
    db.flush()
    data = template_zip_bytes(template_id)
    revision = seed_pack_revision(
        db,
        episode,
        user_name,
        data,
        f"{slugify(meta['id'])}-template.zip",
    )
    return project, episode, revision
