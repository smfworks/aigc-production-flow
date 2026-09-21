from fastapi import APIRouter, Query

from ..audit import ACTIONS, event_out, list_events
from ..deps import DbDep
from ..rbac import ReadUser
from ..schemas import AuditEventOut

router = APIRouter(tags=["audit"])


@router.get("/api/audit", response_model=list[AuditEventOut])
def get_audit(
    _user: ReadUser,
    db: DbDep,
    project_id: str | None = None,
    episode_id: str | None = None,
    action: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[AuditEventOut]:
    if action and action not in ACTIONS:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"action must be one of: {', '.join(ACTIONS)}",
        )
    return [
        AuditEventOut.model_validate(event_out(row))
        for row in list_events(
            db,
            project_id=project_id,
            episode_id=episode_id,
            action=action,
            limit=limit,
        )
    ]
