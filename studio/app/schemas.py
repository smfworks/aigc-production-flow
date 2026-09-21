from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ReviewStateName = Literal[
    "draft",
    "needs-art",
    "needs-edit",
    "preview-watched",
    "generate-ok",
]

MediaKind = Literal["sheet", "plate", "other"]


class UserOut(BaseModel):
    name: str
    auth_mode: Literal["local-dev"] = "local-dev"
    sso: Literal["later"] = "later"


class MetaOut(BaseModel):
    name: str = "AIGC Studio Spine"
    phase: int = 1
    auth_mode: Literal["local-dev"] = "local-dev"
    sso: str = "not in this phase — do not treat this token as multi-tenant SaaS security"
    pack_builder_url: str
    docs: str = "/docs"
    default_user: str


class OrganizationOut(BaseModel):
    id: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=80)
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=80)
    description: str | None = None


class ProjectOut(BaseModel):
    id: str
    organization_id: str
    name: str
    slug: str
    description: str
    episode_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EpisodeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    chapter: int = Field(default=1, ge=1)
    synopsis: str = ""


class EpisodeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    chapter: int | None = Field(default=None, ge=1)
    synopsis: str | None = None


class GateResultOut(BaseModel):
    id: str
    n: int
    label: str
    ok: bool
    detail: str


class GateSnapshotOut(BaseModel):
    evaluated_at: str
    all_green: bool
    gates: list[GateResultOut]


class PackRevisionSummary(BaseModel):
    id: str
    filename: str
    all_gates_green: bool
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PackRevisionOut(PackRevisionSummary):
    episode_id: str
    pack: dict[str, Any]
    gate_snapshot: GateSnapshotOut


class EpisodeOut(BaseModel):
    id: str
    project_id: str
    title: str
    chapter: int
    synopsis: str
    review_state: ReviewStateName
    latest_revision: PackRevisionSummary | None = None
    comment_count: int = 0
    media_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReviewSet(BaseModel):
    state: ReviewStateName
    note: str = ""


class ReviewStateOut(BaseModel):
    id: str
    episode_id: str
    state: ReviewStateName
    note: str
    set_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewOut(BaseModel):
    current: ReviewStateName
    history: list[ReviewStateOut]
    latest_gates: GateSnapshotOut | None = None


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=8000)
    author: str | None = Field(default=None, max_length=120)


class CommentOut(BaseModel):
    id: str
    episode_id: str
    author: str
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MediaAssetOut(BaseModel):
    id: str
    episode_id: str
    kind: MediaKind
    original_name: str
    stored_name: str
    content_type: str
    path: str
    entity_label: str
    notes: str
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}
