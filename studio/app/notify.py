"""In-app notifications plus an optional outbound webhook.

Unset ``STUDIO_NOTIFY_WEBHOOK_URL`` means no delivery is attempted. This is not
a SaaS notification product.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable

from sqlalchemy.orm import Session

from .config import get_settings
from .models import (
    NOTIFY_BLOCKER_CLEARED,
    NOTIFY_COMMENT_MENTION,
    NOTIFY_COMMENT_SHOT,
    NOTIFY_JOB_FAILED,
    NOTIFY_JOB_SUCCEEDED,
    NOTIFY_KINDS,
    NOTIFY_SIGNOFF_REQUESTED,
    ROLE_PRODUCER,
    ROLE_REVIEWER,
    Comment,
    Episode,
    Job,
    Notification,
    OrgMember,
    utcnow,
)

log = logging.getLogger("studio.notify")

MENTION_RE = re.compile(r"@([A-Za-z0-9._-]{1,80})")


def webhook_configured(settings=None) -> bool:
    cfg = settings or get_settings()
    return bool((cfg.notify_webhook_url or "").strip())


def notification_href(row: Notification) -> str:
    if row.project_id and row.episode_id and row.shot_id:
        return f"#/projects/{row.project_id}/episodes/{row.episode_id}/shots/{row.shot_id}"
    if row.project_id and row.episode_id:
        return f"#/projects/{row.project_id}/episodes/{row.episode_id}"
    if row.project_id:
        return f"#/projects/{row.project_id}"
    if row.job_id:
        return f"#/tasks/{row.job_id}"
    return "#/projects"


def _names(values: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        name = (raw or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def org_role_names(db: Session, org_id: str, *roles: str) -> list[str]:
    rows = (
        db.query(OrgMember)
        .filter(OrgMember.organization_id == org_id, OrgMember.role.in_(roles))
        .all()
    )
    return _names(row.user_name for row in rows)


def emit(
    db: Session,
    *,
    organization_id: str,
    kind: str,
    title: str,
    body: str = "",
    recipients: Iterable[str | None],
    actor: str | None = None,
    project_id: str | None = None,
    episode_id: str | None = None,
    shot_id: str | None = None,
    job_id: str | None = None,
    comment_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> list[Notification]:
    if kind not in NOTIFY_KINDS:
        return []
    names = _names(recipients)
    actor_name = (actor or "").strip()
    created: list[Notification] = []
    blob = payload if isinstance(payload, dict) else {}
    for name in names:
        if name == actor_name and kind in {
            NOTIFY_COMMENT_MENTION,
            NOTIFY_COMMENT_SHOT,
            NOTIFY_SIGNOFF_REQUESTED,
        }:
            continue
        row = Notification(
            organization_id=organization_id,
            user_name=name,
            kind=kind,
            title=title,
            body=body,
            project_id=project_id,
            episode_id=episode_id,
            shot_id=shot_id,
            job_id=job_id,
            comment_id=comment_id,
            payload=blob,
        )
        db.add(row)
        created.append(row)
    if created:
        db.flush()
        _maybe_webhook(
            {
                "event": kind,
                "title": title,
                "body": body,
                "organization_id": organization_id,
                "project_id": project_id,
                "episode_id": episode_id,
                "shot_id": shot_id,
                "job_id": job_id,
                "comment_id": comment_id,
                "recipients": [row.user_name for row in created],
                "payload": blob,
                "honesty": (
                    "Optional outbound webhook. Unset STUDIO_NOTIFY_WEBHOOK_URL "
                    "means this event is in-app only."
                ),
            }
        )
    return created


def _maybe_webhook(event: dict[str, Any]) -> None:
    cfg = get_settings()
    url = (cfg.notify_webhook_url or "").strip()
    if not url:
        return
    try:
        import httpx

        httpx.post(url, json=event, timeout=2.5)
    except Exception as exc:  # noqa: BLE001 — webhook is best-effort
        log.warning("notify webhook failed: %s", exc)


def notify_job_finished(db: Session, job: Job) -> None:
    episode = job.episode
    project = episode.project if episode else None
    org_id = project.organization_id if project else None
    if not org_id:
        return
    if job.status == "succeeded":
        kind = NOTIFY_JOB_SUCCEEDED
        title = f"Job succeeded · {job.job_type}"
        body = f"adapter={job.adapter or 'stub'} (fixture unless a live hook ran)."
    elif job.status == "failed":
        kind = NOTIFY_JOB_FAILED
        title = f"Job failed · {job.job_type}"
        body = (job.error or "Adapter failed.").strip()
    else:
        return
    recipients = [job.created_by, *org_role_names(db, org_id, ROLE_PRODUCER)]
    emit(
        db,
        organization_id=org_id,
        kind=kind,
        title=title,
        body=body,
        recipients=recipients,
        actor=job.created_by,
        project_id=episode.project_id if episode else None,
        episode_id=job.episode_id,
        shot_id=job.shot_id,
        job_id=job.id,
        payload={"job_type": job.job_type, "adapter": job.adapter, "status": job.status},
    )


def mentioned_names(body: str) -> list[str]:
    return _names(match.group(1) for match in MENTION_RE.finditer(body or ""))


def notify_comment(db: Session, comment: Comment, *, org_id: str) -> None:
    episode = comment.episode
    project_id = episode.project_id if episode else None
    mentions = mentioned_names(comment.body)
    members = {row.user_name for row in memberships(db, org_id)}
    mention_targets = [name for name in mentions if name in members]
    if mention_targets:
        emit(
            db,
            organization_id=org_id,
            kind=NOTIFY_COMMENT_MENTION,
            title=f"{comment.author} mentioned you",
            body=comment.body[:400],
            recipients=mention_targets,
            actor=comment.author,
            project_id=project_id,
            episode_id=comment.episode_id,
            shot_id=comment.shot_id,
            comment_id=comment.id,
        )
    if not comment.shot_id or episode is None:
        return
    shot = comment.shot
    watched = bool(shot and shot.receipt and shot.receipt.preview_watched)
    if not watched:
        return
    prior = [
        row.author
        for row in episode.comments
        if row.shot_id == comment.shot_id and row.id != comment.id
    ]
    emit(
        db,
        organization_id=org_id,
        kind=NOTIFY_COMMENT_SHOT,
        title=f"New comment on watched shot {shot.take or shot.sort_index}",
        body=comment.body[:400],
        recipients=[
            *prior,
            *org_role_names(db, org_id, ROLE_PRODUCER, ROLE_REVIEWER),
        ],
        actor=comment.author,
        project_id=project_id,
        episode_id=comment.episode_id,
        shot_id=comment.shot_id,
        comment_id=comment.id,
    )


def memberships(db: Session, org_id: str) -> list[OrgMember]:
    return db.query(OrgMember).filter(OrgMember.organization_id == org_id).all()


def notify_signoff_requested(db: Session, episode: Episode, *, actor: str) -> None:
    project = episode.project
    org_id = project.organization_id if project else None
    if not org_id:
        return
    emit(
        db,
        organization_id=org_id,
        kind=NOTIFY_SIGNOFF_REQUESTED,
        title=f"Sign-off requested · {episode.title}",
        body="generate-ok stays blocked until a reviewer or producer signs off.",
        recipients=org_role_names(db, org_id, ROLE_PRODUCER, ROLE_REVIEWER),
        actor=actor,
        project_id=episode.project_id,
        episode_id=episode.id,
    )


def blocker_codes(episode: Episode) -> list[str]:
    from .preview import generate_ok_blockers
    from .signoff import signoff_blockers

    codes: list[str] = []
    blocked = generate_ok_blockers(episode)
    if blocked:
        codes.append(str(blocked.get("code") or "gates_not_green"))
        for row in blocked.get("missing") or []:
            if isinstance(row, dict):
                codes.append(f"shot:{row.get('shot_id')}:{row.get('reason')}")
    unsigned = signoff_blockers(episode)
    if unsigned:
        codes.append(str(unsigned.get("code") or "review_unsigned"))
    return codes


def notify_blockers_cleared(
    db: Session,
    episode: Episode,
    before: list[str],
    after: list[str],
    *,
    actor: str,
) -> None:
    cleared = [item for item in before if item not in after]
    if not cleared:
        return
    project = episode.project
    org_id = project.organization_id if project else None
    if not org_id:
        return
    emit(
        db,
        organization_id=org_id,
        kind=NOTIFY_BLOCKER_CLEARED,
        title=f"generate-ok blocker cleared · {episode.title}",
        body="; ".join(cleared)[:800],
        recipients=org_role_names(db, org_id, ROLE_PRODUCER, ROLE_REVIEWER),
        actor=actor,
        project_id=episode.project_id,
        episode_id=episode.id,
        payload={"cleared": cleared, "remaining": after},
    )


def list_for_user(
    db: Session,
    *,
    org_id: str,
    user_name: str,
    unread_only: bool = False,
    limit: int = 50,
) -> list[Notification]:
    query = db.query(Notification).filter(
        Notification.organization_id == org_id,
        Notification.user_name == user_name,
    )
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    return query.order_by(Notification.created_at.desc()).limit(max(1, min(limit, 200))).all()


def unread_count(db: Session, *, org_id: str, user_name: str) -> int:
    return (
        db.query(Notification)
        .filter(
            Notification.organization_id == org_id,
            Notification.user_name == user_name,
            Notification.read_at.is_(None),
        )
        .count()
    )


def mark_read(db: Session, row: Notification) -> Notification:
    if row.read_at is None:
        row.read_at = utcnow()
    return row


def mark_all_read(db: Session, *, org_id: str, user_name: str) -> int:
    rows = (
        db.query(Notification)
        .filter(
            Notification.organization_id == org_id,
            Notification.user_name == user_name,
            Notification.read_at.is_(None),
        )
        .all()
    )
    stamp = utcnow()
    for row in rows:
        row.read_at = stamp
    return len(rows)
