"""App-level org roles. Identity comes from AUTH.md (local / forward-header / optional OIDC).

Phase 7 multi-org lite: membership is per-org. Active org is `X-Org-Id` (else the
default org the user belongs to, else the first membership). This is not SaaS
billing and not SSO org mapping.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .auth import get_current_user
from .database import get_db
from .models import Organization, OrgMember
from .schemas import OrgMembershipOut, UserOut

active_org_id: ContextVar[str | None] = ContextVar("studio_active_org_id", default=None)

ROLE_PRODUCER = "producer"
ROLE_EDITOR = "editor"
ROLE_REVIEWER = "reviewer"
ROLE_VIEWER = "viewer"

ORG_ROLES = frozenset({ROLE_PRODUCER, ROLE_EDITOR, ROLE_REVIEWER, ROLE_VIEWER})

PERM_READ = "read"
PERM_COMMENT = "comment"
PERM_REVIEW = "review"
PERM_JOBS = "jobs"
PERM_PACK = "pack"
PERM_MEDIA = "media"
PERM_MUTATE = "mutate"
PERM_BUDGET = "budget"
PERM_RETENTION = "retention"
PERM_MEMBERS = "members"
PERM_SIGNOFF = "signoff"

_PRODUCER_PERMS = frozenset(
    {
        PERM_READ,
        PERM_COMMENT,
        PERM_REVIEW,
        PERM_JOBS,
        PERM_PACK,
        PERM_MEDIA,
        PERM_MUTATE,
        PERM_BUDGET,
        PERM_RETENTION,
        PERM_MEMBERS,
        PERM_SIGNOFF,
    }
)
_EDITOR_PERMS = frozenset(
    {
        PERM_READ,
        PERM_COMMENT,
        PERM_REVIEW,
        PERM_JOBS,
        PERM_PACK,
        PERM_MEDIA,
        PERM_MUTATE,
    }
)
_REVIEWER_PERMS = frozenset({PERM_READ, PERM_COMMENT, PERM_REVIEW, PERM_SIGNOFF})
_VIEWER_PERMS = frozenset({PERM_READ})

ROLE_PERMISSIONS = {
    ROLE_PRODUCER: _PRODUCER_PERMS,
    ROLE_EDITOR: _EDITOR_PERMS,
    ROLE_REVIEWER: _REVIEWER_PERMS,
    ROLE_VIEWER: _VIEWER_PERMS,
}


def normalize_role(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value not in ORG_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="role must be producer, editor, reviewer, or viewer.",
        )
    return value


def permissions_for(role: str | None) -> frozenset[str]:
    if not role:
        return frozenset()
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_perm(role: str | None, perm: str) -> bool:
    return perm in permissions_for(role)


def default_org(db: Session) -> Organization | None:
    flagged = db.query(Organization).filter(Organization.is_default.is_(True)).first()
    if flagged:
        return flagged
    return db.query(Organization).order_by(Organization.created_at.asc()).first()


def memberships_for(db: Session, user_name: str) -> list[OrgMember]:
    name = (user_name or "").strip()
    if not name:
        return []
    return (
        db.query(OrgMember)
        .filter(OrgMember.user_name == name)
        .order_by(OrgMember.created_at.asc())
        .all()
    )


def org_summaries(db: Session, user_name: str) -> list[OrgMembershipOut]:
    rows: list[OrgMembershipOut] = []
    for member in memberships_for(db, user_name):
        org = member.organization
        if org is None:
            continue
        rows.append(
            OrgMembershipOut(
                id=org.id,
                name=org.name,
                is_default=bool(org.is_default),
                role=member.role,  # type: ignore[arg-type]
                created_at=org.created_at,
            )
        )
    rows.sort(key=lambda row: (not row.is_default, row.created_at, row.name.lower()))
    return rows


def resolve_org(
    db: Session, user: UserOut, requested_org_id: str | None
) -> tuple[Organization | None, OrgMember | None]:
    members = memberships_for(db, user.name)
    by_org = {row.organization_id: row for row in members}
    wanted = (requested_org_id or "").strip() or None
    if wanted:
        org = db.get(Organization, wanted)
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found.",
            )
        return org, by_org.get(org.id)
    seeded = default_org(db)
    if seeded and seeded.id in by_org:
        return seeded, by_org[seeded.id]
    if members:
        first = members[0]
        return first.organization, first
    return seeded, None


def get_member(db: Session, org_id: str, user_name: str) -> OrgMember | None:
    name = (user_name or "").strip()
    if not name:
        return None
    return (
        db.query(OrgMember)
        .filter(OrgMember.organization_id == org_id, OrgMember.user_name == name)
        .first()
    )


def _maybe_apply_oidc_role(
    db: Session, org: Organization, user: UserOut, member: OrgMember | None
) -> OrgMember | None:
    """App roles stay authoritative unless the optional OIDC claim map is enabled."""
    from .audit import MEMBER_ADD, MEMBER_ROLE, record
    from .config import get_settings
    from .models import utcnow

    settings = get_settings()
    if not settings.oidc_apply_role_claim:
        return member
    if user.auth_mode != "oidc" or not user.oidc_role:
        return member
    role = user.oidc_role
    if member is None:
        member = OrgMember(organization_id=org.id, user_name=user.name, role=role)
        db.add(member)
        record(
            db,
            actor=user.name,
            action=MEMBER_ADD,
            entity_type="org_member",
            entity_id=org.id,
            detail={"user_name": user.name, "role": role, "source": "oidc_claim"},
        )
        db.commit()
        db.refresh(member)
        return member
    if member.role != role:
        previous = member.role
        member.role = role
        member.updated_at = utcnow()
        record(
            db,
            actor=user.name,
            action=MEMBER_ROLE,
            entity_type="org_member",
            entity_id=member.id,
            detail={
                "user_name": user.name,
                "from": previous,
                "to": role,
                "source": "oidc_claim",
            },
        )
        db.commit()
        db.refresh(member)
    return member


def attach_role(
    user: UserOut,
    db: Session,
    *,
    required: bool = False,
    org_id: str | None = None,
) -> UserOut:
    org, member = resolve_org(db, user, org_id)
    orgs = org_summaries(db, user.name)
    if org is None:
        active_org_id.set(None)
        if required:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Default organization is missing. Restart the API to seed it.",
            )
        return user.model_copy(
            update={
                "role": None,
                "org_id": None,
                "org_name": None,
                "permissions": [],
                "orgs": orgs,
                "multi_org": len(orgs) > 1,
            }
        )
    if org.is_default:
        member = _maybe_apply_oidc_role(db, org, user, member)
        if member is not None:
            orgs = org_summaries(db, user.name)
    if member is None:
        active_org_id.set(None)
        if required:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"{user.name} is not a member of this organization. A producer must add "
                    "this user (viewer / reviewer / editor / producer). Multi-org lite is "
                    "membership isolation only — not SaaS billing. Roles are app-level — "
                    "see docs/AUTH.md. OIDC claims do not map orgs."
                ),
            )
        return user.model_copy(
            update={
                "role": None,
                "org_id": None,
                "org_name": None,
                "permissions": [],
                "orgs": orgs,
                "multi_org": len(orgs) > 1,
            }
        )
    active_org_id.set(org.id)
    return user.model_copy(
        update={
            "role": member.role,
            "org_id": org.id,
            "org_name": org.name,
            "permissions": sorted(permissions_for(member.role)),
            "orgs": orgs,
            "multi_org": len(orgs) > 1,
        }
    )


def require_perm(*perms: str):
    needed = frozenset(perms)

    def _dep(
        user: Annotated[UserOut, Depends(get_current_user)],
        db: Annotated[Session, Depends(get_db)],
        x_org_id: Annotated[str | None, Header()] = None,
    ) -> UserOut:
        actor = attach_role(user, db, required=True, org_id=x_org_id)
        missing = [perm for perm in needed if perm not in permissions_for(actor.role)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "forbidden_role",
                    "message": (
                        f"Role {actor.role} cannot {', '.join(missing)}. "
                        "Viewers are read-only. Reviewer/producer sign-off is required "
                        "before generate-ok. Promote the member to the needed role."
                    ),
                    "role": actor.role,
                    "required": sorted(needed),
                },
            )
        return actor

    return _dep


def refuse_cross_org(user: UserOut, organization_id: str | None) -> None:
    if not organization_id or not user.org_id or organization_id == user.org_id:
        return
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Not found.",
    )


def refuse_unless(user: UserOut, perm: str, *, field: str | None = None) -> None:
    if has_perm(user.role, perm):
        return
    extra = f" ({field})" if field else ""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "forbidden_role",
            "message": (
                f"Role {user.role or 'none'} cannot {perm}{extra}. "
                "Budget hard-stop, retention apply, and member admin are producer-only. "
                "Sign-off is reviewer or producer."
            ),
            "role": user.role,
            "required": [perm],
        },
    )


ReadUser = Annotated[UserOut, Depends(require_perm(PERM_READ))]
CommentUser = Annotated[UserOut, Depends(require_perm(PERM_COMMENT))]
ReviewUser = Annotated[UserOut, Depends(require_perm(PERM_REVIEW))]
JobsUser = Annotated[UserOut, Depends(require_perm(PERM_JOBS))]
PackUser = Annotated[UserOut, Depends(require_perm(PERM_PACK))]
MediaUser = Annotated[UserOut, Depends(require_perm(PERM_MEDIA))]
MutateUser = Annotated[UserOut, Depends(require_perm(PERM_MUTATE))]
BudgetUser = Annotated[UserOut, Depends(require_perm(PERM_BUDGET))]
RetentionUser = Annotated[UserOut, Depends(require_perm(PERM_RETENTION))]
MembersUser = Annotated[UserOut, Depends(require_perm(PERM_MEMBERS))]
SignoffUser = Annotated[UserOut, Depends(require_perm(PERM_SIGNOFF))]
