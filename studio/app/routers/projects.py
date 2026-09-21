from fastapi import APIRouter

from ..adapters.catalog import require_slot
from ..audit import PROJECT_CREATE, record
from ..config import get_settings
from ..deps import DbDep, get_active_org, get_project
from ..models import Project, utcnow
from ..packzip import slugify
from ..rbac import PERM_BUDGET, PERM_RETENTION, MutateUser, ReadUser, refuse_unless
from ..schemas import ProjectCreate, ProjectOut, ProjectUpdate
from ..serializers import project_out

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _unique_slug(db, org_id: str, raw: str, exclude_id: str | None = None) -> str:
    base = slugify(raw, "untitled-project")
    slug = base
    n = 2
    while True:
        query = db.query(Project).filter(Project.organization_id == org_id, Project.slug == slug)
        if exclude_id:
            query = query.filter(Project.id != exclude_id)
        if query.first() is None:
            return slug
        slug = f"{base}-{n}"
        n += 1


def _adapter_or_default(value: str | None, kind: str, fallback: str) -> str:
    if not (value or "").strip():
        return fallback
    return require_slot(value, kind)  # type: ignore[arg-type]


@router.get("", response_model=list[ProjectOut])
def list_projects(user: ReadUser, db: DbDep) -> list[ProjectOut]:
    org = get_active_org(db, user)
    projects = (
        db.query(Project)
        .filter(Project.organization_id == org.id)
        .order_by(Project.updated_at.desc())
        .all()
    )
    return [project_out(project) for project in projects]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, user: MutateUser, db: DbDep) -> ProjectOut:
    org = get_active_org(db, user)
    cfg = get_settings()
    slug = _unique_slug(db, org.id, body.slug or body.name)
    project = Project(
        organization_id=org.id,
        name=body.name.strip(),
        slug=slug,
        description=body.description.strip(),
        still_adapter=_adapter_or_default(body.still_adapter, "still", cfg.still_adapter or "stub"),
        clip_adapter=_adapter_or_default(body.clip_adapter, "clip", cfg.clip_adapter or "stub"),
        budget_cap_units=body.budget_cap_units,
        budget_hard_stop=bool(body.budget_hard_stop) if body.budget_hard_stop is not None else False,
        retention_days=body.retention_days,
    )
    db.add(project)
    db.flush()
    record(
        db,
        actor=user.name,
        action=PROJECT_CREATE,
        project_id=project.id,
        entity_type="project",
        entity_id=project.id,
        organization_id=org.id,
        detail={"name": project.name, "still_adapter": project.still_adapter, "clip_adapter": project.clip_adapter},
    )
    db.commit()
    db.refresh(project)
    return project_out(project)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project_detail(project_id: str, user: ReadUser, db: DbDep) -> ProjectOut:
    return project_out(get_project(db, project_id, user))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, body: ProjectUpdate, user: MutateUser, db: DbDep) -> ProjectOut:
    project = get_project(db, project_id, user)
    if body.budget_hard_stop is not None or body.budget_cap_units is not None or body.clear_budget_cap:
        refuse_unless(user, PERM_BUDGET, field="budget hard-stop / cap")
    if body.retention_days is not None or body.clear_retention_days:
        refuse_unless(user, PERM_RETENTION, field="retention")
    if body.name is not None:
        project.name = body.name.strip()
    if body.description is not None:
        project.description = body.description.strip()
    if body.slug is not None:
        project.slug = _unique_slug(db, project.organization_id, body.slug, exclude_id=project.id)
    if body.still_adapter is not None:
        project.still_adapter = require_slot(body.still_adapter, "still")
    if body.clip_adapter is not None:
        project.clip_adapter = require_slot(body.clip_adapter, "clip")
    if body.clear_budget_cap:
        project.budget_cap_units = None
    elif body.budget_cap_units is not None:
        project.budget_cap_units = body.budget_cap_units
    if body.budget_hard_stop is not None:
        project.budget_hard_stop = body.budget_hard_stop
    if body.clear_retention_days:
        project.retention_days = None
    elif body.retention_days is not None:
        project.retention_days = body.retention_days
    project.updated_at = utcnow()
    db.commit()
    db.refresh(project)
    return project_out(project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, user: MutateUser, db: DbDep) -> None:
    project = get_project(db, project_id, user)
    db.delete(project)
    db.commit()
