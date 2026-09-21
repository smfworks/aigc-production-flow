import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { api, downloadExport, downloadMedia, downloadPack, downloadBackup, getOrgId, getToken, getUserName, setOrgId, setToken, setUserName } from "./api.ts";
import type {
  AdapterCatalog,
  AdapterHealth,
  Comment,
  Episode,
  IdentityStore as IdentityStoreData,
  Job,
  MediaAsset,
  Meta,
  PackDiff,
  PreviewDesk,
  Project,
  RetentionPreview,
  Review,
  ReviewStateName,
  Shot,
  StudioOrg,
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
import { OrgSwitcher } from "./OrgSwitcher.tsx";
import { NotificationBell } from "./NotificationBell.tsx";
import { ContinuityPanel } from "./ContinuityPanel.tsx";
import { IdentityStore } from "./IdentityStore.tsx";
import { PlaylistScrubber } from "./PlaylistScrubber.tsx";
import { PackDiffPanel } from "./PackDiffPanel.tsx";
import { PackStage } from "./PackStage.tsx";
import { StartHere } from "./StartHere.tsx";
import { ConfirmDialog } from "./ConfirmDialog.tsx";
import { navigate, parseHash, shareUrl, importHint, clearImportHint, type View } from "./nav.ts";
import {
  clearHandoffSearch,
  clearPendingHandoff,
  getPendingFile,
  getPendingHandoff,
  listenForBuilderHandoff,
  parseHandoffSearch,
  setPendingHandoff,
} from "./handoff.ts";

function can(user: StudioUser | null, perm: string): boolean {
  return Boolean(user?.permissions?.includes(perm));
}

function copyShare(view: View): Promise<void> {
  const href = shareUrl(view);
  return navigator.clipboard.writeText(href);
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
  const [orgs, setOrgs] = useState<StudioOrg[]>([]);
  const [adapterHealth, setAdapterHealth] = useState<AdapterHealth[]>([]);

  const [handoffNotice, setHandoffNotice] = useState<string | null>(null);

  const packBuilderUrl =
    meta?.pack_builder_url || import.meta.env.VITE_PACK_BUILDER_URL || "http://localhost:5173";

  const showError = useCallback((err: unknown) => {
    setError(err instanceof Error ? err.message : String(err));
  }, []);

  useEffect(() => {
    api.meta().then(setMeta).catch(() => setMeta(null));
    api.me().then((user) => {
      setMe(user);
      if (user.org_id && !getOrgId()) setOrgId(user.org_id);
    }).catch(() => setMe(null));
    api.orgs().then(setOrgs).catch(() => setOrgs([]));
    api.adapterHealth().then(setAdapterHealth).catch(() => setAdapterHealth([]));
  }, [token, userName, view.page]);

  useEffect(() => {
    const parsed = parseHandoffSearch();
    if (parsed.handoffId) {
      setPendingHandoff({
        id: parsed.handoffId,
        filename: "builder pack.zip",
        notice:
          "Builder handoff is ready. Pick a project/episode — import uses the staged zip (no re-choose file). Not auto-generate.",
      });
      setHandoffNotice(
        "Builder handoff is ready. Pick a project/episode — import uses the staged zip. Not auto-generate.",
      );
    } else if (parsed.importHint) {
      const pending = getPendingHandoff();
      if (pending) setHandoffNotice(pending.notice);
    }
    return listenForBuilderHandoff(
      (_file, filename) => {
        setHandoffNotice(
          `Builder zip “${filename}” landed. Pick a project/episode to import it. Not auto-generate.`,
        );
      },
      [packBuilderUrl, window.location.origin],
    );
  }, [packBuilderUrl]);

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
            <p className="eyebrow">SMF Works · Studio · Phase 10</p>
            <h1>AIGC Studio</h1>
          </div>
        </div>
        <p className="lede">
          One app for the pack. Start a project here — blank, template, or brain dump — then edit
          Script → Assets → Storyboard → Preview on the episode. Export for an agent feeds Comfy
          MCP (stills, then clips). Pack zip stays the collaboration contract. Import is optional.
          Hermes <code>smf-h3-capture</code> can stay; Studio is the create surface. Jobs default
          to stub. Unset comfy hooks are not live. No model is claimed unless one is configured.
        </p>
        <nav className="mast-nav" aria-label="Studio">
          <button
            type="button"
            className="btn btn-go"
            onClick={() => {
              navigate({ page: "projects" });
              window.setTimeout(() => {
                document.getElementById("start-here")?.scrollIntoView({ behavior: "smooth", block: "start" });
              }, 50);
            }}
          >
            New project
          </button>
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
          <OrgSwitcher
            me={me}
            orgs={orgs}
            onSwitch={() => {
              navigate({ page: "projects" });
              api.me().then(setMe).catch(() => setMe(null));
              api.orgs().then(setOrgs).catch(() => setOrgs([]));
            }}
            onCreated={(org) => {
              setOrgId(org.id);
              setNotice(`Created ${org.name} — multi-org lite, not SaaS`);
              navigate({ page: "projects" });
              api.me().then(setMe).catch(() => setMe(null));
              api.orgs().then(setOrgs).catch(() => setOrgs([]));
            }}
            onError={showError}
          />
          <NotificationBell
            orgId={me?.org_id}
            onError={showError}
            onOpenHref={(href) => {
              const next = href.startsWith("#") ? href : `#${href}`;
              window.location.hash = next;
            }}
          />
          <span className="hint">
            Auth {meta?.auth_mode ?? "local"}
            {meta?.oidc_configured ? " (OIDC JWKS configured)" : " (OIDC off)"}. Roles are
            app-level. docs/AUTH.md.
          </span>
          {meta?.still_adapter ? (
            <span className="hint">
              still={meta.still_adapter} · clip={meta.clip_adapter} · worker={meta.job_worker}
              {meta.celery_enabled ? " (celery opt-in)" : ""} · media={meta.media_backend || "local"}
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
      {handoffNotice ? (
        <p className="banner banner-ok" role="status">
          {handoffNotice}{" "}
          <button
            type="button"
            className="text-btn"
            onClick={() => {
              clearPendingHandoff();
              clearHandoffSearch();
              setHandoffNotice(null);
            }}
          >
            dismiss
          </button>
        </p>
      ) : null}
      {importHint() ? (
        <p className="banner banner-ok" role="status" data-testid="import-hint">
          Optional zip handoff: pick a project/episode, then{" "}
          <strong>Import pack zip</strong>. You can also start a pack here. Deep links:{" "}
          <code>#/projects/&lt;id&gt;/episodes/&lt;id&gt;</code>
          <button
            type="button"
            className="text-btn"
            onClick={() => {
              clearImportHint();
              setNotice("Import hint dismissed");
            }}
          >
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
          orgId={me?.org_id}
          onOpen={(projectId) => navigate({ page: "project", projectId })}
          onStarted={(projectId, episodeId) =>
            navigate({ page: "episode", projectId, episodeId })
          }
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
          identityId={view.identityId}
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
  orgId,
  onOpen,
  onStarted,
  onError,
  onNotice,
}: {
  me: StudioUser | null;
  orgId?: string | null;
  onOpen: (id: string) => void;
  onStarted: (projectId: string, episodeId: string) => void;
  onError: (err: unknown) => void;
  onNotice: (msg: string) => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [busy, setBusy] = useState(false);
  const [restoreFile, setRestoreFile] = useState<File | null>(null);
  const [restoreSummary, setRestoreSummary] = useState("");
  const restoreRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const nextProjects = await api.projects();
      setProjects(nextProjects);
    } catch (err) {
      onError(err);
    }
  }, [onError, orgId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="panel">
      <StartHere
        me={me}
        onError={onError}
        onStarted={(projectId, episodeId, note) => {
          onNotice(note);
          void load().then(() => onStarted(projectId, episodeId));
        }}
      />
      <div className="panel-head">
        <h2>Projects</h2>
        <p>One title. Episodes hold the pack. Zip import stays available on the episode as a secondary path.</p>
      </div>
      {projects.length === 0 ? (
        <div className="empty-tip">
          <p className="empty">Start here — new project, blank pack, template, or a brain dump. A zip is optional.</p>
          <p className="hint">
            First-run: <strong>Seed demo episode</strong> uses the short-drama-ep template plus JSON fixture
            metadata — no likeness still, no engine MP4, gates stay red.
          </p>
          <button
            type="button"
            className="btn btn-go"
            data-testid="seed-demo"
            disabled={!can(me, "mutate") || busy}
            onClick={() => {
              setBusy(true);
              void api
                .seedDemo()
                .then((seeded) => {
                  onNotice(seeded.honesty);
                  onOpen(seeded.project.id);
                })
                .catch(onError)
                .finally(() => setBusy(false));
            }}
          >
            Seed demo episode
          </button>
        </div>
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
      <div className="toolbar">
        <button
          type="button"
          className="btn"
          onClick={() =>
            void downloadBackup()
              .then(() => onNotice("Downloaded org backup zip (metadata + media manifest). Pack revisions kept on restore."))
              .catch(onError)
          }
        >
          Export backup zip
        </button>
        <button type="button" className="btn" disabled={!can(me, "members")} onClick={() => restoreRef.current?.click()}>
          Restore backup
        </button>
        <input
          ref={restoreRef}
          type="file"
          accept=".zip,application/zip"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (!file) return;
            void api
              .restoreBackup(file, true)
              .then((dry) => {
                if (dry.cross_org_conflicts?.length) {
                  throw new Error(
                    `Cross-org restore refused. These ids belong to another organization: ${dry.cross_org_conflicts.join(", ")}`,
                  );
                }
                const summary = `Dry-run: create ${dry.would_create_projects?.length ?? 0} projects, add ${
                  dry.would_add_revisions?.length ?? 0
                } missing pack revisions, keep ${dry.would_keep_revisions?.length ?? 0} existing. Pack revisions are never deleted.`;
                onNotice(summary);
                setRestoreFile(file);
                setRestoreSummary(summary);
              })
              .catch(onError);
          }}
        />
      </div>
      <ConfirmDialog
        open={Boolean(restoreFile)}
        title="Apply backup restore?"
        message={restoreSummary}
        confirmLabel="Apply restore"
        onCancel={() => setRestoreFile(null)}
        onConfirm={() => {
          const file = restoreFile;
          setRestoreFile(null);
          if (!file) return;
          void api
            .restoreBackup(file, false)
            .then((applied) => {
              if (applied?.applied) {
                onNotice(
                  `Restore applied. Pack revisions preserved. Added ${applied.added_revisions ?? 0} missing revisions.`,
                );
                return load();
              }
            })
            .catch(onError);
        }}
      />
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
  const [episodeMode, setEpisodeMode] = useState<"blank" | "template" | "brain">("blank");
  const [episodeTemplate, setEpisodeTemplate] = useState("");
  const [episodeBrain, setEpisodeBrain] = useState("");
  const [templates, setTemplates] = useState<VerticalTemplate[]>([]);
  const [stillAdapter, setStillAdapter] = useState("stub");
  const [clipAdapter, setClipAdapter] = useState("stub");
  const [cap, setCap] = useState("");
  const [hardStop, setHardStop] = useState(false);
  const [retentionDays, setRetentionDays] = useState("");
  const [retention, setRetention] = useState<RetentionPreview | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [nextProject, nextEpisodes, nextAdapters, nextRetention, nextTemplates] = await Promise.all([
        api.project(projectId),
        api.episodes(projectId),
        api.adapters().catch(() => null),
        api.retentionPreview({ project_id: projectId }).catch(() => null),
        api.templates().catch(() => [] as VerticalTemplate[]),
      ]);
      setTemplates(nextTemplates);
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
    if (episodeMode === "template" && !episodeTemplate) return;
    if (episodeMode === "brain" && !episodeBrain.trim()) return;
    setBusy(true);
    try {
      const episode = await api.createEpisode(projectId, {
        title: title.trim(),
        synopsis: episodeMode === "brain" ? episodeBrain.trim() : synopsis.trim(),
        pack: episodeMode === "blank" ? "blank" : "none",
        template_id: episodeMode === "template" ? episodeTemplate : undefined,
        brain_dump: episodeMode === "brain" ? episodeBrain.trim() : "",
      });
      setTitle("");
      setSynopsis("");
      setEpisodeBrain("");
      onNotice(
        episodeMode === "brain"
          ? `Draft pack on ${episode.title}. Gates stay red until filled.`
          : `Created ${episode.title} with a ${episodeMode === "template" ? "template" : "blank"} pack.`,
      );
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

  async function moveEpisode(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= episodes.length) return;
    const current = episodes[index];
    const neighbor = episodes[target];
    try {
      const ordered = await api.reorderEpisodes(
        projectId,
        episodes.map((episode) => {
          if (episode.id === current.id) {
            return {
              id: episode.id,
              season: neighbor.season || 1,
              sequence: neighbor.sequence || neighbor.chapter,
            };
          }
          if (episode.id === neighbor.id) {
            return {
              id: episode.id,
              season: current.season || 1,
              sequence: current.sequence || current.chapter,
            };
          }
          return {
            id: episode.id,
            season: episode.season || 1,
            sequence: episode.sequence || episode.chapter,
          };
        }),
      );
      setEpisodes(ordered);
      onNotice("Episode order updated. Backup and retention keep this season/sequence.");
    } catch (err) {
      onError(err);
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
        <p>{project?.description || "Episodes are chapters. Start a blank pack, a template, or a brain dump here."}</p>
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
        <button
          type="button"
          className="btn"
          onClick={() =>
            void copyShare({ page: "project", projectId })
              .then(() => onNotice("Copied project link"))
              .catch(onError)
          }
        >
          Copy project link
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
        <select
          value={episodeMode}
          onChange={(event) => setEpisodeMode(event.target.value as "blank" | "template" | "brain")}
          aria-label="Episode pack"
        >
          <option value="blank">New blank pack</option>
          <option value="template">New from template</option>
          <option value="brain">Brain dump</option>
        </select>
        <input
          placeholder="Episode / chapter title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          required
          aria-label="Episode title"
        />
        {episodeMode === "template" ? (
          <select
            value={episodeTemplate}
            onChange={(event) => setEpisodeTemplate(event.target.value)}
            required
            aria-label="Episode template"
          >
            <option value="">Choose a vertical</option>
            {templates.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </select>
        ) : episodeMode === "brain" ? null : (
          <input
            placeholder="Synopsis (optional)"
            value={synopsis}
            onChange={(event) => setSynopsis(event.target.value)}
            aria-label="Episode synopsis"
          />
        )}
        <button type="submit" className="btn btn-go" disabled={busy || !can(me, "script")}>
          {episodeMode === "blank" ? "New blank pack" : episodeMode === "template" ? "New from template" : "New from brain dump"}
        </button>
      </form>
      {episodeMode === "brain" ? (
        <label className="field">
          <span className="editor-label">Brain dump</span>
          <textarea
            value={episodeBrain}
            onChange={(event) => setEpisodeBrain(event.target.value)}
            rows={4}
            placeholder="Freeform brief for this episode. Draft skeleton only."
            aria-label="New episode brain dump"
          />
        </label>
      ) : null}
      {episodes.length === 0 ? (
        <p className="empty">Start here. Add a blank pack, a template, or a brain dump. You do not need a zip.</p>
      ) : (
        <ul className="card-list" data-testid="episode-list">
          {episodes.map((episode, index) => (
            <li key={episode.id}>
              <button
                type="button"
                className="card-btn"
                data-testid="episode-card"
                onClick={() => onOpenEpisode(episode.id)}
              >
                <strong>
                  S{episode.season || 1} · seq {episode.sequence || episode.chapter} · {episode.title}
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
              {can(me, "script") && episodes.length > 1 ? (
                <span className="toolbar">
                  <button
                    type="button"
                    className="btn"
                    disabled={index === 0}
                    onClick={() => void moveEpisode(index, -1)}
                  >
                    Up
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={index === episodes.length - 1}
                    onClick={() => void moveEpisode(index, 1)}
                  >
                    Down
                  </button>
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      <p className="hint">
        Season and sequence are the episode order. Retention and backup keep that order; they do
        not reorder episodes. Writer (and the legacy editor bundle) can move them.
      </p>
    </section>
  );
}

function EpisodeView({
  projectId,
  episodeId,
  shotId,
  identityId,
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
  identityId?: string;
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
  const [signoffNote, setSignoffNote] = useState("");
  const [overrideGenerate, setOverrideGenerate] = useState(false);
  const [kind, setKind] = useState("plate");
  const [entityType, setEntityType] = useState("");
  const [entity, setEntity] = useState("");
  const [mediaNotes, setMediaNotes] = useState("");
  const [showBuilder, setShowBuilder] = useState(false);
  const [identity, setIdentity] = useState<IdentityStoreData | null>(null);
  const [packDiff, setPackDiff] = useState<PackDiff | null>(null);
  const [pendingImport, setPendingImport] = useState<{ file?: File; handoffId?: string } | null>(null);
  const [diffBusy, setDiffBusy] = useState(false);
  const packRef = useRef<HTMLInputElement>(null);
  const mediaRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [nextEpisode, nextReview, nextComments, nextMedia, nextShots, nextJobs, nextDesk, nextIdentity] =
        await Promise.all([
          api.episode(episodeId),
          api.review(episodeId),
          api.comments(episodeId),
          api.media(episodeId),
          api.shots(episodeId).catch(() => [] as Shot[]),
          api.episodeJobs(episodeId).catch(() => [] as Job[]),
          api.previewDesk(episodeId).catch(() => null),
          api.identity(episodeId).catch(() => null),
        ]);
      setEpisode(nextEpisode);
      setReview(nextReview);
      setComments(nextComments);
      setMedia(nextMedia);
      setShots(nextShots);
      setJobs(nextJobs);
      setDesk(nextDesk);
      setIdentity(nextIdentity);
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
  const signedOff = review?.signed_off === true;
  const generateBlocked = useMemo(() => {
    if (!allGreen || desk?.generate_ok_ready !== true) return true;
    if (signedOff) return false;
    return !(overrideGenerate && me?.role === "producer");
  }, [allGreen, desk, signedOff, overrideGenerate, me?.role]);

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
      const next = await api.setReview(
        episodeId,
        state,
        note.trim(),
        state === "generate-ok" && overrideGenerate && !signedOff,
      );
      setReview(next);
      setEpisode((current) => (current ? { ...current, review_state: next.current } : current));
      setNote("");
      setOverrideGenerate(false);
      onNotice(`Review → ${state}`);
    } catch (err) {
      onError(err);
    }
  }

  async function submitSignoff() {
    try {
      const next = await api.signOff(episodeId, signoffNote.trim());
      setReview(next);
      setSignoffNote("");
      onNotice("Signed off — generate-ok can proceed if gates and hop-1 receipts are ready");
    } catch (err) {
      onError(err);
    }
  }

  async function previewThenImport(file?: File, handoffId?: string) {
    try {
      setDiffBusy(true);
      const diff = await api.previewPackDiff(episodeId, file, handoffId);
      setPackDiff(diff);
      setPendingImport({ file, handoffId });
      onNotice("Review the pack diff, then Confirm import. Not auto-generate.");
    } catch (err) {
      onError(err);
    } finally {
      setDiffBusy(false);
    }
  }

  async function importPack(file?: File, handoffId?: string) {
    try {
      const result = await api.importPack(episodeId, file, handoffId);
      onNotice(
        result.all_gates_green
          ? `Imported ${result.filename} — all gates green`
          : `Imported ${result.filename} — gates still red (generate-ok blocked)`,
      );
      clearPendingHandoff();
      clearHandoffSearch();
      setPackDiff(null);
      setPendingImport(null);
      await load();
    } catch (err) {
      onError(err);
    }
  }

  useEffect(() => {
    if (!can(me, "pack")) return;
    const pending = getPendingHandoff();
    const file = getPendingFile();
    if (!pending && !file) return;
    if (packDiff || pendingImport) return;
    void previewThenImport(file || undefined, pending?.id);
    // Preview once per episode when a builder handoff is waiting. Confirm still applies it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [episodeId, me]);

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
          S{episode?.season ?? 1} · seq {episode?.sequence ?? episode?.chapter ?? "—"} · chapter{" "}
          {episode?.chapter ?? "—"}.{" "}
          {episode?.synopsis ||
            "Edit the four stages below. generate-ok stays locked until every gate is green. Zip import is optional."}
        </p>
      </div>
      <form
        className="create-row"
        key={`${episodeId}:${episode?.updated_at || ""}`}
        onSubmit={(event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          void api
            .updateEpisode(episodeId, {
              log_line: String(data.get("log_line") || ""),
              map_notes: String(data.get("map_notes") || ""),
              dialogue: String(data.get("dialogue") || ""),
            })
            .then(() => {
              onNotice("Script, map, and dialogue saved. Pack zip is still the round-trip.");
              return load();
            })
            .catch(onError);
        }}
      >
        <input
          name="log_line"
          defaultValue={episode?.log_line || ""}
          placeholder="Log line (writer)"
          disabled={!can(me, "script")}
          aria-label="Log line"
        />
        <input
          name="map_notes"
          defaultValue={episode?.map_notes || ""}
          placeholder="Map notes — clock to beat, not shots"
          disabled={!can(me, "script")}
          aria-label="Map notes"
        />
        <input
          name="dialogue"
          defaultValue={episode?.dialogue || ""}
          placeholder="Dialogue finish-by"
          disabled={!can(me, "script")}
          aria-label="Dialogue"
        />
        <button type="submit" className="btn" disabled={!can(me, "script")}>
          Save script fields
        </button>
      </form>
      <PresenceBar episodeId={episodeId} shotId={selectedShotId} onError={onError} />

      <PackStage
        episodeId={episodeId}
        canEdit={can(me, "script") || can(me, "pack") || can(me, "identity") || can(me, "edit")}
        onError={onError}
        onNotice={onNotice}
        onSaved={() => void load()}
      />

      <section className="panel">
        <div className="panel-head">
          <h3>Optional zip</h3>
          <p>Import a pack zip or use Open in Studio when a file already exists. Creating the pack does not require it.</p>
        </div>
        <div className="toolbar">
          <button
            type="button"
            className={importHint() || getPendingHandoff() ? "btn btn-go" : "btn"}
            onClick={() => {
              const pending = getPendingHandoff();
              const file = getPendingFile();
              if (pending?.id || file) {
                void previewThenImport(file || undefined, pending?.id);
                return;
              }
              packRef.current?.click();
            }}
            disabled={!can(me, "pack") || diffBusy}
          >
            {getPendingHandoff() || getPendingFile() ? "Import handed-off zip" : "Import zip"}
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
            Pack builder (optional)
          </a>
          <button
            type="button"
            className="btn"
            onClick={() =>
              void copyShare({ page: "episode", projectId, episodeId, shotId: selectedShotId || undefined })
                .then(() => onNotice("Copied episode/shot link"))
                .catch(onError)
            }
          >
            Copy episode link
          </button>
          <button type="button" className="btn" onClick={() => setShowBuilder((value) => !value)}>
            {showBuilder ? "Hide builder window" : "Optional builder window"}
          </button>
          <input
            ref={packRef}
            type="file"
            accept=".zip,application/zip"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void previewThenImport(file);
              event.target.value = "";
            }}
          />
        </div>
        {episode?.latest_revision ? (
          <p className="hint">
            Latest: {episode.latest_revision.filename}
            {episode.latest_revision.all_gates_green ? " · gates green" : " · not generate-ready"}
            {" · "}
            Share: {typeof window !== "undefined" ? shareUrl({ page: "episode", projectId, episodeId }) : ""}
          </p>
        ) : (
          <p className="hint">
            No stored revision yet. Use the stages above (blank, template, or brain dump). A zip from{" "}
            {packBuilderUrl} is optional
            {importHint() || getPendingHandoff() ? " — a handoff is waiting." : "."}
          </p>
        )}
        {packDiff ? (
          <PackDiffPanel
            diff={packDiff}
            canApply={can(me, "pack")}
            applying={diffBusy}
            onApply={() => {
              setDiffBusy(true);
              void importPack(pendingImport?.file, pendingImport?.handoffId).finally(() => setDiffBusy(false));
            }}
            onCancel={() => {
              setPackDiff(null);
              setPendingImport(null);
            }}
          />
        ) : null}
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
          <p className="empty">No stored snapshot yet. Fill the stages above. Gates stay red until the pack is filled.</p>
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

      <ContinuityPanel
        episodeId={episodeId}
        refreshKey={(identity?.plates || [])
          .map((asset) => `${asset.id}:${asset.shot_id || ""}:${asset.approval_status}`)
          .join("|")}
        onError={onError}
        onOpenHref={(href) => {
          const next = href.startsWith("#") ? href : `#${href}`;
          window.location.hash = next;
        }}
      />

      <IdentityStore
        sheets={identity?.sheets || []}
        plates={identity?.plates || []}
        shots={shots.map((shot) => ({
          id: shot.id,
          sort_index: shot.sort_index,
          take: shot.take,
          edit_row_id: shot.edit_row_id,
        }))}
        selectedId={identityId}
        canIdentity={can(me, "identity")}
        honesty={identity?.honesty || "Approved sheets and per-window plates. Not embeddings."}
        onApprove={(assetId, lockKeywords) => {
          void api
            .approveIdentity(episodeId, assetId, "", lockKeywords)
            .then(() => {
              onNotice(
                "Identity asset approved (who/when recorded). Approved lock keywords count for lock-diff and generate-ok. Draft does not.",
              );
              return load();
            })
            .catch(onError);
        }}
        onSaveKeywords={(assetId, lockKeywords) => {
          void api
            .saveIdentityKeywords(episodeId, assetId, lockKeywords, "keyword edit")
            .then(() => {
              onNotice("Keywords saved as draft. They do not count until you re-approve.");
              return load();
            })
            .catch(onError);
        }}
        onUnapprove={(assetId) => {
          void api
            .unapproveIdentity(episodeId, assetId, "unapproved in studio")
            .then(() => {
              onNotice("Identity unapproved. Audit recorded. Draft keywords do not count.");
              return load();
            })
            .catch(onError);
        }}
        onLink={(assetId, nextShotId) => {
          void api
            .linkIdentityPlate(episodeId, assetId, nextShotId)
            .then(() => {
              onNotice("Plate linked to shot/window.");
              navigate({ page: "episode", projectId, episodeId, identityId: assetId });
              return load();
            })
            .catch(onError);
        }}
        onSelect={(assetId) => navigate({ page: "episode", projectId, episodeId, identityId: assetId })}
      />

      <ShotBoard
        shots={shots}
        media={media}
        packBuilderUrl={packBuilderUrl}
        selectedShotId={selectedShotId}
        onSelectShot={selectShot}
        episodeId={episodeId}
        canComment={can(me, "comment")}
        canMutate={can(me, "edit")}
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

      <PlaylistScrubber episodeId={episodeId} onError={onError} />

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
          Adapter label is honest. Default worker is thread. Celery is opt-in.
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
            ? " — generate-ok refused while any gate is red, a required hop-1 lacks preview-watched + receipt, or a reviewer/producer has not signed off."
            : ""}
        </p>
        <div className="signoff-box" data-testid="signoff-status">
          <p>
            Sign-off:{" "}
            {signedOff
              ? `${review?.signoffs?.[0]?.user_name ?? "someone"} (${review?.signoffs?.[0]?.role ?? ""})`
              : "none yet — required before generate-ok"}
          </p>
          <label className="note-field">
            Sign-off note
            <input value={signoffNote} onChange={(event) => setSignoffNote(event.target.value)} />
          </label>
          <button
            type="button"
            className="btn btn-go"
            disabled={!can(me, "signoff")}
            onClick={() => void submitSignoff()}
          >
            Sign off
          </button>
          {!can(me, "signoff") ? (
            <span className="hint">Reviewers and producers can sign off. Viewers cannot.</span>
          ) : null}
          {me?.role === "producer" && !signedOff ? (
            <label className="check">
              <input
                type="checkbox"
                checked={overrideGenerate}
                onChange={(event) => setOverrideGenerate(event.target.checked)}
              />
              Producer override (audited as review.override)
            </label>
          ) : null}
          {review?.signoffs?.length ? (
            <ul className="history">
              {review.signoffs.map((row) => (
                <li key={row.id}>
                  <strong>{row.user_name}</strong> · {row.role} · {formatWhen(row.created_at)}
                  {row.note ? ` — ${row.note}` : ""}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
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
            <button
              type="button"
              className="btn"
              disabled={
                kind === "preview" || kind === "other" ? !can(me, "media") : !can(me, "identity")
              }
              onClick={() => mediaRef.current?.click()}
            >
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
                    {asset.kind === "sheet" || asset.kind === "plate"
                      ? ` · ${asset.approval_status || "draft"}`
                      : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
      <p className="hint">
        Project {projectId}. Builder remains the four-stage walk. generate-ok needs every gate
        green, hop-1 receipts watched, and a reviewer/producer sign-off.
      </p>
    </div>
  );
}
