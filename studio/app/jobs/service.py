"""Job enqueue / cancel / retry. Job rows are the source of truth for thread and optional Celery."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..adapters import resolve_adapter_name
from ..budget import COST_NOTE, currency, estimate_units, refuse_if_over_cap
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
        estimated_cost_units=float(job.estimated_cost_units or 0),
        actual_cost_units=job.actual_cost_units,
        cost_currency=job.cost_currency or "credits",
        cost_note=job.cost_note or "",
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


def dispatch_job(db: Session, job: Job) -> Job:
    """Run or wake a queued job. Inline mode finishes before return."""
    from ..config import get_settings
    from .modes import WORKER_CELERY, WORKER_INLINE, WORKER_THREAD, normalize_worker

    cfg = get_settings()
    mode = normalize_worker(cfg.job_worker)
    if mode == WORKER_INLINE:
        execute_job(db, job.id)
        db.refresh(job)
    elif mode == WORKER_THREAD:
        worker = get_worker()
        if worker:
            worker.wakeup()
    elif mode == WORKER_CELERY:
        try:
            from .celery_app import send_execute_job

            send_execute_job(job.id)
        except Exception as exc:  # noqa: BLE001 — leave the Job row, fail the HTTP call honestly
            job.status = "failed"
            job.error = f"Celery dispatch failed: {exc}"
            job.finished_at = utcnow()
            job.actual_cost_units = 0.0
            job.updated_at = utcnow()
            db.commit()
            db.refresh(job)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "celery_unavailable",
                    "message": (
                        f"Celery enqueue failed: {exc}. "
                        "Celery is opt-in. Default worker is thread. "
                        "Never run thread and Celery against the same SQLite file."
                    ),
                    "job_id": job.id,
                },
            ) from exc
    return job


def enqueue_job(
    db: Session,
    *,
    episode: Episode,
    user_name: str,
    job_type: str,
    shot_id: str | None = None,
    payload: dict[str, Any] | None = None,
    retry_of_id: str | None = None,
    adapter: str | None = None,
    allow_stub_fixture: bool = False,
    autocommit: bool = True,
) -> Job:
    if job_type not in JOB_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"job_type must be one of: {', '.join(JOB_TYPES)}",
        )
    shot = _require_shot(db, episode, shot_id, job_type)
    body = dict(payload) if isinstance(payload, dict) else {}
    from ..promptpreview import consume_preview, mark_preview_enqueued, require_preview_or_raise

    preview_id = str(body.get("preview_id") or "").strip()
    if preview_id:
        consumed = consume_preview(db, preview_id, episode, job_type)
        body["prompt"] = consumed["prompt"]
        body["negative"] = consumed["negative"]
        body["refs"] = consumed["refs"]
        body["workflow_id"] = consumed["workflow_id"]
        body["preview_id"] = consumed["preview_id"]
        body["called_comfy"] = False
        if consumed["continue_requested"]:
            body["continue_from"] = consumed["continue_from"] or "previous"
        if not adapter:
            adapter = consumed["adapter"] or None
    else:
        require_preview_or_raise(body, job_type)
    requested = adapter or (str(body.get("adapter") or "").strip() or None)
    from ..config import get_settings

    cfg = get_settings()
    if job_type == "stitch":
        resolved = "stitch"
    elif job_type == "batch-precheck":
        resolved = "stub"
    else:
        resolved = resolve_adapter_name(job_type, cfg, requested=requested, project=episode.project)
    from ..promptpreview import continue_decision

    if str(body.get("continue_from") or "").strip() or body.get("continue"):
        decision = continue_decision(episode, shot, body, live=resolved not in {"stub", "stitch"})
        if decision["requested"] and not decision["allowed"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "continue_blocked",
                    "message": decision["warning"] or "Continue-from-previous is disabled.",
                },
            )
    if job_type == "clip-hop1":
        stub_fixture = allow_stub_fixture and resolved == "stub"
        if stub_fixture:
            body["fixture_only"] = True
            body["stamps_generate_ok"] = False
        else:
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

    if resolved not in {"stub", "stitch"}:
        from ..adapters.health import refuse_if_unhealthy

        refuse_if_unhealthy(resolved, cfg)
    estimated = estimate_units(job_type, "stub" if job_type == "stitch" else resolved, cfg)
    refuse_if_over_cap(db, episode.project, estimated, cfg)
    job = Job(
        episode_id=episode.id,
        shot_id=shot.id if shot else None,
        job_type=job_type,
        status="queued",
        progress=0,
        adapter=resolved,
        payload=body,
        result={},
        retry_of_id=retry_of_id,
        created_by=user_name,
        estimated_cost_units=estimated,
        actual_cost_units=None,
        cost_currency=currency(cfg),
        cost_note=COST_NOTE,
    )
    db.add(job)
    db.flush()
    mark_preview_enqueued(db, str(body.get("preview_id") or ""))
    if not autocommit:
        return job
    db.commit()
    db.refresh(job)
    return dispatch_job(db, job)


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
        job.actual_cost_units = 0.0
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
        adapter=job.adapter,
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
    organization_id: str | None = None,
    limit: int = 100,
) -> list[Job]:
    query = db.query(Job).order_by(Job.created_at.desc())
    if organization_id:
        from ..models import Episode, Project

        query = (
            query.join(Episode, Job.episode_id == Episode.id)
            .join(Project, Episode.project_id == Project.id)
            .filter(Project.organization_id == organization_id)
        )
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
