"""Job enqueue / cancel / retry. Job rows are the source of truth for Celery later."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..adapters import resolve_adapter_name
from ..models import JOB_STATUSES, JOB_TYPES, Episode, Job, Shot, utcnow
from ..precheck import hop1_enqueue_blockers
from ..preview import extend_ok
from ..schemas import JobOut
from .runner import execute_job
from .worker import get_worker


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def elapsed_ms(job: Job) -> int:
    start = _aware(job.started_at) or _aware(job.created_at)
    end = _aware(job.finished_at) or utcnow()
    if start is None:
        return 0
    return max(0, int((end - start).total_seconds() * 1000))


def job_out(job: Job) -> JobOut:
    episode = job.episode
    project = episode.project if episode else None
    shot = job.shot
    return JobOut(
        id=job.id,
        episode_id=job.episode_id,
        project_id=episode.project_id if episode else "",
        shot_id=job.shot_id,
        media_id=job.media_id,
        retry_of_id=job.retry_of_id,
        job_type=job.job_type,  # type: ignore[arg-type]
        status=job.status,  # type: ignore[arg-type]
        progress=job.progress or 0,
        error=job.error or "",
        adapter=job.adapter or "stub",
        payload=job.payload if isinstance(job.payload, dict) else {},
        result=job.result if isinstance(job.result, dict) else {},
        cancel_requested=bool(job.cancel_requested),
        created_by=job.created_by,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        updated_at=job.updated_at,
        elapsed_ms=elapsed_ms(job),
        episode_title=episode.title if episode else "",
        project_name=project.name if project else "",
        shot_sort_index=shot.sort_index if shot else None,
        shot_take=shot.take if shot else "",
    )


def _require_shot(db: Session, episode: Episode, shot_id: str | None, job_type: str) -> Shot | None:
    if not shot_id:
        if job_type in {"clip-hop1", "clip-extend"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{job_type} requires shot_id.",
            )
        return None
    shot = db.get(Shot, shot_id)
    if not shot or shot.episode_id != episode.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shot not found.")
    return shot


def enqueue_job(
    db: Session,
    *,
    episode: Episode,
    user_name: str,
    job_type: str,
    shot_id: str | None = None,
    payload: dict[str, Any] | None = None,
    retry_of_id: str | None = None,
) -> Job:
    if job_type not in JOB_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"job_type must be one of: {', '.join(JOB_TYPES)}",
        )
    shot = _require_shot(db, episode, shot_id, job_type)
    body = payload if isinstance(payload, dict) else {}
    if job_type == "clip-hop1":
        blocked = hop1_enqueue_blockers(episode, shot)
        if blocked:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=blocked)
    if job_type == "clip-extend":
        if shot is None or not extend_ok(shot.receipt):
            blockers = []
            if shot is None:
                blockers = ["clip-extend requires a shot."]
            else:
                from ..preview import receipt_blockers

                blockers = receipt_blockers(shot.receipt, for_extend=True)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "preview_incomplete",
                    "message": (
                        "Refuse clip-extend until this shot's hop-1 is preview-watched with a "
                        "continuity receipt and no NG reason."
                    ),
                    "blockers": blockers,
                },
            )

    adapter = "stub" if job_type == "batch-precheck" else resolve_adapter_name(job_type)
    job = Job(
        episode_id=episode.id,
        shot_id=shot.id if shot else None,
        job_type=job_type,
        status="queued",
        progress=0,
        adapter=adapter,
        payload=body,
        result={},
        retry_of_id=retry_of_id,
        created_by=user_name,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from ..config import get_settings

    mode = (get_settings().job_worker or "thread").strip().lower()
    if mode == "inline":
        execute_job(db, job.id)
        db.refresh(job)
    elif mode == "thread":
        worker = get_worker()
        if worker:
            worker.wakeup()
    return job


def cancel_job(db: Session, job: Job) -> Job:
    if job.status in {"succeeded", "failed", "cancelled"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "not_cancellable",
                "message": f"Cannot cancel a {job.status} job. Retry it instead if it failed or was cancelled.",
            },
        )
    job.cancel_requested = True
    if job.status == "queued":
        job.status = "cancelled"
        job.finished_at = utcnow()
        job.error = job.error or "cancelled"
        job.updated_at = utcnow()
        db.commit()
        db.refresh(job)
        return job
    db.commit()
    db.refresh(job)
    return job


def retry_job(db: Session, job: Job, user_name: str) -> Job:
    if job.status not in {"failed", "cancelled"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "not_retryable",
                "message": "Retry is for failed or cancelled jobs. Queued/running jobs can be cancelled.",
            },
        )
    episode = job.episode
    return enqueue_job(
        db,
        episode=episode,
        user_name=user_name,
        job_type=job.job_type,
        shot_id=job.shot_id,
        payload=job.payload if isinstance(job.payload, dict) else {},
        retry_of_id=job.id,
    )


def get_job(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


def list_jobs(
    db: Session,
    *,
    episode_id: str | None = None,
    status_value: str | None = None,
    job_type: str | None = None,
    limit: int = 100,
) -> list[Job]:
    query = db.query(Job).order_by(Job.created_at.desc())
    if episode_id:
        query = query.filter(Job.episode_id == episode_id)
    if status_value:
        if status_value not in JOB_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown job status.")
        query = query.filter(Job.status == status_value)
    if job_type:
        if job_type not in JOB_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown job type.")
        query = query.filter(Job.job_type == job_type)
    return query.limit(max(1, min(limit, 500))).all()
