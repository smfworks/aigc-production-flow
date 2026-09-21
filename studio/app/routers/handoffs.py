from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from ..deps import DbDep
from ..handoff import HONESTY, create_handoff, get_live_handoff, handoff_out
from ..rbac import PackUser, ReadUser
from ..schemas import PackHandoffOut

router = APIRouter(tags=["handoffs"])


@router.post("/api/handoffs", response_model=PackHandoffOut, status_code=status.HTTP_201_CREATED)
async def stage_handoff(
    user: PackUser,
    db: DbDep,
    file: UploadFile = File(..., description="Pack zip from the builder Open in Studio handoff."),
    episode_id: str = Form(""),
) -> PackHandoffOut:
    if not user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Join an organization before staging a pack handoff.",
        )
    data = await file.read()
    row = create_handoff(
        db,
        organization_id=user.org_id,
        user_name=user.name,
        filename=file.filename or "pack.zip",
        data=data,
        episode_id=episode_id.strip() or None,
    )
    db.commit()
    db.refresh(row)
    return PackHandoffOut.model_validate(handoff_out(row))


@router.get("/api/handoffs/{handoff_id}", response_model=PackHandoffOut)
def get_handoff(handoff_id: str, user: ReadUser, db: DbDep) -> PackHandoffOut:
    if not user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handoff not found.")
    row = get_live_handoff(db, handoff_id, user.org_id)
    body = handoff_out(row)
    body["honesty"] = HONESTY
    return PackHandoffOut.model_validate(body)
