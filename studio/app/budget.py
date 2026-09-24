"""Operator-configured cost units. Not a cloud invoice — never claim a bill was paid."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .adapters.catalog import STUB_NAME, slot_for
from .config import Settings, get_settings
from .models import Episode, Job, Project

DISCLAIMER = (
    "Operator-configured rate table. Opaque credits (or a USD estimate from "
    "STUDIO_COST_USD_PER_UNIT). Not a cloud invoice — no bill was paid."
)

DEFAULT_RATES = {
    STUB_NAME: 0.1,
    "webhook": 1.0,
    "cli": 1.0,
    "comfy-h3": 2.0,
    "comfy-qwen": 0.5,
    "grok-imagine": 4.0,
}

JOB_MULTIPLIERS = {
    "batch-precheck": 0.0,
    "still-sheet": 1.0,
    "still-plate": 1.0,
    "clip-hop1": 1.0,
    "clip-extend": 0.75,
    "stitch": 0.25,
    "imagine-episode": 1.0,
}

COST_NOTE = "operator rate table — not a cloud bill"


def parse_rate_table(raw: str | None, settings: Settings | None = None) -> dict[str, float]:
    rates = dict(DEFAULT_RATES)
    cfg = settings or get_settings()
    blob = raw if raw is not None else (cfg.cost_rates or "")
    for part in blob.split(","):
        item = part.strip()
        if not item or ":" not in item:
            continue
        key, _, value = item.partition(":")
        name = key.strip().lower()
        try:
            rates[name] = float(value.strip())
        except ValueError:
            continue
    return rates


def estimate_units(
    job_type: str,
    adapter: str,
    settings: Settings | None = None,
) -> float:
    cfg = settings or get_settings()
    rates = parse_rate_table(None, cfg)
    slot = slot_for(adapter)
    rate = float(rates.get(slot.id, rates.get(STUB_NAME, 0.1)))
    mult = float(JOB_MULTIPLIERS.get(job_type, 1.0))
    return round(max(0.0, rate * mult), 4)


def currency(settings: Settings | None = None) -> str:
    cfg = settings or get_settings()
    return (cfg.cost_currency or "credits").strip() or "credits"


def usd_per_unit(settings: Settings | None = None) -> float:
    cfg = settings or get_settings()
    try:
        return max(0.0, float(cfg.cost_usd_per_unit or 0))
    except (TypeError, ValueError):
        return 0.0


def usd_estimate(units: float, settings: Settings | None = None) -> float | None:
    rate = usd_per_unit(settings)
    if rate <= 0:
        return None
    return round(units * rate, 4)


def project_cap(project: Project, settings: Settings | None = None) -> float | None:
    if project.budget_cap_units is not None:
        return float(project.budget_cap_units)
    cfg = settings or get_settings()
    if cfg.budget_cap_units is None:
        return None
    return float(cfg.budget_cap_units)


def project_hard_stop(project: Project, settings: Settings | None = None) -> bool:
    if project.budget_hard_stop:
        return True
    cfg = settings or get_settings()
    return bool(cfg.budget_hard_stop)


def _units_of(job: Job, *, pending: bool) -> float:
    if pending:
        return float(job.estimated_cost_units or 0)
    if job.actual_cost_units is not None:
        return float(job.actual_cost_units)
    if job.status == "succeeded":
        return float(job.estimated_cost_units or 0)
    return 0.0


def spent_and_pending(jobs: list[Job]) -> tuple[float, float]:
    spent = 0.0
    pending = 0.0
    for job in jobs:
        if job.status in {"queued", "running"}:
            pending += _units_of(job, pending=True)
        else:
            spent += _units_of(job, pending=False)
    return round(spent, 4), round(pending, 4)


def adapter_mix(jobs: list[Job]) -> dict[str, int]:
    mix: dict[str, int] = {}
    for job in jobs:
        name = job.adapter or STUB_NAME
        mix[name] = mix.get(name, 0) + 1
    return dict(sorted(mix.items()))


def job_counts(jobs: list[Job]) -> dict[str, int]:
    counts = {
        "queued": 0,
        "running": 0,
        "succeeded": 0,
        "failed": 0,
        "cancelled": 0,
        "total": len(jobs),
    }
    for job in jobs:
        if job.status in counts:
            counts[job.status] += 1
    return counts


def refuse_if_over_cap(
    db: Session,
    project: Project,
    extra_units: float,
    settings: Settings | None = None,
) -> None:
    cfg = settings or get_settings()
    if not project_hard_stop(project, cfg):
        return
    cap = project_cap(project, cfg)
    if cap is None:
        return
    jobs = (
        db.query(Job)
        .join(Episode, Job.episode_id == Episode.id)
        .filter(Episode.project_id == project.id)
        .all()
    )
    spent, pending = spent_and_pending(jobs)
    projected = spent + pending + extra_units
    if projected > cap + 1e-9:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "budget_cap",
                "message": (
                    "Hard stop: this enqueue would exceed the project budget cap. "
                    "Units are operator credits, not a cloud bill."
                ),
                "spent_units": spent,
                "pending_units": pending,
                "extra_units": extra_units,
                "cap_units": cap,
                "currency": currency(cfg),
                "disclaimer": DISCLAIMER,
            },
        )


def _episode_row(episode: Episode, jobs: list[Job]) -> dict[str, Any]:
    spent, pending = spent_and_pending(jobs)
    counts = job_counts(jobs)
    return {
        "episode_id": episode.id,
        "title": episode.title,
        "chapter": episode.chapter,
        "spent_units": spent,
        "pending_units": pending,
        "job_count": counts["total"],
        "succeeded": counts["succeeded"],
        "failed": counts["failed"],
        "cancelled": counts["cancelled"],
        "adapter_mix": adapter_mix(jobs),
    }


def summarize(
    db: Session,
    *,
    project_id: str | None = None,
    episode_id: str | None = None,
    organization_id: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    query = db.query(Job)
    if episode_id:
        query = query.filter(Job.episode_id == episode_id)
    elif project_id:
        query = query.join(Episode, Job.episode_id == Episode.id).filter(
            Episode.project_id == project_id
        )
    elif organization_id:
        query = (
            query.join(Episode, Job.episode_id == Episode.id)
            .join(Project, Episode.project_id == Project.id)
            .filter(Project.organization_id == organization_id)
        )
    jobs = query.all()
    spent, pending = spent_and_pending(jobs)
    projects_q = db.query(Project).order_by(Project.updated_at.desc())
    if project_id:
        projects_q = projects_q.filter(Project.id == project_id)
    elif organization_id:
        projects_q = projects_q.filter(Project.organization_id == organization_id)
    project_rows: list[dict[str, Any]] = []
    for project in projects_q.all():
        if episode_id and all(ep.id != episode_id for ep in project.episodes):
            continue
        project_jobs = [job for job in jobs if job.episode and job.episode.project_id == project.id]
        if not project_jobs and project_id is None and episode_id is None:
            # still show projects with zero spend on the org-wide dashboard
            project_jobs = (
                db.query(Job)
                .join(Episode, Job.episode_id == Episode.id)
                .filter(Episode.project_id == project.id)
                .all()
            )
        p_spent, p_pending = spent_and_pending(project_jobs)
        cap = project_cap(project, cfg)
        episode_rows = []
        for episode in project.episodes:
            if episode_id and episode.id != episode_id:
                continue
            ep_jobs = [job for job in project_jobs if job.episode_id == episode.id]
            episode_rows.append(_episode_row(episode, ep_jobs))
        project_rows.append(
            {
                "project_id": project.id,
                "name": project.name,
                "slug": project.slug,
                "spent_units": p_spent,
                "pending_units": p_pending,
                "cap_units": cap,
                "hard_stop": project_hard_stop(project, cfg),
                "over_cap": cap is not None and (p_spent + p_pending) > cap + 1e-9,
                "job_count": len(project_jobs),
                "adapter_mix": adapter_mix(project_jobs),
                "still_adapter": project.still_adapter or STUB_NAME,
                "clip_adapter": project.clip_adapter or STUB_NAME,
                "usd_estimate": usd_estimate(p_spent, cfg),
                "episodes": episode_rows,
            }
        )
    cap = None
    hard = bool(cfg.budget_hard_stop)
    if project_id and project_rows:
        cap = project_rows[0]["cap_units"]
        hard = project_rows[0]["hard_stop"]
    elif cfg.budget_cap_units is not None:
        cap = float(cfg.budget_cap_units)
    return {
        "currency": currency(cfg),
        "usd_per_unit": usd_per_unit(cfg),
        "rates": parse_rate_table(None, cfg),
        "disclaimer": DISCLAIMER,
        "spent_units": spent,
        "pending_units": pending,
        "usd_estimate": usd_estimate(spent, cfg),
        "cap_units": cap,
        "hard_stop": hard,
        "job_counts": job_counts(jobs),
        "adapter_mix": adapter_mix(jobs),
        "projects": project_rows,
    }
