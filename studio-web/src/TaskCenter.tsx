import { useCallback, useEffect, useState } from "react";
import { api } from "./api.ts";
import { JobTable } from "./JobTable.tsx";
import { navigate } from "./nav.ts";
import type { Job } from "./types.ts";

export function TaskCenter({
  jobId,
  onError,
  onNotice,
}: {
  jobId?: string;
  onError: (err: unknown) => void;
  onNotice: (msg: string) => void;
}) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [filter, setFilter] = useState("");

  const load = useCallback(async () => {
    try {
      setJobs(await api.jobs(filter ? { status: filter } : {}));
    } catch (err) {
      onError(err);
    }
  }, [filter, onError]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const dirty = jobs.some((job) => job.status === "queued" || job.status === "running");
    if (!dirty) return;
    const id = window.setInterval(() => void load(), 1500);
    return () => window.clearInterval(id);
  }, [jobs, load]);

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Task Center</h2>
        <p>
          In-process jobs. Default adapter=<code>stub</code> — fixture receipts, never a real H3/Qwen
          run. Cancel queued/running; retry failed/cancelled. Celery is the upgrade path, not this
          process.
        </p>
      </div>
      <div className="toolbar">
        <button type="button" className="text-btn" onClick={() => navigate({ page: "projects" })}>
          ← Projects
        </button>
        <select value={filter} onChange={(event) => setFilter(event.target.value)}>
          <option value="">all statuses</option>
          <option value="queued">queued</option>
          <option value="running">running</option>
          <option value="succeeded">succeeded</option>
          <option value="failed">failed</option>
          <option value="cancelled">cancelled</option>
        </select>
        <button type="button" className="btn" onClick={() => void load()}>
          Refresh
        </button>
      </div>
      <JobTable
        jobs={jobs}
        highlightId={jobId}
        onCancel={(job) => {
          void api
            .cancelJob(job.id)
            .then(() => {
              onNotice(`Cancelled ${job.job_type}`);
              return load();
            })
            .catch(onError);
        }}
        onRetry={(job) => {
          void api
            .retryJob(job.id)
            .then((next) => {
              onNotice(`Retried ${job.job_type} → ${next.status}`);
              return load();
            })
            .catch(onError);
        }}
      />
    </section>
  );
}
