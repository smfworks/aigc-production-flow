"""Execute one Job row through the still/clip factory (or batch-precheck)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ..adapters import get_clip_factory, get_still_factory
from ..adapters.base import AdapterResult, JobContext
from ..config import get_settings
from ..database import SessionLocal
from ..deps import latest_revision, touch
from ..models import Episode, Job, MediaAsset, utcnow
from ..packzip import slugify, write_bytes
from ..precheck import run_batch_precheck


def _session(db: Session | None) -> tuple[Session, bool]:
    if db is not None:
        return db, False
    return SessionLocal(), True


def execute_job(db: Session | None, job_id: str) -> Job | None:
    session, owned = _session(db)
    try:
        job = session.get(Job, job_id)
        if not job:
            return None
        if job.status == "cancelled":
            return job
        if job.cancel_requested and job.status == "queued":
            job.status = "cancelled"
            job.finished_at = utcnow()
            job.error = job.error or "cancelled"
            job.actual_cost_units = 0.0
            job.updated_at = utcnow()
            session.commit()
            return job
        if job.status not in {"queued", "running"}:
            return job

        job.status = "running"
        job.started_at = job.started_at or utcnow()
        job.progress = max(job.progress or 0, 1)
        job.updated_at = utcnow()
        session.commit()

        def cancel_requested() -> bool:
            session.refresh(job)
            return bool(job.cancel_requested)

        def set_progress(value: int) -> None:
            job.progress = max(0, min(100, int(value)))
            job.updated_at = utcnow()
            session.commit()

        if cancel_requested():
            _cancel(job)
            session.commit()
            return job

        episode = job.episode
        try:
            result = _run(session, job, episode, cancel_requested, set_progress)
        except Exception as exc:  # noqa: BLE001 — job row records the failure
            job.status = "failed"
            job.error = str(exc)
            job.actual_cost_units = 0.0
            job.finished_at = utcnow()
            job.updated_at = utcnow()
            session.commit()
            return job

        session.refresh(job)
        if job.cancel_requested or (result and result.error == "cancelled"):
            _cancel(job)
            session.commit()
            return job

        if result is None:
            job.status = "failed"
            job.error = "Adapter returned no result."
            job.actual_cost_units = 0.0
            job.finished_at = utcnow()
            session.commit()
            return job

        job.adapter = result.adapter or job.adapter or "stub"
        job.result = result.receipt if isinstance(result.receipt, dict) else {"result": result.receipt}
        if result.media_bytes:
            asset = _store_media(session, job, episode, result)
            job.media_id = asset.id
            if result.ok and job.job_type == "clip-hop1" and job.shot:
                from ..preview import apply_receipt

                apply_receipt(
                    session,
                    job.shot,
                    user_name=job.created_by,
                    media_id=asset.id,
                    parse_media=True,
                )
        if result.ok:
            job.status = "succeeded"
            job.progress = 100
            job.error = ""
            job.actual_cost_units = float(job.estimated_cost_units or 0)
        else:
            job.status = "failed"
            job.error = result.error or "Adapter failed."
            job.actual_cost_units = 0.0
        job.finished_at = utcnow()
        job.updated_at = utcnow()
        episode.updated_at = utcnow()
        touch(episode.project)
        session.commit()
        return job
    finally:
        if owned:
            session.close()


def _cancel(job: Job) -> None:
    job.status = "cancelled"
    job.cancel_requested = True
    job.finished_at = utcnow()
    job.error = job.error or "cancelled"
    job.actual_cost_units = 0.0
    job.updated_at = utcnow()


def _run(
    session: Session,
    job: Job,
    episode: Episode,
    cancel_requested,
    set_progress,
) -> AdapterResult:
    revision = latest_revision(episode)
    pack = revision.pack_json if revision and isinstance(revision.pack_json, dict) else {}
    ctx = JobContext(
        job_id=job.id,
        job_type=job.job_type,
        episode_id=episode.id,
        shot_id=job.shot_id,
        payload=job.payload if isinstance(job.payload, dict) else {},
        pack=pack,
        cancel_requested=cancel_requested,
        set_progress=set_progress,
    )
    if job.job_type == "batch-precheck":
        set_progress(30)
        shot = job.shot
        report = run_batch_precheck(session, episode, shot)
        set_progress(90)
        return AdapterResult(
            ok=bool(report.get("ok")),
            adapter="stub",
            receipt=report,
            error="" if report.get("ok") else _precheck_error(report),
        )
    if job.job_type == "still-sheet":
        return get_still_factory(requested=job.adapter).generate_sheet(ctx)
    if job.job_type == "still-plate":
        return get_still_factory(requested=job.adapter).generate_plate(ctx)
    if job.job_type == "clip-hop1":
        return get_clip_factory(requested=job.adapter).hop1(ctx)
    if job.job_type == "clip-extend":
        return get_clip_factory(requested=job.adapter).extend(ctx)
    return AdapterResult(ok=False, adapter=job.adapter or "stub", error=f"Unknown job type {job.job_type}")


def _precheck_error(report: dict) -> str:
    problems = report.get("problems") or []
    if not problems:
        return "batch-precheck failed."
    first = problems[0]
    if isinstance(first, dict):
        return str(first.get("message") or first.get("code") or "batch-precheck failed.")
    return str(first)


def _store_media(session: Session, job: Job, episode: Episode, result: AdapterResult) -> MediaAsset:
    original = result.media_name or f"{job.job_type}-{job.id[:8]}.json"
    suffix = Path(original).suffix.lower() or ".json"
    asset = MediaAsset(
        episode_id=episode.id,
        kind=result.media_kind if result.media_kind in {"sheet", "plate", "costume", "preview", "other"} else "other",
        original_name=original,
        stored_name="",
        content_type=result.content_type or "application/json",
        path="",
        entity_label=str((job.payload or {}).get("entity") or (job.payload or {}).get("entity_label") or ""),
        notes=f"adapter={result.adapter} job={job.id} type={job.job_type}",
        created_by=job.created_by,
    )
    session.add(asset)
    session.flush()
    stored = f"{asset.id}_{slugify(Path(original).stem, 'job')}{suffix}"
    rel = Path(episode.id) / "jobs" / stored
    write_bytes(get_settings().media_path / rel, result.media_bytes or b"")
    asset.stored_name = stored
    asset.path = str(rel)
    return asset
