import { useCallback, useEffect, useState } from "react";
import { api } from "./api.ts";
import { navigate } from "./nav.ts";
import type { AuditEvent } from "./types.ts";

function formatWhen(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString();
}

export function AuditLog({
  projectId,
  episodeId,
  onError,
}: {
  projectId?: string;
  episodeId?: string;
  onError: (err: unknown) => void;
}) {
  const [rows, setRows] = useState<AuditEvent[]>([]);
  const [action, setAction] = useState("");
  const [projectFilter, setProjectFilter] = useState(projectId || "");

  const load = useCallback(async () => {
    try {
      setRows(
        await api.audit({
          project_id: projectFilter || undefined,
          episode_id: episodeId,
          action: action || undefined,
        }),
      );
    } catch (err) {
      onError(err);
    }
  }, [action, episodeId, onError, projectFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Audit log</h2>
        <p>
          Who / what / when for review, jobs, pack import/export, and media upload. Local-dev user
          ids are fine. Not a SIEM.
        </p>
      </div>
      <div className="toolbar">
        <button type="button" className="text-btn" onClick={() => navigate({ page: "projects" })}>
          ← Projects
        </button>
        <input
          placeholder="Filter project id"
          value={projectFilter}
          onChange={(event) => setProjectFilter(event.target.value)}
        />
        <select value={action} onChange={(event) => setAction(event.target.value)}>
          <option value="">all actions</option>
          <option value="review.set">review.set</option>
          <option value="job.enqueue">job.enqueue</option>
          <option value="job.cancel">job.cancel</option>
          <option value="pack.import">pack.import</option>
          <option value="pack.export">pack.export</option>
          <option value="media.upload">media.upload</option>
          <option value="project.create">project.create</option>
          <option value="retention.apply">retention.apply</option>
        </select>
        <button type="button" className="btn" onClick={() => void load()}>
          Refresh
        </button>
      </div>
      {rows.length === 0 ? (
        <p className="empty">No audit rows for this filter.</p>
      ) : (
        <ul className="audit-list">
          {rows.map((row) => (
            <li key={row.id}>
              <strong>{row.action}</strong>
              <span>
                {row.actor} · {formatWhen(row.created_at)}
              </span>
              <em>
                {row.project_name || row.project_id || "—"}
                {row.episode_title ? ` / ${row.episode_title}` : ""}
              </em>
              {row.project_id ? (
                <button
                  type="button"
                  className="text-btn"
                  onClick={() =>
                    row.episode_id
                      ? navigate({
                          page: "episode",
                          projectId: row.project_id as string,
                          episodeId: row.episode_id,
                        })
                      : navigate({ page: "project", projectId: row.project_id as string })
                  }
                >
                  Open
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
