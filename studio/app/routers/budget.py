from fastapi import APIRouter

from ..budget import summarize
from ..deps import DbDep, get_episode, get_project
from ..rbac import ReadUser
from ..schemas import BudgetDashboardOut

router = APIRouter(tags=["budget"])


@router.get("/api/budget", response_model=BudgetDashboardOut)
def org_budget(user: ReadUser, db: DbDep) -> BudgetDashboardOut:
    return BudgetDashboardOut.model_validate(summarize(db, organization_id=user.org_id))


@router.get("/api/projects/{project_id}/budget", response_model=BudgetDashboardOut)
def project_budget(project_id: str, _user: ReadUser, db: DbDep) -> BudgetDashboardOut:
    get_project(db, project_id)
    return BudgetDashboardOut.model_validate(summarize(db, project_id=project_id))


@router.get("/api/episodes/{episode_id}/budget", response_model=BudgetDashboardOut)
def episode_budget(episode_id: str, _user: ReadUser, db: DbDep) -> BudgetDashboardOut:
    get_episode(db, episode_id)
    return BudgetDashboardOut.model_validate(summarize(db, episode_id=episode_id))
