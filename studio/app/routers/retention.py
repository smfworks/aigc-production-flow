from fastapi import APIRouter, HTTPException, Query, status

from ..audit import RETENTION_APPLY, record
from ..deps import DbDep, get_episode, get_project
from ..rbac import PERM_RETENTION, ReadUser, refuse_unless
from ..retention import apply, candidates
from ..schemas import RetentionApply

router = APIRouter(tags=["retention"])


@router.get("/api/retention")
def retention_preview(
    user: ReadUser,
    db: DbDep,
    project_id: str | None = None,
    episode_id: str | None = None,
) -> dict:
    if project_id:
        get_project(db, project_id, user)
    if episode_id:
        get_episode(db, episode_id, user)
    body = candidates(db, project_id=project_id, episode_id=episode_id, organization_id=user.org_id)
    body["applied"] = False
    body["dry_run"] = True
    return body


@router.post("/api/retention")
def retention_run(body: RetentionApply, user: ReadUser, db: DbDep) -> dict:
    if body.project_id:
        get_project(db, body.project_id, user)
    if body.episode_id:
        get_episode(db, body.episode_id, user)
    if body.dry_run:
        preview = candidates(
            db,
            project_id=body.project_id,
            episode_id=body.episode_id,
            organization_id=user.org_id,
        )
        preview["applied"] = False
        preview["dry_run"] = True
        return preview
    refuse_unless(user, PERM_RETENTION)
    if body.confirm != "expire":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Set dry_run=false and confirm="expire" to delete stub/temp media. Pack revisions are kept.',
        )
    result = apply(
        db,
        project_id=body.project_id,
        episode_id=body.episode_id,
        organization_id=user.org_id,
    )
    record(
        db,
        actor=user.name,
        action=RETENTION_APPLY,
        project_id=body.project_id,
        episode_id=body.episode_id,
        entity_type="media",
        detail={
            "deleted_count": result.get("deleted_count", 0),
            "retention_days": result.get("retention_days"),
            "keep_pack_revisions": True,
        },
    )
    db.commit()
    result["dry_run"] = False
    return result


@router.get("/api/retention/dry-run")
def retention_dry_run_alias(
    user: ReadUser,
    db: DbDep,
    project_id: str | None = Query(default=None),
    episode_id: str | None = Query(default=None),
) -> dict:
    if project_id:
        get_project(db, project_id, user)
    if episode_id:
        get_episode(db, episode_id, user)
    body = candidates(db, project_id=project_id, episode_id=episode_id, organization_id=user.org_id)
    body["applied"] = False
    body["dry_run"] = True
    return body
