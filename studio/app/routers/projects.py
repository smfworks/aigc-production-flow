from fastapi import APIRouter

from ..deps import DbDep, UserDep, get_default_org, get_project
from ..models import Project, utcnow
from ..packzip import slugify
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


@router.get("", response_model=list[ProjectOut])
def list_projects(_user: UserDep, db: DbDep) -> list[ProjectOut]:
    projects = db.query(Project).order_by(Project.updated_at.desc()).all()
    return [project_out(project) for project in projects]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, user: UserDep, db: DbDep) -> ProjectOut:
    del user
    org = get_default_org(db)
    slug = _unique_slug(db, org.id, body.slug or body.name)
    project = Project(
        organization_id=org.id,
        name=body.name.strip(),
        slug=slug,
        description=body.description.strip(),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project_out(project)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project_detail(project_id: str, _user: UserDep, db: DbDep) -> ProjectOut:
    return project_out(get_project(db, project_id))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, body: ProjectUpdate, _user: UserDep, db: DbDep) -> ProjectOut:
    project = get_project(db, project_id)
    if body.name is not None:
        project.name = body.name.strip()
    if body.description is not None:
        project.description = body.description.strip()
    if body.slug is not None:
        project.slug = _unique_slug(db, project.organization_id, body.slug, exclude_id=project.id)
    project.updated_at = utcnow()
    db.commit()
    db.refresh(project)
    return project_out(project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, _user: UserDep, db: DbDep) -> None:
    project = get_project(db, project_id)
    db.delete(project)
    db.commit()
