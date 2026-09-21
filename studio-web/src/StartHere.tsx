import { useEffect, useState, type FormEvent } from "react";
import { api } from "./api.ts";
import type { StudioUser, VerticalTemplate } from "./types.ts";

type Mode = "blank" | "template" | "brain";

type Props = {
  me: StudioUser | null;
  onStarted: (projectId: string, episodeId: string, note: string) => void;
  onError: (err: unknown) => void;
};

function canMutate(user: StudioUser | null): boolean {
  return Boolean(user?.permissions?.includes("mutate"));
}

export function StartHere({ me, onStarted, onError }: Props) {
  const [mode, setMode] = useState<Mode>("blank");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [brain, setBrain] = useState("");
  const [templates, setTemplates] = useState<VerticalTemplate[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.templates().then(setTemplates).catch(() => setTemplates([]));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canMutate(me)) return;
    setBusy(true);
    try {
      const created = await api.startStudio({
        name: name.trim(),
        description: description.trim(),
        mode,
        template_id: mode === "template" ? templateId : undefined,
        brain_dump: mode === "brain" ? brain.trim() : "",
      });
      setName("");
      setDescription("");
      setBrain("");
      const model = created.model_ran
        ? "A local model returned a draft skeleton."
        : created.model_note;
      onStarted(
        created.project_id,
        created.episode_id,
        `Started in Studio (${created.source}). Gates ${
          created.gates_green ? "green" : "red"
        }. ${model} Not generate-ready.`,
      );
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form id="start-here" className="start-here pack-stage" onSubmit={submit} data-testid="start-here">
      <div className="panel-head">
        <h2>Start here</h2>
        <p>
          New project with a blank pack, a vertical template, or a brain dump. The episode opens
          in Studio. Importing a zip is optional.
        </p>
      </div>
      <div className="seg-row" role="radiogroup" aria-label="How to start">
        {(
          [
            ["blank", "New blank pack"],
            ["template", "New from template"],
            ["brain", "Brain dump"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={mode === id ? "seg is-on" : "seg"}
            aria-pressed={mode === id}
            onClick={() => setMode(id)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="create-row">
        <input
          placeholder={mode === "brain" ? "Project name (optional — first line is used)" : "Project name"}
          value={name}
          onChange={(event) => setName(event.target.value)}
          required={mode !== "brain"}
          aria-label="Project name"
        />
        <input
          placeholder="Description (optional)"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          aria-label="Project description"
        />
        {mode === "template" ? (
          <select
            value={templateId}
            onChange={(event) => setTemplateId(event.target.value)}
            required
            aria-label="Vertical template"
          >
            <option value="">Choose a vertical</option>
            {templates.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </select>
        ) : null}
        <button type="submit" className="btn btn-go" disabled={busy || !canMutate(me)}>
          {mode === "blank" ? "New project" : mode === "template" ? "New from template" : "New from brain dump"}
        </button>
      </div>
      {mode === "brain" ? (
        <label className="field">
          <span className="editor-label">Brain dump</span>
          <textarea
            value={brain}
            onChange={(event) => setBrain(event.target.value)}
            required
            rows={5}
            placeholder="Paste a freeform brief. A log line and rough beats become a draft pack. Gates stay red."
            aria-label="Brain dump"
            data-testid="brain-dump"
          />
          <span className="field-hint">
            If no model endpoint is configured, Studio expands this text with a template and says so.
            It does not invent that an LLM ran.
          </span>
        </label>
      ) : null}
      {mode === "template" ? (
        <p className="hint">Templates are empty structured packs. Gates stay red. No fake generate.</p>
      ) : null}
      {mode === "blank" ? (
        <p className="hint">Look starts blank. Gates stay red until you fill the four stages.</p>
      ) : null}
    </form>
  );
}
