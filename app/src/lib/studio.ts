/** Studio handoff. Default is local studio-web. Not a rewrite of the builder. Not auto-generate. */

const HANDOFF_MESSAGE = "aigc-pack-handoff";
const READY_MESSAGE = "aigc-studio-ready";

function envString(name: string): string | undefined {
  try {
    const value = (import.meta.env as Record<string, unknown> | undefined)?.[name];
    return typeof value === "string" && value.trim() ? value.trim() : undefined;
  } catch {
    return undefined;
  }
}

export function studioBaseUrl(): string {
  const raw = envString("VITE_STUDIO_URL") || "http://localhost:5174";
  return raw.replace(/\/$/, "");
}

export function studioApiUrl(): string {
  const raw = envString("VITE_STUDIO_API_URL");
  if (raw) return raw.replace(/\/$/, "");
  try {
    const studio = new URL(studioBaseUrl());
    if (studio.port === "5174") {
      studio.port = "8000";
      return studio.origin;
    }
    if (studio.port === "4174") {
      studio.port = "8000";
      return studio.origin;
    }
  } catch {
    /* fall through */
  }
  return "http://localhost:8000";
}

export function studioToken(): string {
  const fromEnv = envString("VITE_STUDIO_TOKEN");
  if (fromEnv) return fromEnv;
  try {
    const host = new URL(studioApiUrl()).hostname;
    if (host === "localhost" || host === "127.0.0.1") {
      return "local-dev-token";
    }
  } catch {
    return "";
  }
  return "";
}

export function studioImportUrl(): string {
  return `${studioBaseUrl()}/?import=1#/projects`;
}

export function studioHandoffUrl(handoffId: string): string {
  const id = encodeURIComponent(handoffId);
  return `${studioBaseUrl()}/?handoff=${id}#/projects`;
}

export type StudioHandoffFailure = "studio-down" | "auth" | "none";

export type StudioHandoffResult = {
  ok: boolean;
  url: string;
  handoffId?: string;
  message: string;
  failure: StudioHandoffFailure;
  autoGenerate: false;
};

export function handoffFailureMessage(failure: StudioHandoffFailure): string {
  if (failure === "auth") {
    return (
      "Studio refused the zip (auth). Set VITE_STUDIO_TOKEN to the same value as STUDIO_API_TOKEN, " +
      "or pick a project/episode and Import pack zip by hand. Never auto-generate."
    );
  }
  if (failure === "studio-down") {
    return (
      "Studio API did not accept the zip (studio down or CORS). Export the zip, then Import pack zip " +
      "after picking an episode. Never auto-generate."
    );
  }
  return "Open in Studio. Pick a project/episode to finish import. Never auto-generate.";
}

async function stageHandoff(blob: Blob, filename: string): Promise<{ id?: string; failure: StudioHandoffFailure }> {
  const api = studioApiUrl();
  const token = studioToken();
  try {
    const data = new FormData();
    data.append("file", blob, filename);
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    const response = await fetch(`${api}/api/handoffs`, { method: "POST", body: data, headers });
    if (response.status === 401 || response.status === 403) {
      return { failure: "auth" };
    }
    if (!response.ok) {
      return { failure: "studio-down" };
    }
    const body = (await response.json()) as { id?: string };
    if (body.id) return { id: body.id, failure: "none" };
    return { failure: "studio-down" };
  } catch {
    return { failure: "studio-down" };
  }
}

function postZipToStudio(target: Window, blob: Blob, filename: string, origin: string): void {
  void blob.arrayBuffer().then((bytes) => {
    const payload = { type: HANDOFF_MESSAGE, filename, bytes };
    target.postMessage(payload, origin);
    window.setTimeout(() => target.postMessage(payload, origin), 400);
    window.setTimeout(() => target.postMessage(payload, origin), 1200);
  });
}

export async function openInStudio(blob: Blob, filename: string): Promise<StudioHandoffResult> {
  const staged = await stageHandoff(blob, filename);
  const url = staged.id ? studioHandoffUrl(staged.id) : studioImportUrl();
  const studioOrigin = studioBaseUrl();
  let opened: Window | null = null;
  try {
    opened = window.open(url, "aigc-studio");
  } catch {
    opened = null;
  }
  if (opened) {
    postZipToStudio(opened, blob, filename, studioOrigin);
  }
  const ok = Boolean(staged.id);
  const failure = staged.failure;
  const pick = "Pick a project/episode — import uses the handed-off zip (no re-choose file).";
  const message = ok
    ? `Studio handoff staged. ${pick} Not auto-generate.`
    : `${handoffFailureMessage(failure)} ${pick}`;
  return {
    ok,
    url,
    handoffId: staged.id,
    message,
    failure,
    autoGenerate: false,
  };
}

export const STUDIO_HANDOFF_MESSAGE = HANDOFF_MESSAGE;
export const STUDIO_READY_MESSAGE = READY_MESSAGE;
