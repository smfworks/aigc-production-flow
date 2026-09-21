from fastapi import APIRouter, HTTPException, status

from ..audit import ORG_CREATE, record
from ..deps import DbDep, ScopedUserDep
from ..models import ROLE_PRODUCER, Organization, OrgMember
from ..rbac import MembersUser, ReadUser, org_summaries
from ..schemas import OrganizationCreate, OrganizationOut

router = APIRouter(tags=["orgs"])

MULTI_ORG_NOTE = "Multi-org lite — not SaaS billing or SSO org mapping."


def _out(org: Organization, role: str | None = None) -> OrganizationOut:
    return OrganizationOut(
        id=org.id,
        name=org.name,
        is_default=bool(org.is_default),
        role=role,  # type: ignore[arg-type]
        created_at=org.created_at,
        note=MULTI_ORG_NOTE,
    )


@router.get("/api/orgs", response_model=list[OrganizationOut])
def list_orgs(user: ScopedUserDep, db: DbDep) -> list[OrganizationOut]:
    rows = org_summaries(db, user.name)
    return [
        OrganizationOut(
            id=row.id,
            name=row.name,
            is_default=row.is_default,
            role=row.role,
            created_at=row.created_at,
            note=MULTI_ORG_NOTE,
        )
        for row in rows
    ]


@router.post("/api/orgs", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def create_org(body: OrganizationCreate, user: MembersUser, db: DbDep) -> OrganizationOut:
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization name is empty.")
    org = Organization(name=name, is_default=False)
    db.add(org)
    db.flush()
    member = OrgMember(organization_id=org.id, user_name=user.name, role=ROLE_PRODUCER)
    db.add(member)
    record(
        db,
        actor=user.name,
        action=ORG_CREATE,
        organization_id=org.id,
        entity_type="organization",
        entity_id=org.id,
        detail={"name": name, "multi_org": True, "billing": False},
    )
    db.commit()
    db.refresh(org)
    return _out(org, ROLE_PRODUCER)


@router.get("/api/orgs/{org_id}", response_model=OrganizationOut)
def get_org(org_id: str, user: ReadUser, db: DbDep) -> OrganizationOut:
    if user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    return _out(org, user.role)
