"""Start a project and its first pack inside Studio. Zip import stays optional."""

from fastapi import APIRouter, status

from ..audit import BRAIN_DUMP, PACK_IMPORT, PROJECT_CREATE, record
from ..createflow import start_project
from ..deps import DbDep, get_active_org
from ..models import utcnow
from ..rbac import MutateUser
from ..schemas import DraftHonestyOut, StudioStartIn

router = APIRouter(tags=["create"])


@router.post("/api/studio/start", response_model=DraftHonestyOut, status_code=status.HTTP_201_CREATED)
def studio_start(body: StudioStartIn, user: MutateUser, db: DbDep) -> DraftHonestyOut:
    org = get_active_org(db, user)
    from .projects import _unique_slug

    project, episode, revision, honesty = start_project(
        db,
        org_id=org.id,
        user_name=user.name,
        name=body.name,
        description=body.description,
        mode=body.mode,
        template_id=body.template_id,
        brain_dump=body.brain_dump,
        episode_title=body.episode_title,
        unique_slug=_unique_slug,
    )
    record(
        db,
        actor=user.name,
        action=PROJECT_CREATE,
        project_id=project.id,
        episode_id=episode.id,
        entity_type="project",
        entity_id=project.id,
        organization_id=org.id,
        detail={"mode": body.mode, "template_id": body.template_id, "fake_generate": False},
    )
    record(
        db,
        actor=user.name,
        action=BRAIN_DUMP if body.mode == "brain" else PACK_IMPORT,
        project_id=project.id,
        episode_id=episode.id,
        entity_type="pack",
        entity_id=revision.id,
        detail={
            "source": honesty.get("source") or body.mode,
            "model_ran": bool(honesty.get("model_ran")),
            "model": honesty.get("model") or "none",
            "gates_green": bool(revision.all_gates_green),
            "generate_ready": False,
        },
    )
    project.updated_at = utcnow()
    db.commit()
    db.refresh(episode)
    return DraftHonestyOut(
        project_id=project.id,
        episode_id=episode.id,
        revision_id=revision.id,
        gates_green=bool(revision.all_gates_green),
        generate_ready=False,
        model_ran=bool(honesty.get("model_ran")),
        model=str(honesty.get("model") or "none"),
        model_note=str(honesty.get("note") or ""),
        source=str(honesty.get("source") or body.mode),
    )
