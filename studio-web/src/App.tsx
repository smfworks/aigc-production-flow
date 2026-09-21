import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { api, downloadMedia, downloadPack, getToken, setToken } from "./api.ts";
import type {
  Comment,
  Episode,
  MediaAsset,
  Meta,
  Project,
  Review,
  ReviewStateName,
} from "./types.ts";
import { REVIEW_COPY, REVIEW_STATES } from "./types.ts";

type View =
  | { page: "projects" }
  | { page: "project"; projectId: string }
  | { page: "episode"; projectId: string; episodeId: string };

function formatWhen(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString();
}

export default function App() {
  const [view, setView] = useState<View>({ page: "projects" });
  const [token, setTokenState] = useState(getToken);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);

  const packBuilderUrl =
    meta?.pack_builder_url || import.meta.env.VITE_PACK_BUILDER_URL || "http://localhost:5173";

  const showError = useCallback((err: unknown) => {
    setError(err instanceof Error ? err.message : String(err));
  }, []);

  useEffect(() => {
    api.meta().then(setMeta).catch(() => setMeta(null));
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
            <p className="eyebrow">SMF Works · Studio spine · Phase 1</p>
            <h1>AIGC Studio</h1>
          </div>
        </div>
        <p className="lede">
          Projects and episodes around the pack zip. The nine-gate builder stays in{" "}
          <code>app/</code> — this shell does not rewrite it, and it does not run a
          generate queue.
        </p>
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
          <span className="hint">SSO later. This is not multi-tenant SaaS security.</span>
        </div>
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
          onOpen={(projectId) => setView({ page: "project", projectId })}
          onError={showError}
          onNotice={setNotice}
        />
      ) : null}
      {view.page === "project" ? (
        <ProjectView
          projectId={view.projectId}
          onBack={() => setView({ page: "projects" })}
          onOpenEpisode={(episodeId) =>
            setView({ page: "episode", projectId: view.projectId, episodeId })
          }
          onError={showError}
          onNotice={setNotice}
        />
      ) : null}
      {view.page === "episode" ? (
        <EpisodeView
          projectId={view.projectId}
          episodeId={view.episodeId}
          packBuilderUrl={packBuilderUrl}
          onBack={() => setView({ page: "project", projectId: view.projectId })}
          onError={showError}
          onNotice={setNotice}
        />
      ) : null}
    </div>
  );
}

function ProjectList({
  onOpen,
  onError,
  onNotice,
}: {
  onOpen: (id: string) => void;
  onError: (err: unknown) => void;
  onNotice: (msg: string) => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setProjects(await api.projects());
    } catch (err) {
      onError(err);
    }
  }, [onError]);

  useEffect(() => {
    void load();
  }, [load]);

  async function create(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const project = await api.createProject({ name: name.trim(), description: description.trim() });
      setName("");
      setDescription("");
      onNotice(`Created ${project.name}`);
      await load();
      onOpen(project.id);
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
        <p>One title. Episodes are chapters. Pack zip is the collaboration object.</p>
      </div>
      <form className="create-row" onSubmit={create}>
        <input
          placeholder="Project name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
        />
        <input
          placeholder="Log line / description (optional)"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
        <button type="submit" className="btn btn-go" disabled={busy}>
          New project
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
    </section>
  );
}

function ProjectView({
  projectId,
  onBack,
  onOpenEpisode,
  onError,
  onNotice,
}: {
  projectId: string;
  onBack: () => void;
  onOpenEpisode: (id: string) => void;
  onError: (err: unknown) => void;
  onNotice: (msg: string) => void;
}) {
  const [project, setProject] = useState<Project | null>(null);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [title, setTitle] = useState("");
  const [synopsis, setSynopsis] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [nextProject, nextEpisodes] = await Promise.all([
        api.project(projectId),
        api.episodes(projectId),
      ]);
      setProject(nextProject);
      setEpisodes(nextEpisodes);
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

  return (
    <section className="panel">
      <button type="button" className="text-btn" onClick={onBack}>
        ← Projects
      </button>
      <div className="panel-head">
        <h2>{project?.name ?? "Project"}</h2>
        <p>{project?.description || "Episodes are chapters. Review state lives on each episode."}</p>
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
        <button type="submit" className="btn btn-go" disabled={busy}>
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
                      ? " · nine green"
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
  packBuilderUrl,
  onBack,
  onError,
  onNotice,
}: {
  projectId: string;
  episodeId: string;
  packBuilderUrl: string;
  onBack: () => void;
  onError: (err: unknown) => void;
  onNotice: (msg: string) => void;
}) {
  const [episode, setEpisode] = useState<Episode | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [media, setMedia] = useState<MediaAsset[]>([]);
  const [commentBody, setCommentBody] = useState("");
  const [note, setNote] = useState("");
  const [kind, setKind] = useState("plate");
  const [entity, setEntity] = useState("");
  const [mediaNotes, setMediaNotes] = useState("");
  const [showBuilder, setShowBuilder] = useState(false);
  const packRef = useRef<HTMLInputElement>(null);
  const mediaRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [nextEpisode, nextReview, nextComments, nextMedia] = await Promise.all([
        api.episode(episodeId),
        api.review(episodeId),
        api.comments(episodeId),
        api.media(episodeId),
      ]);
      setEpisode(nextEpisode);
      setReview(nextReview);
      setComments(nextComments);
      setMedia(nextMedia);
    } catch (err) {
      onError(err);
    }
  }, [episodeId, onError]);

  useEffect(() => {
    void load();
  }, [load]);

  const gates = review?.latest_gates?.gates ?? [];
  const allGreen = review?.latest_gates?.all_green === true;
  const generateBlocked = useMemo(() => !allGreen, [allGreen]);

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
          ? `Imported ${result.filename} — nine gates green`
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
      await api.uploadMedia(episodeId, file, kind, entity.trim(), mediaNotes.trim());
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
        <h2>
          Ch. {episode?.chapter ?? "—"} · {episode?.title ?? "Episode"}
        </h2>
        <p>
          {episode?.synopsis || "Import a pack zip from the builder. generate-ok stays locked until nine green."}
        </p>
      </div>

      <section className="panel">
        <div className="toolbar">
          <button type="button" className="btn" onClick={() => packRef.current?.click()}>
            Import pack zip
          </button>
          <button type="button" className="btn" onClick={() => void exportPack()}>
            Export pack zip
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
            {episode.latest_revision.all_gates_green ? " · nine green" : " · not generate-ready"}
          </p>
        ) : (
          <p className="hint">No revision yet. Export from the builder at {packBuilderUrl}, then import here.</p>
        )}
        {showBuilder ? (
          <iframe
            className="builder-frame"
            title="Pack builder"
            src={packBuilderUrl}
          />
        ) : null}
      </section>

      <section className="panel">
        <h3>Nine gates</h3>
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

      <section className="panel">
        <h3>Review state</h3>
        <p className="hint">
          Current: <strong>{review?.current ?? "draft"}</strong>
          {generateBlocked ? " — generate-ok refused while any gate is red." : ""}
        </p>
        <div className="states">
          {REVIEW_STATES.map((state) => (
            <button
              key={state}
              type="button"
              className={review?.current === state ? "btn btn-go" : "btn"}
              disabled={state === "generate-ok" && generateBlocked}
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
            <button type="submit" className="btn btn-go">
              Add comment
            </button>
          </form>
          <ul className="thread">
            {comments.map((comment) => (
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
          <p className="hint">Sheets and plates only. No engine MP4s. Files land in gitignored data/media/.</p>
          <div className="create-row">
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              <option value="sheet">sheet</option>
              <option value="plate">plate</option>
              <option value="other">other</option>
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
            <button type="button" className="btn" onClick={() => mediaRef.current?.click()}>
              Upload
            </button>
            <input
              ref={mediaRef}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/tiff,.png,.jpg,.jpeg,.webp,.md,.txt"
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
                    {asset.entity_label ? ` · ${asset.entity_label}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
      <p className="hint">Project {projectId}. Builder remains the four-stage / nine-gate walk.</p>
    </div>
  );
}
