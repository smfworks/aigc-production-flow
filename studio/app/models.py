from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .database import Base

REVIEW_STATES = (
    "draft",
    "needs-art",
    "needs-edit",
    "preview-watched",
    "generate-ok",
)
ROLE_PRODUCER = "producer"
ROLE_EDITOR = "editor"
ROLE_REVIEWER = "reviewer"
ROLE_VIEWER = "viewer"
ORG_ROLES = frozenset({ROLE_PRODUCER, ROLE_EDITOR, ROLE_REVIEWER, ROLE_VIEWER})
SIGNOFF_ROLES = frozenset({ROLE_PRODUCER, ROLE_REVIEWER})

MEDIA_KINDS = ("sheet", "plate", "costume", "preview", "other")
ENTITY_TYPES = ("character", "prop", "scene", "costume")
IDENTITY_KINDS = ("sheet", "plate")
APPROVAL_DRAFT = "draft"
APPROVAL_APPROVED = "approved"
APPROVAL_STATUSES = (APPROVAL_DRAFT, APPROVAL_APPROVED)
SHOT_READINESS = ("draft", "candidates", "linked", "ready")
CANDIDATE_KINDS = ("character", "prop", "scene", "costume")
CANDIDATE_STATUSES = ("pending", "accepted", "ignored", "linked")
CANDIDATE_SOURCES = ("stub", "manual")
JOB_TYPES = ("still-sheet", "still-plate", "clip-hop1", "clip-extend", "batch-precheck")
JOB_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")
RECEIPT_SOURCES = ("manual", "parsed")
ADAPTER_IDS = ("stub", "comfy-h3", "comfy-qwen", "webhook", "cli")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    projects: Mapped[list["Project"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    members: Mapped[list["OrgMember"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
        order_by="OrgMember.created_at.asc()",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
        order_by="Notification.created_at.desc()",
    )


class OrgMember(Base):
    """App-level role on one org. Multi-org lite is not SaaS billing or SSO org mapping."""

    __tablename__ = "org_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_name", name="uq_org_member_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    user_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=ROLE_VIEWER)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    organization: Mapped[Organization] = relationship(back_populates="members")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_project_org_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    still_adapter: Mapped[str] = mapped_column(String(80), default="stub")
    clip_adapter: Mapped[str] = mapped_column(String(80), default="stub")
    budget_cap_units: Mapped[float | None] = mapped_column(Float, nullable=True)
    budget_hard_stop: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    organization: Mapped[Organization] = relationship(back_populates="projects")
    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Episode.chapter",
    )


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    chapter: Mapped[int] = mapped_column(Integer, default=1)
    synopsis: Mapped[str] = mapped_column(Text, default="")
    review_state: Mapped[str] = mapped_column(String(32), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    project: Mapped[Project] = relationship(back_populates="episodes")
    revisions: Mapped[list["PackRevision"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        order_by="PackRevision.created_at.desc()",
    )
    review_events: Mapped[list["ReviewState"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        order_by="ReviewState.created_at.desc()",
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        order_by="Comment.created_at.asc()",
    )
    presence: Mapped[list["PresenceHeartbeat"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        order_by="PresenceHeartbeat.last_seen.desc()",
    )
    media: Mapped[list["MediaAsset"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        order_by="MediaAsset.created_at.desc()",
    )
    handoffs: Mapped[list["PackHandoff"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        order_by="PackHandoff.created_at.desc()",
    )
    shots: Mapped[list["Shot"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        order_by="Shot.sort_index.asc()",
    )
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        order_by="Job.created_at.desc()",
        foreign_keys="Job.episode_id",
    )
    receipts: Mapped[list["ContinuityReceipt"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        order_by="ContinuityReceipt.created_at.asc()",
    )
    signoffs: Mapped[list["ReviewSignoff"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        order_by="ReviewSignoff.created_at.desc()",
    )


class PackRevision(Base):
    __tablename__ = "pack_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(260), nullable=False)
    pack_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    gate_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    all_gates_green: Mapped[bool] = mapped_column(Boolean, default=False)
    zip_path: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), default="local-dev")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    episode: Mapped[Episode] = relationship(back_populates="revisions")


class ReviewSignoff(Base):
    """Reviewer or producer sign-off required before generate-ok (unless producer override)."""

    __tablename__ = "review_signoffs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), nullable=False)
    user_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    episode: Mapped[Episode] = relationship(back_populates="signoffs")


class ReviewState(Base):
    """History row. Current value is also denormalized on Episode.review_state."""

    __tablename__ = "review_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")
    set_by: Mapped[str] = mapped_column(String(120), default="local-dev")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    episode: Mapped[Episode] = relationship(back_populates="review_events")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), nullable=False)
    shot_id: Mapped[str | None] = mapped_column(ForeignKey("shots.id"), nullable=True)
    board_node_id: Mapped[str] = mapped_column(String(80), default="")
    author: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_by: Mapped[str] = mapped_column(String(120), default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    episode: Mapped[Episode] = relationship(back_populates="comments")
    shot: Mapped["Shot | None"] = relationship(back_populates="comments")


class PresenceHeartbeat(Base):
    """Who is on an episode. TTL is enforced at read time (~60s)."""

    __tablename__ = "presence_heartbeats"
    __table_args__ = (
        UniqueConstraint("episode_id", "user_name", name="uq_presence_episode_user"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), nullable=False)
    user_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="")
    shot_id: Mapped[str] = mapped_column(String(36), default="")
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    episode: Mapped[Episode] = relationship(back_populates="presence")


class MediaAsset(Base):
    """Sheet/plate/costume/preview file. Identity sheets/plates start as draft."""

    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    original_name: Mapped[str] = mapped_column(String(260), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(260), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    entity_label: Mapped[str] = mapped_column(String(200), default="")
    entity_type: Mapped[str] = mapped_column(String(32), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(120), default="local-dev")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approval_status: Mapped[str] = mapped_column(String(20), default=APPROVAL_DRAFT)
    approved_by: Mapped[str] = mapped_column(String(120), default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shot_id: Mapped[str] = mapped_column(String(36), default="")
    edit_row_id: Mapped[str] = mapped_column(String(80), default="")
    lock_keywords: Mapped[str] = mapped_column(Text, default="")

    episode: Mapped[Episode] = relationship(back_populates="media")


class Shot(Base):
    """One edit-list row mapped to a studio shot. ready = prepared, not generating."""

    __tablename__ = "shots"
    __table_args__ = (UniqueConstraint("episode_id", "edit_row_id", name="uq_shot_episode_row"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), nullable=False)
    pack_revision_id: Mapped[str | None] = mapped_column(ForeignKey("pack_revisions.id"), nullable=True)
    edit_row_id: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_index: Mapped[int] = mapped_column(Integer, default=0)
    song_t: Mapped[str] = mapped_column(String(40), default="")
    join: Mapped[str] = mapped_column(String(20), default="")
    take: Mapped[str] = mapped_column(String(40), default="")
    location_grade: Mapped[str] = mapped_column(String(200), default="")
    camera_verb: Mapped[str] = mapped_column(String(40), default="")
    action: Mapped[str] = mapped_column(Text, default="")
    entities: Mapped[str] = mapped_column(String(400), default="")
    readiness: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    episode: Mapped[Episode] = relationship(back_populates="shots")
    candidates: Mapped[list["ShotCandidate"]] = relationship(
        back_populates="shot",
        cascade="all, delete-orphan",
        order_by="ShotCandidate.created_at.asc()",
    )
    receipt: Mapped["ContinuityReceipt | None"] = relationship(
        back_populates="shot",
        cascade="all, delete-orphan",
        uselist=False,
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="shot",
        foreign_keys="Comment.shot_id",
    )
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="shot",
        foreign_keys="Job.shot_id",
    )


class ShotCandidate(Base):
    __tablename__ = "shot_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    shot_id: Mapped[str] = mapped_column(ForeignKey("shots.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    source: Mapped[str] = mapped_column(String(20), default="stub")
    linked_asset_id: Mapped[str | None] = mapped_column(ForeignKey("media_assets.id"), nullable=True)
    linked_ref: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    shot: Mapped[Shot] = relationship(back_populates="candidates")


class Job(Base):
    """Async still/clip/precheck work. Thread worker default; Celery is opt-in."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), nullable=False)
    shot_id: Mapped[str | None] = mapped_column(ForeignKey("shots.id"), nullable=True)
    media_id: Mapped[str | None] = mapped_column(ForeignKey("media_assets.id"), nullable=True)
    retry_of_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    adapter: Mapped[str] = mapped_column(String(80), default="stub")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    estimated_cost_units: Mapped[float] = mapped_column(Float, default=0.0)
    actual_cost_units: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_currency: Mapped[str] = mapped_column(String(32), default="credits")
    cost_note: Mapped[str] = mapped_column(Text, default="")
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(120), default="local-dev")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    episode: Mapped[Episode] = relationship(back_populates="jobs", foreign_keys=[episode_id])
    shot: Mapped[Shot | None] = relationship(back_populates="jobs", foreign_keys=[shot_id])
    media: Mapped[MediaAsset | None] = relationship(foreign_keys=[media_id])


class ContinuityReceipt(Base):
    """Hop-1 preview receipt: duration/frames, still-vs-lock, optional NG."""

    __tablename__ = "continuity_receipts"
    __table_args__ = (UniqueConstraint("shot_id", name="uq_receipt_shot"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), nullable=False)
    shot_id: Mapped[str] = mapped_column(ForeignKey("shots.id"), nullable=False)
    media_id: Mapped[str | None] = mapped_column(ForeignKey("media_assets.id"), nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    frames: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    still_vs_lock: Mapped[str] = mapped_column(Text, default="")
    ng_reason: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20), default="manual")
    preview_watched: Mapped[bool] = mapped_column(Boolean, default=False)
    watched_by: Mapped[str] = mapped_column(String(120), default="")
    watched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(120), default="local-dev")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    episode: Mapped[Episode] = relationship(back_populates="receipts")
    shot: Mapped[Shot] = relationship(back_populates="receipt")
    media: Mapped[MediaAsset | None] = relationship(foreign_keys=[media_id])


class AuditEvent(Base):
    """Who / what / when. Local-dev user ids are fine. Not a SIEM."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(120), default="local-dev")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), default="")
    entity_id: Mapped[str] = mapped_column(String(36), default="")
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    episode_id: Mapped[str | None] = mapped_column(
        ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True
    )
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project | None] = relationship(foreign_keys=[project_id])
    episode: Mapped[Episode | None] = relationship(foreign_keys=[episode_id])
    organization: Mapped[Organization | None] = relationship(foreign_keys=[organization_id])


NOTIFY_JOB_SUCCEEDED = "job.succeeded"
NOTIFY_JOB_FAILED = "job.failed"
NOTIFY_COMMENT_MENTION = "comment.mention"
NOTIFY_COMMENT_SHOT = "comment.shot"
NOTIFY_SIGNOFF_REQUESTED = "review.signoff_requested"
NOTIFY_BLOCKER_CLEARED = "review.blocker_cleared"
NOTIFY_KINDS = (
    NOTIFY_JOB_SUCCEEDED,
    NOTIFY_JOB_FAILED,
    NOTIFY_COMMENT_MENTION,
    NOTIFY_COMMENT_SHOT,
    NOTIFY_SIGNOFF_REQUESTED,
    NOTIFY_BLOCKER_CLEARED,
)


class PackHandoff(Base):
    """Staged pack zip from the builder Open-in-Studio handoff. Not a generate."""

    __tablename__ = "pack_handoffs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    episode_id: Mapped[str | None] = mapped_column(ForeignKey("episodes.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(260), nullable=False)
    zip_path: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), default="local-dev")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    episode: Mapped[Episode | None] = relationship(back_populates="handoffs")


class Notification(Base):
    """In-app notice for one org member. Optional outbound webhook is separate."""

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    user_name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    episode_id: Mapped[str | None] = mapped_column(
        ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True
    )
    shot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    comment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="notifications")

