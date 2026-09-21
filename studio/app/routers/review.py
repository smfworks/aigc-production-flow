from fastapi import APIRouter, HTTPException, status

from ..audit import REVIEW_SET, record
from ..deps import DbDep, get_episode, latest_revision, touch
from ..models import ReviewState, utcnow
from ..preview import generate_ok_blockers
from ..rbac import ReadUser, ReviewUser
from ..schemas import GateSnapshotOut, ReviewOut, ReviewSet, ReviewStateOut

router = APIRouter(tags=["review"])


@router.get("/api/episodes/{episode_id}/review", response_model=ReviewOut)
def get_review(episode_id: str, _user: ReadUser, db: DbDep) -> ReviewOut:
    episode = get_episode(db, episode_id)
    revision = latest_revision(episode)
    snapshot = (
        GateSnapshotOut.model_validate(revision.gate_snapshot) if revision else None
    )
    return ReviewOut(
        current=episode.review_state,  # type: ignore[arg-type]
        history=[ReviewStateOut.model_validate(row) for row in episode.review_events],
        latest_gates=snapshot,
    )


@router.put("/api/episodes/{episode_id}/review", response_model=ReviewOut)
def set_review(episode_id: str, body: ReviewSet, user: ReviewUser, db: DbDep) -> ReviewOut:
    episode = get_episode(db, episode_id)
    if body.state == "generate-ok":
        blocked = generate_ok_blockers(episode)
        if blocked:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=blocked)
    event = ReviewState(
        episode_id=episode.id,
        state=body.state,
        note=body.note.strip(),
        set_by=user.name,
    )
    db.add(event)
    episode.review_state = body.state
    episode.updated_at = utcnow()
    touch(episode.project)
    record(
        db,
        actor=user.name,
        action=REVIEW_SET,
        project_id=episode.project_id,
        episode_id=episode.id,
        entity_type="episode",
        entity_id=episode.id,
        detail={"state": body.state, "note": body.note.strip()},
    )
    db.commit()
    db.refresh(episode)
    revision = latest_revision(episode)
    return ReviewOut(
        current=episode.review_state,  # type: ignore[arg-type]
        history=[ReviewStateOut.model_validate(row) for row in episode.review_events],
        latest_gates=(
            GateSnapshotOut.model_validate(revision.gate_snapshot) if revision else None
        ),
    )
