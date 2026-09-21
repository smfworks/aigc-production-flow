"""Reviewer/producer sign-off required before generate-ok."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .models import SIGNOFF_ROLES, Episode, ReviewSignoff, utcnow
from .schemas import ReviewSignoffOut


def signoff_out(row: ReviewSignoff) -> ReviewSignoffOut:
    return ReviewSignoffOut.model_validate(row)


def list_signoffs(episode: Episode) -> list[ReviewSignoff]:
    return list(episode.signoffs or [])


def qualifying_signoffs(episode: Episode) -> list[ReviewSignoff]:
    return [row for row in list_signoffs(episode) if row.role in SIGNOFF_ROLES]


def is_signed_off(episode: Episode) -> bool:
    return bool(qualifying_signoffs(episode))


def add_signoff(
    db: Session,
    episode: Episode,
    *,
    user_name: str,
    role: str,
    note: str = "",
) -> ReviewSignoff:
    row = ReviewSignoff(
        episode_id=episode.id,
        user_name=user_name,
        role=role,
        note=(note or "").strip(),
    )
    db.add(row)
    episode.updated_at = utcnow()
    return row


def signoff_blockers(episode: Episode) -> dict[str, Any] | None:
    rows = qualifying_signoffs(episode)
    if rows:
        return None
    return {
        "code": "review_unsigned",
        "message": (
            "Refuse generate-ok until a reviewer or producer signs off "
            "(who / when / note). Viewers cannot sign off. "
            "A producer may override; that override is audited as review.override."
        ),
        "signoffs": [],
    }
