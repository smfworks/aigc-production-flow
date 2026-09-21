export const REVIEW_STATES = [
  "draft",
  "needs-art",
  "needs-edit",
  "preview-watched",
  "generate-ok",
] as const;

export type ReviewStateName = (typeof REVIEW_STATES)[number];

export type GateResult = {
  id: string;
  n: number;
  label: string;
  ok: boolean;
  detail: string;
};

export type GateSnapshot = {
  evaluated_at: string;
  all_green: boolean;
  gates: GateResult[];
};

export type PackRevisionSummary = {
  id: string;
  filename: string;
  all_gates_green: boolean;
  created_by: string;
  created_at: string;
};

export type Project = {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description: string;
  still_adapter: string;
  clip_adapter: string;
  budget_cap_units: number | null;
  budget_hard_stop: boolean;
  retention_days: number | null;
  episode_count: number;
  created_at: string;
  updated_at: string;
};

export type Episode = {
  id: string;
  project_id: string;
  title: string;
  chapter: number;
  season: number;
  sequence: number;
  synopsis: string;
  log_line: string;
  map_notes: string;
  dialogue: string;
  review_state: ReviewStateName;
  latest_revision: PackRevisionSummary | null;
  comment_count: number;
  media_count: number;
  shot_count: number;
  created_at: string;
  updated_at: string;
};

export type ReviewEvent = {
  id: string;
  episode_id: string;
  state: ReviewStateName;
  note: string;
  set_by: string;
  created_at: string;
};

export type ReviewSignoff = {
  id: string;
  episode_id: string;
  user_name: string;
  role: OrgRole;
  note: string;
  created_at: string;
};

export type Review = {
  current: ReviewStateName;
  history: ReviewEvent[];
  latest_gates: GateSnapshot | null;
  signoffs?: ReviewSignoff[];
  signed_off?: boolean;
};

export type Comment = {
  id: string;
  episode_id: string;
  shot_id: string | null;
  board_node_id: string;
  author: string;
  body: string;
  resolved: boolean;
  resolved_by: string;
  resolved_at: string | null;
  created_at: string;
};

export type OrgRole = "producer" | "editor" | "reviewer" | "viewer" | "writer" | "art";

export type RoleMatrixRow = {
  role: string;
  label: string;
  legacy: boolean;
  permissions: string[];
  note: string;
};

export type StudioUser = {
  name: string;
  auth_mode: "local" | "forward-header" | "oidc";
  sso: string;
  role: OrgRole | null;
  org_id: string | null;
  org_name?: string | null;
  permissions: string[];
  oidc_role?: OrgRole | null;
  orgs?: StudioOrgMembership[];
  multi_org?: boolean;
};

export type StudioOrgMembership = {
  id: string;
  name: string;
  is_default: boolean;
  role: OrgRole;
  created_at: string;
};

export type StudioOrg = {
  id: string;
  name: string;
  is_default: boolean;
  role: OrgRole | null;
  created_at: string;
  note?: string;
};

export type OrgMember = {
  id: string;
  organization_id: string;
  user_name: string;
  role: OrgRole;
  created_at: string;
  updated_at: string;
};

export type PresenceUser = {
  user_name: string;
  role: string;
  shot_id: string;
  last_seen: string;
  ttl_seconds: number;
};

export type AdapterHealth = {
  id: string;
  ok: boolean;
  live: boolean;
  config_present: boolean;
  reachable: boolean | null;
  transport: string;
  detail: string;
  schema_ok?: boolean | null;
  not_live?: boolean;
  window_s?: number | null;
  frames?: number | null;
  fps?: number | null;
  canvas?: string | null;
  hop1_watch_required?: boolean;
};

export type MediaAsset = {
  id: string;
  episode_id: string;
  kind: "sheet" | "plate" | "costume" | "preview" | "other";
  original_name: string;
  stored_name: string;
  content_type: string;
  path: string;
  entity_label: string;
  entity_type: string;
  notes: string;
  created_by: string;
  created_at: string;
  approval_status?: "draft" | "approved";
  approved_by?: string;
  approved_at?: string | null;
  shot_id?: string | null;
  edit_row_id?: string;
  lock_keywords?: string;
  approved?: boolean;
};

export type Meta = {
  name: string;
  phase: number;
  auth_mode: "local" | "forward-header" | "oidc";
  sso: string;
  pack_builder_url: string;
  docs: string;
  default_user: string;
  job_worker?: string;
  still_adapter?: string;
  clip_adapter?: string;
  cost_currency?: string;
  retention_days?: number;
  budget_hard_stop?: boolean;
  media_backend?: "local" | "s3";
  media_s3_configured?: boolean;
  media_note?: string;
  presence_ttl_seconds?: number;
  roles?: string[];
  role_matrix?: RoleMatrixRow[];
  celery_enabled?: boolean;
  oidc_configured?: boolean;
  oidc_apply_role_claim?: boolean;
  notify_webhook_configured?: boolean;
  multi_org?: boolean;
  multi_org_note?: string;
  llm_configured?: boolean;
  llm_note?: string;
  primary_create?: string;
};

export const REVIEW_COPY: Record<ReviewStateName, string> = {
  draft: "Script / pack in progress",
  "needs-art": "Sheets or plates missing",
  "needs-edit": "Joins / verbs / takes still open",
  "preview-watched": "Hop-1 watched; not generate-ok yet",
  "generate-ok": "All gates green, hop-1 receipts watched, AND a reviewer/producer sign-off — GPU spend allowed",
};

export const SHOT_READINESS = ["draft", "candidates", "linked", "ready"] as const;
export type ShotReadiness = (typeof SHOT_READINESS)[number];

export const CANDIDATE_KINDS = ["character", "prop", "scene", "costume"] as const;
export type CandidateKind = (typeof CANDIDATE_KINDS)[number];

export type CandidateStatus = "pending" | "accepted" | "ignored" | "linked";

export type Candidate = {
  id: string;
  shot_id: string;
  kind: CandidateKind;
  label: string;
  evidence: string;
  status: CandidateStatus;
  source: "stub" | "manual";
  linked_asset_id: string | null;
  linked_ref: string;
  created_at: string;
  updated_at: string;
};

export type ContinuityReceipt = {
  id: string;
  episode_id: string;
  shot_id: string;
  media_id: string | null;
  duration_s: number | null;
  frames: number | null;
  fps: number | null;
  still_vs_lock: string;
  ng_reason: string;
  source: "manual" | "parsed";
  preview_watched: boolean;
  watched_by: string;
  watched_at: string | null;
  notes: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  complete: boolean;
  extend_ok: boolean;
  blockers: string[];
};

export type Shot = {
  id: string;
  episode_id: string;
  pack_revision_id: string | null;
  edit_row_id: string;
  sort_index: number;
  song_t: string;
  join: string;
  take: string;
  location_grade: string;
  camera_verb: string;
  action: string;
  entities: string;
  readiness: ShotReadiness;
  candidates: Candidate[];
  hop1_required?: boolean;
  preview?: ContinuityReceipt | null;
  created_at: string;
  updated_at: string;
};

export type Board = {
  shots: Shot[];
  continue_chains: string[][];
  boundaries: { shot_id: string; join: string }[];
};

export const JOB_TYPES = [
  "still-sheet",
  "still-plate",
  "clip-hop1",
  "clip-extend",
  "batch-precheck",
] as const;
export type JobType = (typeof JOB_TYPES)[number];

export const JOB_STATUSES = ["queued", "running", "succeeded", "failed", "cancelled"] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];

export type Job = {
  id: string;
  episode_id: string;
  project_id: string;
  shot_id: string | null;
  media_id: string | null;
  retry_of_id: string | null;
  job_type: JobType;
  status: JobStatus;
  progress: number;
  error: string;
  adapter: string;
  payload: Record<string, unknown>;
  result: Record<string, unknown>;
  estimated_cost_units: number;
  actual_cost_units: number | null;
  cost_currency: string;
  cost_note: string;
  cancel_requested: boolean;
  created_by: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  updated_at: string;
  elapsed_ms: number;
  episode_title: string;
  project_name: string;
  shot_sort_index: number | null;
  shot_take: string;
};

export type PreviewDesk = {
  episode_id: string;
  required_count: number;
  complete_count: number;
  generate_ok_ready: boolean;
  blockers: { shot_id: string; take: string; reason: string }[];
  shots: {
    shot: Shot;
    required: boolean;
    complete: boolean;
    extend_ok: boolean;
    blockers: string[];
  }[];
};

export type AdapterSlot = {
  id: string;
  label: string;
  kinds: string[];
  live: boolean;
  transport: string;
  note: string;
  health?: AdapterHealth | null;
  window_s?: number | null;
  frames?: number | null;
  fps?: number | null;
  canvas?: string | null;
  hop1_watch_required?: boolean;
  config_schema?: Record<string, unknown>;
  honesty?: string;
};

export type AdapterCatalog = {
  adapters: AdapterSlot[];
  still_default: string;
  clip_default: string;
  health?: AdapterHealth[];
  note: string;
};

export type BudgetEpisodeRow = {
  episode_id: string;
  title: string;
  chapter: number;
  spent_units: number;
  pending_units: number;
  job_count: number;
  succeeded: number;
  failed: number;
  cancelled: number;
  adapter_mix: Record<string, number>;
};

export type BudgetProjectRow = {
  project_id: string;
  name: string;
  slug: string;
  spent_units: number;
  pending_units: number;
  cap_units: number | null;
  hard_stop: boolean;
  over_cap: boolean;
  job_count: number;
  adapter_mix: Record<string, number>;
  still_adapter: string;
  clip_adapter: string;
  usd_estimate: number | null;
  episodes: BudgetEpisodeRow[];
};

export type BudgetDashboard = {
  currency: string;
  usd_per_unit: number;
  rates: Record<string, number>;
  disclaimer: string;
  spent_units: number;
  pending_units: number;
  usd_estimate: number | null;
  cap_units: number | null;
  hard_stop: boolean;
  job_counts: Record<string, number>;
  adapter_mix: Record<string, number>;
  projects: BudgetProjectRow[];
};

export type AuditEvent = {
  id: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  project_id: string | null;
  episode_id: string | null;
  project_name: string;
  episode_title: string;
  detail: Record<string, unknown>;
  created_at: string;
};

export type VerticalTemplate = {
  id: string;
  name: string;
  blurb: string;
  still_adapter: string;
  clip_adapter: string;
  stages: string[];
  gates_green: boolean;
  fake_generate: boolean;
};

export type RetentionPreview = {
  retention_days: number;
  enabled: boolean;
  keep_pack_revisions: boolean;
  keep_note: string;
  candidates: { id: string; kind: string; original_name: string; path: string }[];
  revision_count_kept: number;
  dry_run?: boolean;
  applied?: boolean;
  deleted_count?: number;
};

export type StudioNotification = {
  id: string;
  organization_id: string;
  user_name: string;
  kind: string;
  title: string;
  body: string;
  project_id: string | null;
  episode_id: string | null;
  shot_id: string | null;
  job_id: string | null;
  comment_id: string | null;
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
  href: string;
};

export type NotificationList = {
  items: StudioNotification[];
  unread_count: number;
};

export type ContinuityShot = {
  shot_id: string;
  edit_row_id: string;
  sort_index: number;
  take: string;
  join: string;
  entities: string;
  issues: string[];
  href: string;
  identity_href?: string;
  identity_hrefs?: string[];
};

export type ContinuitySummary = {
  episode_id: string;
  project_id: string;
  honesty: string;
  all_green: boolean;
  red_gates: GateResult[];
  entity_schedule: Record<string, unknown>[];
  entity_schedule_problems: string[];
  lock_diff_problems: string[];
  mismatches: string[];
  shots: ContinuityShot[];
  identity?: IdentityStore;
  identity_href?: string;
  identity_lock_diff_problems?: string[];
};

export type IdentityAsset = {
  id: string;
  kind: "sheet" | "plate";
  original_name: string;
  entity_label: string;
  entity_type: string;
  notes: string;
  href: string;
  approval_status: "draft" | "approved";
  approved_by: string;
  approved_at: string | null;
  shot_id: string | null;
  edit_row_id: string;
  lock_keywords: string;
  approved: boolean;
  created_by: string;
  created_at: string;
};

export type IdentityStore = {
  episode_id: string;
  project_id: string;
  honesty: string;
  embeddings: boolean;
  likeness: boolean;
  sheets: IdentityAsset[];
  plates: IdentityAsset[];
  approved_sheet_count: number;
  approved_plate_count: number;
};

export type PackDiffGate = {
  id: string;
  n: number;
  label: string;
  left_ok: boolean | null;
  right_ok: boolean | null;
  left_detail: string;
  right_detail: string;
  changed: boolean;
};

export type PackDiffRef = {
  id?: string | null;
  filename: string;
  all_gates_green?: boolean;
  created_by?: string;
  created_at?: string | null;
  label?: string;
  candidate?: boolean;
};

export type PackDiff = {
  honesty: string;
  left: PackDiffRef | null;
  right: PackDiffRef | null;
  gates: PackDiffGate[];
  entity_schedule: {
    added?: unknown[];
    removed?: unknown[];
    changed?: unknown[];
    ambiguous?: { natural?: string; note?: string; matched_by?: string }[];
  };
  edit_list: { added?: unknown[]; removed?: unknown[]; changed?: unknown[] };
  identity_keywords: { added?: unknown[]; removed?: unknown[]; changed?: unknown[] };
  summary: Record<string, unknown>;
  auto_generate: boolean;
};

export type PackHandoff = {
  id: string;
  filename: string;
  created_by: string;
  created_at: string;
  expires_at: string;
  consumed: boolean;
  episode_id: string | null;
  honesty: string;
  auto_generate: boolean;
};

export type PlaylistScrubShot = {
  shot_id: string;
  sort_index: number;
  edit_row_id: string;
  take: string;
  join: string;
  action: string;
  song_t: string;
  camera_verb: string;
  duration_s: number | null;
  frames: number | null;
  preview_watched: boolean;
  media_id: string | null;
  content_type: string;
  original_name: string;
  playable: boolean;
  image: boolean;
  stub: boolean;
  empty: boolean;
  note: string;
};

export type PlaylistScrub = {
  episode_id: string;
  honesty: string;
  nle: boolean;
  shot_count: number;
  shots: PlaylistScrubShot[];
};

export type DemoSeed = {
  project: Project;
  episode: Episode;
  template_id: string;
  honesty: string;
  fixture_media: number;
  fake_generate: boolean;
  likeness: boolean;
  engine_mp4: boolean;
};

export type BackupRestoreResult = {
  honesty?: string;
  keep_pack_revisions: boolean;
  keep_note?: string;
  dry_run: boolean;
  applied: boolean;
  would_create_projects?: string[];
  would_skip_projects?: string[];
  would_create_episodes?: string[];
  would_add_revisions?: string[];
  would_keep_revisions?: string[];
  cross_org_conflicts?: string[];
  created_projects?: number;
  created_episodes?: number;
  added_revisions?: number;
  created_media?: number;
};
