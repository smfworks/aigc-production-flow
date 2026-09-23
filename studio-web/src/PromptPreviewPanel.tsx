import { useEffect, useState } from "react";
import { api } from "./api.ts";
import type { PromptPreview, WorkflowSummary } from "./types.ts";

type Props = {
  preview: PromptPreview;
  busy: boolean;
  onPreview: (next: PromptPreview) => void;
  onGenerate: (preview: PromptPreview) => void;
  onClose: () => void;
  onError: (err: unknown) => void;
};

export function PromptPreviewPanel({ preview, busy, onPreview, onGenerate, onClose, onError }: Props) {
  const [prompt, setPrompt] = useState(preview.prompt);
  const [negative, setNegative] = useState(preview.negative || "");
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);

  useEffect(() => {
    setPrompt(preview.prompt);
    setNegative(preview.negative || "");
  }, [preview.id, preview.prompt, preview.negative]);

  useEffect(() => {
    api
      .workflows()
      .then(setWorkflows)
      .catch(() => setWorkflows([]));
  }, []);

  async function save() {
    try {
      onPreview(await api.patchPreview(preview.id, { prompt, negative }));
    } catch (err) {
      onError(err);
    }
  }

  async function rewrite() {
    try {
      onPreview(await api.rewritePreview(preview.id));
    } catch (err) {
      onError(err);
    }
  }

  async function cancel() {
    try {
      await api.cancelPreview(preview.id);
      onClose();
    } catch (err) {
      onError(err);
    }
  }

  async function retarget(payload: Record<string, unknown>) {
    try {
      onPreview(
        await api.previewJob({
          episode_id: preview.episode_id,
          shot_id: preview.shot_id || undefined,
          job_type: preview.job_type,
          payload: { ...payload, prompt, negative },
        }),
      );
    } catch (err) {
      onError(err);
    }
  }

  const stub = preview.stub || preview.adapter === "stub" || !preview.live;
  return (
    <section className="prompt-preview" data-testid="prompt-preview">
      <p className="editor-label">Prompt preview</p>
      <p className="hint">{preview.honesty}</p>
      <p className={stub ? "chip-status is-stub" : "chip-status is-running"} data-testid="preview-adapter">
        {stub ? "stub fixture — Comfy has not been called" : `live lane ${preview.adapter}`}
        {preview.called_comfy ? "" : ""}
      </p>
      <p className="hint">{preview.cause}</p>
      {preview.warning ? (
        <p className="hint warn" data-testid="preview-warning">
          {preview.warning}
        </p>
      ) : null}
      <label className="field">
        <span className="editor-label">Workflow</span>
        <select
          aria-label="Workflow"
          value={preview.workflow_id || ""}
          onChange={(event) => {
            const workflow_id = event.target.value;
            const continue_from = preview.continue?.requested ? "previous" : "";
            void retarget({
              workflow_id,
              ...(continue_from ? { continue_from } : {}),
            });
          }}
        >
          <option value="">No role-tagged workflow</option>
          {workflows.map((row) => (
            <option key={row.id} value={row.id}>
              {row.id}
              {row.has_video_input ? " · video in" : ""}
              {row.asks_h3 ? " · H3 profile" : ""}
              {row.source === "builtin" ? " · builtin" : ""}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span className="editor-label">Prompt that would be sent</span>
        <textarea
          rows={8}
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          aria-label="Prompt preview text"
          data-testid="preview-prompt"
        />
      </label>
      <label className="field">
        <span className="editor-label">Negative</span>
        <textarea
          rows={3}
          value={negative}
          onChange={(event) => setNegative(event.target.value)}
          aria-label="Negative prompt"
        />
      </label>
      {preview.refs?.length ? (
        <ul className="preview-refs">
          {preview.refs.map((ref, index) => (
            <li key={`${ref.role}-${ref.media_id || index}`}>
              {ref.ref_role || ref.role}
              {ref.label ? ` · ${ref.label}` : ""}
              {ref.value ? ` · ${ref.value}` : ""}
            </li>
          ))}
        </ul>
      ) : (
        <p className="hint">No reference slots on this preview.</p>
      )}
      <label className="field inline">
        <input
          type="checkbox"
          checked={Boolean(preview.continue?.requested)}
          onChange={(event) =>
            void retarget({
              workflow_id: preview.workflow_id || (event.target.checked ? "h3-extend" : ""),
              ...(event.target.checked ? { continue_from: "previous" } : {}),
            })
          }
          data-testid="preview-continue"
        />
        Continue from the previous timeline clip
      </label>
      <div className="wizard-actions">
        <button type="button" className="btn" disabled={busy} onClick={() => void save()}>
          Save draft
        </button>
        <button
          type="button"
          className="btn"
          disabled={busy || preview.prompt_profile !== "h3"}
          onClick={() => void rewrite()}
          data-testid="preview-rewrite"
        >
          Rewrite H3 profile
        </button>
        <button type="button" className="btn" disabled={busy} onClick={() => void cancel()}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-go"
          disabled={busy || !preview.generate_enabled}
          onClick={() => onGenerate({ ...preview, prompt, negative })}
          data-testid="preview-generate"
        >
          Generate
        </button>
      </div>
    </section>
  );
}
