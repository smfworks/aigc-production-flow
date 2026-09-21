import type {
  Board,
  Comment,
  Episode,
  MediaAsset,
  Meta,
  Project,
  Review,
  ReviewStateName,
  Shot,
  ShotReadiness,
} from "./types.ts";

const TOKEN_KEY = "smf.aigc-studio.token";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || import.meta.env.VITE_API_TOKEN || "local-dev-token";
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
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
  projects: () => request<Project[]>("/api/projects"),
  createProject: (body: { name: string; description?: string }) =>
    request<Project>("/api/projects", { method: "POST", body: JSON.stringify(body) }),
  project: (id: string) => request<Project>(`/api/projects/${id}`),
  episodes: (projectId: string) => request<Episode[]>(`/api/projects/${projectId}/episodes`),
  createEpisode: (projectId: string, body: { title: string; synopsis?: string }) =>
    request<Episode>(`/api/projects/${projectId}/episodes`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  episode: (id: string) => request<Episode>(`/api/episodes/${id}`),
  review: (episodeId: string) => request<Review>(`/api/episodes/${episodeId}/review`),
  setReview: (episodeId: string, state: ReviewStateName, note = "") =>
    request<Review>(`/api/episodes/${episodeId}/review`, {
      method: "PUT",
      body: JSON.stringify({ state, note }),
    }),
  comments: (episodeId: string) => request<Comment[]>(`/api/episodes/${episodeId}/comments`),
  addComment: (episodeId: string, body: string) =>
    request<Comment>(`/api/episodes/${episodeId}/comments`, {
      method: "POST",
      body: JSON.stringify({ body }),
    }),
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
  importPack: (episodeId: string, file: File) => {
    const data = new FormData();
    data.append("file", file);
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

export async function downloadPack(episodeId: string): Promise<void> {
  const response = await fetch(api.exportPackUrl(episodeId), {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!response.ok) throw new Error(await parseError(response));
  await saveDownload(response, "pack.zip");
}

export async function downloadMedia(assetId: string, filename: string): Promise<void> {
  const response = await fetch(api.mediaUrl(assetId), {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!response.ok) throw new Error(await parseError(response));
  await saveDownload(response, filename);
}
