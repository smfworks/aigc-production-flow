from fastapi import APIRouter, status

from ..adapters.catalog import require_slot
from ..audit import PROJECT_CREATE, record
from ..deps import DbDep, UserDep, get_default_org
from ..models import utcnow
from ..schemas import ProjectFromTemplate, VerticalTemplateOut
from ..serializers import episode_out, project_out
from ..verticals import create_project_from_template, get_template, list_templates

router = APIRouter(tags=["templates"])


def _out(meta: dict) -> VerticalTemplateOut:
    return VerticalTemplateOut(
        id=meta["id"],
        name=meta["name"],
        blurb=meta["blurb"],
        still_adapter=meta["still_adapter"],
        clip_adapter=meta["clip_adapter"],
        stages=meta["stages"],
        gates_green=False,
        fake_generate=False,
    )


@router.get("/api/templates", response_model=list[VerticalTemplateOut])
def templates(_user: UserDep) -> list[VerticalTemplateOut]:
    return [_out(meta) for meta in list_templates()]


@router.get("/api/templates/{template_id}", response_model=VerticalTemplateOut)
def template_detail(template_id: str, _user: UserDep) -> VerticalTemplateOut:
    return _out(get_template(template_id))


@router.post(
    "/api/templates/{template_id}/projects",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
)
def new_from_template(
    template_id: str,
    body: ProjectFromTemplate,
    user: UserDep,
    db: DbDep,
) -> dict:
    still = require_slot(body.still_adapter, "still") if body.still_adapter else None
    clip = require_slot(body.clip_adapter, "clip") if body.clip_adapter else None
    org = get_default_org(db)
    from ..routers.projects import _unique_slug

    project, episode, revision = create_project_from_template(
        db,
        org_id=org.id,
        template_id=template_id,
        user_name=user.name,
        name=body.name,
        description=body.description,
        still_adapter=still,
        clip_adapter=clip,
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
        detail={
            "template_id": template_id,
            "gates_green": bool(revision.all_gates_green),
            "fake_generate": False,
        },
    )
    project.updated_at = utcnow()
    db.commit()
    db.refresh(project)
    db.refresh(episode)
    return {
        "project": project_out(project).model_dump(mode="json"),
        "episode": episode_out(episode).model_dump(mode="json"),
        "gates_green": bool(revision.all_gates_green),
        "template_id": template_id,
    }
