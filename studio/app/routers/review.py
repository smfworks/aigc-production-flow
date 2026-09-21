from fastapi import APIRouter, HTTPException, status

from ..deps import DbDep, UserDep, get_episode, latest_revision, touch
from ..models import ReviewState, utcnow
from ..schemas import GateSnapshotOut, ReviewOut, ReviewSet, ReviewStateOut

router = APIRouter(tags=["review"])


@router.get("/api/episodes/{episode_id}/review", response_model=ReviewOut)
def get_review(episode_id: str, _user: UserDep, db: DbDep) -> ReviewOut:
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
def set_review(episode_id: str, body: ReviewSet, user: UserDep, db: DbDep) -> ReviewOut:
    episode = get_episode(db, episode_id)
    if body.state == "generate-ok":
        revision = latest_revision(episode)
        snapshot = revision.gate_snapshot if revision else None
        gates = (snapshot or {}).get("gates") if isinstance(snapshot, dict) else None
        all_green = bool(revision and revision.all_gates_green)
        if not all_green:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "gates_not_green",
                    "message": (
                        "Refuse generate-ok until the latest pack revision shows all gates green "
                        "(nine README gates plus entity-schedule and lock-diff). "
                        "Do not skip the four-stage / gate order. Shot ready ≠ generating."
                    ),
                    "gates": gates or [],
                },
            )
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
