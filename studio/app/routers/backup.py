from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response

from ..audit import BACKUP_EXPORT, BACKUP_RESTORE, record
from ..backup import KEEP_REVISIONS_NOTE, export_org_backup, restore_backup
from ..deps import DbDep, get_active_org
from ..packzip import slugify
from ..rbac import MembersUser, ReadUser

router = APIRouter(tags=["backup"])


@router.get("/api/backup")
def download_backup(user: ReadUser, db: DbDep):
    org = get_active_org(db, user)
    data = export_org_backup(db, org)
    record(
        db,
        actor=user.name,
        action=BACKUP_EXPORT,
        organization_id=org.id,
        entity_type="organization",
        entity_id=org.id,
        detail={"bytes": len(data), "keep_pack_revisions": True},
    )
    db.commit()
    filename = f"{slugify(org.name, 'org')}-backup.zip"
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/backup/restore")
async def restore(
    user: MembersUser,
    db: DbDep,
    file: UploadFile = File(..., description="Backup zip from GET /api/backup."),
    dry_run: bool = Form(True),
    confirm: str = Form(""),
):
    org = get_active_org(db, user)
    data = await file.read()
    apply = not dry_run
    if apply and confirm.strip().lower() != "restore":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Set dry_run=false and confirm="restore" to apply. Pack revisions are never deleted.',
        )
    result = restore_backup(db, org, data, dry_run=not apply, user_name=user.name)
    if apply:
        record(
            db,
            actor=user.name,
            action=BACKUP_RESTORE,
            organization_id=org.id,
            entity_type="organization",
            entity_id=org.id,
            detail={
                "created_projects": result.get("created_projects"),
                "added_revisions": result.get("added_revisions"),
                "keep_pack_revisions": True,
                "keep_note": KEEP_REVISIONS_NOTE,
            },
        )
        db.commit()
    result["keep_note"] = KEEP_REVISIONS_NOTE
    return result
