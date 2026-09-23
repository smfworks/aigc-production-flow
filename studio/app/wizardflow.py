"""Persist the Create wizard and turn finished answers into a draft pack."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .agentbrief import build_agent_brief
from .clarify import clarify_questions
from .agentrun import build_steps, kickoff, recompute, resume_if_idle
from .blankpack import pack_zip_bytes
from .createflow import new_episode
from .director import public_director, scope_note
from .hermesdrop import write_drop
from .models import (
    APPROVAL_DRAFT,
    AgentRun,
    Episode,
    MediaAsset,
    PackRevision,
    Project,
    WizardSession,
    new_id,
    utcnow,
)
from .packzip import slugify
from .signoff import is_signed_off
from .store import get_store
from .verticals import seed_pack_revision
from .wizardpack import (
    FORMATS,
    engine_report,
    missing_answers,
    normalize_answers,
    pack_from_answers,
)

WIZARD_STEPS = (
    "prompt",
    "format",
    "length",
    "tone",
    "scope",
    "cast",
    "audio",
    "engines",
    "tree",
    "checkpoints",
)
_READY_KEYS = ("task_tree", "must_nots", "platform_formats", "claim_bans")


def _steps_public() -> list[str]:
    return list(WIZARD_STEPS)


def engine_for(wizard: WizardSession, project: Project | None = None) -> dict[str, Any]:
    return engine_report(wizard.answers if isinstance(wizard.answers, dict) else {}, project)


def create_session(
    db: Session,
    *,
    org_id: str,
    user_name: str,
    prompt: str,
    recipe: dict[str, Any] | None = None,
) -> WizardSession:
    raw: dict[str, Any] = {}
    if recipe:
        saved = recipe.get("answers") if isinstance(recipe.get("answers"), dict) else {}
        raw.update(saved)
        if recipe.get("task_tree"):
            raw["task_tree"] = recipe["task_tree"]
    if prompt:
        raw["prompt"] = prompt
    elif "prompt" not in raw:
        raw["prompt"] = ""
    answers = normalize_answers(raw)
    wizard = WizardSession(
        organization_id=org_id,
        status="draft",
        step="format" if answers["prompt"] else "prompt",
        answers=answers,
        created_by=user_name,
    )
    db.add(wizard)
    db.flush()
    return wizard


def get_session(db: Session, wizard_id: str, org_id: str) -> WizardSession:
    wizard = db.get(WizardSession, wizard_id)
    if wizard is None or wizard.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wizard not found.")
    return wizard


def latest_draft(db: Session, *, org_id: str, user_name: str) -> WizardSession | None:
    return (
        db.query(WizardSession)
        .filter(
            WizardSession.organization_id == org_id,
            WizardSession.created_by == user_name,
            WizardSession.status == "draft",
        )
        .order_by(WizardSession.updated_at.desc())
        .first()
    )


def _identity_counts(db: Session, episode_id: str | None) -> tuple[int, int, bool]:
    if not episode_id:
        return 0, 0, False
    episode = db.get(Episode, episode_id)
    if episode is None:
        return 0, 0, False
    sheets = (
        db.query(MediaAsset)
        .filter(MediaAsset.episode_id == episode.id, MediaAsset.kind == "sheet")
        .all()
    )
    approved = sum(1 for row in sheets if row.approval_status == "approved")
    draft = sum(1 for row in sheets if row.approval_status != "approved")
    return approved, draft, is_signed_off(episode)


def director_for_session(db: Session, wizard: WizardSession) -> dict[str, Any]:
    answers = normalize_answers(wizard.answers if isinstance(wizard.answers, dict) else {})
    pack = None
    if wizard.revision_id:
        revision = db.get(PackRevision, wizard.revision_id)
        if revision and isinstance(revision.pack_json, dict):
            pack = revision.pack_json
    if pack is None and not missing_answers(answers):
        pack, _honesty, _people, _answers = pack_from_answers(answers)
    approved, draft, signed = _identity_counts(db, wizard.episode_id)
    if wizard.episode_id is None and pack is not None:
        characters = pack.get("characters") if isinstance(pack.get("characters"), list) else []
        named = [row for row in characters if isinstance(row, dict) and str(row.get("name") or "").strip()]
        draft = len(named)
    return public_director(
        answers,
        pack=pack,
        approved_sheets=approved,
        draft_sheets=draft,
        signed_off=signed,
    )


def _store_director(db: Session, wizard: WizardSession) -> None:
    """Write the plan onto the draft pack and the project. Does not run jobs."""
    if not wizard.revision_id or not wizard.project_id:
        return
    revision = db.get(PackRevision, wizard.revision_id)
    project = db.get(Project, wizard.project_id)
    if revision is None or not isinstance(revision.pack_json, dict):
        return
    answers = normalize_answers(wizard.answers if isinstance(wizard.answers, dict) else {})
    director = director_for_session(db, wizard)
    answers["task_tree"] = director["task_tree"]
    pack = dict(revision.pack_json)
    meta = pack.get("studioMeta") if isinstance(pack.get("studioMeta"), dict) else {}
    meta = dict(meta)
    meta["notes"] = scope_note(director["scope"])
    meta["director"] = director
    pack["studioMeta"] = meta
    revision.pack_json = pack
    flag_modified(revision, "pack_json")
    if revision.zip_path:
        get_store().put(revision.zip_path, pack_zip_bytes(pack))
    if project is not None:
        project.director_state = {
            "scope": director["scope"],
            "task_tree": director["task_tree"],
            "craft_lanes": director["craft_lanes"],
            "checkpoints": director["checkpoints"],
            "agents_ran": False,
            "called_comfy": False,
            "hermes_ran": False,
            "produced_mp4": False,
            "executes": False,
        }
        project.updated_at = utcnow()
    wizard.answers = answers


def patch_session(db: Session, wizard: WizardSession, *, step: str | None, answers: dict[str, Any]) -> WizardSession:
    if wizard.status == "handed_off":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This creation was already sent. Start a new one to change the plan.",
        )
    if wizard.status != "draft":
        incoming = answers or {}
        if not any(key in incoming for key in _READY_KEYS):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This creation already has a pack. You can still update the task tree and deliverable scope.",
            )
        current = dict(wizard.answers or {})
        for key in _READY_KEYS:
            if key in incoming:
                current[key] = incoming[key]
        wizard.answers = normalize_answers(current)
        _store_director(db, wizard)
        wizard.updated_at = utcnow()
        db.flush()
        return wizard
    if step:
        if step not in WIZARD_STEPS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"step must be one of: {', '.join(WIZARD_STEPS)}",
            )
        wizard.step = step
    current = dict(wizard.answers or {})
    if answers:
        current.update(answers)
    wizard.answers = normalize_answers(current)
    wizard.updated_at = utcnow()
    db.flush()
    return wizard


def _seed_identity_drafts(db: Session, episode: Episode, user_name: str, people: list[dict[str, str]]) -> None:
    store = get_store()
    for person in people:
        name = person["name"][:200]
        body = json.dumps(
            {
                "kind": "identity-draft",
                "entity": name,
                "entity_type": "character",
                "approval_status": "draft",
                "claim": "Wizard cast note. Not an approved sheet. No pixels. Not a likeness.",
                "notes": person.get("notes") or "",
            },
            indent=2,
        ).encode("utf-8")
        asset = MediaAsset(
            episode_id=episode.id,
            kind="sheet",
            original_name=f"draft-{slugify(name, 'lead')}.json",
            stored_name="",
            content_type="application/json",
            path="",
            entity_label=name,
            entity_type="character",
            notes=("Wizard cast note. Not approved. " + (person.get("notes") or ""))[:2000],
            created_by=user_name,
            approval_status=APPROVAL_DRAFT,
            lock_keywords="",
        )
        db.add(asset)
        db.flush()
        stored = f"{asset.id}.json"
        rel = str(Path(episode.id) / "identity" / stored)
        store.put(rel, body)
        asset.stored_name = stored
        asset.path = rel


def finish_session(
    db: Session,
    wizard: WizardSession,
    *,
    user_name: str,
    unique_slug,
    acknowledge_gaps: bool = False,
) -> tuple[WizardSession, Project, Episode, PackRevision]:
    if wizard.status in {"ready", "handed_off"} and wizard.episode_id and wizard.project_id:
        project = db.get(Project, wizard.project_id)
        episode = db.get(Episode, wizard.episode_id)
        revision = db.get(PackRevision, wizard.revision_id) if wizard.revision_id else None
        if project and episode and revision:
            return wizard, project, episode, revision
    answers = normalize_answers(wizard.answers if isinstance(wizard.answers, dict) else {})
    missing = missing_answers(answers)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Wizard still needs: {', '.join(missing)}.",
        )
    if answers["format"] not in FORMATS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pick a format.")
    questions = clarify_questions(answers)
    if questions and not acknowledge_gaps and not answers.get("clarify_ack"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "clarify_required",
                "message": (
                    "Brief fields are missing. Answer them, or proceed with the gaps named. "
                    "This pause is not a gate checkpoint."
                ),
                "questions": questions,
            },
        )
    if acknowledge_gaps and questions:
        answers = {**answers, "clarify_ack": True, "clarify_gaps": [row["field"] for row in questions]}
    pack, _honesty, people, answers = pack_from_answers(answers)
    title = str(pack.get("title") or "Untitled")[:200]
    project = Project(
        organization_id=wizard.organization_id,
        name=title,
        slug=unique_slug(db, wizard.organization_id, title),
        description=str(answers["prompt"])[:2000],
        still_adapter=answers["still_pref"],
        clip_adapter=answers["clip_pref"],
        director_state={},
    )
    db.add(project)
    db.flush()
    episode = new_episode(
        db,
        project,
        title="Ep 1",
        chapter=1,
        season=1,
        sequence=1,
        synopsis=str(answers["prompt"])[:2000],
        log_line=str(pack.get("logLine") or "")[:2000],
    )
    revision = seed_pack_revision(
        db,
        episode,
        user_name,
        pack_zip_bytes(pack),
        f"wizard-{slugify(title, 'pack')}.zip",
    )
    _seed_identity_drafts(db, episode, user_name, people)
    wizard.project_id = project.id
    wizard.episode_id = episode.id
    wizard.revision_id = revision.id
    wizard.status = "ready"
    wizard.step = "checkpoints"
    wizard.answers = answers
    wizard.updated_at = utcnow()
    db.flush()
    _store_director(db, wizard)
    db.flush()
    return wizard, project, episode, revision


def handoff_hermes(
    db: Session,
    wizard: WizardSession,
    *,
    user_name: str,
) -> tuple[WizardSession, AgentRun, dict[str, Any]]:
    if wizard.status == "draft" or not wizard.episode_id or not wizard.revision_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Finish the wizard before sending to Hermes.",
        )
    answers = wizard.answers if isinstance(wizard.answers, dict) else {}
    questions = clarify_questions(answers)
    if questions and not answers.get("clarify_ack"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "clarify_required",
                "message": (
                    "Brief fields are still missing. Answer them before the handoff writes craft lanes. "
                    "This pause is not a gate checkpoint."
                ),
                "questions": questions,
            },
        )
    episode = db.get(Episode, wizard.episode_id)
    revision = db.get(PackRevision, wizard.revision_id)
    project = db.get(Project, wizard.project_id) if wizard.project_id else None
    if episode is None or revision is None or episode.project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wizard pack is missing.")
    _store_director(db, wizard)
    db.flush()
    db.refresh(revision)
    engines = engine_report(wizard.answers if isinstance(wizard.answers, dict) else {}, project or episode.project)
    run_id = new_id()
    payload = write_drop(
        episode,
        revision,
        run_id=run_id,
        wizard_id=wizard.id,
        engines=engines,
    )
    brief = build_agent_brief(episode, revision)
    db.refresh(episode)
    steps = build_steps(episode, brief)
    run = AgentRun(
        id=run_id,
        organization_id=wizard.organization_id,
        wizard_id=wizard.id,
        project_id=episode.project_id,
        episode_id=episode.id,
        revision_id=revision.id,
        status="queued",
        drop_dir=str(payload.get("drop_dir") or ""),
        deep_link=str(payload.get("deep_link") or ""),
        payload=payload,
        plan={"steps": steps},
        called_comfy=False,
        hermes_ran=False,
        stitch_state="pending",
        created_by=user_name,
    )
    db.add(run)
    wizard.agent_run_id = run.id
    wizard.status = "handed_off"
    wizard.updated_at = utcnow()
    db.commit()
    db.refresh(run)
    kickoff(db, run, user_name)
    db.refresh(run)
    return wizard, run, payload


def run_for_org(db: Session, run_id: str, org_id: str) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if run is None or run.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found.")
    return run


def refresh_run(db: Session, run: AgentRun) -> AgentRun:
    return resume_if_idle(db, run)


def public_steps(run: AgentRun) -> list[dict[str, Any]]:
    raw = run.plan if isinstance(run.plan, dict) else {}
    steps = raw.get("steps") if isinstance(raw.get("steps"), list) else []
    return [step for step in steps if isinstance(step, dict)]


def ensure_recompute(run: AgentRun) -> None:
    recompute(run, public_steps(run))
