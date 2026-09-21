from fastapi import APIRouter, HTTPException, status

from ..audit import REVIEW_OVERRIDE, REVIEW_SET, REVIEW_SIGNOFF, record
from ..deps import DbDep, get_episode, latest_revision, touch
from ..models import ROLE_PRODUCER, ReviewState, utcnow
from ..preview import generate_ok_blockers
from ..rbac import PERM_SIGNOFF, ReadUser, ReviewUser, SignoffUser, has_perm
from ..schemas import (
    GateSnapshotOut,
    ReviewOut,
    ReviewSet,
    ReviewSignoffCreate,
    ReviewSignoffOut,
    ReviewStateOut,
)
from ..signoff import add_signoff, is_signed_off, list_signoffs, signoff_blockers, signoff_out

router = APIRouter(tags=["review"])


def _review_out(episode) -> ReviewOut:
    revision = latest_revision(episode)
    snapshot = (
        GateSnapshotOut.model_validate(revision.gate_snapshot) if revision else None
    )
    rows = list_signoffs(episode)
    return ReviewOut(
        current=episode.review_state,  # type: ignore[arg-type]
        history=[ReviewStateOut.model_validate(row) for row in episode.review_events],
        latest_gates=snapshot,
        signoffs=[signoff_out(row) for row in rows],
        signed_off=is_signed_off(episode),
    )


@router.get("/api/episodes/{episode_id}/review", response_model=ReviewOut)
def get_review(episode_id: str, user: ReadUser, db: DbDep) -> ReviewOut:
    episode = get_episode(db, episode_id, user)
    return _review_out(episode)


@router.get("/api/episodes/{episode_id}/review/signoffs", response_model=list[ReviewSignoffOut])
def get_signoffs(episode_id: str, user: ReadUser, db: DbDep) -> list[ReviewSignoffOut]:
    episode = get_episode(db, episode_id, user)
    return [signoff_out(row) for row in list_signoffs(episode)]


@router.post(
    "/api/episodes/{episode_id}/review/signoff",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
)
def create_signoff(
    episode_id: str, body: ReviewSignoffCreate, user: SignoffUser, db: DbDep
) -> ReviewOut:
    episode = get_episode(db, episode_id, user)
    from ..notify import blocker_codes, notify_blockers_cleared

    before = blocker_codes(episode)
    row = add_signoff(
        db,
        episode,
        user_name=user.name,
        role=user.role or "",
        note=body.note,
    )
    touch(episode.project)
    record(
        db,
        actor=user.name,
        action=REVIEW_SIGNOFF,
        project_id=episode.project_id,
        episode_id=episode.id,
        entity_type="episode",
        entity_id=episode.id,
        detail={"note": (body.note or "").strip(), "role": user.role, "signoff_id": row.id},
    )
    db.flush()
    notify_blockers_cleared(db, episode, before, blocker_codes(episode), actor=user.name)
    db.commit()
    db.refresh(episode)
    return _review_out(episode)


@router.put("/api/episodes/{episode_id}/review", response_model=ReviewOut)
def set_review(episode_id: str, body: ReviewSet, user: ReviewUser, db: DbDep) -> ReviewOut:
    episode = get_episode(db, episode_id, user)
    override = bool(body.override)
    if body.state == "generate-ok":
        blocked = generate_ok_blockers(episode)
        if blocked:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=blocked)
        unsigned = signoff_blockers(episode)
        if unsigned:
            if not override:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=unsigned)
            if user.role != ROLE_PRODUCER:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "forbidden_role",
                        "message": (
                            "Only a producer may override a missing reviewer sign-off. "
                            "That override is audited as review.override."
                        ),
                        "role": user.role,
                        "required": [PERM_SIGNOFF],
                    },
                )
            if not has_perm(user.role, PERM_SIGNOFF):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Producer override requires the signoff permission.",
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
    record(
        db,
        actor=user.name,
        action=REVIEW_SET,
        project_id=episode.project_id,
        episode_id=episode.id,
        entity_type="episode",
        entity_id=episode.id,
        detail={"state": body.state, "note": body.note.strip(), "override": override},
    )
    if body.state == "generate-ok" and override and not is_signed_off(episode):
        record(
            db,
            actor=user.name,
            action=REVIEW_OVERRIDE,
            project_id=episode.project_id,
            episode_id=episode.id,
            entity_type="episode",
            entity_id=episode.id,
            detail={"state": body.state, "note": body.note.strip()},
        )
    if body.state == "preview-watched":
        from ..notify import notify_signoff_requested

        notify_signoff_requested(db, episode, actor=user.name)
    db.commit()
    db.refresh(episode)
    return _review_out(episode)
