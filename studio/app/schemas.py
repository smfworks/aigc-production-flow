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

MediaKind = Literal["sheet", "plate", "costume", "preview", "other"]
JobType = Literal["still-sheet", "still-plate", "clip-hop1", "clip-extend", "batch-precheck"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
ReceiptSource = Literal["manual", "parsed"]
EntityType = Literal["character", "prop", "scene", "costume", ""]
ShotReadiness = Literal["draft", "candidates", "linked", "ready"]
CandidateKind = Literal["character", "prop", "scene", "costume"]
CandidateStatus = Literal["pending", "accepted", "ignored", "linked"]
CandidateSource = Literal["stub", "manual"]


class UserOut(BaseModel):
    name: str
    auth_mode: Literal["local-dev"] = "local-dev"
    sso: Literal["later"] = "later"


class MetaOut(BaseModel):
    name: str = "AIGC Studio Spine"
    phase: int = 3
    auth_mode: Literal["local-dev"] = "local-dev"
    sso: str = "not in this phase — do not treat this token as multi-tenant SaaS security"
    pack_builder_url: str
    docs: str = "/docs"
    default_user: str
    job_worker: str = "thread"
    still_adapter: str = "stub"
    clip_adapter: str = "stub"


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
    shot_count: int = 0
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
    entity_type: str = ""
    notes: str
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CandidateOut(BaseModel):
    id: str
    shot_id: str
    kind: CandidateKind
    label: str
    evidence: str
    status: CandidateStatus
    source: CandidateSource
    linked_asset_id: str | None = None
    linked_ref: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CandidateCreate(BaseModel):
    kind: CandidateKind
    label: str = Field(min_length=1, max_length=200)
    evidence: str = ""


class CandidateUpdate(BaseModel):
    status: CandidateStatus | None = None
    linked_asset_id: str | None = None
    linked_ref: str | None = None
    kind: CandidateKind | None = None
    label: str | None = Field(default=None, min_length=1, max_length=200)


class ContinuityReceiptOut(BaseModel):
    id: str
    episode_id: str
    shot_id: str
    media_id: str | None = None
    duration_s: float | None = None
    frames: int | None = None
    fps: float | None = None
    still_vs_lock: str = ""
    ng_reason: str = ""
    source: ReceiptSource = "manual"
    preview_watched: bool = False
    watched_by: str = ""
    watched_at: datetime | None = None
    notes: str = ""
    created_by: str
    created_at: datetime
    updated_at: datetime
    complete: bool = False
    extend_ok: bool = False
    blockers: list[str] = []

    model_config = {"from_attributes": True}


class ReceiptSet(BaseModel):
    media_id: str | None = None
    duration_s: float | None = Field(default=None, ge=0)
    frames: int | None = Field(default=None, ge=0)
    fps: float | None = Field(default=None, ge=0)
    still_vs_lock: str | None = None
    ng_reason: str | None = None
    source: ReceiptSource | None = None
    parse_media: bool = True
    notes: str | None = None
    watched: bool | None = None


class PreviewWatchedSet(BaseModel):
    watched: bool = True
    note: str = ""


class ShotOut(BaseModel):
    id: str
    episode_id: str
    pack_revision_id: str | None = None
    edit_row_id: str
    sort_index: int
    song_t: str
    join: str
    take: str
    location_grade: str
    camera_verb: str
    action: str
    entities: str
    readiness: ShotReadiness
    candidates: list[CandidateOut] = []
    hop1_required: bool = False
    preview: ContinuityReceiptOut | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ShotReadinessSet(BaseModel):
    readiness: ShotReadiness
    note: str = ""


class BoardOut(BaseModel):
    shots: list[ShotOut]
    continue_chains: list[list[str]]
    boundaries: list[dict[str, str]]


class JobEnqueue(BaseModel):
    episode_id: str
    shot_id: str | None = None
    job_type: JobType
    payload: dict[str, Any] = Field(default_factory=dict)


class JobOut(BaseModel):
    id: str
    episode_id: str
    project_id: str
    shot_id: str | None = None
    media_id: str | None = None
    retry_of_id: str | None = None
    job_type: JobType
    status: JobStatus
    progress: int = 0
    error: str = ""
    adapter: str = "stub"
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    cancel_requested: bool = False
    created_by: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime
    elapsed_ms: int = 0
    episode_title: str = ""
    project_name: str = ""
    shot_sort_index: int | None = None
    shot_take: str = ""

    model_config = {"from_attributes": True}


class PreviewDeskShot(BaseModel):
    shot: ShotOut
    required: bool
    complete: bool
    extend_ok: bool
    blockers: list[str] = []


class PreviewDeskOut(BaseModel):
    episode_id: str
    required_count: int
    complete_count: int
    generate_ok_ready: bool
    blockers: list[dict[str, str]] = []
    shots: list[PreviewDeskShot]


class PrecheckProblem(BaseModel):
    code: str
    message: str
    shot_id: str | None = None

