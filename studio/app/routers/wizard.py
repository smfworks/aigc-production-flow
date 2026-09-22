"""Create wizard, Hermes handoff, and agent-run status."""

from fastapi import APIRouter, status

from ..agentrun import honesty_note
from ..audit import HERMES_HANDOFF, PROJECT_CREATE, WIZARD_FINISH, WIZARD_START, record
from ..deps import DbDep, get_active_org
from ..models import AgentRun, PackRevision, utcnow
from ..rbac import JobsUser, MutateUser, ReadUser
from ..schemas import (
    AgentRunOut,
    AgentStepOut,
    EngineHonestyOut,
    HermesHandoffOut,
    WizardOut,
    WizardPatchIn,
    WizardStartIn,
)
from ..wizardflow import (
    WIZARD_STEPS,
    create_session,
    engine_for,
    finish_session,
    get_session,
    handoff_hermes,
    latest_draft,
    patch_session,
    public_steps,
    refresh_run,
    run_for_org,
)

router = APIRouter(tags=["wizard"])


def _wizard_out(db, wizard) -> WizardOut:
    project = None
    gates = False
    if wizard.project_id:
        from ..models import Project

        project = db.get(Project, wizard.project_id)
    if wizard.revision_id:
        revision = db.get(PackRevision, wizard.revision_id)
        gates = bool(revision and revision.all_gates_green)
    engines = EngineHonestyOut(**engine_for(wizard, project))
    return WizardOut(
        id=wizard.id,
        status=wizard.status,
        step=wizard.step,
        steps=list(WIZARD_STEPS),
        answers=wizard.answers if isinstance(wizard.answers, dict) else {},
        project_id=wizard.project_id,
        episode_id=wizard.episode_id,
        revision_id=wizard.revision_id or None,
        agent_run_id=wizard.agent_run_id or None,
        gates_green=gates,
        generate_ready=False,
        engines=engines,
        created_at=wizard.created_at,
        updated_at=wizard.updated_at,
    )


def _step_out(raw: dict) -> AgentStepOut:
    return AgentStepOut(
        order=int(raw.get("order") or 0),
        kind=str(raw.get("kind") or ""),
        subject=str(raw.get("subject") or ""),
        take=str(raw.get("take") or ""),
        status=str(raw.get("status") or "planned"),
        job_id=str(raw.get("job_id") or ""),
        shot_id=str(raw.get("shot_id") or ""),
        adapter=str(raw.get("adapter") or ""),
        adapter_label=str(raw.get("adapter_label") or ""),
        note=str(raw.get("note") or ""),
        error=str(raw.get("error") or ""),
        claim=str(raw.get("claim") or ""),
        called_comfy=bool(raw.get("called_comfy")),
        produced_mp4=bool(raw.get("produced_mp4")),
        stitch_state=str(raw.get("stitch_state") or ""),
    )


def _run_out(run: AgentRun) -> AgentRunOut:
    return AgentRunOut(
        id=run.id,
        wizard_id=run.wizard_id,
        project_id=run.project_id,
        episode_id=run.episode_id,
        revision_id=run.revision_id or "",
        status=run.status,
        stitch_state=run.stitch_state or "pending",
        deep_link=run.deep_link or "",
        drop_dir=run.drop_dir or "",
        called_comfy=bool(run.called_comfy),
        hermes_ran=bool(run.hermes_ran),
        honesty_note=honesty_note(run),
        steps=[_step_out(step) for step in public_steps(run)],
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


@router.post("/api/create/wizard", response_model=WizardOut, status_code=status.HTTP_201_CREATED)
def start_wizard(body: WizardStartIn, user: MutateUser, db: DbDep) -> WizardOut:
    org = get_active_org(db, user)
    wizard = create_session(db, org_id=org.id, user_name=user.name, prompt=body.prompt)
    record(
        db,
        actor=user.name,
        action=WIZARD_START,
        organization_id=org.id,
        entity_type="wizard",
        entity_id=wizard.id,
        detail={"has_prompt": bool((body.prompt or "").strip()), "fake_generate": False},
    )
    db.commit()
    db.refresh(wizard)
    return _wizard_out(db, wizard)


@router.get("/api/create/wizard/open", response_model=WizardOut | None)
def open_wizard(user: ReadUser, db: DbDep) -> WizardOut | None:
    org = get_active_org(db, user)
    wizard = latest_draft(db, org_id=org.id, user_name=user.name)
    if wizard is None:
        return None
    return _wizard_out(db, wizard)


@router.get("/api/create/wizard/{wizard_id}", response_model=WizardOut)
def read_wizard(wizard_id: str, user: ReadUser, db: DbDep) -> WizardOut:
    org = get_active_org(db, user)
    return _wizard_out(db, get_session(db, wizard_id, org.id))


@router.patch("/api/create/wizard/{wizard_id}", response_model=WizardOut)
def update_wizard(wizard_id: str, body: WizardPatchIn, user: MutateUser, db: DbDep) -> WizardOut:
    org = get_active_org(db, user)
    wizard = patch_session(
        db,
        get_session(db, wizard_id, org.id),
        step=body.step,
        answers=body.answers,
    )
    wizard.updated_at = utcnow()
    db.commit()
    db.refresh(wizard)
    return _wizard_out(db, wizard)


@router.post("/api/create/wizard/{wizard_id}/finish", response_model=WizardOut)
def finish_wizard(wizard_id: str, user: MutateUser, db: DbDep) -> WizardOut:
    org = get_active_org(db, user)
    wizard = get_session(db, wizard_id, org.id)
    from .projects import _unique_slug

    already = wizard.status in {"ready", "handed_off"} and bool(wizard.episode_id)
    wizard, project, episode, revision = finish_session(
        db,
        wizard,
        user_name=user.name,
        unique_slug=_unique_slug,
    )
    if not already:
        record(
            db,
            actor=user.name,
            action=PROJECT_CREATE,
            project_id=project.id,
            episode_id=episode.id,
            organization_id=org.id,
            entity_type="project",
            entity_id=project.id,
            detail={"mode": "wizard", "fake_generate": False, "gates_green": bool(revision.all_gates_green)},
        )
        record(
            db,
            actor=user.name,
            action=WIZARD_FINISH,
            project_id=project.id,
            episode_id=episode.id,
            organization_id=org.id,
            entity_type="wizard",
            entity_id=wizard.id,
            detail={
                "revision_id": revision.id,
                "gates_green": bool(revision.all_gates_green),
                "generate_ready": False,
                "source": "wizard",
            },
        )
    db.commit()
    db.refresh(wizard)
    return _wizard_out(db, wizard)


@router.post(
    "/api/create/wizard/{wizard_id}/handoff/hermes",
    response_model=HermesHandoffOut,
    status_code=status.HTTP_201_CREATED,
)
def send_hermes(wizard_id: str, user: JobsUser, db: DbDep) -> HermesHandoffOut:
    org = get_active_org(db, user)
    wizard = get_session(db, wizard_id, org.id)
    wizard, run, payload = handoff_hermes(db, wizard, user_name=user.name)
    record(
        db,
        actor=user.name,
        action=HERMES_HANDOFF,
        project_id=run.project_id,
        episode_id=run.episode_id,
        organization_id=org.id,
        entity_type="agent_run",
        entity_id=run.id,
        detail={
            "called_comfy": False,
            "hermes_ran": False,
            "deep_link": run.deep_link,
            "drop_dir": run.drop_dir,
        },
    )
    db.commit()
    db.refresh(run)
    return HermesHandoffOut(
        wizard_id=wizard.id,
        deep_link=run.deep_link,
        drop_dir=run.drop_dir,
        payload=payload,
        run=_run_out(run),
    )


@router.get("/api/agent-runs/{run_id}", response_model=AgentRunOut)
def read_agent_run(run_id: str, user: ReadUser, db: DbDep) -> AgentRunOut:
    org = get_active_org(db, user)
    run = refresh_run(db, run_for_org(db, run_id, org.id))
    return _run_out(run)


@router.get("/api/episodes/{episode_id}/agent-runs", response_model=list[AgentRunOut])
def list_episode_runs(episode_id: str, user: ReadUser, db: DbDep) -> list[AgentRunOut]:
    from ..deps import get_episode

    episode = get_episode(db, episode_id, user)
    rows = (
        db.query(AgentRun)
        .filter(AgentRun.episode_id == episode.id, AgentRun.organization_id == user.org_id)
        .order_by(AgentRun.created_at.desc())
        .all()
    )
    refreshed = [refresh_run(db, row) for row in rows]
    return [_run_out(row) for row in refreshed]
