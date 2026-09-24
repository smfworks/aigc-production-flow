"""Fast path: one story prompt, the local Imagine app, one episode.mp4.

Plan does not spend Studio budget units. Run requires the jobs permission and
``confirm: true``. Gates, sign-off, and generate-ok are unchanged. ``called_comfy``
stays false. ``produced_mp4`` is true only after episode.mp4 is in the media store.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..audit import QUICK_PLAN, QUICK_RUN, record
from ..blankpack import pack_zip_bytes
from ..budget import COST_NOTE, currency, estimate_units, refuse_if_over_cap
from ..config import get_settings
from ..createflow import new_episode
from ..deps import DbDep, get_active_org, get_episode
from ..imagine_bridge import (
    IMAGINE_ADAPTER,
    ImagineError,
    ImagineNotConfigured,
    get_imagine_client,
    imagine_configured,
    pack_body_for_create,
    studio_pack_from_imagine,
)
from ..models import Job, MediaAsset, Project, utcnow
from ..rbac import JobsUser, ReadUser
from ..routers.projects import _unique_slug
from ..store import get_store
from ..verticals import seed_pack_revision

router = APIRouter(prefix="/api/quick", tags=["quick"])


class QuickPlanIn(BaseModel):
    prompt: str
    target_duration_sec: int = Field(ge=1, le=600)
    aspect_ratio: str | None = None
    resolution: str | None = None
    title: str | None = None
    style_preset: str | None = None


class QuickRunIn(BaseModel):
    plan: dict[str, Any]
    confirm: bool = False


def _refuse_unconfigured() -> None:
    if imagine_configured():
        return
    url = (get_settings().imagine_url or "").strip()
    if not url:
        detail = "Imagine is not configured. Set STUDIO_IMAGINE_URL."
    else:
        detail = (
            "Imagine health did not report imagine_configured. "
            "The fast path stays off until GET /api/health says so."
        )
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _http_from_imagine(exc: ImagineError) -> HTTPException:
    code = exc.status_code if exc.status_code in {400, 401, 404, 409, 422} else 502
    return HTTPException(status_code=code, detail=str(exc))


@router.post("/plan")
def plan_quick(body: QuickPlanIn, user: ReadUser, db: DbDep) -> dict[str, Any]:
    """Proxy POST /api/packs/plan. No Studio budget units. Does not render."""
    _refuse_unconfigured()
    payload = body.model_dump(exclude_none=True)
    try:
        planned = get_imagine_client().plan(payload)
    except ImagineNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ImagineError as exc:
        raise _http_from_imagine(exc) from exc
    record(
        db,
        actor=user.name,
        action=QUICK_PLAN,
        organization_id=user.org_id,
        entity_type="imagine-plan",
        detail={
            "target_duration_sec": body.target_duration_sec,
            "aspect_ratio": body.aspect_ratio or "",
            "estimated_cost_units": 0,
            "called_comfy": False,
            "called_imagine": False,
            "produced_mp4": False,
            "note": "Plan only. Imagine video was not called. Comfy was not called.",
        },
    )
    db.commit()
    return {
        "plan": planned,
        "called_comfy": False,
        "called_imagine": False,
        "produced_mp4": False,
        "estimated_cost_units": 0,
    }


@router.post("/run", status_code=status.HTTP_201_CREATED)
def run_quick(body: QuickRunIn, user: JobsUser, db: DbDep) -> dict[str, Any]:
    """Create a Studio episode and start an Imagine pack. Requires confirm."""
    if body.confirm is not True:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "imagine_confirm_required",
                "message": "Set confirm true to start a paid xAI render. Nothing was sent.",
            },
        )
    _refuse_unconfigured()
    plan = body.plan if isinstance(body.plan, dict) else {}
    shots = plan.get("shots")
    if not isinstance(shots, list) or not shots:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The plan needs at least one shot.",
        )
    title = str(plan.get("title") or "").strip() or "Imagine episode"
    org = get_active_org(db, user)
    project = Project(
        organization_id=org.id,
        name=title[:200],
        slug=_unique_slug(db, org.id, title),
        description=str(plan.get("logline") or "").strip()[:2000],
        still_adapter="stub",
        clip_adapter="stub",
    )
    db.add(project)
    db.flush()
    units = estimate_units("imagine-episode", IMAGINE_ADAPTER)
    refuse_if_over_cap(db, project, units)
    episode = new_episode(
        db,
        project,
        title=title[:200],
        chapter=1,
        season=1,
        sequence=1,
        synopsis=str(plan.get("logline") or "").strip(),
        log_line=str(plan.get("logline") or "").strip(),
    )
    pack = studio_pack_from_imagine(plan)
    try:
        client = get_imagine_client()
        created = client.create_pack(pack_body_for_create(plan))
        pack_id = str(created.get("id") or "").strip()
        if not pack_id:
            raise ImagineError("Imagine did not return a pack id.")
        started = client.run(pack_id)
    except ImagineNotConfigured as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ImagineError as exc:
        db.rollback()
        raise _http_from_imagine(exc) from exc
    imagine_job_id = str(started.get("job_id") or "").strip()
    revision = seed_pack_revision(
        db,
        episode,
        user.name,
        pack_zip_bytes(pack),
        "imagine-plan.zip",
    )
    job = Job(
        episode_id=episode.id,
        job_type="imagine-episode",
        status="running",
        progress=5,
        adapter=IMAGINE_ADAPTER,
        payload={
            "imagine_pack_id": pack_id,
            "imagine_job_id": imagine_job_id,
            "confirm": True,
        },
        result={
            "called_comfy": False,
            "called_imagine": True,
            "produced_mp4": False,
            "stitched_episode": False,
            "imagine_status": str(started.get("status") or "queued"),
            "honesty": (
                "Imagine accepted the pack run. produced_mp4 stays false until "
                "episode.mp4 is in the Studio media store. Comfy was not called."
            ),
        },
        estimated_cost_units=units,
        actual_cost_units=None,
        cost_currency=currency(),
        cost_note=COST_NOTE,
        created_by=user.name,
        started_at=utcnow(),
    )
    db.add(job)
    db.flush()
    record(
        db,
        actor=user.name,
        action=QUICK_RUN,
        project_id=project.id,
        episode_id=episode.id,
        organization_id=org.id,
        entity_type="job",
        entity_id=job.id,
        detail={
            "job_type": "imagine-episode",
            "imagine_pack_id": pack_id,
            "imagine_job_id": imagine_job_id,
            "estimated_cost_units": units,
            "revision_id": revision.id,
            "called_comfy": False,
            "called_imagine": True,
            "produced_mp4": False,
            "confirm": True,
        },
    )
    db.commit()
    db.refresh(job)
    return _public_status(job, episode_id=episode.id, project_id=project.id)


@router.get("/{run_id}")
def quick_status(run_id: str, user: ReadUser, db: DbDep) -> dict[str, Any]:
    """Poll Imagine. Import episode.mp4 only after stitched_episode is true."""
    job = _imagine_job(db, run_id, user)
    episode = job.episode
    project_id = episode.project_id if episode else ""
    payload = job.payload if isinstance(job.payload, dict) else {}
    pack_id = str(payload.get("imagine_pack_id") or "").strip()
    imagine_job_id = str(payload.get("imagine_job_id") or "").strip()
    if job.status in {"succeeded", "failed", "cancelled"} and _stored_mp4(job):
        return _public_status(job, episode_id=job.episode_id, project_id=project_id)
    if not pack_id or not imagine_configured():
        result = _result(job)
        result["called_comfy"] = False
        if not imagine_configured():
            result["message"] = "Imagine is not configured. The stored run was not polled."
        job.result = result
        db.commit()
        return _public_status(job, episode_id=job.episode_id, project_id=project_id)
    try:
        remote = _remote_job(get_imagine_client().jobs(pack_id), imagine_job_id)
    except ImagineError as exc:
        result = _result(job)
        result["called_comfy"] = False
        result["poll_error"] = str(exc)
        job.result = result
        db.commit()
        return _public_status(job, episode_id=job.episode_id, project_id=project_id)
    _apply_remote(db, job, remote, pack_id, user.name)
    db.commit()
    db.refresh(job)
    return _public_status(job, episode_id=job.episode_id, project_id=project_id)


def _imagine_job(db, run_id: str, user) -> Job:
    job = db.get(Job, run_id)
    if job is None or job.job_type != "imagine-episode":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quick run not found.")
    get_episode(db, job.episode_id, user)
    return job


def _remote_job(body: dict[str, Any], imagine_job_id: str) -> dict[str, Any]:
    jobs = body.get("jobs")
    rows = [row for row in jobs if isinstance(row, dict)] if isinstance(jobs, list) else []
    if imagine_job_id:
        for row in rows:
            if str(row.get("id") or "") == imagine_job_id:
                return row
    if rows:
        return rows[-1]
    return {}


def _apply_remote(db, job: Job, remote: dict[str, Any], pack_id: str, user_name: str) -> None:
    result = _result(job)
    result["called_comfy"] = False
    result["called_imagine"] = True
    result["imagine_status"] = str(remote.get("status") or "")
    result["stitched_episode"] = bool(remote.get("stitched_episode"))
    message = str(remote.get("message") or remote.get("error") or "")
    if message:
        result["message"] = message
    shots = remote.get("shots") if isinstance(remote.get("shots"), list) else []
    finished = sum(1 for shot in shots if isinstance(shot, dict) and shot.get("produced_mp4"))
    if shots:
        result["shot_progress"] = {"done": finished, "total": len(shots)}
        job.progress = min(95, int(100 * finished / len(shots)))
    remote_status = str(remote.get("status") or "").lower()
    failed = remote_status in {"failed", "error", "expired"} or bool(remote.get("error"))
    if failed and not remote.get("stitched_episode"):
        job.status = "failed"
        job.error = str(remote.get("error") or remote.get("message") or "Imagine job failed.")
        job.finished_at = job.finished_at or utcnow()
        job.actual_cost_units = 0.0
        result["produced_mp4"] = False
        job.result = result
        return
    if remote.get("stitched_episode") and not _stored_mp4(job):
        try:
            data = get_imagine_client().download_episode(pack_id)
        except ImagineError as exc:
            result["produced_mp4"] = False
            result["download_error"] = str(exc)
            job.status = "running"
            job.result = result
            return
        asset = _store_episode_mp4(db, job.episode, user_name, data)
        job.media_id = asset.id
        result["media_id"] = asset.id
        result["produced_mp4"] = True
        result["called_imagine"] = True
        result["called_comfy"] = False
        result["honesty"] = (
            "episode.mp4 is in the Studio media store. called_imagine is true. "
            "called_comfy is false. This file does not stamp generate-ok or preview-watched."
        )
        job.status = "succeeded"
        job.progress = 100
        job.error = ""
        job.finished_at = utcnow()
        job.actual_cost_units = float(job.estimated_cost_units or 0)
        job.result = result
        return
    if _stored_mp4(job):
        result["produced_mp4"] = True
        result["called_comfy"] = False
        job.status = "succeeded"
        job.progress = 100
    else:
        result["produced_mp4"] = False
        if remote_status in {"done", "succeeded", "success"} and not remote.get("stitched_episode"):
            job.status = "running"
            result["message"] = result.get("message") or "Imagine finished without a stitched episode."
        else:
            job.status = "running"
    result["called_comfy"] = False
    job.result = result


def _store_episode_mp4(db, episode, user_name: str, data: bytes) -> MediaAsset:
    asset = MediaAsset(
        episode_id=episode.id,
        kind="preview",
        original_name="episode.mp4",
        stored_name="",
        content_type="video/mp4",
        path="",
        notes=(
            "Imagine episode.mp4 in the Studio media store. "
            "Not a hop-1 watch receipt. called_comfy is false."
        ),
        created_by=user_name,
    )
    db.add(asset)
    db.flush()
    stored = f"{asset.id}_episode.mp4"
    rel = Path(episode.id) / "previews" / stored
    get_store().put(str(rel), data)
    asset.stored_name = stored
    asset.path = str(rel)
    return asset


def _stored_mp4(job: Job) -> bool:
    if not job.media_id:
        return False
    asset = job.media
    if asset is None or asset.kind != "preview" or not asset.path:
        return False
    if not str(asset.original_name or "").lower().endswith(".mp4"):
        return False
    return bool(get_store().exists(asset.path))


def _result(job: Job) -> dict[str, Any]:
    raw = job.result if isinstance(job.result, dict) else {}
    body = dict(raw)
    body["called_comfy"] = False
    return body


def _public_status(job: Job, *, episode_id: str, project_id: str) -> dict[str, Any]:
    payload = job.payload if isinstance(job.payload, dict) else {}
    result = _result(job)
    produced = bool(result.get("produced_mp4")) and _stored_mp4(job)
    cfg = get_settings()
    return {
        "run_id": job.id,
        "status": job.status,
        "progress": int(job.progress or 0),
        "message": str(
            result.get("message")
            or result.get("download_error")
            or result.get("poll_error")
            or job.error
            or ""
        ),
        "error": job.error or "",
        "project_id": project_id,
        "episode_id": episode_id,
        "imagine_pack_id": str(payload.get("imagine_pack_id") or ""),
        "imagine_job_id": str(payload.get("imagine_job_id") or ""),
        "called_imagine": bool(result.get("called_imagine")),
        "called_comfy": False,
        "produced_mp4": produced,
        "stitched_episode": bool(result.get("stitched_episode")) and produced,
        "media_id": job.media_id if produced else None,
        "estimated_cost_units": float(job.estimated_cost_units or 0),
        "actual_cost_units": job.actual_cost_units,
        "cost_currency": job.cost_currency or "credits",
        "poll_seconds": float(cfg.imagine_poll_seconds or 5),
        "shot_progress": result.get("shot_progress") or None,
        "gates_forced": False,
        "review_state": job.episode.review_state if job.episode else "draft",
    }
