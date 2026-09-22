import { useEffect, useState, type FormEvent } from "react";
import { api, downloadAgentExport } from "./api.ts";
import type { HermesHandoff, StudioUser, WizardSession } from "./types.ts";
import { AgentRunStatus } from "./AgentRunStatus.tsx";

const WIZARD_KEY = "smf.aigc-studio.wizard";

const FORMATS = [
  ["short-drama", "Short drama", "A face, a turn, windows instead of a montage."],
  ["vertical-ad", "Vertical ad", "One product. A short clock. Cuts."],
  ["music-video", "Music video", "One take. Later windows stay in that chain."],
  ["custom", "Custom", "You name the shape. The pack stays a draft."],
] as const;

type Props = {
  wizardId?: string;
  me: StudioUser | null;
  onWizard: (id: string) => void;
  onOpenEpisode: (projectId: string, episodeId: string) => void;
  onError: (err: unknown) => void;
  onNotice: (msg: string) => void;
};

function can(user: StudioUser | null, perm: string): boolean {
  return Boolean(user?.permissions?.includes(perm));
}

function textValue(answers: Record<string, unknown>, key: string): string {
  const value = answers[key];
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function numberValue(answers: Record<string, unknown>, key: string): string {
  const value = answers[key];
  if (value == null || value === "") return "";
  return String(value);
}

export function CreateWizard({ wizardId, me, onWizard, onOpenEpisode, onError, onNotice }: Props) {
  const [wizard, setWizard] = useState<WizardSession | null>(null);
  const [prompt, setPrompt] = useState("");
  const [format, setFormat] = useState("short-drama");
  const [shotCount, setShotCount] = useState("3");
  const [lengthS, setLengthS] = useState("30");
  const [tone, setTone] = useState("");
  const [look, setLook] = useState("");
  const [castNotes, setCastNotes] = useState("");
  const [audioNotes, setAudioNotes] = useState("");
  const [stillPref, setStillPref] = useState("comfy-qwen");
  const [clipPref, setClipPref] = useState("comfy-h3");
  const [busy, setBusy] = useState(false);
  const [handoff, setHandoff] = useState<HermesHandoff | null>(null);

  useEffect(() => {
    if (wizardId) return;
    const stored = localStorage.getItem(WIZARD_KEY);
    if (stored) onWizard(stored);
  }, [onWizard, wizardId]);

  useEffect(() => {
    if (!wizardId) {
      setWizard(null);
      setHandoff(null);
      return;
    }
    let stop = false;
    api
      .wizard(wizardId)
      .then((row) => {
        if (stop) return;
        setWizard(row);
        localStorage.setItem(WIZARD_KEY, row.id);
        const answers = row.answers || {};
        setPrompt(textValue(answers, "prompt"));
        if (textValue(answers, "format")) setFormat(textValue(answers, "format"));
        if (numberValue(answers, "shot_count")) setShotCount(numberValue(answers, "shot_count"));
        if (numberValue(answers, "target_length_s")) setLengthS(numberValue(answers, "target_length_s"));
        setTone(textValue(answers, "tone"));
        setLook(textValue(answers, "look"));
        setCastNotes(textValue(answers, "cast_notes"));
        setAudioNotes(textValue(answers, "audio_notes"));
        if (textValue(answers, "still_pref")) setStillPref(textValue(answers, "still_pref"));
        if (textValue(answers, "clip_pref")) setClipPref(textValue(answers, "clip_pref"));
      })
      .catch((err) => {
        localStorage.removeItem(WIZARD_KEY);
        onError(err);
      });
    return () => {
      stop = true;
    };
  }, [onError, wizardId]);

  async function save(step: string, answers: Record<string, unknown>) {
    if (!wizard) return null;
    const next = await api.patchWizard(wizard.id, { step, answers });
    setWizard(next);
    return next;
  }

  async function start(event: FormEvent) {
    event.preventDefault();
    if (!can(me, "mutate")) return;
    setBusy(true);
    try {
      const created = await api.startWizard(prompt.trim());
      localStorage.setItem(WIZARD_KEY, created.id);
      setWizard(created);
      onWizard(created.id);
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  }

  async function go(step: string, answers: Record<string, unknown>, finish = false) {
    if (!wizard) return;
    setBusy(true);
    try {
      await save(step, answers);
      if (finish) {
        const done = await api.finishWizard(wizard.id);
        setWizard(done);
        onNotice("Draft pack is in. Gates stay red. Nothing was generated.");
      }
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  }

  async function send() {
    if (!wizard) return;
    setBusy(true);
    try {
      const sent = await api.handoffHermes(wizard.id);
      setHandoff(sent);
      setWizard(await api.wizard(wizard.id));
      onNotice("Brief is on disk. Hermes has not been invoked. Comfy was not called.");
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  }

  async function copyText(value: string, label: string) {
    try {
      await navigator.clipboard.writeText(value);
      onNotice(label);
    } catch (err) {
      onError(err);
    }
  }

  const ready = wizard?.status === "ready" || wizard?.status === "handed_off";
  const step = ready ? "review" : wizard?.step || "prompt";
  const steps = wizard?.steps || ["prompt", "format", "length", "tone", "cast", "audio", "engines"];
  const runId = handoff?.run.id || wizard?.agent_run_id || "";

  return (
    <section className="wizard" data-testid="create-wizard">
      <div className="panel-head">
        <p className="eyebrow">New creation</p>
        <h2>What do you want to make?</h2>
        <p>
          A short wizard fills a draft pack. Send it to Hermes when you are done. The zip stays
          available. Gates stay red until the pack is actually filled. Nothing here generates a clip.
        </p>
      </div>
      {wizard ? (
        <ol className="wizard-rail" aria-label="Wizard steps">
          {steps.map((name, index) => (
            <li key={name} className={step === name || (ready && name === "engines") ? "is-on" : ""}>
              <span>{index + 1}</span>
              {name}
            </li>
          ))}
        </ol>
      ) : null}

      {wizard ? (
        <button
          type="button"
          className="text-btn"
          onClick={() => {
            localStorage.removeItem(WIZARD_KEY);
            setWizard(null);
            setHandoff(null);
            setPrompt("");
            onWizard("");
          }}
        >
          Start over
        </button>
      ) : null}

      {!wizard || step === "prompt" ? (
        <form
          onSubmit={(event) => {
            if (wizard) {
              event.preventDefault();
              void go("format", { prompt: prompt.trim() });
              return;
            }
            void start(event);
          }}
          className="wizard-card"
        >
          <label className="field">
            <span className="editor-label">Prompt</span>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              required
              rows={5}
              placeholder="Mara waits in the hall. She turns."
              aria-label="What do you want to make?"
              data-testid="wizard-prompt"
            />
          </label>
          <button type="submit" className="btn btn-go" disabled={busy || !can(me, "mutate")} data-testid="wizard-continue">
            Continue
          </button>
        </form>
      ) : null}

      {wizard && step === "format" ? (
        <form
          className="wizard-card"
          onSubmit={(event) => {
            event.preventDefault();
            void go("length", { format });
          }}
        >
          <p className="editor-label">Format</p>
          <div className="format-grid">
            {FORMATS.map(([id, label, blurb]) => (
              <button
                key={id}
                type="button"
                className={format === id ? "format-card is-on" : "format-card"}
                aria-pressed={format === id}
                onClick={() => setFormat(id)}
              >
                <strong>{label}</strong>
                <span>{blurb}</span>
              </button>
            ))}
          </div>
          <div className="wizard-actions">
            <button type="button" className="btn" onClick={() => void go("prompt", { format })}>
              Back
            </button>
            <button type="submit" className="btn btn-go" disabled={busy}>
              Continue
            </button>
          </div>
        </form>
      ) : null}

      {wizard && step === "length" ? (
        <form
          className="wizard-card"
          onSubmit={(event) => {
            event.preventDefault();
            void go("tone", {
              shot_count: Number(shotCount) || 1,
              target_length_s: Number(lengthS) || undefined,
            });
          }}
        >
          <label className="field">
            <span className="editor-label">Shot count</span>
            <input
              type="number"
              min={1}
              max={24}
              value={shotCount}
              onChange={(event) => setShotCount(event.target.value)}
              aria-label="Shot count"
              data-testid="wizard-shots"
            />
          </label>
          <label className="field">
            <span className="editor-label">Target length (seconds)</span>
            <input
              type="number"
              min={1}
              max={600}
              value={lengthS}
              onChange={(event) => setLengthS(event.target.value)}
              aria-label="Target length in seconds"
            />
          </label>
          <p className="hint">A measured hop-1 window is 10.125 seconds. This is a target, not a render.</p>
          <div className="wizard-actions">
            <button type="button" className="btn" onClick={() => void go("format", {})}>
              Back
            </button>
            <button type="submit" className="btn btn-go" disabled={busy}>
              Continue
            </button>
          </div>
        </form>
      ) : null}

      {wizard && step === "tone" ? (
        <form
          className="wizard-card"
          onSubmit={(event) => {
            event.preventDefault();
            void go("cast", { tone, look });
          }}
        >
          <label className="field">
            <span className="editor-label">Tone</span>
            <input value={tone} onChange={(event) => setTone(event.target.value)} aria-label="Tone" data-testid="wizard-tone" />
          </label>
          <label className="field">
            <span className="editor-label">Look</span>
            <input
              value={look}
              onChange={(event) => setLook(event.target.value)}
              aria-label="Look"
              placeholder="One style line. Leave blank if you do not have it yet."
            />
          </label>
          <p className="hint">Look can stay blank. A blank look keeps that gate red, which is the honest state.</p>
          <div className="wizard-actions">
            <button type="button" className="btn" onClick={() => void go("length", { tone, look })}>
              Back
            </button>
            <button type="submit" className="btn btn-go" disabled={busy}>
              Continue
            </button>
          </div>
        </form>
      ) : null}

      {wizard && step === "cast" ? (
        <form
          className="wizard-card"
          onSubmit={(event) => {
            event.preventDefault();
            void go("audio", { cast_notes: castNotes });
          }}
        >
          <label className="field">
            <span className="editor-label">Cast</span>
            <textarea
              rows={4}
              value={castNotes}
              onChange={(event) => setCastNotes(event.target.value)}
              placeholder={"Mara — lead\nProp: token"}
              aria-label="Cast and identity notes"
              data-testid="wizard-cast"
            />
          </label>
          <p className="hint">
            Names become identity drafts. Nothing is approved. No likeness is stored. Leave this empty and
            the pack keeps a placeholder called lead.
          </p>
          <div className="wizard-actions">
            <button type="button" className="btn" onClick={() => void go("tone", { cast_notes: castNotes })}>
              Back
            </button>
            <button type="submit" className="btn btn-go" disabled={busy}>
              Continue
            </button>
          </div>
        </form>
      ) : null}

      {wizard && step === "audio" ? (
        <form
          className="wizard-card"
          onSubmit={(event) => {
            event.preventDefault();
            void go("engines", { audio_notes: audioNotes });
          }}
        >
          <label className="field">
            <span className="editor-label">Audio / SFX</span>
            <textarea
              rows={3}
              value={audioNotes}
              onChange={(event) => setAudioNotes(event.target.value)}
              placeholder="Room tone. No score yet."
              aria-label="Audio and SFX notes"
            />
          </label>
          <p className="hint">Notes stay notes. Write N/A, silence, prompt score, or path: … only if that is the real path.</p>
          <div className="wizard-actions">
            <button type="button" className="btn" onClick={() => void go("cast", { audio_notes: audioNotes })}>
              Back
            </button>
            <button type="submit" className="btn btn-go" disabled={busy}>
              Continue
            </button>
          </div>
        </form>
      ) : null}

      {wizard && step === "engines" ? (
        <form
          className="wizard-card"
          onSubmit={(event) => {
            event.preventDefault();
            void go("engines", { still_pref: stillPref, clip_pref: clipPref }, true);
          }}
        >
          <p className="editor-label">Engines</p>
          <p className="hint" data-testid="engine-honesty">
            {wizard.engines.note}
          </p>
          <div className="format-grid">
            <label className={stillPref === "comfy-qwen" ? "format-card is-on" : "format-card"}>
              <input
                type="radio"
                name="still"
                checked={stillPref === "comfy-qwen"}
                onChange={() => setStillPref("comfy-qwen")}
              />
              <strong>Stills · Qwen-Image</strong>
              <span>Slot comfy-qwen, canvas 1344×768. {wizard.engines.still_label}.</span>
            </label>
            <label className={stillPref === "stub" ? "format-card is-on" : "format-card"}>
              <input type="radio" name="still" checked={stillPref === "stub"} onChange={() => setStillPref("stub")} />
              <strong>Stills · stub</strong>
              <span>Fixture receipts only.</span>
            </label>
            <label className={clipPref === "comfy-h3" ? "format-card is-on" : "format-card"}>
              <input type="radio" name="clip" checked={clipPref === "comfy-h3"} onChange={() => setClipPref("comfy-h3")} />
              <strong>Clips · MiniMax H3</strong>
              <span>Slot comfy-h3, 10.125 s / 243 frames. {wizard.engines.clip_label}.</span>
            </label>
            <label className={clipPref === "stub" ? "format-card is-on" : "format-card"}>
              <input type="radio" name="clip" checked={clipPref === "stub"} onChange={() => setClipPref("stub")} />
              <strong>Clips · stub</strong>
              <span>Fixture receipts only. No hop-1 watch is stamped.</span>
            </label>
          </div>
          <div className="wizard-actions">
            <button type="button" className="btn" onClick={() => void go("audio", { still_pref: stillPref, clip_pref: clipPref })}>
              Back
            </button>
            <button type="submit" className="btn btn-go" disabled={busy || !can(me, "mutate")} data-testid="wizard-finish">
              Create the pack
            </button>
          </div>
        </form>
      ) : null}

      {wizard && ready ? (
        <div className="wizard-card" data-testid="wizard-review">
          <h3>Draft pack</h3>
          <p>
            {wizard.gates_green ? "Gates are green." : "Gates are red."} Generate-ready is no. Comfy has not
            been called. {wizard.engines.note}
          </p>
          <div className="wizard-actions">
            <button
              type="button"
              className="btn btn-go"
              disabled={busy || !can(me, "jobs")}
              onClick={() => void send()}
              data-testid="send-hermes"
            >
              Send to Hermes
            </button>
            <button
              type="button"
              className="btn"
              disabled={!wizard.episode_id}
              onClick={() => {
                if (!wizard.episode_id) return;
                void downloadAgentExport(wizard.episode_id).catch(onError);
              }}
              data-testid="download-agent-zip"
            >
              Download agent zip
            </button>
            {wizard.project_id && wizard.episode_id ? (
              <button
                type="button"
                className="btn"
                onClick={() => onOpenEpisode(wizard.project_id as string, wizard.episode_id as string)}
              >
                Open the episode
              </button>
            ) : null}
          </div>
          {handoff ? (
            <div className="handoff-box" data-testid="hermes-handoff">
              <p>
                Drop folder is local. Deep link <code>{handoff.deep_link}</code>
              </p>
              <div className="wizard-actions">
                <button type="button" className="btn" onClick={() => void copyText(handoff.deep_link, "Deep link copied.")}>
                  Copy deep link
                </button>
                <button
                  type="button"
                  className="btn"
                  onClick={() => void copyText(JSON.stringify(handoff.payload, null, 2), "Handoff payload copied.")}
                  data-testid="copy-handoff"
                >
                  Copy handoff payload
                </button>
              </div>
            </div>
          ) : null}
          {runId ? <AgentRunStatus runId={runId} onError={onError} /> : null}
          <p className="hint">
            Blank pack, template, and brain dump still live under Projects. The zip is the fallback, not the
            front door.
          </p>
        </div>
      ) : null}
    </section>
  );
}
