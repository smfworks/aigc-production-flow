from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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

MEDIA_KINDS = ("sheet", "plate", "other")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    projects: Mapped[list["Project"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_project_org_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
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
    media: Mapped[list["MediaAsset"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        order_by="MediaAsset.created_at.desc()",
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
    author: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    episode: Mapped[Episode] = relationship(back_populates="comments")


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    original_name: Mapped[str] = mapped_column(String(260), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(260), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    entity_label: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(120), default="local-dev")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    episode: Mapped[Episode] = relationship(back_populates="media")
