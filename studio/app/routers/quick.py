"""Fast path: one story prompt, a local shot plan, one Studio episode.

Plan does not spend budget units and does not call a renderer. Run requires the
jobs permission and ``confirm: true``. It writes a project, an episode, and a
pack revision on this machine. Stills and clips stay on the desk adapters
(stub, or Comfy when a private lane is set). Gates, sign-off, and generate-ok
are unchanged. ``called_comfy`` stays false. ``produced_mp4`` stays false.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..adapters.registry import resolve_adapter_name
from ..audit import QUICK_PLAN, QUICK_RUN, record
from ..blankpack import pack_zip_bytes
from ..budget import refuse_if_over_cap
from ..config import get_settings
from ..createflow import new_episode
from ..deps import DbDep, get_active_org, get_episode
from ..models import Project
from ..quickpack import local_plan, studio_pack_from_plan
from ..rbac import JobsUser, ReadUser
from ..routers.projects import _unique_slug
from ..verticals import seed_pack_revision

router = APIRouter(prefix="/api/quick", tags=["quick"])


class QuickPlanIn(BaseModel):
    prompt: str
    target_duration_sec: int = Field(ge=1, le=600)
    aspect_ratio: str | None = None
    resolution: str | None = None
    title: str | None = None
    style_preset: str | None = None
    cast: list[dict[str, Any]] | None = None
    cast_notes: str | None = None


class QuickRunIn(BaseModel):
    plan: dict[str, Any]
    confirm: bool = False


@router.post("/plan")
def plan_quick(body: QuickPlanIn, user: ReadUser, db: DbDep) -> dict[str, Any]:
    """Build a local shot plan. No budget units. Does not render."""
    prompt = (body.prompt or "").strip()
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Add a story prompt before planning.",
        )
    planned = local_plan(
        prompt=prompt,
        target_duration_sec=body.target_duration_sec,
        aspect_ratio=body.aspect_ratio,
        resolution=body.resolution,
        title=body.title,
        style_preset=body.style_preset,
        cast=body.cast,
        cast_notes=body.cast_notes,
    )
    record(
        db,
        actor=user.name,
        action=QUICK_PLAN,
        organization_id=user.org_id,
        entity_type="quick-plan",
        detail={
            "target_duration_sec": body.target_duration_sec,
            "aspect_ratio": body.aspect_ratio or "",
            "estimated_cost_units": 0,
            "called_comfy": False,
            "produced_mp4": False,
            "note": "Local plan only. No renderer was called.",
        },
    )
    db.commit()
    return {
        "plan": planned,
        "called_comfy": False,
        "produced_mp4": False,
        "estimated_cost_units": 0,
    }


@router.post("/run", status_code=status.HTTP_201_CREATED)
def run_quick(body: QuickRunIn, user: JobsUser, db: DbDep) -> dict[str, Any]:
    """Save the plan as a Studio episode on the local desk. Requires confirm."""
    if body.confirm is not True:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "confirm_required",
                "message": "Set confirm true to save this episode on the local desk. Nothing was created.",
            },
        )
    plan = body.plan if isinstance(body.plan, dict) else {}
    shots = plan.get("shots")
    if not isinstance(shots, list) or not shots:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The plan needs at least one shot.",
        )
    title = str(plan.get("title") or "").strip() or "Quick episode"
    org = get_active_org(db, user)
    cfg = get_settings()
    still_adapter = resolve_adapter_name("still-sheet", cfg)
    clip_adapter = resolve_adapter_name("clip-hop1", cfg)
    project = Project(
        organization_id=org.id,
        name=title[:200],
        slug=_unique_slug(db, org.id, title),
        description=str(plan.get("logline") or "").strip()[:2000],
        still_adapter=still_adapter,
        clip_adapter=clip_adapter,
    )
    db.add(project)
    db.flush()
    refuse_if_over_cap(db, project, 0)
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
    pack = studio_pack_from_plan(plan)
    revision = seed_pack_revision(
        db,
        episode,
        user.name,
        pack_zip_bytes(pack),
        "quick-plan.zip",
    )
    record(
        db,
        actor=user.name,
        action=QUICK_RUN,
        project_id=project.id,
        episode_id=episode.id,
        organization_id=org.id,
        entity_type="episode",
        entity_id=episode.id,
        detail={
            "source": "quick",
            "still_adapter": still_adapter,
            "clip_adapter": clip_adapter,
            "estimated_cost_units": 0,
            "revision_id": revision.id,
            "called_comfy": False,
            "produced_mp4": False,
            "confirm": True,
            "note": "Episode saved on the local desk. No cloud render. Generate stays on the desk.",
        },
    )
    db.commit()
    db.refresh(episode)
    return _public_status(episode)


@router.get("/{run_id}")
def quick_status(run_id: str, user: ReadUser, db: DbDep) -> dict[str, Any]:
    """Read the episode this quick run saved. Does not poll a renderer."""
    episode = get_episode(db, run_id, user)
    return _public_status(episode)


def _public_status(episode) -> dict[str, Any]:
    project = episode.project
    still_adapter = (project.still_adapter if project else "") or "stub"
    clip_adapter = (project.clip_adapter if project else "") or "stub"
    return {
        "run_id": episode.id,
        "status": "saved",
        "progress": 100,
        "message": (
            f"Episode saved on the local desk ({still_adapter} stills, {clip_adapter} clips). "
            "Generate stays on the desk. produced_mp4 is false. called_comfy is false."
        ),
        "error": "",
        "project_id": episode.project_id,
        "episode_id": episode.id,
        "still_adapter": still_adapter,
        "clip_adapter": clip_adapter,
        "called_comfy": False,
        "produced_mp4": False,
        "stitched_episode": False,
        "media_id": None,
        "estimated_cost_units": 0,
        "actual_cost_units": None,
        "cost_currency": "credits",
        "poll_seconds": 0,
        "shot_progress": None,
        "gates_forced": False,
        "review_state": episode.review_state or "draft",
    }
