/** Pending builder → studio pack zip. Not auto-generate. */

const KEY = "smf.aigc-studio.handoff";
const FILE_KEY = "smf.aigc-studio.handoff-file";
const MESSAGE = "aigc-pack-handoff";

export type PendingHandoff = {
  id?: string;
  filename: string;
  notice: string;
};

let memoryFile: File | null = null;

export function getPendingHandoff(): PendingHandoff | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PendingHandoff;
    if (!parsed || (!parsed.id && !parsed.filename)) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function setPendingHandoff(row: PendingHandoff): void {
  sessionStorage.setItem(KEY, JSON.stringify(row));
}

export function clearPendingHandoff(): void {
  sessionStorage.removeItem(KEY);
  sessionStorage.removeItem(FILE_KEY);
  memoryFile = null;
}

export function getPendingFile(): File | null {
  return memoryFile;
}

export function setPendingFile(file: File): void {
  memoryFile = file;
}

export function parseHandoffSearch(search = window.location.search): { importHint: string | null; handoffId: string | null } {
  const params = new URLSearchParams(search);
  const handoff = params.get("handoff");
  const hint = params.has("import") ? params.get("import") || "1" : null;
  return { importHint: hint, handoffId: handoff && handoff.trim() ? handoff.trim() : null };
}

export function clearHandoffSearch(): void {
  const url = new URL(window.location.href);
  let dirty = false;
  if (url.searchParams.has("handoff")) {
    url.searchParams.delete("handoff");
    dirty = true;
  }
  if (url.searchParams.has("import")) {
    url.searchParams.delete("import");
    dirty = true;
  }
  if (!dirty) return;
  const search = url.searchParams.toString();
  window.history.replaceState(null, "", `${url.pathname}${search ? `?${search}` : ""}${url.hash}`);
}

export function trustedHandoffOrigin(eventOrigin: string, allowed: string[]): boolean {
  const origin = (eventOrigin || "").trim();
  if (!origin || origin === "null") return false;
  for (const raw of allowed) {
    const value = (raw || "").trim();
    if (!value) continue;
    try {
      if (new URL(value).origin === origin) return true;
    } catch {
      if (value === origin) return true;
    }
  }
  return false;
}

export function listenForBuilderHandoff(
  onReceive: (file: File, filename: string) => void,
  allowedOrigins: string[],
): () => void {
  function onMessage(event: MessageEvent) {
    if (!trustedHandoffOrigin(event.origin, allowedOrigins)) return;
    const data = event.data as { type?: string; filename?: string; bytes?: ArrayBuffer } | null;
    if (!data || data.type !== MESSAGE || !data.bytes) return;
    const filename = data.filename || "pack.zip";
    const file = new File([data.bytes], filename, { type: "application/zip" });
    setPendingFile(file);
    setPendingHandoff({
      filename,
      notice: `Builder zip “${filename}” is ready. Pick a project/episode — import will not re-ask for the file. Not auto-generate.`,
    });
    onReceive(file, filename);
  }
  window.addEventListener("message", onMessage);
  return () => window.removeEventListener("message", onMessage);
}
