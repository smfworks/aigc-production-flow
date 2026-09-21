import { useCallback, useEffect, useState } from "react";
import { api } from "./api.ts";
import { navigate } from "./nav.ts";
import type { BudgetDashboard } from "./types.ts";

function formatUnits(value: number, currency: string): string {
  const amount = Number.isFinite(value) ? value.toFixed(2) : "0.00";
  return `${amount} ${currency}`;
}

function mixLabel(mix: Record<string, number>): string {
  const parts = Object.entries(mix).map(([name, count]) => `${name}×${count}`);
  return parts.length ? parts.join(" · ") : "—";
}

export function BudgetDashboard({
  projectId,
  onError,
}: {
  projectId?: string;
  onError: (err: unknown) => void;
}) {
  const [data, setData] = useState<BudgetDashboard | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api.budget(projectId ? { project_id: projectId } : {}));
    } catch (err) {
      onError(err);
    }
  }, [onError, projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Budget</h2>
        <p>
          {data?.disclaimer ||
            "Operator-configured rate table. Opaque credits — not a cloud invoice."}
        </p>
      </div>
      <div className="toolbar">
        <button type="button" className="text-btn" onClick={() => navigate({ page: "projects" })}>
          ← Projects
        </button>
        <button type="button" className="btn" onClick={() => void load()}>
          Refresh
        </button>
      </div>
      {data ? (
        <>
          <div className="stat-grid">
            <div className="stat">
              <span>Spent</span>
              <strong>{formatUnits(data.spent_units, data.currency)}</strong>
            </div>
            <div className="stat">
              <span>Pending</span>
              <strong>{formatUnits(data.pending_units, data.currency)}</strong>
            </div>
            <div className="stat">
              <span>Cap</span>
              <strong>
                {data.cap_units == null ? "none" : formatUnits(data.cap_units, data.currency)}
              </strong>
            </div>
            <div className="stat">
              <span>Hard stop</span>
              <strong>{data.hard_stop ? "on" : "off"}</strong>
            </div>
            <div className="stat">
              <span>Jobs</span>
              <strong>{data.job_counts.total ?? 0}</strong>
            </div>
            <div className="stat">
              <span>Adapter mix</span>
              <strong>{mixLabel(data.adapter_mix)}</strong>
            </div>
          </div>
          {data.usd_estimate != null ? (
            <p className="hint">
              USD estimate {data.usd_estimate.toFixed(2)} at {data.usd_per_unit} / unit. Estimate
              only — no bill was paid.
            </p>
          ) : (
            <p className="hint">
              Rates:{" "}
              {Object.entries(data.rates)
                .map(([name, rate]) => `${name}=${rate}`)
                .join(" · ")}
            </p>
          )}
          {data.projects.length === 0 ? (
            <p className="empty">No projects yet.</p>
          ) : (
            <ul className="card-list">
              {data.projects.map((project) => (
                <li key={project.project_id}>
                  <div className={`budget-card ${project.over_cap ? "is-over" : ""}`}>
                    <div className="budget-card-head">
                      <strong>{project.name}</strong>
                      <span>
                        still={project.still_adapter} · clip={project.clip_adapter}
                        {project.hard_stop ? " · hard stop" : ""}
                        {project.over_cap ? " · over cap" : ""}
                      </span>
                    </div>
                    <p>
                      {formatUnits(project.spent_units, data.currency)} spent
                      {project.pending_units
                        ? ` · ${formatUnits(project.pending_units, data.currency)} pending`
                        : ""}
                      {project.cap_units != null
                        ? ` · cap ${formatUnits(project.cap_units, data.currency)}`
                        : ""}{" "}
                      · {project.job_count} jobs · {mixLabel(project.adapter_mix)}
                    </p>
                    <div className="toolbar">
                      <button
                        type="button"
                        className="text-btn"
                        onClick={() => navigate({ page: "project", projectId: project.project_id })}
                      >
                        Open project
                      </button>
                      <button
                        type="button"
                        className="text-btn"
                        onClick={() => navigate({ page: "audit", projectId: project.project_id })}
                      >
                        Audit
                      </button>
                    </div>
                    {project.episodes.length ? (
                      <ul className="history">
                        {project.episodes.map((episode) => (
                          <li key={episode.episode_id}>
                            Ch. {episode.chapter} · {episode.title} —{" "}
                            {formatUnits(episode.spent_units, data.currency)} · {episode.job_count}{" "}
                            jobs
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      ) : (
        <p className="empty">Loading budget…</p>
      )}
    </section>
  );
}
