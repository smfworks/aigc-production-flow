"""Create a project or episode pack inside Studio. No zip upload required."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from .blankpack import empty_pack, pack_zip_bytes
from .braindump import draft_from_dump
from .models import Episode, PackRevision, Project
from .packzip import slugify
from .verticals import seed_pack_revision, template_zip_bytes


def _filename(prefix: str, title: str) -> str:
    return f"{prefix}-{slugify(title or 'pack', 'pack')}.zip"


def seed_blank_pack(db, episode: Episode, user_name: str) -> PackRevision:
    pack = empty_pack(episode.title or "")
    return seed_pack_revision(
        db,
        episode,
        user_name,
        pack_zip_bytes(pack),
        _filename("blank", episode.title or pack["title"]),
    )


def seed_brain_pack(
    db,
    episode: Episode,
    user_name: str,
    text: str,
    *,
    title: str = "",
) -> tuple[PackRevision, dict[str, Any]]:
    try:
        pack, honesty = draft_from_dump(text, title=title or episode.title or "")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if pack.get("title") and not (episode.title or "").strip():
        episode.title = str(pack["title"])[:200]
    if pack.get("logLine"):
        episode.log_line = str(pack["logLine"])[:2000]
    episode.synopsis = (text or "").strip()[:2000]
    revision = seed_pack_revision(
        db,
        episode,
        user_name,
        pack_zip_bytes(pack),
        _filename("brain-draft", str(pack.get("title") or episode.title)),
    )
    return revision, honesty


def seed_template_pack(db, episode: Episode, user_name: str, template_id: str) -> PackRevision:
    data = template_zip_bytes(template_id)
    return seed_pack_revision(
        db,
        episode,
        user_name,
        data,
        _filename(slugify(template_id, "template"), template_id),
    )


def new_episode(
    db,
    project: Project,
    *,
    title: str,
    chapter: int,
    season: int,
    sequence: int,
    synopsis: str = "",
    log_line: str = "",
    map_notes: str = "",
    dialogue: str = "",
) -> Episode:
    episode = Episode(
        project_id=project.id,
        title=title.strip() or "Ep 1",
        chapter=chapter,
        season=season,
        sequence_index=sequence,
        synopsis=synopsis.strip(),
        log_line=log_line.strip(),
        map_notes=map_notes.strip(),
        dialogue=dialogue.strip(),
        review_state="draft",
    )
    db.add(episode)
    db.flush()
    return episode


def start_project(
    db,
    *,
    org_id: str,
    user_name: str,
    name: str,
    description: str,
    mode: str,
    template_id: str | None,
    brain_dump: str,
    episode_title: str,
    unique_slug,
    still_adapter: str = "stub",
    clip_adapter: str = "stub",
) -> tuple[Project, Episode, PackRevision, dict[str, Any]]:
    title = (name or "").strip()
    if mode == "brain" and not title:
        title = (brain_dump or "").strip().splitlines()[0][:80] if (brain_dump or "").strip() else ""
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project name is required.")
    if mode == "template" and not (template_id or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pick a vertical template.")
    if mode == "brain" and not (brain_dump or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Brain dump is empty.")
    if mode not in {"blank", "template", "brain"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mode must be blank, template, or brain.")

    project = Project(
        organization_id=org_id,
        name=title[:200],
        slug=unique_slug(db, org_id, title),
        description=(description or "").strip(),
        still_adapter=still_adapter or "stub",
        clip_adapter=clip_adapter or "stub",
    )
    db.add(project)
    db.flush()
    episode = new_episode(
        db,
        project,
        title=(episode_title or "Ep 1").strip() or "Ep 1",
        chapter=1,
        season=1,
        sequence=1,
        synopsis=(description or "").strip(),
    )
    honesty: dict[str, Any] = {
        "model_ran": False,
        "model": "none",
        "source": mode,
        "note": "Blank pack. Look is blank. No model ran.",
        "generate_ready": False,
    }
    if mode == "template":
        revision = seed_template_pack(db, episode, user_name, template_id or "")
        honesty["note"] = "Vertical template. Gates stay red. No fake generate."
        honesty["source"] = "template"
    elif mode == "brain":
        revision, honesty = seed_brain_pack(db, episode, user_name, brain_dump, title=title)
    else:
        revision = seed_blank_pack(db, episode, user_name)
    return project, episode, revision, honesty
