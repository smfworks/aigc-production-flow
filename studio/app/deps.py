from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .auth import get_current_user
from .database import get_db
from .models import Episode, Job, Organization, Project
from .rbac import active_org_id, attach_role, refuse_cross_org
from .schemas import UserOut

DbDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[UserOut, Depends(get_current_user)]


def current_org_id() -> str | None:
    return active_org_id.get()


def scoped_user(
    user: UserDep,
    db: DbDep,
    x_org_id: Annotated[str | None, Header()] = None,
) -> UserOut:
    return attach_role(user, db, required=False, org_id=x_org_id)


ScopedUserDep = Annotated[UserOut, Depends(scoped_user)]


def get_default_org(db: Session) -> Organization:
    from .rbac import default_org

    org_id = current_org_id()
    if org_id:
        org = db.get(Organization, org_id)
        if org:
            return org
    org = default_org(db)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default organization is missing. Restart the API to seed it.",
        )
    return org


def get_active_org(db: Session, user: UserOut | None = None) -> Organization:
    org_id = (user.org_id if user else None) or current_org_id()
    if org_id:
        org = db.get(Organization, org_id)
        if org:
            return org
    return get_default_org(db)


def get_project(db: Session, project_id: str, user: UserOut | None = None) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    org_id = (user.org_id if user else None) or current_org_id()
    if org_id and project.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    if user:
        refuse_cross_org(user, project.organization_id)
    return project


def get_episode(db: Session, episode_id: str, user: UserOut | None = None) -> Episode:
    episode = db.get(Episode, episode_id)
    if not episode:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Episode not found.")
    project = episode.project
    org_id = (user.org_id if user else None) or current_org_id()
    if project is not None and org_id and project.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Episode not found.")
    if user and project is not None:
        refuse_cross_org(user, project.organization_id)
    return episode


def latest_revision(episode: Episode):
    return episode.revisions[0] if episode.revisions else None


def touch(model) -> None:
    from .models import utcnow

    if hasattr(model, "updated_at"):
        model.updated_at = utcnow()


def org_of_episode(episode: Episode) -> str | None:
    project = episode.project
    return project.organization_id if project else None


def org_of_job(job: Job) -> str | None:
    episode = job.episode
    if episode is None:
        return None
    return org_of_episode(episode)


ProjectGetter = Callable[[Session, str], Project]
EpisodeGetter = Callable[[Session, str], Episode]
