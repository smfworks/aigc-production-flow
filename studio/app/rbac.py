"""App-level org roles. Identity still comes from AUTH.md — this is not OIDC."""

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
_REVIEWER_PERMS = frozenset({PERM_READ, PERM_COMMENT, PERM_REVIEW})
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
    if member is None:
        if required:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"{user.name} is not an org member. A producer must add this user "
                    "(viewer / reviewer / editor / producer). Roles are app-level — "
                    "see docs/AUTH.md. OIDC is not implemented."
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
                        "Viewers are read-only. Promote the member to editor or producer."
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
                "Budget hard-stop, retention apply, and member admin are producer-only."
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
