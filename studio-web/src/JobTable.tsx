import type { Job } from "./types.ts";
import { navigate } from "./nav.ts";

export function formatElapsed(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return "—";
  const total = Math.round(ms / 1000);
  if (total < 60) return `${total}s`;
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  if (minutes < 60) return `${minutes}m ${seconds}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

export function JobTable({
  jobs,
  highlightId,
  onCancel,
  onRetry,
}: {
  jobs: Job[];
  highlightId?: string;
  onCancel: (job: Job) => void;
  onRetry: (job: Job) => void;
}) {
  if (jobs.length === 0) {
    return <p className="empty">No jobs yet. Enqueue batch-precheck or a stub hop-1 from an episode.</p>;
  }
  return (
    <ul className="job-list">
      {jobs.map((job) => (
        <li key={job.id} className={highlightId === job.id ? "is-on" : ""}>
          <div className="job-row">
            <div>
              <strong>
                {job.job_type} · <em className={`chip-status is-${job.status}`}>{job.status}</em>
              </strong>
              <span>
                adapter={job.adapter}
                {job.shot_sort_index !== null ? ` · shot #${job.shot_sort_index + 1}` : ""}
                {job.shot_take ? ` · take ${job.shot_take}` : ""}
                {" · "}
                {formatElapsed(job.elapsed_ms)}
                {typeof job.estimated_cost_units === "number"
                  ? ` · ${job.actual_cost_units ?? job.estimated_cost_units} ${job.cost_currency || "credits"}`
                  : ""}
              </span>
              <em>
                {job.project_name || "project"} / {job.episode_title || "episode"}
                {job.error ? ` — ${job.error}` : ""}
              </em>
            </div>
            <div className="toolbar">
              {job.status === "running" || job.status === "queued" ? (
                <div className="progress" aria-label={`progress ${job.progress}`}>
                  <span style={{ width: `${Math.max(4, job.progress)}%` }} />
                </div>
              ) : null}
              <button
                type="button"
                className="text-btn"
                onClick={() =>
                  navigate({
                    page: "episode",
                    projectId: job.project_id,
                    episodeId: job.episode_id,
                    shotId: job.shot_id || undefined,
                  })
                }
              >
                {job.shot_id ? "Jump to shot" : "Jump to episode"}
              </button>
              {job.status === "queued" || job.status === "running" ? (
                <button type="button" className="btn" onClick={() => onCancel(job)}>
                  Cancel
                </button>
              ) : null}
              {job.status === "failed" || job.status === "cancelled" ? (
                <button type="button" className="btn" onClick={() => onRetry(job)}>
                  Retry
                </button>
              ) : null}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
