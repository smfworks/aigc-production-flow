from fastapi import APIRouter

from ..continuity import continuity_summary
from ..deps import DbDep, get_episode
from ..rbac import ReadUser
from ..schemas import ContinuitySummaryOut

router = APIRouter(tags=["continuity"])


@router.get("/api/episodes/{episode_id}/continuity", response_model=ContinuitySummaryOut)
def get_continuity(episode_id: str, _user: ReadUser, db: DbDep) -> ContinuitySummaryOut:
    episode = get_episode(db, episode_id)
    return ContinuitySummaryOut.model_validate(continuity_summary(episode))
