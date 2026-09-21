from fastapi import APIRouter, HTTPException, status

from ..audit import BRAIN_DUMP, EPISODE_REORDER, PACK_IMPORT, record
from ..createflow import seed_blank_pack, seed_brain_pack, seed_template_pack
from ..deps import DbDep, get_episode, get_project, touch
from ..models import Episode, utcnow
from ..rbac import ReadUser, ScriptUser
from ..schemas import BrainDumpIn, DraftHonestyOut, EpisodeCreate, EpisodeOut, EpisodeReorder, EpisodeUpdate
from ..serializers import episode_out

router = APIRouter(tags=["episodes"])


def _episodes(db, project_id: str) -> list[Episode]:
    return (
        db.query(Episode)
        .filter(Episode.project_id == project_id)
        .order_by(Episode.season.asc(), Episode.sequence_index.asc(), Episode.chapter.asc())
        .all()
    )


def _next_index(db, project_id: str, season: int) -> int:
    episodes = (
        db.query(Episode)
        .filter(Episode.project_id == project_id, Episode.season == season)
        .all()
    )
    if not episodes:
        return 1
    return max(row.sequence_index or row.chapter or 0 for row in episodes) + 1


def _clash(
    db,
    project_id: str,
    season: int,
    chapter: int,
    sequence: int,
    exclude_id: str | None = None,
) -> Episode | None:
    rows = (
        db.query(Episode)
        .filter(Episode.project_id == project_id, Episode.season == season)
        .all()
    )
    for row in rows:
        if exclude_id and row.id == exclude_id:
            continue
        if row.chapter == chapter or row.sequence_index == sequence:
            return row
    return None


@router.get("/api/projects/{project_id}/episodes", response_model=list[EpisodeOut])
def list_episodes(project_id: str, user: ReadUser, db: DbDep) -> list[EpisodeOut]:
    get_project(db, project_id, user)
    return [episode_out(row) for row in _episodes(db, project_id)]


@router.post(
    "/api/projects/{project_id}/episodes",
    response_model=EpisodeOut,
    status_code=status.HTTP_201_CREATED,
)
def create_episode(
    project_id: str, body: EpisodeCreate, user: ScriptUser, db: DbDep
) -> EpisodeOut:
    project = get_project(db, project_id, user)
    season = body.season or 1
    sequence = body.sequence or _next_index(db, project.id, season)
    chapter = body.chapter if body.chapter is not None else sequence
    if _clash(db, project.id, season, chapter, sequence):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Season {season} sequence {sequence} (chapter {chapter}) already exists.",
        )
    episode = Episode(
        project_id=project.id,
        title=body.title.strip(),
        chapter=chapter,
        season=season,
        sequence_index=sequence,
        synopsis=body.synopsis.strip(),
        log_line=body.log_line.strip(),
        map_notes=body.map_notes.strip(),
        dialogue=body.dialogue.strip(),
        review_state="draft",
    )
    db.add(episode)
    db.flush()
    if (body.brain_dump or "").strip():
        revision, honesty = seed_brain_pack(
            db, episode, user.name, body.brain_dump, title=episode.title
        )
        record(
            db,
            actor=user.name,
            action=BRAIN_DUMP,
            project_id=project.id,
            episode_id=episode.id,
            entity_type="pack",
            entity_id=revision.id,
            detail={
                "model_ran": honesty.get("model_ran"),
                "model": honesty.get("model"),
                "gates_green": bool(revision.all_gates_green),
                "generate_ready": False,
            },
        )
    elif (body.template_id or "").strip():
        revision = seed_template_pack(db, episode, user.name, body.template_id.strip())
        record(
            db,
            actor=user.name,
            action=PACK_IMPORT,
            project_id=project.id,
            episode_id=episode.id,
            entity_type="pack",
            entity_id=revision.id,
            detail={"template_id": body.template_id, "source": "template", "fake_generate": False},
        )
    elif body.pack == "blank":
        revision = seed_blank_pack(db, episode, user.name)
        record(
            db,
            actor=user.name,
            action=PACK_IMPORT,
            project_id=project.id,
            episode_id=episode.id,
            entity_type="pack",
            entity_id=revision.id,
            detail={"source": "blank", "gates_green": False, "fake_generate": False},
        )
    touch(project)
    db.commit()
    db.refresh(episode)
    return episode_out(episode)


@router.post("/api/projects/{project_id}/episodes/reorder", response_model=list[EpisodeOut])
def reorder_episodes(
    project_id: str, body: EpisodeReorder, user: ScriptUser, db: DbDep
) -> list[EpisodeOut]:
    """Rewrite season/sequence for every episode. Order is the writer-facing leftover."""
    project = get_project(db, project_id, user)
    rows = _episodes(db, project.id)
    by_id = {row.id: row for row in rows}
    ids = [item.id for item in body.items]
    if len(ids) != len(set(ids)) or set(ids) != set(by_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reorder must list every episode on this project exactly once.",
        )
    pairs = [(item.season, item.sequence) for item in body.items]
    if len(pairs) != len(set(pairs)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Season/sequence pairs must be unique.",
        )
    for index, row in enumerate(rows):
        row.sequence_index = -(index + 1)
        row.chapter = -(index + 1)
    db.flush()
    for item in body.items:
        episode = by_id[item.id]
        episode.season = item.season
        episode.sequence_index = item.sequence
        episode.chapter = item.sequence
        episode.updated_at = utcnow()
    touch(project)
    record(
        db,
        actor=user.name,
        action=EPISODE_REORDER,
        project_id=project.id,
        entity_type="project",
        entity_id=project.id,
        detail={
            "order": [
                {"id": item.id, "season": item.season, "sequence": item.sequence}
                for item in body.items
            ]
        },
    )
    db.commit()
    return [episode_out(row) for row in _episodes(db, project.id)]


@router.get("/api/episodes/{episode_id}", response_model=EpisodeOut)
def get_episode_detail(episode_id: str, user: ReadUser, db: DbDep) -> EpisodeOut:
    return episode_out(get_episode(db, episode_id, user))


@router.patch("/api/episodes/{episode_id}", response_model=EpisodeOut)
def update_episode(
    episode_id: str, body: EpisodeUpdate, user: ScriptUser, db: DbDep
) -> EpisodeOut:
    episode = get_episode(db, episode_id, user)
    if body.title is not None:
        episode.title = body.title.strip()
    if body.synopsis is not None:
        episode.synopsis = body.synopsis.strip()
    if body.log_line is not None:
        episode.log_line = body.log_line.strip()
    if body.map_notes is not None:
        episode.map_notes = body.map_notes.strip()
    if body.dialogue is not None:
        episode.dialogue = body.dialogue.strip()
    season = body.season if body.season is not None else episode.season
    chapter = body.chapter if body.chapter is not None else episode.chapter
    sequence = body.sequence if body.sequence is not None else episode.sequence_index
    if body.season is not None or body.chapter is not None or body.sequence is not None:
        clash = _clash(db, episode.project_id, season, chapter, sequence, exclude_id=episode.id)
        if clash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Season {season} sequence {sequence} (chapter {chapter}) already exists.",
            )
        episode.season = season
        episode.chapter = chapter
        episode.sequence_index = sequence
    episode.updated_at = utcnow()
    touch(episode.project)
    db.commit()
    db.refresh(episode)
    return episode_out(episode)


@router.post("/api/episodes/{episode_id}/brain-dump", response_model=DraftHonestyOut)
def brain_dump_episode(
    episode_id: str, body: BrainDumpIn, user: ScriptUser, db: DbDep
) -> DraftHonestyOut:
    """Turn a freeform brief into a draft pack revision. Does not call Comfy."""
    episode = get_episode(db, episode_id, user)
    revision, honesty = seed_brain_pack(db, episode, user.name, body.text, title=body.title or episode.title)
    record(
        db,
        actor=user.name,
        action=BRAIN_DUMP,
        project_id=episode.project_id,
        episode_id=episode.id,
        entity_type="pack",
        entity_id=revision.id,
        detail={
            "model_ran": honesty.get("model_ran"),
            "model": honesty.get("model"),
            "gates_green": bool(revision.all_gates_green),
            "generate_ready": False,
        },
    )
    touch(episode.project)
    db.commit()
    return DraftHonestyOut(
        project_id=episode.project_id,
        episode_id=episode.id,
        revision_id=revision.id,
        gates_green=bool(revision.all_gates_green),
        generate_ready=False,
        model_ran=bool(honesty.get("model_ran")),
        model=str(honesty.get("model") or "none"),
        model_note=str(honesty.get("note") or ""),
        source="brain-dump",
    )


@router.delete("/api/episodes/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_episode(episode_id: str, user: ScriptUser, db: DbDep) -> None:
    episode = get_episode(db, episode_id, user)
    project = episode.project
    db.delete(episode)
    touch(project)
    db.commit()
