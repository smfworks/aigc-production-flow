from fastapi import APIRouter, Query, status

from ..deps import DbDep, UserDep, get_episode, touch
from ..jobs.service import cancel_job, enqueue_job, get_job, job_out, list_jobs, retry_job
from ..models import utcnow
from ..schemas import JobEnqueue, JobOut

router = APIRouter(tags=["jobs"])


@router.get("/api/jobs", response_model=list[JobOut])
def list_all_jobs(
    _user: UserDep,
    db: DbDep,
    episode_id: str | None = None,
    job_status: str | None = Query(default=None, alias="status"),
    job_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[JobOut]:
    return [
        job_out(row)
        for row in list_jobs(db, episode_id=episode_id, status_value=job_status, job_type=job_type, limit=limit)
    ]


@router.get("/api/episodes/{episode_id}/jobs", response_model=list[JobOut])
def list_episode_jobs(
    episode_id: str,
    _user: UserDep,
    db: DbDep,
    job_status: str | None = Query(default=None, alias="status"),
    job_type: str | None = None,
) -> list[JobOut]:
    get_episode(db, episode_id)
    return [
        job_out(row)
        for row in list_jobs(db, episode_id=episode_id, status_value=job_status, job_type=job_type)
    ]


@router.post("/api/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def enqueue(body: JobEnqueue, user: UserDep, db: DbDep) -> JobOut:
    episode = get_episode(db, body.episode_id)
    job = enqueue_job(
        db,
        episode=episode,
        user_name=user.name,
        job_type=body.job_type,
        shot_id=body.shot_id,
        payload=body.payload,
    )
    episode.updated_at = utcnow()
    touch(episode.project)
    db.commit()
    db.refresh(job)
    return job_out(job)


@router.get("/api/jobs/{job_id}", response_model=JobOut)
def get_one(job_id: str, _user: UserDep, db: DbDep) -> JobOut:
    return job_out(get_job(db, job_id))


@router.post("/api/jobs/{job_id}/cancel", response_model=JobOut)
def cancel(job_id: str, _user: UserDep, db: DbDep) -> JobOut:
    job = cancel_job(db, get_job(db, job_id))
    return job_out(job)


@router.post("/api/jobs/{job_id}/retry", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def retry(job_id: str, user: UserDep, db: DbDep) -> JobOut:
    job = retry_job(db, get_job(db, job_id), user.name)
    return job_out(job)
