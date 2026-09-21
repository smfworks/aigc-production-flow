from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from .auth import get_current_user
from .database import get_db
from .models import Episode, Organization, Project
from .schemas import UserOut

DbDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[UserOut, Depends(get_current_user)]


def get_default_org(db: Session) -> Organization:
    org = db.query(Organization).order_by(Organization.created_at.asc()).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default organization is missing. Restart the API to seed it.",
        )
    return org


def get_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


def get_episode(db: Session, episode_id: str) -> Episode:
    episode = db.get(Episode, episode_id)
    if not episode:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Episode not found.")
    return episode


def latest_revision(episode: Episode):
    return episode.revisions[0] if episode.revisions else None


def touch(model) -> None:
    from .models import utcnow

    if hasattr(model, "updated_at"):
        model.updated_at = utcnow()


ProjectGetter = Callable[[Session, str], Project]
EpisodeGetter = Callable[[Session, str], Episode]
