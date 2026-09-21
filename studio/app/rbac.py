"""App-level org roles. Identity comes from AUTH.md (local / forward-header / optional OIDC)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from .auth import get_current_user
from .database import get_db
from .models import Organization, OrgMember
from .schemas import UserOut

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
    return db.query(Organization).order_by(Organization.created_at.asc()).first()


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


def attach_role(user: UserOut, db: Session, *, required: bool = False) -> UserOut:
    org = default_org(db)
    if org is None:
        if required:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Default organization is missing. Restart the API to seed it.",
            )
        return user.model_copy(update={"role": None, "org_id": None, "permissions": []})
    member = get_member(db, org.id, user.name)
    member = _maybe_apply_oidc_role(db, org, user, member)
    if member is None:
        if required:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"{user.name} is not an org member. A producer must add this user "
                    "(viewer / reviewer / editor / producer). Roles are app-level — "
                    "see docs/AUTH.md. OIDC claims do not grant membership unless "
                    "STUDIO_OIDC_APPLY_ROLE_CLAIM is set."
                ),
            )
        return user.model_copy(
            update={"role": None, "org_id": org.id, "permissions": []}
        )
    return user.model_copy(
        update={
            "role": member.role,
            "org_id": org.id,
            "permissions": sorted(permissions_for(member.role)),
        }
    )


def require_perm(*perms: str):
    needed = frozenset(perms)

    def _dep(
        user: Annotated[UserOut, Depends(get_current_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> UserOut:
        actor = attach_role(user, db, required=True)
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
