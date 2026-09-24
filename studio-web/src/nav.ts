export type View =
  | { page: "create"; wizardId?: string; fullWizard?: boolean }
  | { page: "projects" }
  | { page: "project"; projectId: string }
  | { page: "episode"; projectId: string; episodeId: string; shotId?: string; identityId?: string }
  | { page: "tasks"; jobId?: string }
  | { page: "budget"; projectId?: string }
  | { page: "audit"; projectId?: string; episodeId?: string };

export function parseHash(hash = window.location.hash): View {
  const raw = hash.replace(/^#/, "");
  const parts = raw.split("/").filter(Boolean);
  if (parts[0] === "create") {
    if (parts[1] === "full") {
      return { page: "create", fullWizard: true, wizardId: parts[2] };
    }
    return { page: "create", wizardId: parts[1] };
  }
  if (parts[0] === "tasks") {
    return { page: "tasks", jobId: parts[1] };
  }
  if (parts[0] === "budget") {
    return { page: "budget", projectId: parts[1] };
  }
  if (parts[0] === "audit") {
    return { page: "audit", projectId: parts[1], episodeId: parts[2] };
  }
  if (parts[0] === "projects" && parts[1] && parts[2] === "episodes" && parts[3]) {
    return {
      page: "episode",
      projectId: parts[1],
      episodeId: parts[3],
      shotId: parts[4] === "shots" ? parts[5] : undefined,
      identityId: parts[4] === "identity" ? parts[5] || "" : undefined,
    };
  }
  if (parts[0] === "projects" && parts[1]) {
    return { page: "project", projectId: parts[1] };
  }
  return { page: "projects" };
}

export function viewToHash(view: View): string {
  if (view.page === "create") {
    if (view.fullWizard) {
      return view.wizardId ? `#/create/full/${view.wizardId}` : "#/create/full";
    }
    return view.wizardId ? `#/create/${view.wizardId}` : "#/create";
  }
  if (view.page === "tasks") {
    return view.jobId ? `#/tasks/${view.jobId}` : "#/tasks";
  }
  if (view.page === "budget") {
    return view.projectId ? `#/budget/${view.projectId}` : "#/budget";
  }
  if (view.page === "audit") {
    if (view.projectId && view.episodeId) return `#/audit/${view.projectId}/${view.episodeId}`;
    if (view.projectId) return `#/audit/${view.projectId}`;
    return "#/audit";
  }
  if (view.page === "project") {
    return `#/projects/${view.projectId}`;
  }
  if (view.page === "episode") {
    const base = `#/projects/${view.projectId}/episodes/${view.episodeId}`;
    if (view.identityId !== undefined) {
      return view.identityId ? `${base}/identity/${view.identityId}` : `${base}/identity`;
    }
    return view.shotId ? `${base}/shots/${view.shotId}` : base;
  }
  return "#/projects";
}

export function navigate(view: View): void {
  const next = viewToHash(view);
  if (window.location.hash !== next) {
    window.location.hash = next;
  }
}

export function shareUrl(view: View): string {
  const url = new URL(window.location.href);
  return `${url.origin}${url.pathname}${viewToHash(view)}`;
}

export function importHint(): string | null {
  const params = new URLSearchParams(window.location.search);
  if (!params.has("import")) return null;
  return params.get("import") || "1";
}

export function clearImportHint(): void {
  const url = new URL(window.location.href);
  if (!url.searchParams.has("import")) return;
  url.searchParams.delete("import");
  const search = url.searchParams.toString();
  window.history.replaceState(null, "", `${url.pathname}${search ? `?${search}` : ""}${url.hash}`);
}

export function sameView(a: View, b: View): boolean {
  return viewToHash(a) === viewToHash(b);
}
