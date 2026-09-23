import { useEffect, useState, type FormEvent } from "react";
import { api, downloadAgentExport } from "./api.ts";
import type { CreateRecipe, DirectorView, HermesHandoff, StudioUser, TaskNode, WizardSession } from "./types.ts";
import { AgentRunStatus } from "./AgentRunStatus.tsx";

const WIZARD_KEY = "smf.aigc-studio.wizard";

const FORMATS = [
  ["short-drama", "Short drama", "A face, a turn, windows instead of a montage."],
  ["vertical-ad", "Vertical ad", "One product. A short clock. Cuts."],
  ["music-video", "Music video", "One take. Later windows stay in that chain."],
  ["custom", "Custom", "You name the shape. The pack stays a draft."],
] as const;

const PLATFORM_FORMATS = ["9:16", "16:9", "1:1", "4:5", "4:3"] as const;

const STEP_LABELS: Record<string, string> = {
  prompt: "Prompt",
  format: "Format",
  length: "Length",
  tone: "Tone",
  scope: "Scope",
  cast: "Cast",
  audio: "Audio",
  engines: "Engines",
  tree: "Task tree",
  checkpoints: "Checkpoints",
};

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

function asTree(value: unknown): TaskNode[] {
  if (!Array.isArray(value)) return [];
  return value.filter((row): row is TaskNode => Boolean(row) && typeof row === "object");
}

function treeDepth(node: TaskNode, byId: Map<string, TaskNode>): number {
  const parents = node.depends_on || [];
  const parentId = parents[parents.length - 1];
  let depth = 0;
  let current = parentId ? byId.get(parentId) : undefined;
  const seen = new Set<string>();
  while (current && !seen.has(current.id)) {
    seen.add(current.id);
    depth += 1;
    const parents = current.depends_on || [];
    const nextId = parents[parents.length - 1];
    current = nextId ? byId.get(nextId) : undefined;
  }
  return depth;
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
  const [mustNots, setMustNots] = useState("");
  const [claimBans, setClaimBans] = useState("");
  const [audience, setAudience] = useState("");
  const [deliverables, setDeliverables] = useState("");
  const [negativeConstraints, setNegativeConstraints] = useState("");
  const [clarify, setClarify] = useState<{ field: string; question: string }[] | null>(null);
  const [platformFormats, setPlatformFormats] = useState<string[]>([]);
  const [taskTree, setTaskTree] = useState<TaskNode[]>([]);
  const [recipes, setRecipes] = useState<CreateRecipe[]>([]);
  const [recipeId, setRecipeId] = useState("");
  const [recipeName, setRecipeName] = useState("");
  const [busy, setBusy] = useState(false);
  const [handoff, setHandoff] = useState<HermesHandoff | null>(null);

  useEffect(() => {
    if (wizardId) return;
    const stored = localStorage.getItem(WIZARD_KEY);
    if (stored) onWizard(stored);
  }, [onWizard, wizardId]);

  useEffect(() => {
    api
      .recipes()
      .then(setRecipes)
      .catch(() => setRecipes([]));
  }, [wizardId]);

  function applyWizard(row: WizardSession) {
    setWizard(row);
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
    setMustNots(textValue(answers, "must_nots"));
    setClaimBans(textValue(answers, "claim_bans"));
    setAudience(textValue(answers, "audience"));
    setDeliverables(textValue(answers, "deliverables"));
    setNegativeConstraints(textValue(answers, "negative_constraints"));
    const formats = answers.platform_formats;
    setPlatformFormats(Array.isArray(formats) ? formats.map(String) : []);
    const tree = asTree(row.director?.task_tree);
    setTaskTree(tree.length ? tree : asTree(answers.task_tree));
  }

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
        localStorage.setItem(WIZARD_KEY, row.id);
        applyWizard(row);
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
      const saved = await save(step, answers);
      if (saved?.director?.task_tree) setTaskTree(asTree(saved.director.task_tree));
      if (step === "checkpoints") {
        const report = await api.clarifyWizard(wizard.id);
        const questions = !report.ready && report.questions.length ? report.questions : [];
        setClarify(questions.length ? questions : null);
        if (finish && questions.length) {
          onNotice("Answer the brief questions before the crew lanes are written. Nothing was generated.");
          return;
        }
      }
      if (finish) {
        const done = await api.finishWizard(wizard.id);
        setClarify(null);
        setWizard(done);
        if (done.director?.task_tree) setTaskTree(asTree(done.director.task_tree));
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

  async function commitTree(next: TaskNode[]) {
    if (!wizard) return;
    setTaskTree(next);
    setBusy(true);
    try {
      const saved = await api.patchWizard(wizard.id, {
        ...(wizard.status === "draft" ? { step: wizard.step } : {}),
        answers: { task_tree: next },
      });
      setWizard(saved);
      setTaskTree(asTree(saved.director?.task_tree));
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  }

  function toggleNode(nodeId: string) {
    const next = taskTree.map((node) =>
      node.id === nodeId && node.prunable !== false ? { ...node, enabled: !node.enabled } : node,
    );
    void commitTree(next);
  }

  function deleteNode(nodeId: string) {
    const next = taskTree.map((node) =>
      node.id === nodeId && node.prunable !== false ? { ...node, deleted: true, enabled: false } : node,
    );
    void commitTree(next);
  }

  async function loadRecipe() {
    if (!recipeId || !can(me, "mutate")) return;
    setBusy(true);
    try {
      const created = await api.startWizard(prompt.trim(), recipeId);
      localStorage.setItem(WIZARD_KEY, created.id);
      applyWizard(created);
      onWizard(created.id);
      onNotice("Recipe loaded. It prefills the wizard. Nothing was generated.");
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  }

  async function saveRecipe() {
    if (!wizard) return;
    const name = recipeName.trim() || format || "Create recipe";
    setBusy(true);
    try {
      const saved = await api.saveRecipe({ name, wizard_id: wizard.id });
      setRecipes(await api.recipes());
      onNotice(`Saved ${saved.filename}. Local recipe only. Nothing ran.`);
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  }

  function toggleFormat(fmt: string) {
    setPlatformFormats((current) =>
      current.includes(fmt) ? current.filter((item) => item !== fmt) : [...current, fmt],
    );
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
  const steps = wizard?.steps || [
    "prompt",
    "format",
    "length",
    "tone",
    "scope",
    "cast",
    "audio",
    "engines",
    "tree",
    "checkpoints",
  ];
  const director: DirectorView | undefined = wizard?.director;
  const byId = new Map(taskTree.map((node) => [node.id, node]));
  const visibleTree = taskTree.filter((node) => !node.deleted);
  const locked = wizard?.status === "handed_off";
  const runId = handoff?.run.id || wizard?.agent_run_id || "";

  return (
    <section className="wizard" data-testid="create-wizard">
      <div className="panel-head">
        <p className="eyebrow">New creation</p>
        <h2>What do you want to make?</h2>
        <p>
          A short wizard fills a draft pack. The task tree is a plan you can prune. Send to Hermes
          writes the brief when you are done. Gates stay red until the pack is actually filled.
          Nothing here generates a clip.
        </p>
      </div>
      {wizard ? (
        <ol className="wizard-rail" aria-label="Wizard steps">
          {steps.map((name, index) => (
            <li key={name} className={step === name || (ready && name === "engines") ? "is-on" : ""}>
              <span>{index + 1}</span>
              {STEP_LABELS[name] || name}
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
          <p className="hint">
            @Name binds to a cast identity when that name is already a slot. It does not create a plate.
          </p>
          <button type="submit" className="btn btn-go" disabled={busy || !can(me, "mutate")} data-testid="wizard-continue">
            Continue
          </button>
          {recipes.length ? (
            <div className="recipe-row" data-testid="recipe-list">
              <label className="field">
                <span className="editor-label">Saved recipe</span>
                <select
                  value={recipeId}
                  onChange={(event) => setRecipeId(event.target.value)}
                  aria-label="Saved Create recipe"
                  data-testid="recipe-select"
                >
                  <option value="">None</option>
                  {recipes.map((recipe) => (
                    <option key={recipe.id} value={recipe.id}>
                      {recipe.name} v{recipe.version}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="btn"
                disabled={busy || !recipeId || !can(me, "mutate")}
                onClick={() => void loadRecipe()}
                data-testid="load-recipe"
              >
                Load recipe
              </button>
              <p className="hint">Local JSON only. A recipe prefills answers and the task tree. It does not run anything.</p>
            </div>
          ) : null}
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
            void go("scope", { tone, look });
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

      {wizard && step === "scope" ? (
        <form
          className="wizard-card"
          data-testid="wizard-scope"
          onSubmit={(event) => {
            event.preventDefault();
            void go("cast", {
              audience,
              deliverables,
              negative_constraints: negativeConstraints,
              must_nots: mustNots,
              claim_bans: claimBans,
              platform_formats: platformFormats,
            });
          }}
        >
          <p className="editor-label">Brief, deliverables, and must-nots</p>
          <p className="hint">
            Audience and deliverables are asked again before the pack is created if they are still empty.
            That pause is not a gate. Notes travel with the pack and the brief. They do not clear a gate.
          </p>
          <label className="field">
            <span className="editor-label">Audience</span>
            <input
              value={audience}
              onChange={(event) => setAudience(event.target.value)}
              aria-label="Audience"
              data-testid="wizard-audience"
              placeholder="Who this is for"
            />
          </label>
          <label className="field">
            <span className="editor-label">Deliverables</span>
            <textarea
              rows={2}
              value={deliverables}
              onChange={(event) => setDeliverables(event.target.value)}
              aria-label="Deliverables"
              data-testid="wizard-deliverables"
              placeholder="One 9:16 pilot. Two hop-1 windows."
            />
          </label>
          <label className="field">
            <span className="editor-label">Negative constraints</span>
            <textarea
              rows={2}
              value={negativeConstraints}
              onChange={(event) => setNegativeConstraints(event.target.value)}
              aria-label="Negative constraints"
              data-testid="wizard-negative"
              placeholder="No neon. Write none if there are none."
            />
          </label>
          <label className="field">
            <span className="editor-label">Must not</span>
            <textarea
              rows={3}
              value={mustNots}
              onChange={(event) => setMustNots(event.target.value)}
              placeholder="No logos. No on-screen claims."
              aria-label="Must nots"
              data-testid="wizard-must-nots"
            />
          </label>
          <fieldset className="format-grid">
            <legend className="editor-label">Platform formats</legend>
            {PLATFORM_FORMATS.map((fmt) => (
              <label key={fmt} className={platformFormats.includes(fmt) ? "format-card is-on" : "format-card"}>
                <input
                  type="checkbox"
                  checked={platformFormats.includes(fmt)}
                  onChange={() => toggleFormat(fmt)}
                  data-testid={`platform-${fmt.replace(":", "-")}`}
                />
                <strong>{fmt}</strong>
                <span>{fmt === "9:16" ? "Vertical only when this is the only box." : "Optional frame."}</span>
              </label>
            ))}
          </fieldset>
          <label className="field">
            <span className="editor-label">Claim bans</span>
            <textarea
              rows={2}
              value={claimBans}
              onChange={(event) => setClaimBans(event.target.value)}
              placeholder="No medical claims. No before/after."
              aria-label="Claim bans"
              data-testid="wizard-claim-bans"
            />
          </label>
          <div className="wizard-actions">
            <button
              type="button"
              className="btn"
              onClick={() =>
                void go("tone", {
                  audience,
                  deliverables,
                  negative_constraints: negativeConstraints,
                  must_nots: mustNots,
                  claim_bans: claimBans,
                  platform_formats: platformFormats,
                })
              }
            >
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
            <button type="button" className="btn" onClick={() => void go("scope", { cast_notes: castNotes })}>
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
            void go("tree", { still_pref: stillPref, clip_pref: clipPref, engine_mode: "approve" });
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
            <button type="submit" className="btn btn-go" disabled={busy || !can(me, "mutate")} data-testid="wizard-approve-engines">
              Continue
            </button>
            <p className="hint">Continuing approves these lanes. Ask stays open until you do. This does not call Comfy.</p>
          </div>
        </form>
      ) : null}

      {wizard && step === "tree" ? (
        <div className="wizard-card" data-testid="wizard-tree">
          <p className="editor-label">Task tree</p>
          <p className="hint">
            Script, sheets, plates, hop-1, stitch, then review. Disable or delete a branch you will not use.
            This does not run Comfy or Hermes.
          </p>
          <TaskTree
            nodes={visibleTree}
            byId={byId}
            busy={busy || locked}
            onToggle={toggleNode}
            onDelete={deleteNode}
          />
          <div className="wizard-actions">
            <button type="button" className="btn" onClick={() => void go("engines", { task_tree: taskTree })}>
              Back
            </button>
            <button
              type="button"
              className="btn btn-go"
              disabled={busy}
              onClick={() => void go("checkpoints", { task_tree: taskTree })}
            >
              Continue
            </button>
          </div>
        </div>
      ) : null}

      {wizard && step === "checkpoints" ? (
        <div className="wizard-card" data-testid="wizard-checkpoints">
          <p className="editor-label">Director checkpoints</p>
          <p className="hint">{director?.checkpoints.note}</p>
          <SubjectRefs answers={wizard.answers} />
          <ExecutionGates director={director} />
          <CheckpointList director={director} />
          <CrewLanes director={director} />
          {clarify ? (
            <div className="prompt-preview" data-testid="wizard-clarify">
              <p className="editor-label">Clarify before the crew lanes</p>
              <p className="hint">
                These questions are missing brief fields. They are not director checkpoints and they do not turn a
                gate green.
              </p>
              <ul>
                {clarify.map((row) => (
                  <li key={row.field}>{row.question}</li>
                ))}
              </ul>
              <label className="field">
                <span className="editor-label">Audience</span>
                <input value={audience} onChange={(event) => setAudience(event.target.value)} aria-label="Clarify audience" />
              </label>
              <label className="field">
                <span className="editor-label">Deliverables</span>
                <textarea rows={2} value={deliverables} onChange={(event) => setDeliverables(event.target.value)} aria-label="Clarify deliverables" />
              </label>
              <label className="field">
                <span className="editor-label">Negative constraints</span>
                <textarea
                  rows={2}
                  value={negativeConstraints}
                  onChange={(event) => setNegativeConstraints(event.target.value)}
                  aria-label="Clarify negative constraints"
                />
              </label>
              <label className="field">
                <span className="editor-label">Cast / references</span>
                <textarea rows={2} value={castNotes} onChange={(event) => setCastNotes(event.target.value)} aria-label="Clarify cast" />
              </label>
              <div className="wizard-actions">
                <button
                  type="button"
                  className="btn btn-go"
                  disabled={busy}
                  onClick={() =>
                    void go(
                      "checkpoints",
                      {
                        audience,
                        deliverables,
                        negative_constraints: negativeConstraints,
                        must_nots: mustNots,
                        claim_bans: claimBans,
                        cast_notes: castNotes,
                        task_tree: taskTree,
                      },
                      true,
                    )
                  }
                >
                  Save answers and check again
                </button>
                {clarify.some((row) => row.field === "engines") ? (
                  <button
                    type="button"
                    className="btn"
                    disabled={busy}
                    data-testid="wizard-approve-engines"
                    onClick={() =>
                      void go(
                        "checkpoints",
                        {
                          audience,
                          deliverables,
                          negative_constraints: negativeConstraints,
                          must_nots: mustNots,
                          claim_bans: claimBans,
                          cast_notes: castNotes,
                          task_tree: taskTree,
                          still_pref: stillPref,
                          clip_pref: clipPref,
                          engine_mode: "approve",
                        },
                        true,
                      )
                    }
                  >
                    Approve these lanes
                  </button>
                ) : null}
                <button
                  type="button"
                  className="btn"
                  disabled={busy}
                  data-testid="wizard-acknowledge-gaps"
                  onClick={() => {
                    setBusy(true);
                    void api
                      .finishWizard(wizard.id, true)
                      .then((done) => {
                        setClarify(null);
                        setWizard(done);
                        if (done.director?.task_tree) setTaskTree(asTree(done.director.task_tree));
                        onNotice("Pack created with the gaps you named. Gates stay red. Nothing was generated.");
                      })
                      .catch(onError)
                      .finally(() => setBusy(false));
                  }}
                >
                  Proceed with these gaps
                </button>
              </div>
            </div>
          ) : null}
          <div className="wizard-actions">
            <button type="button" className="btn" onClick={() => void go("tree", { task_tree: taskTree })}>
              Back
            </button>
            <button
              type="button"
              className="btn btn-go"
              disabled={busy || !can(me, "mutate")}
              data-testid="wizard-finish"
              onClick={() => void go("checkpoints", { task_tree: taskTree }, true)}
            >
              Create the pack
            </button>
          </div>
        </div>
      ) : null}

      {wizard && ready ? (
        <div className="wizard-card" data-testid="wizard-review">
          <h3>Crew brief</h3>
          <p>
            {wizard.gates_green ? "Gates are green." : "Gates are red."} Generate-ready is no. Comfy has not
            been called. Hermes has not been started. {wizard.engines.note}
          </p>
          <CrewLanes director={director} />
          <SubjectRefs answers={wizard.answers} />
          <ExecutionGates director={director} />
          <CheckpointList director={director} />
          {locked ? (
            <TaskTree nodes={visibleTree} byId={byId} busy onToggle={() => undefined} onDelete={() => undefined} />
          ) : (
            <div data-testid="wizard-tree-review">
              <p className="editor-label">Task tree</p>
              <p className="hint">Prune before you send. Disabled branches stay in the brief as skipped. Nothing runs from this list.</p>
              <TaskTree
                nodes={visibleTree}
                byId={byId}
                busy={busy}
                onToggle={toggleNode}
                onDelete={deleteNode}
              />
            </div>
          )}
          <div className="recipe-row">
            <label className="field">
              <span className="editor-label">Save as recipe</span>
              <input
                value={recipeName}
                onChange={(event) => setRecipeName(event.target.value)}
                placeholder="Short drama"
                aria-label="Recipe name"
                data-testid="recipe-name"
              />
            </label>
            <button
              type="button"
              className="btn"
              disabled={busy || !can(me, "mutate")}
              onClick={() => void saveRecipe()}
              data-testid="save-recipe"
            >
              Save recipe
            </button>
            <p className="hint">Writes a local JSON file such as skill_short_drama_v0.1.json. No marketplace.</p>
          </div>
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

function CrewLanes({ director }: { director: DirectorView | undefined }) {
  const lanes = director?.craft_lanes || [];
  if (!lanes.length) return null;
  return (
    <div data-testid="craft-lanes">
      <p className="editor-label">Craft lanes</p>
      <p className="hint" data-testid="craft-lane-note">
        Writer, Art, Picture, and Sound are routing labels in the brief. They are not four agents that ran.
      </p>
      <div className="format-grid">
        {lanes.map((lane) => (
          <article
            key={lane.id}
            className={lane.enabled ? "format-card is-on" : "format-card"}
            data-testid={`craft-lane-${lane.id}`}
            data-ran={lane.ran ? "true" : "false"}
          >
            <strong>
              {lane.label}
              {lane.enabled ? "" : " · off"}
            </strong>
            <span>{lane.covers}</span>
            <span>{lane.routing}</span>
          </article>
        ))}
      </div>
    </div>
  );
}

function SubjectRefs({ answers }: { answers: Record<string, unknown> | undefined }) {
  const refs = Array.isArray(answers?.subject_refs) ? answers.subject_refs : [];
  const rows = refs.filter((row): row is { token?: string; bound?: boolean; role?: string } => !!row && typeof row === "object");
  if (!rows.length) return null;
  return (
    <ul className="checkpoint-list" data-testid="subject-refs">
      {rows.map((row) => (
        <li key={String(row.token)} data-bound={row.bound ? "true" : "false"}>
          <strong>@{row.token}</strong>
          <span>{row.bound ? "identity draft" : "no slot"}</span>
        </li>
      ))}
    </ul>
  );
}

function ExecutionGates({ director }: { director: DirectorView | undefined }) {
  const gates = director?.execution_gates;
  if (!gates) return null;
  return (
    <ul className="checkpoint-list" data-testid="execution-gates">
      {(["brief", "cut"] as const).map((key) => {
        const row = gates[key];
        return (
          <li key={key} data-cleared={row.cleared ? "true" : "false"} data-testid={`execution-${key}`}>
            <strong>
              {row.cleared ? "Clear" : "Open"} · {row.label}
            </strong>
            <span>{row.detail}</span>
          </li>
        );
      })}
    </ul>
  );
}

function CheckpointList({ director }: { director: DirectorView | undefined }) {
  const items = director?.checkpoints?.items || [];
  const gates = director?.checkpoints?.gates || [];
  if (!items.length) return null;
  return (
    <div data-testid="director-checkpoints">
      <p className="editor-label">Director checkpoints</p>
      <ul className="checkpoint-list">
        {items.map((item) => (
          <li key={item.id} data-cleared={item.cleared ? "true" : "false"} data-testid={`checkpoint-${item.id}`}>
            <strong>
              {item.cleared ? "Clear" : "Open"} · {item.label}
            </strong>
            <span>{item.detail}</span>
          </li>
        ))}
      </ul>
      {gates.length ? (
        <ul className="checkpoint-list gate-names">
          {gates.map((gate) => (
            <li key={gate.id} data-cleared={gate.ok ? "true" : "false"}>
              <strong>
                {gate.n}. {gate.label}
              </strong>
              <span>{gate.detail}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function TaskTree({
  nodes,
  byId,
  busy,
  onToggle,
  onDelete,
}: {
  nodes: TaskNode[];
  byId: Map<string, TaskNode>;
  busy: boolean;
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  if (!nodes.length) return null;
  return (
    <ul className="task-tree" data-testid="task-tree">
      {nodes.map((node) => (
        <li
          key={node.id}
          className={node.enabled ? "" : "is-off"}
          style={{ marginLeft: `${treeDepth(node, byId) * 16}px` }}
          data-testid={`task-node-${node.id}`}
          data-enabled={node.enabled ? "true" : "false"}
          data-executes="false"
        >
          <label>
            <input
              type="checkbox"
              checked={node.enabled}
              disabled={busy || node.prunable === false}
              onChange={() => onToggle(node.id)}
              aria-label={`${node.enabled ? "Disable" : "Enable"} ${node.label}`}
            />
            <strong>{node.label}</strong>
            <span className="hint">
              {node.lane} · does not run
            </span>
          </label>
          {node.prunable === false ? (
            <span className="hint">Required</span>
          ) : (
            <button type="button" className="text-btn" disabled={busy} onClick={() => onDelete(node.id)}>
              Delete
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
