import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { api, downloadExport, downloadMedia, downloadPack, getToken, getUserName, setToken, setUserName } from "./api.ts";
import type {
  AdapterCatalog,
  AdapterHealth,
  Comment,
  Episode,
  Job,
  MediaAsset,
  Meta,
  PreviewDesk,
  Project,
  RetentionPreview,
  Review,
  ReviewStateName,
  Shot,
  StudioUser,
  VerticalTemplate,
} from "./types.ts";
import { REVIEW_COPY, REVIEW_STATES } from "./types.ts";
import { ShotBoard } from "./ShotBoard.tsx";
import { TaskCenter } from "./TaskCenter.tsx";
import { PreviewDesk as PreviewDeskPanel } from "./PreviewDesk.tsx";
import { JobTable } from "./JobTable.tsx";
import { BudgetDashboard } from "./BudgetDashboard.tsx";
import { AuditLog } from "./AuditLog.tsx";
import { MembersPanel } from "./MembersPanel.tsx";
import { PresenceBar } from "./PresenceBar.tsx";
import { AdapterStrip } from "./AdapterStrip.tsx";
import { navigate, parseHash, type View } from "./nav.ts";

function can(user: StudioUser | null, perm: string): boolean {
  return Boolean(user?.permissions?.includes(perm));
}

function formatWhen(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString();
}

export default function App() {
  const [view, setView] = useState<View>(() => parseHash());
  const [token, setTokenState] = useState(getToken);
  const [userName, setUserNameState] = useState(getUserName);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [me, setMe] = useState<StudioUser | null>(null);
  const [adapterHealth, setAdapterHealth] = useState<AdapterHealth[]>([]);

  const packBuilderUrl =
    meta?.pack_builder_url || import.meta.env.VITE_PACK_BUILDER_URL || "http://localhost:5173";

  const showError = useCallback((err: unknown) => {
    setError(err instanceof Error ? err.message : String(err));
  }, []);

  useEffect(() => {
    api.meta().then(setMeta).catch(() => setMeta(null));
    api.me().then(setMe).catch(() => setMe(null));
    api.adapterHealth().then(setAdapterHealth).catch(() => setAdapterHealth([]));
  }, [token, userName]);

  useEffect(() => {
    const onHash = () => setView(parseHash());
    window.addEventListener("hashchange", onHash);
    if (!window.location.hash) navigate({ page: "projects" });
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (!notice) return;
    const id = window.setTimeout(() => setNotice(null), 3200);
    return () => window.clearTimeout(id);
  }, [notice]);

  return (
    <div className="page">
      <div className="ambient" aria-hidden="true" />
      <header className="mast">
        <div className="mast-brand">
          <div className="mark" aria-hidden="true" />
          <div>
            <p className="eyebrow">SMF Works · Studio spine · Phase 5</p>
            <h1>AIGC Studio</h1>
          </div>
        </div>
        <p className="lede">
          Projects, hop-1 preview desk, members, presence, and adapter health around the pack zip.
          Jobs run in-process with adapter=<code>stub</code> unless a live hook is set. Budget
          units are operator credits — not a cloud bill. Media is local disk unless S3 is
          configured. Pack zip remains the contract.
        </p>
        <nav className="mast-nav" aria-label="Studio">
          <button
            type="button"
            className={view.page === "projects" || view.page === "project" || view.page === "episode" ? "btn btn-go" : "btn"}
            onClick={() => navigate({ page: "projects" })}
          >
            Projects
          </button>
          <button
            type="button"
            className={view.page === "tasks" ? "btn btn-go" : "btn"}
            onClick={() => navigate({ page: "tasks" })}
          >
            Task Center
          </button>
          <button
            type="button"
            className={view.page === "budget" ? "btn btn-go" : "btn"}
            onClick={() => navigate({ page: "budget" })}
          >
            Budget
          </button>
          <button
            type="button"
            className={view.page === "audit" ? "btn btn-go" : "btn"}
            onClick={() => navigate({ page: "audit" })}
          >
            Audit
          </button>
        </nav>
        <div className="auth-row">
          <label>
            Local-dev token
            <input
              value={token}
              onChange={(event) => {
                setTokenState(event.target.value);
                setToken(event.target.value);
              }}
              autoComplete="off"
            />
          </label>
          <label>
            Local user
            <input
              value={userName}
              placeholder={meta?.default_user || "local-dev"}
              onChange={(event) => {
                setUserNameState(event.target.value);
                setUserName(event.target.value);
              }}
              autoComplete="username"
            />
          </label>
          {me?.role ? <em className={`role-chip is-${me.role}`}>{me.role}</em> : <em className="role-chip">not a member</em>}
          <span className="hint">
            Auth {meta?.auth_mode ?? "local"}. Roles are app-level. SSO/OIDC is not implemented —
            docs/AUTH.md.
          </span>
          {meta?.still_adapter ? (
            <span className="hint">
              still={meta.still_adapter} · clip={meta.clip_adapter} · worker={meta.job_worker} ·
              media={meta.media_backend || "local"}
            </span>
          ) : null}
        </div>
        <AdapterStrip
          stillDefault={meta?.still_adapter}
          clipDefault={meta?.clip_adapter}
          onError={showError}
        />
      </header>

      {error ? (
        <p className="banner banner-bad" role="alert">
          {error}
          <button type="button" className="text-btn" onClick={() => setError(null)}>
            dismiss
          </button>
        </p>
      ) : null}
      {notice ? (
        <p className="banner banner-ok" role="status">
          {notice}
        </p>
      ) : null}

      {view.page === "projects" ? (
        <ProjectList
          me={me}
          onOpen={(projectId) => navigate({ page: "project", projectId })}
          onError={showError}
          onNotice={setNotice}
        />
      ) : null}
      {view.page === "project" ? (
        <ProjectView
          projectId={view.projectId}
          me={me}
          onBack={() => navigate({ page: "projects" })}
          onOpenEpisode={(episodeId) =>
            navigate({ page: "episode", projectId: view.projectId, episodeId })
          }
          onError={showError}
          onNotice={setNotice}
        />
      ) : null}
      {view.page === "episode" ? (
        <EpisodeView
          projectId={view.projectId}
          episodeId={view.episodeId}
          shotId={view.shotId}
          packBuilderUrl={packBuilderUrl}
          me={me}
          adapterHealth={adapterHealth}
          onBack={() => navigate({ page: "project", projectId: view.projectId })}
          onError={showError}
          onNotice={setNotice}
        />
      ) : null}
      {view.page === "tasks" ? (
        <TaskCenter jobId={view.jobId} onError={showError} onNotice={setNotice} />
      ) : null}
      {view.page === "budget" ? (
        <BudgetDashboard projectId={view.projectId} onError={showError} />
      ) : null}
      {view.page === "audit" ? (
        <AuditLog projectId={view.projectId} episodeId={view.episodeId} onError={showError} />
      ) : null}
    </div>
  );
}

function ProjectList({
  me,
  onOpen,
  onError,
  onNotice,
}: {
  me: StudioUser | null;
  onOpen: (id: string) => void;
  onError: (err: unknown) => void;
  onNotice: (msg: string) => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [templates, setTemplates] = useState<VerticalTemplate[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [nextProjects, nextTemplates] = await Promise.all([
        api.projects(),
        api.templates().catch(() => [] as VerticalTemplate[]),
      ]);
      setProjects(nextProjects);
      setTemplates(nextTemplates);
    } catch (err) {
      onError(err);
    }
  }, [onError]);

  useEffect(() => {
    void load();
  }, [load]);

  async function create(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() && !templateId) return;
    setBusy(true);
    try {
      if (templateId) {
        const created = await api.createFromTemplate(templateId, {
          name: name.trim() || undefined,
          description: description.trim() || undefined,
        });
        setName("");
        setDescription("");
        setTemplateId("");
        onNotice(
          `Created ${created.project.name} from ${templateId} — gates ${
            created.gates_green ? "green" : "red (fill the pack; no fake generate)"
          }`,
        );
        await load();
        onOpen(created.project.id);
      } else {
        const project = await api.createProject({ name: name.trim(), description: description.trim() });
        setName("");
        setDescription("");
        onNotice(`Created ${project.name}`);
        await load();
        onOpen(project.id);
      }
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Projects</h2>
        <p>One title. Episodes are chapters. Pack zip is the collaboration object. New from template seeds an empty pack — gates stay red.</p>
      </div>
      <form className="create-row" onSubmit={create}>
        <input
          placeholder="Project name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required={!templateId}
        />
        <input
          placeholder="Log line / description (optional)"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
        <select value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
          <option value="">Blank project</option>
          {templates.map((row) => (
            <option key={row.id} value={row.id}>
              New from template: {row.name}
            </option>
          ))}
        </select>
        <button type="submit" className="btn btn-go" disabled={busy || !can(me, "mutate")}>
          {templateId ? "New from template" : "New project"}
        </button>
      </form>
      {projects.length === 0 ? (
        <p className="empty">No projects yet. Create one, then import a pack zip.</p>
      ) : (
        <ul className="card-list">
          {projects.map((project) => (
            <li key={project.id}>
              <button type="button" className="card-btn" onClick={() => onOpen(project.id)}>
                <strong>{project.name}</strong>
                <span>
                  {project.episode_count} episode{project.episode_count === 1 ? "" : "s"} ·{" "}
                  {project.slug}
                </span>
                {project.description ? <em>{project.description}</em> : null}
              </button>
            </li>
          ))}
        </ul>
      )}
      <MembersPanel me={me} onError={onError} onNotice={onNotice} />
    </section>
  );
}

function ProjectView({
  projectId,
  me,
  onBack,
  onOpenEpisode,
  onError,
  onNotice,
}: {
  projectId: string;
  me: StudioUser | null;
  onBack: () => void;
  onOpenEpisode: (id: string) => void;
  onError: (err: unknown) => void;
  onNotice: (msg: string) => void;
}) {
  const [project, setProject] = useState<Project | null>(null);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [adapters, setAdapters] = useState<AdapterCatalog | null>(null);
  const [title, setTitle] = useState("");
  const [synopsis, setSynopsis] = useState("");
  const [stillAdapter, setStillAdapter] = useState("stub");
  const [clipAdapter, setClipAdapter] = useState("stub");
  const [cap, setCap] = useState("");
  const [hardStop, setHardStop] = useState(false);
  const [retentionDays, setRetentionDays] = useState("");
  const [retention, setRetention] = useState<RetentionPreview | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [nextProject, nextEpisodes, nextAdapters, nextRetention] = await Promise.all([
        api.project(projectId),
        api.episodes(projectId),
        api.adapters().catch(() => null),
        api.retentionPreview({ project_id: projectId }).catch(() => null),
      ]);
      setProject(nextProject);
      setEpisodes(nextEpisodes);
      setAdapters(nextAdapters);
      setStillAdapter(nextProject.still_adapter || "stub");
      setClipAdapter(nextProject.clip_adapter || "stub");
      setCap(nextProject.budget_cap_units == null ? "" : String(nextProject.budget_cap_units));
      setHardStop(Boolean(nextProject.budget_hard_stop));
      setRetentionDays(nextProject.retention_days == null ? "" : String(nextProject.retention_days));
      setRetention(nextRetention);
    } catch (err) {
      onError(err);
    }
  }, [onError, projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function create(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try {
      const episode = await api.createEpisode(projectId, {
        title: title.trim(),
        synopsis: synopsis.trim(),
      });
      setTitle("");
      setSynopsis("");
      onNotice(`Created ${episode.title}`);
      await load();
      onOpenEpisode(episode.id);
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  }

  async function saveSettings(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const capValue = cap.trim() === "" ? null : Number(cap);
      const daysValue = retentionDays.trim() === "" ? null : Number(retentionDays);
      await api.updateProject(projectId, {
        still_adapter: stillAdapter,
        clip_adapter: clipAdapter,
        budget_hard_stop: hardStop,
        budget_cap_units: capValue,
        clear_budget_cap: capValue == null,
        retention_days: daysValue,
        clear_retention_days: daysValue == null,
      });
      onNotice("Saved adapter defaults, budget cap, and retention");
      await load();
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  }

  async function runRetention(apply: boolean) {
    try {
      const result = await api.retentionApply({
        project_id: projectId,
        dry_run: !apply,
        confirm: apply ? "expire" : "",
      });
      setRetention(result);
      onNotice(
        apply
          ? `Expired ${result.deleted_count ?? 0} stub/temp media. Pack revisions kept.`
          : `Dry-run: ${result.candidates.length} ephemeral files older than ${result.retention_days} days.`,
      );
    } catch (err) {
      onError(err);
    }
  }

  const stillSlots = adapters?.adapters.filter((row) => row.kinds.includes("still")) ?? [];
  const clipSlots = adapters?.adapters.filter((row) => row.kinds.includes("clip")) ?? [];

  return (
    <section className="panel">
      <button type="button" className="text-btn" onClick={onBack}>
        ← Projects
      </button>
      <div className="panel-head">
        <h2>{project?.name ?? "Project"}</h2>
        <p>{project?.description || "Episodes are chapters. Review state lives on each episode."}</p>
      </div>
      <form className="create-row" onSubmit={saveSettings}>
        <select value={stillAdapter} onChange={(event) => setStillAdapter(event.target.value)}>
          {(stillSlots.length ? stillSlots : [{ id: "stub", label: "stub" }]).map((row) => (
            <option key={row.id} value={row.id}>
              still: {row.label || row.id}
            </option>
          ))}
        </select>
        <select value={clipAdapter} onChange={(event) => setClipAdapter(event.target.value)}>
          {(clipSlots.length ? clipSlots : [{ id: "stub", label: "stub" }]).map((row) => (
            <option key={row.id} value={row.id}>
              clip: {row.label || row.id}
            </option>
          ))}
        </select>
        <input
          placeholder="Budget cap (credits, blank = none)"
          value={cap}
          onChange={(event) => setCap(event.target.value)}
          inputMode="decimal"
          disabled={!can(me, "budget")}
        />
        <label className="check">
          <input
            type="checkbox"
            checked={hardStop}
            onChange={(event) => setHardStop(event.target.checked)}
            disabled={!can(me, "budget")}
          />
          Hard stop
        </label>
        <input
          placeholder="Retention days (blank = env)"
          value={retentionDays}
          onChange={(event) => setRetentionDays(event.target.value)}
          inputMode="numeric"
          disabled={!can(me, "retention")}
        />
        <button type="submit" className="btn" disabled={busy || !can(me, "mutate")}>
          Save settings
        </button>
        <button type="button" className="btn" onClick={() => navigate({ page: "budget", projectId })}>
          Budget
        </button>
        <button type="button" className="btn" onClick={() => navigate({ page: "audit", projectId })}>
          Audit
        </button>
      </form>
      <p className="hint">
        Live slots (comfy-h3, comfy-qwen, webhook, cli) fall back to stub if the hook is unset.
        Budget units are operator credits — not a cloud bill. Retention expires stub/temp media only;
        pack revisions stay.
        {retention
          ? ` Dry-run candidates: ${retention.candidates.length} / revisions kept: ${retention.revision_count_kept}.`
          : ""}
      </p>
      <div className="toolbar">
        <button type="button" className="btn" onClick={() => void runRetention(false)}>
          Retention dry-run
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => void runRetention(true)}
          disabled={!can(me, "retention")}
        >
          Apply retention
        </button>
      </div>
      <form className="create-row" onSubmit={create}>
        <input
          placeholder="Episode / chapter title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          required
        />
        <input
          placeholder="Synopsis (optional)"
          value={synopsis}
          onChange={(event) => setSynopsis(event.target.value)}
        />
        <button type="submit" className="btn btn-go" disabled={busy || !can(me, "mutate")}>
          New episode
        </button>
      </form>
      {episodes.length === 0 ? (
        <p className="empty">No episodes. Add a chapter, then import a pack zip.</p>
      ) : (
        <ul className="card-list">
          {episodes.map((episode) => (
            <li key={episode.id}>
              <button type="button" className="card-btn" onClick={() => onOpenEpisode(episode.id)}>
                <strong>
                  Ch. {episode.chapter} · {episode.title}
                </strong>
                <span>
                  {episode.review_state}
                  {episode.latest_revision
                    ? episode.latest_revision.all_gates_green
                    ? " · gates green"
                    : " · gates red"
                    : " · no pack yet"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function EpisodeView({
  projectId,
  episodeId,
  shotId,
  packBuilderUrl,
  me,
  adapterHealth,
  onBack,
  onError,
  onNotice,
}: {
  projectId: string;
  episodeId: string;
  shotId?: string;
  packBuilderUrl: string;
  me: StudioUser | null;
  adapterHealth: AdapterHealth[];
  onBack: () => void;
  onError: (err: unknown) => void;
  onNotice: (msg: string) => void;
}) {
  const [episode, setEpisode] = useState<Episode | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [media, setMedia] = useState<MediaAsset[]>([]);
  const [shots, setShots] = useState<Shot[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [desk, setDesk] = useState<PreviewDesk | null>(null);
  const [selectedShotId, setSelectedShotId] = useState<string | null>(shotId ?? null);
  const [commentBody, setCommentBody] = useState("");
  const [note, setNote] = useState("");
  const [kind, setKind] = useState("plate");
  const [entityType, setEntityType] = useState("");
  const [entity, setEntity] = useState("");
  const [mediaNotes, setMediaNotes] = useState("");
  const [showBuilder, setShowBuilder] = useState(false);
  const packRef = useRef<HTMLInputElement>(null);
  const mediaRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [nextEpisode, nextReview, nextComments, nextMedia, nextShots, nextJobs, nextDesk] =
        await Promise.all([
          api.episode(episodeId),
          api.review(episodeId),
          api.comments(episodeId),
          api.media(episodeId),
          api.shots(episodeId).catch(() => [] as Shot[]),
          api.episodeJobs(episodeId).catch(() => [] as Job[]),
          api.previewDesk(episodeId).catch(() => null),
        ]);
      setEpisode(nextEpisode);
      setReview(nextReview);
      setComments(nextComments);
      setMedia(nextMedia);
      setShots(nextShots);
      setJobs(nextJobs);
      setDesk(nextDesk);
      setSelectedShotId((current) => {
        if (shotId) return shotId;
        if (current && nextShots.some((shot) => shot.id === current)) return current;
        return nextShots.find((shot) => shot.hop1_required)?.id ?? nextShots[0]?.id ?? null;
      });
    } catch (err) {
      onError(err);
    }
  }, [episodeId, onError, shotId]);

  useEffect(() => {
    void load();
  }, [load]);

  const gates = review?.latest_gates?.gates ?? [];
  const allGreen = review?.latest_gates?.all_green === true;
  const generateBlocked = useMemo(
    () => !allGreen || desk?.generate_ok_ready !== true,
    [allGreen, desk],
  );

  useEffect(() => {
    const dirty = jobs.some((job) => job.status === "queued" || job.status === "running");
    if (!dirty) return;
    const id = window.setInterval(() => {
      void api.episodeJobs(episodeId).then(setJobs).catch(() => undefined);
    }, 1500);
    return () => window.clearInterval(id);
  }, [jobs, episodeId]);

  function selectShot(nextId: string) {
    setSelectedShotId(nextId);
    navigate({ page: "episode", projectId, episodeId, shotId: nextId });
  }

  async function enqueue(jobType: string, withShot = false) {
    try {
      const job = await api.enqueueJob({
        episode_id: episodeId,
        shot_id: withShot ? selectedShotId || undefined : undefined,
        job_type: jobType,
      });
      onNotice(`${job.job_type} → ${job.status} (adapter=${job.adapter})`);
      await load();
    } catch (err) {
      onError(err);
    }
  }

  async function changeState(state: ReviewStateName) {
    try {
      const next = await api.setReview(episodeId, state, note.trim());
      setReview(next);
      setEpisode((current) => (current ? { ...current, review_state: next.current } : current));
      setNote("");
      onNotice(`Review → ${state}`);
    } catch (err) {
      onError(err);
    }
  }

  async function importPack(file: File) {
    try {
      const result = await api.importPack(episodeId, file);
      onNotice(
        result.all_gates_green
          ? `Imported ${result.filename} — all gates green`
          : `Imported ${result.filename} — gates still red (generate-ok blocked)`,
      );
      await load();
    } catch (err) {
      onError(err);
    }
  }

  async function exportPack() {
    try {
      await downloadPack(episodeId);
      onNotice("Exported latest pack zip");
    } catch (err) {
      onError(err);
    }
  }

  async function addComment(event: FormEvent) {
    event.preventDefault();
    if (!commentBody.trim()) return;
    try {
      await api.addComment(episodeId, commentBody.trim());
      setCommentBody("");
      await load();
    } catch (err) {
      onError(err);
    }
  }

  async function uploadMedia(file: File) {
    try {
      await api.uploadMedia(episodeId, file, kind, entity.trim(), mediaNotes.trim(), entityType);
      setEntity("");
      setMediaNotes("");
      onNotice(`Uploaded ${file.name} (${kind})`);
      await load();
    } catch (err) {
      onError(err);
    }
  }

  return (
    <div className="episode-layout">
      <button type="button" className="text-btn" onClick={onBack}>
        ← Episodes
      </button>
      <div className="panel-head">
        <h2>{episode?.title ?? "Episode"}</h2>
        <p>
          Chapter {episode?.chapter ?? "—"}.{" "}
          {episode?.synopsis || "Import a pack zip from the builder. generate-ok stays locked until every gate is green."}
        </p>
      </div>
      <PresenceBar episodeId={episodeId} shotId={selectedShotId} onError={onError} />

      <section className="panel">
        <div className="toolbar">
          <button
            type="button"
            className="btn"
            onClick={() => packRef.current?.click()}
            disabled={!can(me, "pack")}
          >
            Import pack zip
          </button>
          <button type="button" className="btn" onClick={() => void exportPack()}>
            Export pack zip
          </button>
          <button
            type="button"
            className="btn"
            onClick={() =>
              void downloadExport(episodeId, "edl")
                .then(() => onNotice("Exported CMX3600-ish EDL (metadata only)"))
                .catch(onError)
            }
          >
            Export EDL
          </button>
          <button
            type="button"
            className="btn"
            onClick={() =>
              void downloadExport(episodeId, "playlist")
                .then(() => onNotice("Exported shot playlist JSON"))
                .catch(onError)
            }
          >
            Export shot playlist
          </button>
          <button
            type="button"
            className="btn"
            onClick={() =>
              void downloadExport(episodeId, "fcpxml")
                .then(() => onNotice("Exported FCP XML lite"))
                .catch(onError)
            }
          >
            Export FCP XML
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => navigate({ page: "audit", projectId, episodeId })}
          >
            Audit
          </button>
          <a className="btn" href={packBuilderUrl} target="_blank" rel="noreferrer">
            Open pack builder
          </a>
          <button type="button" className="btn" onClick={() => setShowBuilder((value) => !value)}>
            {showBuilder ? "Hide builder iframe" : "Show builder iframe"}
          </button>
          <input
            ref={packRef}
            type="file"
            accept=".zip,application/zip"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void importPack(file);
              event.target.value = "";
            }}
          />
        </div>
        {episode?.latest_revision ? (
          <p className="hint">
            Latest: {episode.latest_revision.filename}
            {episode.latest_revision.all_gates_green ? " · gates green" : " · not generate-ready"}
          </p>
        ) : (
          <p className="hint">No revision yet. Export from the builder at {packBuilderUrl}, then import here.</p>
        )}
        {showBuilder ? (
          <iframe
            className="builder-frame"
            title="Pack builder"
            src={`${packBuilderUrl}?step=edit`}
          />
        ) : null}
      </section>

      <section className="panel">
        <h3>Gates</h3>
        {gates.length === 0 ? (
          <p className="empty">Import a pack to snapshot the gates.</p>
        ) : (
          <ol className="gates">
            {gates.map((gate) => (
              <li key={gate.id} className={gate.ok ? "gate-ok" : "gate-bad"}>
                <span className="gate-n">{gate.n}</span>
                <span>
                  <strong>{gate.label}</strong>
                  <em>{gate.detail}</em>
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <ShotBoard
        shots={shots}
        media={media}
        packBuilderUrl={packBuilderUrl}
        selectedShotId={selectedShotId}
        onSelectShot={selectShot}
        episodeId={episodeId}
        canComment={can(me, "comment")}
        canMutate={can(me, "mutate")}
        onError={onError}
        onNotice={onNotice}
        onExtract={() => {
          void api
            .extractCandidates(episodeId)
            .then((next) => {
              setShots(next);
              onNotice("Candidates extracted — confirm by hand. generate-ok is unchanged.");
            })
            .catch(onError);
        }}
        onReadiness={(shotId, readiness) => {
          void api
            .setShotReadiness(episodeId, shotId, readiness)
            .then((next) => {
              setShots((current) => current.map((shot) => (shot.id === next.id ? next : shot)));
              onNotice(`Shot → ${readiness} (prepared, not generating)`);
            })
            .catch(onError);
        }}
        onCandidate={(shotId, candidateId, body) => {
          void api
            .updateCandidate(episodeId, shotId, candidateId, body)
            .then((next) => {
              setShots((current) => current.map((shot) => (shot.id === next.id ? next : shot)));
            })
            .catch(onError);
        }}
        onAddCandidate={(shotId, body) => {
          void api
            .addCandidate(episodeId, shotId, body)
            .then((next) => {
              setShots((current) => current.map((shot) => (shot.id === next.id ? next : shot)));
            })
            .catch(onError);
        }}
      />

      <PreviewDeskPanel
        episodeId={episodeId}
        desk={desk}
        shots={shots}
        media={media}
        selectedShotId={selectedShotId}
        onSelectShot={selectShot}
        onError={onError}
        onNotice={onNotice}
        onChanged={() => void load()}
      />

      <section className="panel">
        <h3>Jobs</h3>
        <p className="hint">
          Path: green pack → batch-precheck → stub hop-1 → attach preview+receipt → preview-watched.
          Adapter label is honest. This is not Celery.
          {adapterHealth.some((row) => row.live && !row.ok)
            ? " Live adapters in the strip that are down will 409 on enqueue — use stub or fix the hook."
            : ""}
          {!can(me, "jobs") ? " Viewers cannot enqueue. Promote to editor." : ""}
        </p>
        <div className="toolbar">
          <button type="button" className="btn" disabled={!can(me, "jobs")} onClick={() => void enqueue("batch-precheck")}>
            Enqueue batch-precheck
          </button>
          <button type="button" className="btn" disabled={!can(me, "jobs")} onClick={() => void enqueue("still-sheet")}>
            Stub still-sheet
          </button>
          <button type="button" className="btn" disabled={!can(me, "jobs")} onClick={() => void enqueue("still-plate")}>
            Stub still-plate
          </button>
          <button type="button" className="btn" disabled={!can(me, "jobs")} onClick={() => void enqueue("clip-hop1", true)}>
            Stub hop-1
          </button>
          <button type="button" className="btn" disabled={!can(me, "jobs")} onClick={() => void enqueue("clip-extend", true)}>
            Stub clip-extend
          </button>
          <button type="button" className="btn" onClick={() => navigate({ page: "tasks" })}>
            Open Task Center
          </button>
        </div>
        <JobTable
          jobs={jobs}
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
                onNotice(`Retried → ${next.status}`);
                return load();
              })
              .catch(onError);
          }}
        />
      </section>

      <section className="panel">
        <h3>Review state</h3>
        <p className="hint">
          Current: <strong>{review?.current ?? "draft"}</strong>
          {generateBlocked
            ? " — generate-ok refused while any gate is red or a required hop-1 lacks preview-watched + receipt."
            : ""}
        </p>
        <div className="states">
          {REVIEW_STATES.map((state) => (
            <button
              key={state}
              type="button"
              className={review?.current === state ? "btn btn-go" : "btn"}
              disabled={(state === "generate-ok" && generateBlocked) || !can(me, "review")}
              title={REVIEW_COPY[state]}
              onClick={() => void changeState(state)}
            >
              {state}
            </button>
          ))}
        </div>
        <label className="note-field">
          Note (optional)
          <input value={note} onChange={(event) => setNote(event.target.value)} />
        </label>
        {review?.history.length ? (
          <ul className="history">
            {review.history.map((event) => (
              <li key={event.id}>
                <strong>{event.state}</strong> · {event.set_by} · {formatWhen(event.created_at)}
                {event.note ? ` — ${event.note}` : ""}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="split">
        <div className="panel">
          <h3>Comments</h3>
          <form className="stack" onSubmit={addComment}>
            <textarea
              value={commentBody}
              onChange={(event) => setCommentBody(event.target.value)}
              placeholder="Writer / art / editor notes. Pack zip is still the contract."
              rows={3}
            />
            <button type="submit" className="btn btn-go" disabled={!can(me, "comment")}>
              Add comment
            </button>
          </form>
          <ul className="thread">
            {comments
              .filter((comment) => !comment.shot_id)
              .map((comment) => (
              <li key={comment.id}>
                <strong>{comment.author}</strong>
                <span>{formatWhen(comment.created_at)}</span>
                <p>{comment.body}</p>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h3>Media library</h3>
          <p className="hint">
            Sheets, plates, costumes, and hop-1 preview receipts. Store: {me ? "org media adapter" : "local"}.
            Engine MP4s stay gitignored. Never commit them. S3/MinIO is not live unless configured.
          </p>
          <div className="create-row">
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              <option value="sheet">sheet</option>
              <option value="plate">plate</option>
              <option value="costume">costume</option>
              <option value="preview">preview</option>
              <option value="other">other</option>
            </select>
            <select value={entityType} onChange={(event) => setEntityType(event.target.value)}>
              <option value="">entity type</option>
              <option value="character">character</option>
              <option value="prop">prop</option>
              <option value="scene">scene</option>
              <option value="costume">costume</option>
            </select>
            <input
              placeholder="Entity / take label"
              value={entity}
              onChange={(event) => setEntity(event.target.value)}
            />
            <input
              placeholder="Notes"
              value={mediaNotes}
              onChange={(event) => setMediaNotes(event.target.value)}
            />
            <button type="button" className="btn" disabled={!can(me, "media")} onClick={() => mediaRef.current?.click()}>
              Upload
            </button>
            <input
              ref={mediaRef}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/tiff,.png,.jpg,.jpeg,.webp,.md,.txt,.json,.mp4,.webm"
              hidden
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void uploadMedia(file);
                event.target.value = "";
              }}
            />
          </div>
          {media.length === 0 ? (
            <p className="empty">No sheets or plates uploaded.</p>
          ) : (
            <ul className="media-list">
              {media.map((asset) => (
                <li key={asset.id}>
                  <button
                    type="button"
                    className="text-btn"
                    onClick={() => void downloadMedia(asset.id, asset.original_name).catch(onError)}
                  >
                    {asset.original_name}
                  </button>
                  <span>
                    {asset.kind}
                    {asset.entity_type ? ` · ${asset.entity_type}` : ""}
                    {asset.entity_label ? ` · ${asset.entity_label}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
      <p className="hint">
        Project {projectId}. Builder remains the four-stage walk. generate-ok needs every gate green
        and hop-1 receipts watched.
      </p>
    </div>
  );
}
