from fastapi import APIRouter, HTTPException, status

from ..deps import DbDep, UserDep, get_episode, get_project, touch
from ..models import Episode, utcnow
from ..schemas import EpisodeCreate, EpisodeOut, EpisodeUpdate
from ..serializers import episode_out

router = APIRouter(tags=["episodes"])


def _next_chapter(db, project_id: str) -> int:
    episodes = (
        db.query(Episode)
        .filter(Episode.project_id == project_id)
        .order_by(Episode.chapter.desc())
        .all()
    )
    if not episodes:
        return 1
    return episodes[0].chapter + 1


@router.get("/api/projects/{project_id}/episodes", response_model=list[EpisodeOut])
def list_episodes(project_id: str, _user: UserDep, db: DbDep) -> list[EpisodeOut]:
    get_project(db, project_id)
    rows = (
        db.query(Episode)
        .filter(Episode.project_id == project_id)
        .order_by(Episode.chapter.asc())
        .all()
    )
    return [episode_out(row) for row in rows]


@router.post(
    "/api/projects/{project_id}/episodes",
    response_model=EpisodeOut,
    status_code=status.HTTP_201_CREATED,
)
def create_episode(
    project_id: str, body: EpisodeCreate, _user: UserDep, db: DbDep
) -> EpisodeOut:
    project = get_project(db, project_id)
    chapter = body.chapter if body.chapter else _next_chapter(db, project.id)
    clash = (
        db.query(Episode)
        .filter(Episode.project_id == project.id, Episode.chapter == chapter)
        .first()
    )
    if clash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Chapter {chapter} already exists on this project.",
        )
    episode = Episode(
        project_id=project.id,
        title=body.title.strip(),
        chapter=chapter,
        synopsis=body.synopsis.strip(),
        review_state="draft",
    )
    db.add(episode)
    touch(project)
    db.commit()
    db.refresh(episode)
    return episode_out(episode)


@router.get("/api/episodes/{episode_id}", response_model=EpisodeOut)
def get_episode_detail(episode_id: str, _user: UserDep, db: DbDep) -> EpisodeOut:
    return episode_out(get_episode(db, episode_id))


@router.patch("/api/episodes/{episode_id}", response_model=EpisodeOut)
def update_episode(
    episode_id: str, body: EpisodeUpdate, _user: UserDep, db: DbDep
) -> EpisodeOut:
    episode = get_episode(db, episode_id)
    if body.title is not None:
        episode.title = body.title.strip()
    if body.synopsis is not None:
        episode.synopsis = body.synopsis.strip()
    if body.chapter is not None:
        clash = (
            db.query(Episode)
            .filter(
                Episode.project_id == episode.project_id,
                Episode.chapter == body.chapter,
                Episode.id != episode.id,
            )
            .first()
        )
        if clash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Chapter {body.chapter} already exists on this project.",
            )
        episode.chapter = body.chapter
    episode.updated_at = utcnow()
    touch(episode.project)
    db.commit()
    db.refresh(episode)
    return episode_out(episode)


@router.delete("/api/episodes/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_episode(episode_id: str, _user: UserDep, db: DbDep) -> None:
    episode = get_episode(db, episode_id)
    project = episode.project
    db.delete(episode)
    touch(project)
    db.commit()
