"""Enterprise-lite audit trail. Local-dev user ids are fine."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .models import AuditEvent, Episode, Project

REVIEW_SET = "review.set"
REVIEW_SIGNOFF = "review.signoff"
REVIEW_OVERRIDE = "review.override"
JOB_ENQUEUE = "job.enqueue"
JOB_CANCEL = "job.cancel"
PACK_IMPORT = "pack.import"
PACK_EXPORT = "pack.export"
PACK_DIFF = "pack.diff"
MEDIA_UPLOAD = "media.upload"
IDENTITY_APPROVE = "identity.approve"
IDENTITY_UNAPPROVE = "identity.unapprove"
IDENTITY_KEYWORDS = "identity.keywords"
IDENTITY_LINK = "identity.link"
EPISODE_REORDER = "episode.reorder"
PROJECT_CREATE = "project.create"
RETENTION_APPLY = "retention.apply"
COMMENT_CREATE = "comment.create"
COMMENT_RESOLVE = "comment.resolve"
MEMBER_ADD = "member.add"
MEMBER_ROLE = "member.role"
ORG_CREATE = "org.create"
BACKUP_EXPORT = "backup.export"
BACKUP_RESTORE = "backup.restore"
DEMO_SEED = "demo.seed"
PACK_SAVE = "pack.save"
BRAIN_DUMP = "brain.dump"
AGENT_EXPORT = "agent.export"
WIZARD_START = "wizard.start"
WIZARD_FINISH = "wizard.finish"
HERMES_HANDOFF = "hermes.handoff"

ACTIONS = (
    REVIEW_SET,
    REVIEW_SIGNOFF,
    REVIEW_OVERRIDE,
    JOB_ENQUEUE,
    JOB_CANCEL,
    PACK_IMPORT,
    PACK_EXPORT,
    PACK_DIFF,
    MEDIA_UPLOAD,
    IDENTITY_APPROVE,
    IDENTITY_UNAPPROVE,
    IDENTITY_KEYWORDS,
    IDENTITY_LINK,
    EPISODE_REORDER,
    PROJECT_CREATE,
    RETENTION_APPLY,
    COMMENT_CREATE,
    COMMENT_RESOLVE,
    MEMBER_ADD,
    MEMBER_ROLE,
    ORG_CREATE,
    BACKUP_EXPORT,
    BACKUP_RESTORE,
    DEMO_SEED,
    PACK_SAVE,
    BRAIN_DUMP,
    AGENT_EXPORT,
    WIZARD_START,
    WIZARD_FINISH,
    HERMES_HANDOFF,
)


def record(
    db: Session,
    *,
    actor: str,
    action: str,
    project_id: str | None = None,
    episode_id: str | None = None,
    organization_id: str | None = None,
    entity_type: str = "",
    entity_id: str = "",
    detail: dict[str, Any] | None = None,
) -> AuditEvent:
    org_id = organization_id
    if org_id is None and project_id:
        project = db.get(Project, project_id)
        if project:
            org_id = project.organization_id
    if org_id is None and episode_id:
        episode = db.get(Episode, episode_id)
        if episode and episode.project:
            org_id = episode.project.organization_id
    event = AuditEvent(
        actor=actor or "local-dev",
        action=action,
        project_id=project_id,
        episode_id=episode_id,
        organization_id=org_id,
        entity_type=entity_type or "",
        entity_id=entity_id or "",
        detail=detail if isinstance(detail, dict) else {},
    )
    db.add(event)
    return event


def list_events(
    db: Session,
    *,
    project_id: str | None = None,
    episode_id: str | None = None,
    organization_id: str | None = None,
    action: str | None = None,
    limit: int = 200,
) -> list[AuditEvent]:
    query = db.query(AuditEvent).order_by(AuditEvent.created_at.desc())
    if episode_id:
        query = query.filter(AuditEvent.episode_id == episode_id)
    if project_id:
        query = query.filter(AuditEvent.project_id == project_id)
    if organization_id:
        query = query.filter(
            (AuditEvent.organization_id == organization_id)
            | (
                AuditEvent.organization_id.is_(None)
                & AuditEvent.project_id.in_(
                    db.query(Project.id).filter(Project.organization_id == organization_id)
                )
            )
        )
    if action:
        query = query.filter(AuditEvent.action == action)
    return query.limit(max(1, min(limit, 500))).all()


def event_out(event: AuditEvent) -> dict[str, Any]:
    episode: Episode | None = event.episode
    project: Project | None = event.project
    if project is None and episode is not None:
        project = episode.project
    org_id = event.organization_id
    if not org_id and project is not None:
        org_id = project.organization_id
    return {
        "id": event.id,
        "actor": event.actor,
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "project_id": event.project_id or (episode.project_id if episode else None),
        "episode_id": event.episode_id,
        "organization_id": org_id,
        "project_name": project.name if project else "",
        "episode_title": episode.title if episode else "",
        "detail": event.detail if isinstance(event.detail, dict) else {},
        "created_at": event.created_at,
    }
