/** Studio handoff. Default is local studio-web. Not a rewrite of the builder. */

function envStudioUrl(): string | undefined {
  try {
    const value = import.meta.env?.VITE_STUDIO_URL;
    return typeof value === "string" && value.trim() ? value.trim() : undefined;
  } catch {
    return undefined;
  }
}

export function studioBaseUrl(): string {
  const raw = envStudioUrl() || "http://localhost:5174";
  return raw.replace(/\/$/, "");
}

export function studioImportUrl(): string {
  return `${studioBaseUrl()}/?import=1#/projects`;
}
