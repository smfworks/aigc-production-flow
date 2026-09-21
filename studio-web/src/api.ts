import type {
  AdapterCatalog,
  AdapterHealth,
  AuditEvent,
  BackupRestoreResult,
  Board,
  BudgetDashboard,
  Comment,
  ContinuityReceipt,
  ContinuitySummary,
  DemoSeed,
  Episode,
  IdentityStore,
  Job,
  MediaAsset,
  Meta,
  NotificationList,
  OrgMember,
  PackDiff,
  PackHandoff,
  PackRevisionSummary,
  PresenceUser,
  PreviewDesk,
  Project,
  RetentionPreview,
  Review,
  ReviewSignoff,
  ReviewStateName,
  Shot,
  ShotReadiness,
  StudioNotification,
  StudioOrg,
  StudioUser,
  VerticalTemplate,
} from "./types.ts";

const TOKEN_KEY = "smf.aigc-studio.token";
const USER_KEY = "smf.aigc-studio.user";
const ORG_KEY = "smf.aigc-studio.org";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || import.meta.env.VITE_API_TOKEN || "local-dev-token";
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getUserName(): string {
  return localStorage.getItem(USER_KEY) || "";
}

export function setUserName(name: string): void {
  localStorage.setItem(USER_KEY, name);
}

export function getOrgId(): string {
  return localStorage.getItem(ORG_KEY) || "";
}

export function setOrgId(orgId: string): void {
  if (orgId) localStorage.setItem(ORG_KEY, orgId);
  else localStorage.removeItem(ORG_KEY);
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    const detail = body.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message: string }).message);
    }
    return JSON.stringify(detail);
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${getToken()}`);
  }
  const userName = getUserName().trim();
  if (userName && !headers.has("X-User-Name")) {
    headers.set("X-User-Name", userName);
  }
  const orgId = getOrgId().trim();
  if (orgId && !headers.has("X-Org-Id")) {
    headers.set("X-Org-Id", orgId);
  }
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...init, headers });
  if (response.status === 204) return undefined as T;
  if (!response.ok) throw new Error(await parseError(response));
  const type = response.headers.get("content-type") || "";
  if (type.includes("application/json")) return (await response.json()) as T;
  return (await response.blob()) as T;
}

export const api = {
  meta: () => request<Meta>("/api/meta"),
  me: () => request<StudioUser>("/api/me"),
  orgs: () => request<StudioOrg[]>("/api/orgs"),
  createOrg: (name: string) =>
    request<StudioOrg>("/api/orgs", { method: "POST", body: JSON.stringify({ name }) }),
  notifications: (unread = false) =>
    request<NotificationList>(`/api/notifications${unread ? "?unread=true" : ""}`),
  markNotificationRead: (id: string) =>
    request<StudioNotification>(`/api/notifications/${id}/read`, { method: "POST" }),
  markNotificationsRead: () => request<{ ok: boolean; marked: number }>("/api/notifications/read-all", { method: "POST" }),
  continuity: (episodeId: string) => request<ContinuitySummary>(`/api/episodes/${episodeId}/continuity`),
  identity: (episodeId: string) => request<IdentityStore>(`/api/episodes/${episodeId}/identity`),
  approveIdentity: (episodeId: string, assetId: string, note = "", lockKeywords = "") =>
    request<MediaAsset>(`/api/episodes/${episodeId}/identity/${assetId}/approve`, {
      method: "POST",
      body: JSON.stringify({ note, lock_keywords: lockKeywords }),
    }),
  linkIdentityPlate: (episodeId: string, assetId: string, shotId: string) =>
    request<MediaAsset>(`/api/episodes/${episodeId}/identity/${assetId}/link`, {
      method: "POST",
      body: JSON.stringify({ shot_id: shotId }),
    }),
  revisions: (episodeId: string) => request<PackRevisionSummary[]>(`/api/episodes/${episodeId}/revisions`),
  revisionDiff: (episodeId: string, leftId: string, rightId: string) =>
    request<PackDiff>(`/api/episodes/${episodeId}/revisions/${leftId}/diff/${rightId}`),
  previewPackDiff: (episodeId: string, file?: File, handoffId?: string) => {
    const data = new FormData();
    if (file) data.append("file", file);
    if (handoffId) data.append("handoff_id", handoffId);
    return request<PackDiff>(`/api/episodes/${episodeId}/pack/diff`, { method: "POST", body: data });
  },
  handoff: (id: string) => request<PackHandoff>(`/api/handoffs/${id}`),
  seedDemo: () => request<DemoSeed>("/api/demo/seed", { method: "POST" }),
  restoreBackup: (file: File, dryRun: boolean) => {
    const data = new FormData();
    data.append("file", file);
    data.append("dry_run", dryRun ? "true" : "false");
    if (!dryRun) data.append("confirm", "restore");
    return request<BackupRestoreResult>("/api/backup/restore", { method: "POST", body: data });
  },
  members: (orgId: string) => request<OrgMember[]>(`/api/orgs/${orgId}/members`),
  addMember: (orgId: string, body: { user_name: string; role: string }) =>
    request<OrgMember>(`/api/orgs/${orgId}/members`, { method: "POST", body: JSON.stringify(body) }),
  changeMemberRole: (orgId: string, memberId: string, role: string) =>
    request<OrgMember>(`/api/orgs/${orgId}/members/${memberId}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),
  presence: (episodeId: string) => request<PresenceUser[]>(`/api/episodes/${episodeId}/presence`),
  heartbeat: (episodeId: string, shotId?: string | null) =>
    request<PresenceUser[]>(`/api/episodes/${episodeId}/presence`, {
      method: "POST",
      body: JSON.stringify({ shot_id: shotId || null }),
    }),
  adapterHealth: () => request<AdapterHealth[]>("/api/adapters/health"),
  adapterDryRun: (adapterId: string) =>
    request<AdapterHealth>(`/api/adapters/${adapterId}/dry-run`, { method: "POST" }),
  projects: () => request<Project[]>("/api/projects"),
  createProject: (body: {
    name: string;
    description?: string;
    still_adapter?: string;
    clip_adapter?: string;
    budget_cap_units?: number | null;
    budget_hard_stop?: boolean;
  }) => request<Project>("/api/projects", { method: "POST", body: JSON.stringify(body) }),
  project: (id: string) => request<Project>(`/api/projects/${id}`),
  updateProject: (
    id: string,
    body: {
      still_adapter?: string;
      clip_adapter?: string;
      budget_cap_units?: number | null;
      budget_hard_stop?: boolean;
      retention_days?: number | null;
      clear_budget_cap?: boolean;
      clear_retention_days?: boolean;
      description?: string;
    },
  ) => request<Project>(`/api/projects/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  episodes: (projectId: string) => request<Episode[]>(`/api/projects/${projectId}/episodes`),
  createEpisode: (projectId: string, body: { title: string; synopsis?: string }) =>
    request<Episode>(`/api/projects/${projectId}/episodes`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  episode: (id: string) => request<Episode>(`/api/episodes/${id}`),
  review: (episodeId: string) => request<Review>(`/api/episodes/${episodeId}/review`),
  setReview: (episodeId: string, state: ReviewStateName, note = "", override = false) =>
    request<Review>(`/api/episodes/${episodeId}/review`, {
      method: "PUT",
      body: JSON.stringify({ state, note, override }),
    }),
  signoffs: (episodeId: string) =>
    request<ReviewSignoff[]>(`/api/episodes/${episodeId}/review/signoffs`),
  signOff: (episodeId: string, note = "") =>
    request<Review>(`/api/episodes/${episodeId}/review/signoff`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  comments: (episodeId: string, query: { shot_id?: string; include_resolved?: boolean } = {}) => {
    const params = new URLSearchParams();
    if (query.shot_id) params.set("shot_id", query.shot_id);
    if (query.include_resolved === false) params.set("include_resolved", "false");
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<Comment[]>(`/api/episodes/${episodeId}/comments${suffix}`);
  },
  addComment: (episodeId: string, body: string, extra: { shot_id?: string; board_node_id?: string } = {}) =>
    request<Comment>(`/api/episodes/${episodeId}/comments`, {
      method: "POST",
      body: JSON.stringify({ body, ...extra }),
    }),
  resolveComment: (commentId: string) =>
    request<Comment>(`/api/comments/${commentId}/resolve`, { method: "POST" }),
  media: (episodeId: string) => request<MediaAsset[]>(`/api/episodes/${episodeId}/media`),
  uploadMedia: (
    episodeId: string,
    file: File,
    kind: string,
    entityLabel: string,
    notes: string,
    entityType = "",
  ) => {
    const data = new FormData();
    data.append("file", file);
    data.append("kind", kind);
    data.append("entity_label", entityLabel);
    data.append("entity_type", entityType);
    data.append("notes", notes);
    return request<MediaAsset>(`/api/episodes/${episodeId}/media`, { method: "POST", body: data });
  },
  mediaUrl: (assetId: string) => `/api/media/${assetId}`,
  importPack: (episodeId: string, file?: File, handoffId?: string) => {
    const data = new FormData();
    if (file) data.append("file", file);
    if (handoffId) data.append("handoff_id", handoffId);
    return request<{ all_gates_green: boolean; filename: string }>(
      `/api/episodes/${episodeId}/pack`,
      { method: "POST", body: data },
    );
  },
  exportPackUrl: (episodeId: string) => `/api/episodes/${episodeId}/pack`,
  shots: (episodeId: string) => request<Shot[]>(`/api/episodes/${episodeId}/shots`),
  board: (episodeId: string) => request<Board>(`/api/episodes/${episodeId}/board`),
  extractCandidates: (episodeId: string) =>
    request<Shot[]>(`/api/episodes/${episodeId}/shots/extract-candidates`, { method: "POST" }),
  setShotReadiness: (episodeId: string, shotId: string, readiness: ShotReadiness) =>
    request<Shot>(`/api/episodes/${episodeId}/shots/${shotId}/readiness`, {
      method: "PUT",
      body: JSON.stringify({ readiness }),
    }),
  addCandidate: (
    episodeId: string,
    shotId: string,
    body: { kind: string; label: string; evidence?: string },
  ) =>
    request<Shot>(`/api/episodes/${episodeId}/shots/${shotId}/candidates`, {
      method: "POST",
      body: JSON.stringify(body),
    }).then(() => request<Shot>(`/api/episodes/${episodeId}/shots/${shotId}`)),
  updateCandidate: (
    episodeId: string,
    shotId: string,
    candidateId: string,
    body: { status?: string; linked_asset_id?: string; linked_ref?: string },
  ) =>
    request(`/api/episodes/${episodeId}/shots/${shotId}/candidates/${candidateId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }).then(() => request<Shot>(`/api/episodes/${episodeId}/shots/${shotId}`)),
  jobs: (query: { episode_id?: string; status?: string; job_type?: string } = {}) => {
    const params = new URLSearchParams();
    if (query.episode_id) params.set("episode_id", query.episode_id);
    if (query.status) params.set("status", query.status);
    if (query.job_type) params.set("job_type", query.job_type);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<Job[]>(`/api/jobs${suffix}`);
  },
  episodeJobs: (episodeId: string) => request<Job[]>(`/api/episodes/${episodeId}/jobs`),
  job: (jobId: string) => request<Job>(`/api/jobs/${jobId}`),
  enqueueJob: (body: { episode_id: string; shot_id?: string; job_type: string; payload?: Record<string, unknown> }) =>
    request<Job>("/api/jobs", { method: "POST", body: JSON.stringify(body) }),
  cancelJob: (jobId: string) => request<Job>(`/api/jobs/${jobId}/cancel`, { method: "POST" }),
  retryJob: (jobId: string) => request<Job>(`/api/jobs/${jobId}/retry`, { method: "POST" }),
  previewDesk: (episodeId: string) => request<PreviewDesk>(`/api/episodes/${episodeId}/preview-desk`),
  setReceipt: (
    episodeId: string,
    shotId: string,
    body: {
      media_id?: string;
      duration_s?: number | null;
      frames?: number | null;
      fps?: number | null;
      still_vs_lock?: string;
      ng_reason?: string;
      source?: string;
      notes?: string;
      watched?: boolean;
    },
  ) =>
    request<ContinuityReceipt>(`/api/episodes/${episodeId}/shots/${shotId}/receipt`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  setPreviewWatched: (episodeId: string, shotId: string, watched: boolean, note = "") =>
    request<ContinuityReceipt>(`/api/episodes/${episodeId}/shots/${shotId}/preview-watched`, {
      method: "PUT",
      body: JSON.stringify({ watched, note }),
    }),
  attachPreview: (
    episodeId: string,
    shotId: string,
    fields: {
      file?: File;
      media_id?: string;
      duration_s?: string;
      frames?: string;
      still_vs_lock?: string;
      ng_reason?: string;
      notes?: string;
      watched?: boolean;
    },
  ) => {
    const data = new FormData();
    if (fields.file) data.append("file", fields.file);
    if (fields.media_id) data.append("media_id", fields.media_id);
    if (fields.duration_s) data.append("duration_s", fields.duration_s);
    if (fields.frames) data.append("frames", fields.frames);
    if (fields.still_vs_lock) data.append("still_vs_lock", fields.still_vs_lock);
    if (fields.ng_reason) data.append("ng_reason", fields.ng_reason);
    if (fields.notes) data.append("notes", fields.notes);
    if (fields.watched) data.append("watched", "true");
    return request<ContinuityReceipt>(`/api/episodes/${episodeId}/shots/${shotId}/preview`, {
      method: "POST",
      body: data,
    });
  },
  adapters: () => request<AdapterCatalog>("/api/adapters"),
  templates: () => request<VerticalTemplate[]>("/api/templates"),
  createFromTemplate: (templateId: string, body: { name?: string; description?: string }) =>
    request<{ project: Project; episode: Episode; gates_green: boolean; template_id: string }>(
      `/api/templates/${templateId}/projects`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  budget: (query: { project_id?: string; episode_id?: string } = {}) => {
    if (query.episode_id) return request<BudgetDashboard>(`/api/episodes/${query.episode_id}/budget`);
    if (query.project_id) return request<BudgetDashboard>(`/api/projects/${query.project_id}/budget`);
    return request<BudgetDashboard>("/api/budget");
  },
  audit: (query: { project_id?: string; episode_id?: string; action?: string } = {}) => {
    const params = new URLSearchParams();
    if (query.project_id) params.set("project_id", query.project_id);
    if (query.episode_id) params.set("episode_id", query.episode_id);
    if (query.action) params.set("action", query.action);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<AuditEvent[]>(`/api/audit${suffix}`);
  },
  retentionPreview: (query: { project_id?: string; episode_id?: string } = {}) => {
    const params = new URLSearchParams();
    if (query.project_id) params.set("project_id", query.project_id);
    if (query.episode_id) params.set("episode_id", query.episode_id);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<RetentionPreview>(`/api/retention${suffix}`);
  },
  retentionApply: (body: { project_id?: string; episode_id?: string; dry_run?: boolean; confirm?: string }) =>
    request<RetentionPreview>("/api/retention", { method: "POST", body: JSON.stringify(body) }),
};

async function saveDownload(response: Response, fallback: string): Promise<void> {
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/i);
  const name = match?.[1] || fallback;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function authHeaders(): HeadersInit {
  const headers: Record<string, string> = { Authorization: `Bearer ${getToken()}` };
  const userName = getUserName().trim();
  if (userName) headers["X-User-Name"] = userName;
  const orgId = getOrgId().trim();
  if (orgId) headers["X-Org-Id"] = orgId;
  return headers;
}

export async function downloadPack(episodeId: string): Promise<void> {
  const response = await fetch(api.exportPackUrl(episodeId), {
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(await parseError(response));
  await saveDownload(response, "pack.zip");
}

export async function downloadExport(episodeId: string, kind: "edl" | "playlist" | "fcpxml"): Promise<void> {
  const fallback = kind === "edl" ? "episode.edl" : kind === "fcpxml" ? "episode.xml" : "playlist.json";
  const response = await fetch(`/api/episodes/${episodeId}/export/${kind}`, {
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(await parseError(response));
  await saveDownload(response, fallback);
}

export async function downloadBackup(): Promise<void> {
  const response = await fetch("/api/backup", { headers: authHeaders() });
  if (!response.ok) throw new Error(await parseError(response));
  await saveDownload(response, "studio-backup.zip");
}

export async function downloadMedia(assetId: string, filename: string): Promise<void> {
  const response = await fetch(api.mediaUrl(assetId), {
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(await parseError(response));
  await saveDownload(response, filename);
}
