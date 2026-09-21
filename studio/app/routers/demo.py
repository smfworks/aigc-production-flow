from fastapi import APIRouter, status

from ..demo import DEMO_HONESTY, DEMO_TEMPLATE_ID, seed_demo
from ..deps import DbDep, get_active_org
from ..rbac import MutateUser
from ..schemas import DemoSeedOut
from ..serializers import episode_out, project_out

router = APIRouter(tags=["demo"])


@router.post("/api/demo/seed", response_model=DemoSeedOut, status_code=status.HTTP_201_CREATED)
def seed(user: MutateUser, db: DbDep) -> DemoSeedOut:
    org = get_active_org(db, user)
    project, episode, count = seed_demo(db, org_id=org.id, user_name=user.name)
    db.commit()
    db.refresh(project)
    db.refresh(episode)
    return DemoSeedOut(
        project=project_out(project),
        episode=episode_out(episode),
        template_id=DEMO_TEMPLATE_ID,
        honesty=DEMO_HONESTY,
        fixture_media=count,
        fake_generate=False,
        likeness=False,
        engine_mp4=False,
    )
