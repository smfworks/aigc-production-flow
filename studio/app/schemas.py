from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

OrgRole = Literal["producer", "editor", "reviewer", "viewer", "writer", "art"]

ReviewStateName = Literal[
    "draft",
    "needs-art",
    "needs-edit",
    "preview-watched",
    "generate-ok",
]

MediaKind = Literal["sheet", "plate", "costume", "preview", "other"]
ApprovalStatus = Literal["draft", "approved"]
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
    auth_mode: Literal["local", "forward-header", "oidc"] = "local"
    sso: str = "local-dev token. OIDC remains opt-in and off by default — see docs/AUTH.md"
    role: OrgRole | None = None
    org_id: str | None = None
    org_name: str | None = None
    permissions: list[str] = Field(default_factory=list)
    oidc_role: OrgRole | None = None
    orgs: list["OrgMembershipOut"] = Field(default_factory=list)
    multi_org: bool = False


class MetaOut(BaseModel):
    name: str = "AIGC Studio Spine"
    phase: int = 9
    auth_mode: Literal["local", "forward-header", "oidc"] = "local"
    sso: str = "local-dev token. OIDC remains opt-in and off by default — see docs/AUTH.md"
    pack_builder_url: str
    docs: str = "/docs"
    default_user: str
    job_worker: str = "thread"
    still_adapter: str = "stub"
    clip_adapter: str = "stub"
    cost_currency: str = "credits"
    retention_days: int = 30
    budget_hard_stop: bool = False
    media_backend: str = "local"
    media_s3_configured: bool = False
    media_note: str = "Local disk. S3/MinIO is not live until backend=s3 and a bucket are set."
    presence_ttl_seconds: int = 60
    roles: list[str] = Field(
        default_factory=lambda: ["producer", "editor", "writer", "art", "reviewer", "viewer"]
    )
    role_matrix: list["RoleMatrixRow"] = Field(default_factory=list)
    celery_enabled: bool = False
    oidc_configured: bool = False
    oidc_apply_role_claim: bool = False
    notify_webhook_configured: bool = False
    multi_org: bool = True
    multi_org_note: str = (
        "Multi-org lite: membership isolation only. Not SaaS billing, not SSO org mapping."
    )


class RoleMatrixRow(BaseModel):
    role: str
    label: str
    legacy: bool = False
    permissions: list[str] = Field(default_factory=list)
    note: str = ""


class OrganizationOut(BaseModel):
    id: str
    name: str
    is_default: bool = False
    role: OrgRole | None = None
    created_at: datetime
    note: str = "Multi-org lite — not SaaS billing or SSO org mapping."

    model_config = {"from_attributes": True}


class OrgMembershipOut(BaseModel):
    id: str
    name: str
    is_default: bool = False
    role: OrgRole
    created_at: datetime


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=80)
    description: str = ""
    still_adapter: str | None = Field(default=None, max_length=80)
    clip_adapter: str | None = Field(default=None, max_length=80)
    budget_cap_units: float | None = Field(default=None, ge=0)
    budget_hard_stop: bool | None = None
    retention_days: int | None = Field(default=None, ge=0)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=80)
    description: str | None = None
    still_adapter: str | None = Field(default=None, max_length=80)
    clip_adapter: str | None = Field(default=None, max_length=80)
    budget_cap_units: float | None = Field(default=None, ge=0)
    budget_hard_stop: bool | None = None
    retention_days: int | None = Field(default=None, ge=0)
    clear_budget_cap: bool = False
    clear_retention_days: bool = False


class ProjectOut(BaseModel):
    id: str
    organization_id: str
    name: str
    slug: str
    description: str
    still_adapter: str = "stub"
    clip_adapter: str = "stub"
    budget_cap_units: float | None = None
    budget_hard_stop: bool = False
    retention_days: int | None = None
    episode_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EpisodeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    chapter: int | None = Field(default=None, ge=1)
    season: int | None = Field(default=None, ge=1)
    sequence: int | None = Field(default=None, ge=1)
    synopsis: str = ""
    log_line: str = ""
    map_notes: str = ""
    dialogue: str = ""


class EpisodeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    chapter: int | None = Field(default=None, ge=1)
    season: int | None = Field(default=None, ge=1)
    sequence: int | None = Field(default=None, ge=1)
    synopsis: str | None = None
    log_line: str | None = None
    map_notes: str | None = None
    dialogue: str | None = None


class EpisodeOrderItem(BaseModel):
    id: str
    season: int = Field(ge=1)
    sequence: int = Field(ge=1)


class EpisodeReorder(BaseModel):
    items: list[EpisodeOrderItem] = Field(min_length=1)


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
    season: int = 1
    sequence: int = 1
    synopsis: str
    log_line: str = ""
    map_notes: str = ""
    dialogue: str = ""
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
    override: bool = False


class ReviewSignoffCreate(BaseModel):
    note: str = ""


class ReviewSignoffOut(BaseModel):
    id: str
    episode_id: str
    user_name: str
    role: OrgRole
    note: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


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
    signoffs: list[ReviewSignoffOut] = Field(default_factory=list)
    signed_off: bool = False


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=8000)
    author: str | None = Field(default=None, max_length=120)
    shot_id: str | None = None
    board_node_id: str | None = Field(default=None, max_length=80)


class CommentOut(BaseModel):
    id: str
    episode_id: str
    shot_id: str | None = None
    board_node_id: str = ""
    author: str
    body: str
    resolved: bool = False
    resolved_by: str = ""
    resolved_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberCreate(BaseModel):
    user_name: str = Field(min_length=1, max_length=120)
    role: OrgRole = "viewer"


class MemberUpdate(BaseModel):
    role: OrgRole


class MemberOut(BaseModel):
    id: str
    organization_id: str
    user_name: str
    role: OrgRole
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PresenceBeat(BaseModel):
    shot_id: str | None = None


class PresenceOut(BaseModel):
    user_name: str
    role: str = ""
    shot_id: str = ""
    last_seen: datetime
    ttl_seconds: int = 60

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
    approval_status: ApprovalStatus = "draft"
    approved_by: str = ""
    approved_at: datetime | None = None
    shot_id: str | None = None
    edit_row_id: str = ""
    lock_keywords: str = ""
    approved: bool = False

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


class ShotUpdate(BaseModel):
    """Edit-list craft fields. Not an NLE. Writer script fields live on the episode."""

    join: str | None = Field(default=None, max_length=20)
    camera_verb: str | None = Field(default=None, max_length=40)
    action: str | None = None


class BoardOut(BaseModel):
    shots: list[ShotOut]
    continue_chains: list[list[str]]
    boundaries: list[dict[str, str]]


class JobEnqueue(BaseModel):
    episode_id: str
    shot_id: str | None = None
    job_type: JobType
    payload: dict[str, Any] = Field(default_factory=dict)
    adapter: str | None = None


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
    estimated_cost_units: float = 0
    actual_cost_units: float | None = None
    cost_currency: str = "credits"
    cost_note: str = ""
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


class AdapterHealthOut(BaseModel):
    id: str
    ok: bool
    live: bool
    config_present: bool
    reachable: bool | None = None
    transport: str
    detail: str
    schema_ok: bool | None = None
    not_live: bool = False
    window_s: float | None = None
    frames: int | None = None
    fps: float | None = None
    canvas: str | None = None
    hop1_watch_required: bool = True


class AdapterSlotOut(BaseModel):
    id: str
    label: str
    kinds: list[str]
    live: bool
    transport: str
    note: str
    health: AdapterHealthOut | None = None
    window_s: float | None = None
    frames: int | None = None
    fps: float | None = None
    canvas: str | None = None
    hop1_watch_required: bool = True
    config_schema: dict[str, Any] = Field(default_factory=dict)
    honesty: str = ""


class AdapterCatalogOut(BaseModel):
    adapters: list[AdapterSlotOut]
    still_default: str
    clip_default: str
    health: list[AdapterHealthOut] = Field(default_factory=list)
    note: str = (
        "Documented slots (comfy-h3, comfy-qwen, webhook, cli) fall back to stub "
        "when the live hook is unset. Stub never claims H3 or Qwen ran. "
        "Health is a dry-run (reachable? config present? schema valid?) — not a generate. "
        "Unset live hooks report not live. comfy-h3 declares hop-1 10.125s / 243f @ 24fps. "
        "Live adapters never skip the hop-1 watch protocol."
    )


class BudgetEpisodeRow(BaseModel):
    episode_id: str
    title: str
    chapter: int
    spent_units: float
    pending_units: float
    job_count: int
    succeeded: int
    failed: int
    cancelled: int
    adapter_mix: dict[str, int]


class BudgetProjectRow(BaseModel):
    project_id: str
    name: str
    slug: str = ""
    spent_units: float
    pending_units: float
    cap_units: float | None = None
    hard_stop: bool = False
    over_cap: bool = False
    job_count: int
    adapter_mix: dict[str, int]
    still_adapter: str = "stub"
    clip_adapter: str = "stub"
    usd_estimate: float | None = None
    episodes: list[BudgetEpisodeRow] = []


class BudgetDashboardOut(BaseModel):
    currency: str
    usd_per_unit: float = 0
    rates: dict[str, float]
    disclaimer: str
    spent_units: float
    pending_units: float
    usd_estimate: float | None = None
    cap_units: float | None = None
    hard_stop: bool = False
    job_counts: dict[str, int]
    adapter_mix: dict[str, int]
    projects: list[BudgetProjectRow]


class AuditEventOut(BaseModel):
    id: str
    actor: str
    action: str
    entity_type: str = ""
    entity_id: str = ""
    project_id: str | None = None
    episode_id: str | None = None
    organization_id: str | None = None
    project_name: str = ""
    episode_title: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class RetentionApply(BaseModel):
    project_id: str | None = None
    episode_id: str | None = None
    dry_run: bool = True
    confirm: str = ""


class VerticalTemplateOut(BaseModel):
    id: str
    name: str
    blurb: str
    still_adapter: str = "stub"
    clip_adapter: str = "stub"
    stages: list[str]
    gates_green: bool = False
    fake_generate: bool = False


class ProjectFromTemplate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    still_adapter: str | None = None
    clip_adapter: str | None = None


class NotificationOut(BaseModel):
    id: str
    organization_id: str
    user_name: str
    kind: str
    title: str
    body: str = ""
    project_id: str | None = None
    episode_id: str | None = None
    shot_id: str | None = None
    job_id: str | None = None
    comment_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    read_at: datetime | None = None
    created_at: datetime
    href: str = ""

    model_config = {"from_attributes": True}


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    unread_count: int = 0


class DemoSeedOut(BaseModel):
    project: ProjectOut
    episode: EpisodeOut
    template_id: str
    honesty: str
    fixture_media: int = 0
    fake_generate: bool = False
    likeness: bool = False
    engine_mp4: bool = False


class BackupRestoreBody(BaseModel):
    dry_run: bool = True
    confirm: str = ""


class ContinuityShotOut(BaseModel):
    shot_id: str
    edit_row_id: str = ""
    sort_index: int = 0
    take: str = ""
    join: str = ""
    entities: str = ""
    issues: list[str] = Field(default_factory=list)
    href: str = ""
    identity_href: str = ""
    identity_hrefs: list[str] = Field(default_factory=list)


class ContinuitySummaryOut(BaseModel):
    episode_id: str
    project_id: str
    honesty: str = "Read/visualize + navigate only. Not a full NLE."
    all_green: bool = False
    red_gates: list[GateResultOut] = Field(default_factory=list)
    entity_schedule: list[dict[str, Any]] = Field(default_factory=list)
    entity_schedule_problems: list[str] = Field(default_factory=list)
    lock_diff_problems: list[str] = Field(default_factory=list)
    mismatches: list[str] = Field(default_factory=list)
    shots: list[ContinuityShotOut] = Field(default_factory=list)
    identity: dict[str, Any] = Field(default_factory=dict)
    identity_href: str = ""
    identity_lock_diff_problems: list[str] = Field(default_factory=list)


class IdentityApprove(BaseModel):
    note: str = ""
    lock_keywords: str | None = None
    entity_label: str | None = Field(default=None, max_length=200)
    entity_type: str | None = None


class IdentityUnapprove(BaseModel):
    note: str = ""


class IdentityKeywords(BaseModel):
    lock_keywords: str = ""
    note: str = ""


class PlaylistScrubShot(BaseModel):
    shot_id: str
    sort_index: int = 0
    edit_row_id: str = ""
    take: str = ""
    join: str = ""
    action: str = ""
    song_t: str = ""
    camera_verb: str = ""
    duration_s: float | None = None
    frames: int | None = None
    preview_watched: bool = False
    media_id: str | None = None
    content_type: str = ""
    original_name: str = ""
    playable: bool = False
    image: bool = False
    stub: bool = False
    empty: bool = True
    note: str = ""


class PlaylistScrubOut(BaseModel):
    episode_id: str
    honesty: str
    nle: bool = False
    shot_count: int = 0
    shots: list[PlaylistScrubShot] = Field(default_factory=list)


class IdentityLink(BaseModel):
    shot_id: str | None = None
    edit_row_id: str | None = None
    lock_keywords: str | None = None
    entity_label: str | None = Field(default=None, max_length=200)
    entity_type: str | None = None


class IdentityAssetOut(BaseModel):
    id: str
    kind: Literal["sheet", "plate"]
    original_name: str
    entity_label: str = ""
    entity_type: str = ""
    notes: str = ""
    href: str = ""
    approval_status: ApprovalStatus = "draft"
    approved_by: str = ""
    approved_at: datetime | None = None
    shot_id: str | None = None
    edit_row_id: str = ""
    lock_keywords: str = ""
    approved: bool = False
    created_by: str = ""
    created_at: datetime


class IdentityStoreOut(BaseModel):
    episode_id: str
    project_id: str
    honesty: str
    embeddings: bool = False
    likeness: bool = False
    sheets: list[IdentityAssetOut] = Field(default_factory=list)
    plates: list[IdentityAssetOut] = Field(default_factory=list)
    approved_sheet_count: int = 0
    approved_plate_count: int = 0


class PackDiffRef(BaseModel):
    id: str | None = None
    filename: str = ""
    all_gates_green: bool = False
    created_by: str = ""
    created_at: datetime | None = None
    label: str = ""
    candidate: bool = False


class PackDiffOut(BaseModel):
    honesty: str
    left: PackDiffRef | None = None
    right: PackDiffRef | None = None
    gates: list[dict[str, Any]] = Field(default_factory=list)
    entity_schedule: dict[str, Any] = Field(default_factory=dict)
    edit_list: dict[str, Any] = Field(default_factory=dict)
    identity_keywords: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    auto_generate: bool = False


class PackHandoffOut(BaseModel):
    id: str
    filename: str
    created_by: str
    created_at: datetime
    expires_at: datetime
    consumed: bool = False
    episode_id: str | None = None
    honesty: str
    auto_generate: bool = False


UserOut.model_rebuild()
MetaOut.model_rebuild()


