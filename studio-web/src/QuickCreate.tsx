import { useEffect, useState } from "react";
import { api, downloadMedia, fetchMediaBlob } from "./api.ts";
import { whoIsWhere } from "./stagingLine.ts";
import type { ImaginePlan, ImagineShot, QuickStatus, StudioUser } from "./types.ts";

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
  const [plan, setPlan] = useState<ImaginePlan | null>(null);
  const [planning, setPlanning] = useState(false);
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState<QuickStatus | null>(null);
  const [polling, setPolling] = useState(false);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);

  const jobs = can(me, "jobs");

  useEffect(() => {
    if (!polling || !status?.run_id) return;
    let stop = false;
    let timer = 0;
    const runId = status.run_id;
    const tick = async () => {
      try {
        const next = await api.quickStatus(runId);
        if (stop) return;
        setStatus(next);
        if (next.produced_mp4 || next.status === "failed" || next.status === "cancelled") {
          setPolling(false);
          if (next.produced_mp4) onNotice("episode.mp4 is in the Studio media store.");
          return;
        }
        const wait = Math.max(1, next.poll_seconds || 5) * 1000;
        timer = window.setTimeout(() => void tick(), wait);
      } catch (err) {
        if (!stop) onError(err);
        setPolling(false);
      }
    };
    timer = window.setTimeout(() => void tick(), Math.max(1, status.poll_seconds || 5) * 1000);
    return () => {
      stop = true;
      window.clearTimeout(timer);
    };
  }, [polling, status?.run_id, status?.poll_seconds, onError, onNotice]);

  useEffect(() => {
    if (!status?.produced_mp4 || !status.media_id) {
      setVideoUrl(null);
      return;
    }
    let url = "";
    let stop = false;
    void fetchMediaBlob(status.media_id)
      .then((blob) => {
        if (stop) return;
        url = URL.createObjectURL(blob);
        setVideoUrl(url);
      })
      .catch((err) => {
        if (!stop) onError(err);
      });
    return () => {
      stop = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [status?.produced_mp4, status?.media_id, onError]);

  async function planStory() {
    const prompt = story.trim();
    if (!prompt) {
      onError(new Error("Add a story prompt before planning."));
      return;
    }
    setPlanning(true);
    setPlan(null);
    setStatus(null);
    setPolling(false);
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

  function updateShot(index: number, patch: Partial<ImagineShot>) {
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
      setPolling(!started.produced_mp4 && started.status !== "failed");
      onNotice("Imagine accepted the run. Comfy was not called.");
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
          One story prompt. The local Imagine app plans the shots, then a confirmed run renders
          episode.mp4 into Studio&apos;s media store. Gates and generate-ok stay as they are.
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
          <p className="paid-note" data-testid="quick-paid-note">
            Run starts a paid xAI render through the local Imagine app. Studio does not call Comfy.
          </p>
          <div className="wizard-actions">
            <button
              type="button"
              className="btn btn-go"
              data-testid="quick-run"
              disabled={running || polling || !jobs}
              onClick={() => void runPlan()}
            >
              {running ? "Starting…" : "Run"}
            </button>
            {!jobs ? <span className="hint">The jobs permission is required to run.</span> : null}
          </div>
        </div>
      ) : null}

      {status ? (
        <div className="wizard-card" data-testid="quick-progress">
          <h3>Progress</h3>
          <p>
            {status.status} · {status.progress}%
            {status.called_comfy ? "" : " · Comfy was not called"}
          </p>
          <progress value={status.progress} max={100} />
          {status.message ? <p>{status.message}</p> : null}
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

      {videoUrl && status?.media_id ? (
        <div className="wizard-card" data-testid="quick-player">
          <h3>episode.mp4</h3>
          <video src={videoUrl} controls />
          <button
            type="button"
            className="btn"
            data-testid="quick-download"
            onClick={() => void downloadMedia(status.media_id as string, "episode.mp4").catch(onError)}
          >
            Download
          </button>
        </div>
      ) : null}
    </section>
  );
}
