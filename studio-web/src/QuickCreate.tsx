import { useState } from "react";
import { api } from "./api.ts";
import { whoIsWhere } from "./stagingLine.ts";
import type { QuickPlan, QuickShot, QuickStatus, StudioUser } from "./types.ts";

const LENGTHS = [15, 30, 60] as const;
const ASPECTS = ["9:16", "16:9", "1:1"] as const;

type Props = {
  me: StudioUser | null;
  onFullWizard: () => void;
  onOpenEpisode: (projectId: string, episodeId: string) => void;
  onError: (err: unknown) => void;
  onNotice: (msg: string) => void;
};

function can(user: StudioUser | null, perm: string): boolean {
  return Boolean(user?.permissions?.includes(perm));
}

export function QuickCreate({ me, onFullWizard, onOpenEpisode, onError, onNotice }: Props) {
  const [story, setStory] = useState("");
  const [castNotes, setCastNotes] = useState("");
  const [lengthSec, setLengthSec] = useState<(typeof LENGTHS)[number]>(30);
  const [aspect, setAspect] = useState<(typeof ASPECTS)[number]>("9:16");
  const [plan, setPlan] = useState<QuickPlan | null>(null);
  const [planning, setPlanning] = useState(false);
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState<QuickStatus | null>(null);

  const jobs = can(me, "jobs");

  async function planStory() {
    const prompt = story.trim();
    if (!prompt) {
      onError(new Error("Add a story prompt before planning."));
      return;
    }
    setPlanning(true);
    setPlan(null);
    setStatus(null);
    try {
      const planned = await api.quickPlan({
        prompt,
        target_duration_sec: lengthSec,
        aspect_ratio: aspect,
        ...(castNotes.trim() ? { cast_notes: castNotes.trim() } : {}),
      });
      setPlan(planned.plan);
      onNotice("Plan only. Nothing was rendered.");
    } catch (err) {
      onError(err);
    } finally {
      setPlanning(false);
    }
  }

  function updateShot(index: number, patch: Partial<QuickShot>) {
    setPlan((current) => {
      if (!current) return current;
      const shots = current.shots.map((shot, shotIndex) =>
        shotIndex === index ? { ...shot, ...patch } : shot,
      );
      return { ...current, shots };
    });
  }

  async function runPlan() {
    if (!plan) return;
    setRunning(true);
    try {
      const started = await api.quickRun(plan);
      setStatus(started);
      onNotice("Episode saved on the local desk.");
    } catch (err) {
      onError(err);
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className="wizard" data-testid="quick-create">
      <div className="wizard-card">
        <p className="hint">Fast path</p>
        <h2>Quick create</h2>
        <p className="hint">
          One story prompt. Studio plans the shots on this machine. Run saves the episode on the
          local desk. Stills and clips use the configured local engines. Gates and generate-ok stay
          as they are.
        </p>
        <button type="button" className="text-btn" data-testid="full-wizard" onClick={onFullWizard}>
          Full wizard
        </button>
        <label>
          Story
          <textarea
            rows={5}
            required
            value={story}
            data-testid="quick-story"
            placeholder="Mara waits in the hall until the light turns."
            onChange={(event) => setStory(event.target.value)}
          />
        </label>
        <label>
          Cast
          <textarea
            rows={2}
            value={castNotes}
            data-testid="quick-cast"
            placeholder="Optional. Jack — tan hat"
            onChange={(event) => setCastNotes(event.target.value)}
          />
        </label>
        <p className="hint">Optional. Names here go with the plan. Leave this blank to plan from the story alone.</p>
        <fieldset>
          <legend>Length</legend>
          <div className="choice-row">
            {LENGTHS.map((seconds) => (
              <label key={seconds}>
                <input
                  type="radio"
                  name="quick-length"
                  checked={lengthSec === seconds}
                  data-testid={`quick-length-${seconds}`}
                  onChange={() => setLengthSec(seconds)}
                />
                {seconds}s
              </label>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend>Aspect</legend>
          <div className="choice-row">
            {ASPECTS.map((ratio) => (
              <label key={ratio}>
                <input
                  type="radio"
                  name="quick-aspect"
                  checked={aspect === ratio}
                  data-testid={`quick-aspect-${ratio.replace(":", "-")}`}
                  onChange={() => setAspect(ratio)}
                />
                {ratio}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="wizard-actions">
          <button
            type="button"
            className="btn btn-go"
            data-testid="quick-plan"
            disabled={planning || !story.trim()}
            onClick={() => void planStory()}
          >
            {planning ? "Planning…" : "Plan"}
          </button>
        </div>
      </div>

      {plan ? (
        <div className="wizard-card" data-testid="quick-shots">
          <h3>{plan.title || "Shot list"}</h3>
          {plan.logline ? <p>{plan.logline}</p> : null}
          <ol className="quick-shots">
            {plan.shots.map((shot, index) => {
              const where = whoIsWhere(shot, plan.staging, plan.cast);
              return (
                <li key={shot.id || index}>
                  <p>
                    {shot.id || `Shot ${index + 1}`}
                    {shot.duration_sec ? ` · ${shot.duration_sec}s` : ""}
                    {shot.camera?.move ? ` · ${shot.camera.move}` : ""}
                  </p>
                  {where ? (
                    <p className="quick-where" data-testid={`quick-where-${index}`}>
                      {where}
                    </p>
                  ) : null}
                  <label>
                    Still prompt
                    <textarea
                      rows={3}
                      value={shot.prompt_still}
                      data-testid={`quick-still-${index}`}
                      onChange={(event) => updateShot(index, { prompt_still: event.target.value })}
                    />
                  </label>
                  <label>
                    Motion prompt
                    <textarea
                      rows={3}
                      value={shot.prompt_motion}
                      data-testid={`quick-motion-${index}`}
                      onChange={(event) => updateShot(index, { prompt_motion: event.target.value })}
                    />
                  </label>
                </li>
              );
            })}
          </ol>
          <p className="hint" data-testid="quick-run-note">
            Run saves this plan as an episode. Generate stills and clips from the desk.
          </p>
          <div className="wizard-actions">
            <button
              type="button"
              className="btn btn-go"
              data-testid="quick-run"
              disabled={running || !jobs}
              onClick={() => void runPlan()}
            >
              {running ? "Saving…" : "Run"}
            </button>
            {!jobs ? <span className="hint">The jobs permission is required to run.</span> : null}
          </div>
        </div>
      ) : null}

      {status ? (
        <div className="wizard-card" data-testid="quick-progress">
          <h3>Saved</h3>
          <p>{status.message}</p>
          {status.error ? <p className="hint">{status.error}</p> : null}
          {status.project_id && status.episode_id ? (
            <button
              type="button"
              className="btn"
              onClick={() => onOpenEpisode(status.project_id, status.episode_id)}
            >
              Open episode
            </button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
