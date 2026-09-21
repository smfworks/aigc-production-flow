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
MEDIA_UPLOAD = "media.upload"
PROJECT_CREATE = "project.create"
RETENTION_APPLY = "retention.apply"
COMMENT_CREATE = "comment.create"
COMMENT_RESOLVE = "comment.resolve"
MEMBER_ADD = "member.add"
MEMBER_ROLE = "member.role"

ACTIONS = (
    REVIEW_SET,
    REVIEW_SIGNOFF,
    REVIEW_OVERRIDE,
    JOB_ENQUEUE,
    JOB_CANCEL,
    PACK_IMPORT,
    PACK_EXPORT,
    MEDIA_UPLOAD,
    PROJECT_CREATE,
    RETENTION_APPLY,
    COMMENT_CREATE,
    COMMENT_RESOLVE,
    MEMBER_ADD,
    MEMBER_ROLE,
)


def record(
    db: Session,
    *,
    actor: str,
    action: str,
    project_id: str | None = None,
    episode_id: str | None = None,
    entity_type: str = "",
    entity_id: str = "",
    detail: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor=actor or "local-dev",
        action=action,
        project_id=project_id,
        episode_id=episode_id,
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
    action: str | None = None,
    limit: int = 200,
) -> list[AuditEvent]:
    query = db.query(AuditEvent).order_by(AuditEvent.created_at.desc())
    if episode_id:
        query = query.filter(AuditEvent.episode_id == episode_id)
    if project_id:
        query = query.filter(AuditEvent.project_id == project_id)
    if action:
        query = query.filter(AuditEvent.action == action)
    return query.limit(max(1, min(limit, 500))).all()


def event_out(event: AuditEvent) -> dict[str, Any]:
    episode: Episode | None = event.episode
    project: Project | None = event.project
    if project is None and episode is not None:
        project = episode.project
    return {
        "id": event.id,
        "actor": event.actor,
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "project_id": event.project_id or (episode.project_id if episode else None),
        "episode_id": event.episode_id,
        "project_name": project.name if project else "",
        "episode_title": episode.title if episode else "",
        "detail": event.detail if isinstance(event.detail, dict) else {},
        "created_at": event.created_at,
    }
