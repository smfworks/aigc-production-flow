from fastapi import APIRouter, HTTPException, Query, status

from ..deps import DbDep
from ..models import Notification
from ..notify import list_for_user, mark_all_read, mark_read, notification_href, unread_count
from ..rbac import ReadUser
from ..schemas import NotificationListOut, NotificationOut

router = APIRouter(tags=["notifications"])


def _out(row: Notification) -> NotificationOut:
    return NotificationOut(
        id=row.id,
        organization_id=row.organization_id,
        user_name=row.user_name,
        kind=row.kind,
        title=row.title,
        body=row.body or "",
        project_id=row.project_id,
        episode_id=row.episode_id,
        shot_id=row.shot_id,
        job_id=row.job_id,
        comment_id=row.comment_id,
        payload=row.payload if isinstance(row.payload, dict) else {},
        read_at=row.read_at,
        created_at=row.created_at,
        href=notification_href(row),
    )


@router.get("/api/notifications", response_model=NotificationListOut)
def list_notifications(
    user: ReadUser,
    db: DbDep,
    unread: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
) -> NotificationListOut:
    org_id = user.org_id or ""
    rows = list_for_user(db, org_id=org_id, user_name=user.name, unread_only=unread, limit=limit)
    return NotificationListOut(
        items=[_out(row) for row in rows],
        unread_count=unread_count(db, org_id=org_id, user_name=user.name),
    )


@router.post("/api/notifications/read-all", status_code=status.HTTP_200_OK)
def read_all(user: ReadUser, db: DbDep) -> dict:
    count = mark_all_read(db, org_id=user.org_id or "", user_name=user.name)
    db.commit()
    return {"ok": True, "marked": count}


@router.post("/api/notifications/{notification_id}/read", response_model=NotificationOut)
def read_one(notification_id: str, user: ReadUser, db: DbDep) -> NotificationOut:
    row = db.get(Notification, notification_id)
    if (
        row is None
        or row.user_name != user.name
        or row.organization_id != user.org_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    mark_read(db, row)
    db.commit()
    db.refresh(row)
    return _out(row)
