from fastapi import APIRouter, HTTPException, status

from ..audit import MEMBER_ADD, MEMBER_ROLE, record
from ..deps import DbDep
from ..models import OrgMember, utcnow
from ..rbac import MembersUser, ReadUser, default_org, normalize_role
from ..schemas import MemberCreate, MemberOut, MemberUpdate

router = APIRouter(tags=["members"])


def _org_or_404(db, org_id: str):
    org = default_org(db)
    if org is None or org.id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    return org


def _last_producer_count(db, org_id: str, exclude_id: str | None = None) -> int:
    query = db.query(OrgMember).filter(
        OrgMember.organization_id == org_id, OrgMember.role == "producer"
    )
    if exclude_id:
        query = query.filter(OrgMember.id != exclude_id)
    return query.count()


@router.get("/api/orgs/{org_id}/members", response_model=list[MemberOut])
def list_members(org_id: str, _user: ReadUser, db: DbDep) -> list[MemberOut]:
    org = _org_or_404(db, org_id)
    rows = (
        db.query(OrgMember)
        .filter(OrgMember.organization_id == org.id)
        .order_by(OrgMember.created_at.asc())
        .all()
    )
    return [MemberOut.model_validate(row) for row in rows]


@router.post(
    "/api/orgs/{org_id}/members",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(org_id: str, body: MemberCreate, user: MembersUser, db: DbDep) -> MemberOut:
    org = _org_or_404(db, org_id)
    name = body.user_name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_name is empty.")
    role = normalize_role(body.role)
    existing = (
        db.query(OrgMember)
        .filter(OrgMember.organization_id == org.id, OrgMember.user_name == name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{name} is already a member ({existing.role}). Change their role instead.",
        )
    member = OrgMember(organization_id=org.id, user_name=name, role=role)
    db.add(member)
    db.flush()
    record(
        db,
        actor=user.name,
        action=MEMBER_ADD,
        entity_type="member",
        entity_id=member.id,
        detail={"user_name": name, "role": role},
    )
    db.commit()
    db.refresh(member)
    return MemberOut.model_validate(member)


@router.patch("/api/orgs/{org_id}/members/{member_id}", response_model=MemberOut)
def change_role(
    org_id: str, member_id: str, body: MemberUpdate, user: MembersUser, db: DbDep
) -> MemberOut:
    org = _org_or_404(db, org_id)
    member = db.get(OrgMember, member_id)
    if not member or member.organization_id != org.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")
    role = normalize_role(body.role)
    if member.role == "producer" and role != "producer":
        if _last_producer_count(db, org.id, exclude_id=member.id) < 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot demote the last producer.",
            )
    previous = member.role
    member.role = role
    member.updated_at = utcnow()
    record(
        db,
        actor=user.name,
        action=MEMBER_ROLE,
        entity_type="member",
        entity_id=member.id,
        detail={"user_name": member.user_name, "from": previous, "to": role},
    )
    db.commit()
    db.refresh(member)
    return MemberOut.model_validate(member)


@router.delete("/api/orgs/{org_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(org_id: str, member_id: str, user: MembersUser, db: DbDep) -> None:
    org = _org_or_404(db, org_id)
    member = db.get(OrgMember, member_id)
    if not member or member.organization_id != org.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")
    if member.user_name == user.name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot remove yourself. Ask another producer.",
        )
    if member.role == "producer" and _last_producer_count(db, org.id, exclude_id=member.id) < 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot remove the last producer.",
        )
    db.delete(member)
    db.commit()
