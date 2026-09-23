"""Ordered agent-run jobs: sheets, plates, hop-1 clips, then stitch.

Studio writes the jobs. It does not invoke Hermes. Stub clips are fixture receipts
and do not stamp generate-ok. Live clips are refused until batch-precheck is green.
"""

from __future__ import annotations

import copy
from contextvars import ContextVar
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .adapters.registry import resolve_adapter_name
from .config import get_settings
from .models import AgentRun, Episode, Job, Shot, utcnow

_SUPPRESS = ContextVar("agent_run_suppress_advance", default=False)

_SKIP = {"refused_live", "awaiting_gates", "skipped"}
_TERMINAL_OK = {"succeeded", "skipped", "awaiting_stitch", "refused_live", "awaiting_gates"}


def build_steps(episode: Episode, brief: dict[str, Any]) -> list[dict[str, Any]]:
    unused = sorted(list(episode.shots or []), key=lambda row: row.sort_index)
    steps: list[dict[str, Any]] = []
    for job in brief.get("jobs") or []:
        if not isinstance(job, dict):
            continue
        kind = str(job.get("kind") or "")
        step: dict[str, Any] = {
            "order": int(job.get("order") or len(steps) + 1),
            "kind": kind,
            "subject": str(job.get("subject") or ""),
            "take": str(job.get("take") or ""),
            "status": "planned",
            "job_id": "",
            "shot_id": "",
            "adapter": "",
            "adapter_label": str(job.get("adapter_label") or ""),
            "note": str(job.get("note") or ""),
            "error": "",
            "claim": "",
            "called_comfy": False,
            "produced_mp4": False,
            "stitch_state": "pending" if kind == "stitch" else "",
        }
        if job.get("enabled") is False:
            step["status"] = "skipped"
            step["called_comfy"] = False
            step["produced_mp4"] = False
            if kind == "stitch":
                step["stitch_state"] = "pending"
            steps.append(step)
            continue
        if kind == "clip-hop1":
            wanted = step["take"]
            match = next((row for row in unused if wanted and row.take == wanted), None)
            if match is None and unused:
                match = unused[0]
            if match is not None:
                unused.remove(match)
                step["shot_id"] = match.id
                step["take"] = wanted or match.take
        steps.append(step)
    return steps


def _copy(step: dict[str, Any], job: Job) -> None:
    result = job.result if isinstance(job.result, dict) else {}
    step["adapter"] = job.adapter or ""
    step["called_comfy"] = bool(result.get("called_comfy"))
    step["error"] = job.error or ""
    step["claim"] = str(result.get("claim") or "")
    if step.get("kind") == "stitch":
        produced = bool(result.get("produced_mp4"))
        step["produced_mp4"] = produced
        if job.status == "succeeded" and produced:
            step["status"] = "succeeded"
            step["stitch_state"] = "stitched"
        elif job.status == "succeeded":
            step["status"] = "awaiting_stitch"
            step["stitch_state"] = str(result.get("state") or "awaiting_stitch")
        else:
            step["status"] = job.status
            step["stitch_state"] = str(result.get("state") or job.status)
        return
    step["status"] = job.status
    step["produced_mp4"] = False


def _classify(session: Session, steps: list[dict[str, Any]]) -> str | int:
    for index, step in enumerate(steps):
        job_id = str(step.get("job_id") or "")
        if job_id:
            job = session.get(Job, job_id)
            if job is None:
                step["status"] = "failed"
                step["error"] = "Job row is missing."
                return "stopped"
            if job.status in {"queued", "running"}:
                step["status"] = job.status
                return "wait"
            if job.status in {"failed", "cancelled"}:
                step["status"] = job.status
                step["error"] = job.error or ""
                return "stopped"
            _copy(step, job)
            continue
        if step.get("status") in _SKIP or step.get("status") in {"succeeded", "awaiting_stitch", "failed"}:
            continue
        return index
    return "done"


def recompute(run: AgentRun, steps: list[dict[str, Any]]) -> None:
    statuses = [str(step.get("status") or "") for step in steps]
    run.called_comfy = any(bool(step.get("called_comfy")) for step in steps)
    run.hermes_ran = False
    stitch = [step for step in steps if step.get("kind") == "stitch"]
    if stitch:
        run.stitch_state = str(stitch[-1].get("stitch_state") or stitch[-1].get("status") or "pending")
    else:
        run.stitch_state = "pending"
    if any(status == "failed" for status in statuses):
        run.status = "failed"
    elif any(status in {"queued", "running"} for status in statuses):
        run.status = "running"
    elif any(status == "planned" for status in statuses):
        run.status = "queued"
    elif any(status == "awaiting_stitch" for status in statuses):
        run.status = "awaiting_stitch"
    elif any(status in {"refused_live", "awaiting_gates"} for status in statuses) and run.stitch_state != "stitched":
        run.status = "awaiting_stitch" if run.stitch_state == "awaiting_stitch" else "blocked"
    elif statuses and all(status in _TERMINAL_OK for status in statuses):
        # A concat file is a stitch result. It is not an episode Completed stamp.
        run.status = "stitched" if run.stitch_state == "stitched" else "awaiting_stitch"
    else:
        run.status = run.status or "queued"
    run.plan = {"steps": copy.deepcopy(steps)}
    flag_modified(run, "plan")
    run.updated_at = utcnow()


def _payload(run: AgentRun, step: dict[str, Any]) -> dict[str, Any]:
    return {
        "agent_run_id": run.id,
        "order": step.get("order"),
        "entity": step.get("subject") or "",
        "entity_label": step.get("subject") or "",
        "take": step.get("take") or "",
        "source": "create-wizard",
    }


def _refuse_live(step: dict[str, Any]) -> None:
    step["status"] = "refused_live"
    step["called_comfy"] = False
    step["job_id"] = ""
    step["note"] = (
        "This clip lane is live, and the pack is not generate-ready. "
        "Studio did not call Comfy. Hermes should use the stub brief or wait for green gates."
    )


def _enqueue_one(
    session: Session,
    run: AgentRun,
    steps: list[dict[str, Any]],
    index: int,
    user_name: str,
) -> None:
    from .jobs.service import dispatch_job, enqueue_job
    from .precheck import hop1_enqueue_blockers

    step = steps[index]
    episode = session.get(Episode, run.episode_id)
    if episode is None:
        step["status"] = "failed"
        step["error"] = "Episode is missing."
        recompute(run, steps)
        session.commit()
        return
    kind = str(step.get("kind") or "")
    project = episode.project
    payload = _payload(run, step)
    job: Job | None = None
    if kind == "clip-hop1":
        resolved = resolve_adapter_name("clip-hop1", get_settings(), project=project)
        shot_id = str(step.get("shot_id") or "")
        shot = session.get(Shot, shot_id) if shot_id else None
        if resolved != "stub":
            if hop1_enqueue_blockers(episode, shot):
                _refuse_live(step)
                recompute(run, steps)
                session.commit()
                return
        if shot is None:
            step["status"] = "skipped"
            step["note"] = "No shot row for this hop-1. Stitch still reads the playlist."
            recompute(run, steps)
            session.commit()
            return
        job = enqueue_job(
            session,
            episode=episode,
            user_name=user_name,
            job_type="clip-hop1",
            shot_id=shot.id,
            payload=payload,
            allow_stub_fixture=resolved == "stub",
            autocommit=False,
        )
    elif kind == "stitch":
        job = enqueue_job(
            session,
            episode=episode,
            user_name=user_name,
            job_type="stitch",
            payload=payload,
            autocommit=False,
        )
    elif kind in {"still-sheet", "still-plate"}:
        job = enqueue_job(
            session,
            episode=episode,
            user_name=user_name,
            job_type=kind,
            payload=payload,
            autocommit=False,
        )
    else:
        step["status"] = "skipped"
        step["note"] = f"No runner for {kind}."
        recompute(run, steps)
        session.commit()
        return
    step["job_id"] = job.id
    step["status"] = "queued"
    recompute(run, steps)
    session.commit()
    dispatch_job(session, job)
    session.refresh(job)
    _copy(step, job)
    recompute(run, steps)
    session.commit()


def kickoff(session: Session, run: AgentRun, user_name: str) -> AgentRun:
    token = _SUPPRESS.set(True)
    try:
        for _ in range(48):
            session.refresh(run)
            raw = run.plan if isinstance(run.plan, dict) else {}
            steps = copy.deepcopy(raw.get("steps") or [])
            action = _classify(session, steps)
            if not isinstance(action, int):
                recompute(run, steps)
                session.commit()
                return run
            _enqueue_one(session, run, steps, action, user_name)
        session.refresh(run)
        return run
    finally:
        _SUPPRESS.reset(token)


def note_agent_job_finished(session: Session, job: Job) -> None:
    """Thread/Celery path. Inline kickoff suppresses this so it cannot double-enqueue."""
    if _SUPPRESS.get():
        return
    payload = job.payload if isinstance(job.payload, dict) else {}
    run_id = str(payload.get("agent_run_id") or "")
    if not run_id:
        return
    run = session.get(AgentRun, run_id)
    if run is None:
        return
    raw = run.plan if isinstance(run.plan, dict) else {}
    steps = copy.deepcopy(raw.get("steps") or [])
    action = _classify(session, steps)
    if not isinstance(action, int):
        recompute(run, steps)
        session.commit()
        return
    _enqueue_one(session, run, steps, action, job.created_by or run.created_by)


def resume_if_idle(session: Session, run: AgentRun) -> AgentRun:
    raw = run.plan if isinstance(run.plan, dict) else {}
    steps = copy.deepcopy(raw.get("steps") or [])
    action = _classify(session, steps)
    recompute(run, steps)
    session.commit()
    if isinstance(action, int):
        return kickoff(session, run, run.created_by)
    return run


def honesty_note(run: AgentRun) -> str:
    if run.hermes_ran:
        base = "Hermes reported a run."
    else:
        base = "Brief is on disk. Hermes has not been invoked by Studio."
    if run.called_comfy:
        called = " A job result says Comfy was called."
    else:
        called = " Comfy was not called."
    if run.stitch_state == "stitched":
        stitch = (
            " Stitch wrote a local concat file. That file does not mark the episode completed "
            "and does not stamp generate-ok."
        )
    elif run.stitch_state == "awaiting_stitch":
        stitch = " Stitch is awaiting a real concat. No MP4 was produced."
    else:
        stitch = " Stitch has not run."
    if run.status == "blocked":
        stitch += " A live clip was refused because the pack is not generate-ready."
    return base + called + stitch
