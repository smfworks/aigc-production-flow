export type View =
  | { page: "projects" }
  | { page: "project"; projectId: string }
  | { page: "episode"; projectId: string; episodeId: string; shotId?: string }
  | { page: "tasks"; jobId?: string }
  | { page: "budget"; projectId?: string }
  | { page: "audit"; projectId?: string; episodeId?: string };

export function parseHash(hash = window.location.hash): View {
  const raw = hash.replace(/^#/, "");
  const parts = raw.split("/").filter(Boolean);
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
    };
  }
  if (parts[0] === "projects" && parts[1]) {
    return { page: "project", projectId: parts[1] };
  }
  return { page: "projects" };
}

export function viewToHash(view: View): string {
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

export function sameView(a: View, b: View): boolean {
  return viewToHash(a) === viewToHash(b);
}
