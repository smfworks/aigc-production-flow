from fastapi import APIRouter, HTTPException, Query, status

from ..audit import JOB_CANCEL, JOB_ENQUEUE, record
from ..deps import DbDep, get_episode, org_of_job, touch
from ..jobs.runner import touch_comfy_job, touch_comfy_jobs
from ..jobs.service import cancel_job, enqueue_job, get_job, job_out, list_jobs, retry_job
from ..models import PromptDraft, utcnow
from ..promptpreview import (
    build_preview,
    cancel_draft,
    get_draft,
    rewrite_draft,
    update_draft,
)
from ..rbac import JobsUser, ReadUser
from ..schemas import JobEnqueue, JobOut, PromptDraftPatch, PromptPreviewIn

router = APIRouter(tags=["jobs"])


def _draft_out(draft: PromptDraft) -> dict:
    body = draft.body if isinstance(draft.body, dict) else {}
    return {
        "id": draft.id,
        "episode_id": draft.episode_id,
        "shot_id": draft.shot_id,
        "job_type": draft.job_type,
        "adapter": draft.adapter,
        "status": draft.status,
        "created_by": draft.created_by,
        "created_at": draft.created_at,
        "updated_at": draft.updated_at,
        **body,
    }


@router.post("/api/jobs/preview")
def preview_job(body: PromptPreviewIn, user: JobsUser, db: DbDep) -> dict:
    """Show the exact prompt. Does not enqueue and does not call Comfy."""
    episode = get_episode(db, body.episode_id, user)
    shot = None
    if body.shot_id:
        from ..models import Shot

        shot = db.get(Shot, body.shot_id)
        if shot is None or shot.episode_id != episode.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shot not found.")
    draft = build_preview(
        db,
        episode=episode,
        user_name=user.name,
        job_type=body.job_type,
        shot=shot,
        payload=body.payload,
        adapter=body.adapter,
    )
    db.commit()
    db.refresh(draft)
    return _draft_out(draft)


@router.patch("/api/jobs/preview/{draft_id}")
def patch_preview(draft_id: str, body: PromptDraftPatch, user: JobsUser, db: DbDep) -> dict:
    draft = get_draft(db, draft_id)
    get_episode(db, draft.episode_id, user)
    update_draft(draft, prompt=body.prompt, negative=body.negative)
    db.commit()
    db.refresh(draft)
    return _draft_out(draft)


@router.post("/api/jobs/preview/{draft_id}/rewrite")
def rewrite_preview(draft_id: str, user: JobsUser, db: DbDep) -> dict:
    draft = get_draft(db, draft_id)
    get_episode(db, draft.episode_id, user)
    rewrite_draft(draft)
    db.commit()
    db.refresh(draft)
    return _draft_out(draft)


@router.post("/api/jobs/preview/{draft_id}/cancel")
def cancel_preview(draft_id: str, user: JobsUser, db: DbDep) -> dict:
    draft = get_draft(db, draft_id)
    get_episode(db, draft.episode_id, user)
    cancel_draft(draft)
    db.commit()
    db.refresh(draft)
    return _draft_out(draft)


def _job_for_org(db, job_id: str, user):
    job = get_job(db, job_id)
    org_id = org_of_job(job)
    if not user.org_id or org_id != user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


@router.get("/api/jobs", response_model=list[JobOut])
def list_all_jobs(
    user: ReadUser,
    db: DbDep,
    episode_id: str | None = None,
    job_status: str | None = Query(default=None, alias="status"),
    job_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[JobOut]:
    rows = list_jobs(
        db,
        episode_id=episode_id,
        status_value=job_status,
        job_type=job_type,
        limit=limit,
        organization_id=user.org_id,
    )
    touch_comfy_jobs(db, rows)
    return [job_out(row) for row in rows]


@router.get("/api/episodes/{episode_id}/jobs", response_model=list[JobOut])
def list_episode_jobs(
    episode_id: str,
    user: ReadUser,
    db: DbDep,
    job_status: str | None = Query(default=None, alias="status"),
    job_type: str | None = None,
) -> list[JobOut]:
    get_episode(db, episode_id, user)
    rows = list_jobs(db, episode_id=episode_id, status_value=job_status, job_type=job_type)
    touch_comfy_jobs(db, rows)
    return [job_out(row) for row in rows]


@router.post("/api/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def enqueue(body: JobEnqueue, user: JobsUser, db: DbDep) -> JobOut:
    episode = get_episode(db, body.episode_id, user)
    job = enqueue_job(
        db,
        episode=episode,
        user_name=user.name,
        job_type=body.job_type,
        shot_id=body.shot_id,
        payload=body.payload,
        adapter=body.adapter,
    )
    record(
        db,
        actor=user.name,
        action=JOB_ENQUEUE,
        project_id=episode.project_id,
        episode_id=episode.id,
        entity_type="job",
        entity_id=job.id,
        detail={
            "job_type": job.job_type,
            "adapter": job.adapter,
            "estimated_cost_units": job.estimated_cost_units,
            "status": job.status,
        },
    )
    episode.updated_at = utcnow()
    touch(episode.project)
    db.commit()
    db.refresh(job)
    return job_out(job)


@router.get("/api/jobs/{job_id}", response_model=JobOut)
def get_one(job_id: str, user: ReadUser, db: DbDep) -> JobOut:
    job = _job_for_org(db, job_id, user)
    touch_comfy_job(db, job)
    db.refresh(job)
    return job_out(job)


@router.post("/api/jobs/{job_id}/cancel", response_model=JobOut)
def cancel(job_id: str, user: JobsUser, db: DbDep) -> JobOut:
    job = cancel_job(db, _job_for_org(db, job_id, user))
    record(
        db,
        actor=user.name,
        action=JOB_CANCEL,
        project_id=job.episode.project_id if job.episode else None,
        episode_id=job.episode_id,
        entity_type="job",
        entity_id=job.id,
        detail={"job_type": job.job_type, "status": job.status},
    )
    db.commit()
    db.refresh(job)
    return job_out(job)


@router.post("/api/jobs/{job_id}/retry", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def retry(job_id: str, user: JobsUser, db: DbDep) -> JobOut:
    original = _job_for_org(db, job_id, user)
    job = retry_job(db, original, user.name)
    record(
        db,
        actor=user.name,
        action=JOB_ENQUEUE,
        project_id=job.episode.project_id if job.episode else None,
        episode_id=job.episode_id,
        entity_type="job",
        entity_id=job.id,
        detail={"job_type": job.job_type, "adapter": job.adapter, "retry_of": original.id},
    )
    db.commit()
    db.refresh(job)
    return job_out(job)
