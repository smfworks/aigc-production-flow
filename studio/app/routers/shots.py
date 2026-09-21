from fastapi import APIRouter, HTTPException, status

from ..deps import DbDep, get_episode, latest_revision
from ..models import Shot, ShotCandidate, utcnow
from ..rbac import EditUser, ReadUser
from ..schemas import (
    BoardOut,
    CandidateCreate,
    CandidateOut,
    CandidateUpdate,
    ShotOut,
    ShotReadinessSet,
    ShotUpdate,
)
from ..serializers import shot_out
from .. import shots as shot_ops
from ..shots import continue_chains

router = APIRouter(tags=["shots"])


def _shot_out(shot: Shot) -> ShotOut:
    return shot_out(shot)


def _get_shot(db, episode_id: str, shot_id: str, user=None) -> Shot:
    episode = get_episode(db, episode_id, user)
    shot = db.get(Shot, shot_id)
    if not shot or shot.episode_id != episode.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shot not found.")
    return shot


@router.get("/api/episodes/{episode_id}/shots", response_model=list[ShotOut])
def list_shots(episode_id: str, user: ReadUser, db: DbDep) -> list[ShotOut]:
    episode = get_episode(db, episode_id, user)
    return [_shot_out(row) for row in episode.shots]


@router.get("/api/episodes/{episode_id}/board", response_model=BoardOut)
def get_board(episode_id: str, user: ReadUser, db: DbDep) -> BoardOut:
    episode = get_episode(db, episode_id, user)
    shots = list(episode.shots)
    chains, boundaries = continue_chains(shots)
    return BoardOut(
        shots=[_shot_out(row) for row in shots],
        continue_chains=chains,
        boundaries=boundaries,
    )


@router.post(
    "/api/episodes/{episode_id}/shots/extract-candidates",
    response_model=list[ShotOut],
)
def extract_candidates(episode_id: str, user: EditUser, db: DbDep) -> list[ShotOut]:
    episode = get_episode(db, episode_id, user)
    revision = latest_revision(episode)
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Start a pack in Studio, or import a zip, before extracting candidates.",
        )
    pack = revision.pack_json if isinstance(revision.pack_json, dict) else {}
    if not episode.shots:
        shot_ops.sync_shots_from_pack(db, episode, revision)
    for shot in episode.shots:
        shot_ops.extract_candidates_for_shot(shot, pack, list(episode.media))
    episode.updated_at = utcnow()
    db.commit()
    db.refresh(episode)
    return [_shot_out(row) for row in episode.shots]


@router.get("/api/episodes/{episode_id}/shots/{shot_id}", response_model=ShotOut)
def get_shot(episode_id: str, shot_id: str, user: ReadUser, db: DbDep) -> ShotOut:
    return _shot_out(_get_shot(db, episode_id, shot_id, user))


@router.put("/api/episodes/{episode_id}/shots/{shot_id}/readiness", response_model=ShotOut)
def set_shot_readiness(
    episode_id: str, shot_id: str, body: ShotReadinessSet, user: EditUser, db: DbDep
) -> ShotOut:
    shot = _get_shot(db, episode_id, shot_id, user)
    shot_ops.set_readiness(shot, body.readiness)
    shot.episode.updated_at = utcnow()
    db.commit()
    db.refresh(shot)
    return _shot_out(shot)


@router.post(
    "/api/episodes/{episode_id}/shots/{shot_id}/candidates",
    response_model=CandidateOut,
    status_code=status.HTTP_201_CREATED,
)
def add_candidate(
    episode_id: str, shot_id: str, body: CandidateCreate, user: EditUser, db: DbDep
) -> CandidateOut:
    shot = _get_shot(db, episode_id, shot_id, user)
    candidate = ShotCandidate(
        shot_id=shot.id,
        kind=body.kind,
        label=body.label.strip(),
        evidence=body.evidence.strip() or "Manual candidate. Confirm by hand.",
        status="pending",
        source="manual",
    )
    db.add(candidate)
    shot_ops.refresh_readiness(shot)
    shot.episode.updated_at = utcnow()
    db.commit()
    db.refresh(candidate)
    return CandidateOut.model_validate(candidate)


@router.patch(
    "/api/episodes/{episode_id}/shots/{shot_id}/candidates/{candidate_id}",
    response_model=CandidateOut,
)
def update_candidate(
    episode_id: str,
    shot_id: str,
    candidate_id: str,
    body: CandidateUpdate,
    user: EditUser,
    db: DbDep,
) -> CandidateOut:
    shot = _get_shot(db, episode_id, shot_id, user)
    candidate = db.get(ShotCandidate, candidate_id)
    if not candidate or candidate.shot_id != shot.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    if body.kind is not None:
        candidate.kind = body.kind
    if body.label is not None:
        candidate.label = body.label.strip()
    shot_ops.apply_candidate_update(db, candidate, body.status, body.linked_asset_id, body.linked_ref)
    shot.episode.updated_at = utcnow()
    db.commit()
    db.refresh(candidate)
    return CandidateOut.model_validate(candidate)


@router.patch("/api/episodes/{episode_id}/shots/{shot_id}", response_model=ShotOut)
def update_shot(
    episode_id: str, shot_id: str, body: ShotUpdate, user: EditUser, db: DbDep
) -> ShotOut:
    """Joins, camera verb, and action. Metadata only — not an NLE timeline."""
    shot = _get_shot(db, episode_id, shot_id, user)
    if body.join is not None:
        shot.join = body.join.strip()
    if body.camera_verb is not None:
        shot.camera_verb = body.camera_verb.strip()
    if body.action is not None:
        shot.action = body.action.strip()
    shot.updated_at = utcnow()
    shot.episode.updated_at = utcnow()
    db.commit()
    db.refresh(shot)
    return _shot_out(shot)
